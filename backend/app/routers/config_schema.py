import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.deps import get_current_user
from app.models import InventoryTable, User
from app.services.logs import log_operation

router = APIRouter(prefix="/config", tags=["config"])


def schema_response(table: InventoryTable) -> dict[str, Any]:
    return {
        "table_id": str(table.id),
        "table_name": table.name,
        "schema": table.schema or {},
        "updated_at": table.updated_at,
    }


@router.get("/schema")
async def get_schema(
    table_id: uuid.UUID | None = Query(default=None, description="表格ID"),
    table_name: str | None = Query(default=None, description="表格名称"),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    table = None
    if table_id:
        table = await session.get(InventoryTable, table_id)
    elif table_name:
        result = await session.execute(select(InventoryTable).where(InventoryTable.name == table_name))
        table = result.scalar_one_or_none()
    else:
        result = await session.execute(select(InventoryTable).order_by(InventoryTable.updated_at.desc()))
        table = result.scalars().first()

    if not table:
        return {
            "table_id": None,
            "table_name": "",
            "schema": {},
            "updated_at": datetime.now(UTC),
        }
    return schema_response(table)


@router.put("/schema")
async def set_schema(
    payload: dict[str, Any] = Body(default_factory=dict),
    table_id: uuid.UUID | None = Query(default=None, description="表格ID"),
    table_name: str | None = Query(default=None, description="表格名称"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    schema_data = payload.get("schema")
    if not isinstance(schema_data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请求体必须包含对象类型 schema 字段",
        )

    table = None
    if table_id:
        table = await session.get(InventoryTable, table_id)
    elif table_name:
        result = await session.execute(select(InventoryTable).where(InventoryTable.name == table_name))
        table = result.scalar_one_or_none()

    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="表格不存在")

    table.schema = schema_data
    await log_operation(
        session=session,
        action="update_schema",
        target=table.name,
        summary=f"Update schema for table {table.name}",
        detail={"table_id": str(table.id), "fields_count": len(schema_data.get("fields", []))},
        operator_id=current_user.id,
    )
    await session.commit()
    await session.refresh(table)
    return schema_response(table)


@router.post("/schema")
async def set_schema_by_post(
    payload: dict[str, Any] = Body(default_factory=dict),
    table_id: uuid.UUID | None = Query(default=None, description="表格ID"),
    table_name: str | None = Query(default=None, description="表格名称"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return await set_schema(payload, table_id, table_name, session, current_user)
