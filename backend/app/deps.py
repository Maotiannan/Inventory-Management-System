from datetime import UTC, datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.request_context import clear_auth_context, set_auth_context
from app.core.security import decode_access_token, hash_api_key
from app.models import ApiKey, User

bearer_scheme = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _get_user_by_username(session: AsyncSession, username: str) -> User | None:
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def _get_user_by_api_key(session: AsyncSession, raw_api_key: str) -> tuple[User, ApiKey] | None:
    api_key_hash = hash_api_key(raw_api_key)
    stmt = select(ApiKey).where(
        or_(ApiKey.api_key == raw_api_key, ApiKey.key_hash == api_key_hash),
        ApiKey.active.is_(True),
    )
    result = await session.execute(stmt)
    api_key = result.scalar_one_or_none()
    if not api_key:
        return None

    # BUG-02: 只 flush 不 commit，让事务随 endpoint 一起提交
    api_key.last_used_at = datetime.now(UTC)
    await session.flush()
    user = await session.get(User, api_key.owner_id)
    if not user:
        return None
    return user, api_key


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    api_key: str | None = Depends(api_key_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    clear_auth_context()

    if credentials and credentials.scheme.lower() == "bearer":
        payload = decode_access_token(credentials.credentials)
        if payload and payload.get("sub"):
            user = await _get_user_by_username(session, payload["sub"])
            if user:
                set_auth_context(
                    {
                        "operator_id": str(user.id),
                        "operator_username": user.username,
                        "auth_source": "jwt",
                        "auth_label": user.username,
                    }
                )
                return user

    if api_key:
        matched = await _get_user_by_api_key(session, api_key)
        if matched:
            user, key_row = matched
            set_auth_context(
                {
                    "operator_id": str(user.id),
                    "operator_username": user.username,
                    "auth_source": "api_key",
                    "auth_label": f"{key_row.name} ({key_row.key_prefix})",
                }
            )
            return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未认证，请使用 Bearer Token 或 X-API-Key",
    )


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可执行该操作",
        )
    return current_user
