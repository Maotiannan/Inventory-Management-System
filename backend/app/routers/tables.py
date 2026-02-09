import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.deps import get_current_user
from app.models import InventoryTable, Item, User
from app.services.logs import log_operation

router = APIRouter(prefix="/tables", tags=["tables"])


def table_response(table: InventoryTable) -> dict:
    return {
        "id": str(table.id),
        "name": table.name,
        "schema": table.schema or {},
        "created_at": table.created_at,
        "updated_at": table.updated_at,
    }


@router.get("")
async def list_tables(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> list[dict]:
    result = await session.execute(select(InventoryTable).order_by(InventoryTable.updated_at.desc()))
    rows = list(result.scalars().all())
    return [table_response(row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_table(
    payload: dict,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    name = str(payload.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="表格名称不能为空")

    schema_data = payload.get("schema")
    if not isinstance(schema_data, dict):
        schema_data = {"fields": []}

    table = InventoryTable(name=name, schema=schema_data)
    session.add(table)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="表格名称已存在") from None

    await log_operation(
        session=session,
        action="create_table",
        target=table.name,
        summary=f"Create table {table.name}",
        detail={"table_id": str(table.id)},
        operator_id=current_user.id,
    )
    await session.commit()
    await session.refresh(table)
    return table_response(table)


@router.patch("/{table_id}")
async def update_table(
    table_id: uuid.UUID,
    payload: dict,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    table = await session.get(InventoryTable, table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="表格不存在")

    if payload.get("name") is not None:
        table.name = str(payload.get("name")).strip()
    if payload.get("schema") is not None:
        if not isinstance(payload.get("schema"), dict):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="schema 必须是对象")
        table.schema = payload.get("schema")

    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="表格名称已存在") from None

    await log_operation(
        session=session,
        action="update_table",
        target=table.name,
        summary=f"Update table {table.name}",
        detail={"table_id": str(table.id), "schema_fields": len(table.schema.get('fields', []))},
        operator_id=current_user.id,
    )
    await session.commit()
    await session.refresh(table)
    return table_response(table)


@router.delete("/{table_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_table(
    table_id: uuid.UUID,
    purge_items: bool = Query(default=False, description="是否同时删除该表下所有物料"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    table = await session.get(InventoryTable, table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="表格不存在")

    count_stmt = select(func.count(Item.id)).where(Item.table_id == table_id)
    count_result = await session.execute(count_stmt)
    items_count = int(count_result.scalar_one() or 0)

    if items_count > 0 and not purge_items:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "TABLE_HAS_ITEMS",
                "message": "该表下仍有数据，是否同时删除数据？",
                "items_count": items_count,
            },
        )

    if items_count > 0 and purge_items:
        delete_result = await session.execute(delete(Item).where(Item.table_id == table_id))
        deleted_items = int(delete_result.rowcount or 0)
    else:
        deleted_items = 0

    table_name = table.name
    await session.delete(table)
    await log_operation(
        session=session,
        action="delete_table",
        target=table_name,
        summary=f"Delete table {table_name}",
        detail={"table_id": str(table_id), "purge_items": purge_items, "deleted_items": deleted_items},
        operator_id=current_user.id,
    )
    await session.commit()
