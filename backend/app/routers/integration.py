import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import generate_api_key, hash_api_key
from app.deps import get_current_user
from app.models import ApiKey, OperationLog, User
from app.schemas import ApiKeyCreateRequest, ApiKeyCreatedResponse, ApiKeyReadResponse, LogReadResponse
from app.services.logs import log_operation

router = APIRouter(prefix="/integration", tags=["integration"])


def _api_host(request: Request) -> str:
    return f"{request.url.scheme}://{request.headers.get('host', 'localhost:8000')}"


@router.get("/api-info")
async def get_api_info(
    request: Request,
    _: User = Depends(get_current_user),
) -> dict:
    host = _api_host(request)
    return {
        "api_base": host,
        "openapi_url": f"{host}/openapi.json",
        "docs_url": f"{host}/docs",
        "auth_modes": ["Bearer Token", "X-API-Key"],
        "features": [
            "物料增删改查",
            "入库/出库",
            "多表格管理",
            "字段配置管理",
            "账号管理（管理员）",
            "API Key 管理",
            "操作日志",
        ],
    }


@router.get("/api-reference")
async def get_api_reference(
    _: User = Depends(get_current_user),
) -> dict:
    return {
        "auth": ["POST /auth/login", "GET /auth/validate"],
        "users": ["GET /users (admin)", "POST /users (admin)", "DELETE /users/{id} (admin)"],
        "tables": [
            "GET /tables",
            "POST /tables",
            "PATCH /tables/{id}",
            "DELETE /tables/{id}",
            "DELETE /tables/{id}?purge_items=true",
        ],
        "schema": ["GET /config/schema", "PUT /config/schema", "POST /config/schema"],
        "items": [
            "GET /items",
            "GET /items/{id}",
            "POST /items",
            "PATCH /items/{id}",
            "DELETE /items/{id}",
        ],
        "stock": ["POST /stock/in", "POST /stock/out"],
        "upload": ["POST /upload"],
        "integration": [
            "GET /integration/api-info",
            "GET /integration/api-reference",
            "GET /integration/api-keys",
            "POST /integration/api-keys",
            "DELETE /integration/api-keys/{id}",
            "GET /integration/logs",
        ],
        "system": [
            "GET /system/tailscale/config (admin)",
            "PUT /system/tailscale/config (admin)",
            "GET /system/repo/config (admin)",
            "PUT /system/repo/config (admin)",
            "GET /system/update/status (admin)",
            "POST /system/update/apply (admin)",
            "GET /system/version/state (admin)",
            "GET /system/version/history (admin)",
            "GET /system/version/tags (admin)",
            "POST /system/version/rollback (admin)",
            "POST /system/version/rollback/latest (admin)",
        ],
    }


@router.post("/api-keys", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ApiKeyCreatedResponse:
    raw_key = generate_api_key()
    record = ApiKey(
        name=payload.name.strip() or "默认密钥",
        key_prefix=raw_key[:16],
        api_key=raw_key,
        key_hash=hash_api_key(raw_key),
        owner_id=current_user.id,
        active=True,
    )
    session.add(record)
    await session.flush()
    await log_operation(
        session=session,
        action="create_api_key",
        target=record.name,
        summary=f"Create API key {record.name}",
        detail={"api_key_id": str(record.id), "key_prefix": record.key_prefix},
        operator_id=current_user.id,
    )
    await session.commit()
    await session.refresh(record)

    return ApiKeyCreatedResponse(
        id=record.id,
        name=record.name,
        key_prefix=record.key_prefix,
        api_key=raw_key,
        created_at=record.created_at,
    )


@router.get("/api-keys", response_model=list[ApiKeyReadResponse])
async def list_api_keys(
    include_disabled: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[ApiKeyReadResponse]:
    stmt = select(ApiKey).where(ApiKey.owner_id == current_user.id)
    if not include_disabled:
        stmt = stmt.where(ApiKey.active.is_(True))
    stmt = stmt.order_by(ApiKey.created_at.desc())

    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    return [
        ApiKeyReadResponse(
            id=row.id,
            name=row.name,
            key_prefix=row.key_prefix,
            api_key=f"{row.key_prefix}••••••••",  # BUG-05: 不再返回完整 key，只展示前缀
            active=row.active,
            created_at=row.created_at,
            last_used_at=row.last_used_at,
        )
        for row in rows
    ]


@router.delete("/api-keys/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disable_api_key(
    api_key_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    stmt = select(ApiKey).where(ApiKey.id == api_key_id, ApiKey.owner_id == current_user.id)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key 不存在")

    row.active = False
    await log_operation(
        session=session,
        action="disable_api_key",
        target=row.name,
        summary=f"Disable API key {row.name}",
        detail={"api_key_id": str(row.id)},
        operator_id=current_user.id,
    )
    await session.commit()


@router.get("/logs", response_model=list[LogReadResponse])
async def list_logs(
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> list[LogReadResponse]:
    stmt = select(OperationLog).order_by(OperationLog.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    operator_ids = {row.operator_id for row in rows if row.operator_id}
    user_map: dict[uuid.UUID, str] = {}
    if operator_ids:
        user_result = await session.execute(select(User.id, User.username).where(User.id.in_(operator_ids)))
        user_map = {uid: username for uid, username in user_result.all()}

    payload: list[LogReadResponse] = []
    for row in rows:
        detail = row.detail or {}
        operator_username = detail.get("operator_username")
        if not operator_username and row.operator_id:
            operator_username = user_map.get(row.operator_id)
        auth_source = detail.get("auth_source")
        auth_label = detail.get("auth_label")
        payload.append(
            LogReadResponse(
                id=row.id,
                operator_id=row.operator_id,
                operator_username=operator_username,
                auth_source=auth_source,
                auth_label=auth_label,
                action=row.action,
                target=row.target,
                summary=row.summary,
                detail=detail,
                created_at=row.created_at,
            )
        )
    return payload
