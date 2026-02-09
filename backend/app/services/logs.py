import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.request_context import get_auth_context
from app.models import OperationLog


async def log_operation(
    session: AsyncSession,
    action: str,
    target: str,
    summary: str,
    detail: dict[str, Any] | None = None,
    operator_id: uuid.UUID | None = None,
) -> None:
    merged_detail = dict(detail or {})
    auth_context = get_auth_context() or {}
    if auth_context:
        merged_detail.setdefault("operator_id", auth_context.get("operator_id"))
        merged_detail.setdefault("operator_username", auth_context.get("operator_username"))
        merged_detail.setdefault("auth_source", auth_context.get("auth_source"))
        merged_detail.setdefault("auth_label", auth_context.get("auth_label"))

    log_row = OperationLog(
        operator_id=operator_id,
        action=action,
        target=target,
        summary=summary,
        detail=merged_detail,
    )
    session.add(log_row)
    await session.flush()
