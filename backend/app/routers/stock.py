from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.deps import get_current_user
from app.models import InventoryTable, Item, User
from app.schemas import ItemRead, StockInRequest, StockOutRequest
from app.services.logs import log_operation

router = APIRouter(prefix="/stock", tags=["stock"])
DEFAULT_SCANNED_NAME = "NUM"


@router.post("/in", response_model=ItemRead)
async def stock_in(
    payload: StockInRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ItemRead:
    table = await session.get(InventoryTable, payload.table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="表格不存在")

    code = payload.code.strip()
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="编码不能为空")

    stmt = select(Item).where(Item.table_id == payload.table_id, Item.code == code).with_for_update()
    result = await session.execute(stmt)
    item = result.scalar_one_or_none()

    if not item:
        default_name = payload.name.strip() if payload.name and payload.name.strip() else DEFAULT_SCANNED_NAME
        item = Item(
            table_id=payload.table_id,
            name=default_name,
            code=code,
            quantity=payload.quantity,
            notes=payload.notes,
            properties=payload.properties or {},
        )
        session.add(item)
    else:
        item.quantity = int(item.quantity) + int(payload.quantity)
        if payload.name and payload.name.strip():
            item.name = payload.name.strip()
        if payload.notes:
            item.notes = payload.notes
        if payload.properties:
            item.properties = {**(item.properties or {}), **payload.properties}

    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="入库失败，编码可能重复") from None

    await log_operation(
        session=session,
        action="stock_in",
        target=item.code,
        summary=f"Stock in {payload.quantity} for {item.code} in table {table.name}",
        detail={"item_id": str(item.id), "table_id": str(item.table_id), "quantity": payload.quantity},
        operator_id=current_user.id,
    )
    await session.commit()
    await session.refresh(item)
    return ItemRead.model_validate(item)


@router.post("/out", response_model=ItemRead)
async def stock_out(
    payload: StockOutRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ItemRead:
    table = await session.get(InventoryTable, payload.table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="表格不存在")

    code = payload.code.strip()
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="编码不能为空")

    stmt = select(Item).where(Item.table_id == payload.table_id, Item.code == code).with_for_update()
    result = await session.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="物料不存在")

    if item.quantity < payload.quantity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"库存不足，当前库存 {item.quantity}")

    item.quantity = int(item.quantity) - int(payload.quantity)
    if payload.notes:
        item.notes = payload.notes

    await log_operation(
        session=session,
        action="stock_out",
        target=item.code,
        summary=f"Stock out {payload.quantity} for {item.code} in table {table.name}",
        detail={"item_id": str(item.id), "table_id": str(item.table_id), "quantity": payload.quantity},
        operator_id=current_user.id,
    )
    await session.commit()
    await session.refresh(item)
    return ItemRead.model_validate(item)
