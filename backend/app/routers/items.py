import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.deps import get_current_user
from app.models import InventoryTable, Item, User
from app.schemas import ItemCreate, ItemRead, ItemUpdate
from app.services.logs import log_operation

router = APIRouter(tags=["items"])


async def _ensure_table(session: AsyncSession, table_id: uuid.UUID) -> InventoryTable:
    table = await session.get(InventoryTable, table_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="表格不存在")
    return table


def _resolve_media_path(relative_path: str | None) -> Path | None:
    normalized = str(relative_path or "").strip().replace("\\", "/").lstrip("/")
    if not normalized:
        return None

    images_root = Path(settings.images_dir).resolve()
    candidate = (images_root / normalized).resolve()
    try:
        candidate.relative_to(images_root)
    except ValueError:
        return None
    return candidate


async def _cleanup_media_if_unused(
    session: AsyncSession,
    relative_path: str | None,
    exclude_item_id: uuid.UUID | None = None,
) -> None:
    normalized = str(relative_path or "").strip()
    if not normalized:
        return

    stmt = select(Item.id).where(or_(Item.image_original == normalized, Item.image_thumb == normalized)).limit(1)
    if exclude_item_id:
        stmt = stmt.where(Item.id != exclude_item_id)
    in_use = await session.execute(stmt)
    if in_use.scalar_one_or_none():
        return

    absolute_path = _resolve_media_path(normalized)
    if not absolute_path:
        return
    try:
        absolute_path.unlink(missing_ok=True)
    except OSError:
        # Keep request successful even if stale file cleanup fails.
        return


@router.get("/items", response_model=list[ItemRead])
async def list_items(
    table_id: uuid.UUID | None = Query(default=None, description="按表格过滤"),
    q: str | None = Query(default=None, description="按名称或编码模糊搜索"),
    code: str | None = Query(default=None, description="按编码精确搜索"),
    min_quantity: int | None = Query(default=None, ge=0),
    max_quantity: int | None = Query(default=None, ge=0),
    property_key: str | None = Query(default=None, description="JSONB 属性键"),
    property_value: str | None = Query(default=None, description="JSONB 属性值"),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> list[ItemRead]:
    stmt = select(Item)

    if table_id:
        stmt = stmt.where(Item.table_id == table_id)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(Item.name.ilike(pattern), Item.code.ilike(pattern)))
    if code:
        stmt = stmt.where(Item.code == code)
    if min_quantity is not None:
        stmt = stmt.where(Item.quantity >= min_quantity)
    if max_quantity is not None:
        stmt = stmt.where(Item.quantity <= max_quantity)
    if property_key:
        stmt = stmt.where(Item.properties.has_key(property_key))  # type: ignore[attr-defined]
    if property_key and property_value is not None:
        stmt = stmt.where(Item.properties[property_key].astext.cast(String) == property_value)

    stmt = stmt.order_by(Item.updated_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/items/{item_id}", response_model=ItemRead)
async def get_item(
    item_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> ItemRead:
    item = await session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="物料不存在")
    return ItemRead.model_validate(item)


@router.post("/items", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: ItemCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ItemRead:
    table = await _ensure_table(session, payload.table_id)
    item = Item(
        table_id=payload.table_id,
        name=payload.name,
        code=payload.code,
        quantity=payload.quantity,
        image_original=payload.image_original,
        image_thumb=payload.image_thumb,
        notes=payload.notes,
        properties=payload.properties,
    )
    session.add(item)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该表格中物料编码已存在",
        ) from None

    await log_operation(
        session=session,
        action="create_item",
        target=item.code,
        summary=f"Create item {item.code} in table {table.name}",
        detail={"item_id": str(item.id), "table_id": str(item.table_id), "quantity": item.quantity},
        operator_id=current_user.id,
    )
    await session.commit()
    await session.refresh(item)
    return ItemRead.model_validate(item)


@router.patch("/items/{item_id}", response_model=ItemRead)
async def update_item(
    item_id: uuid.UUID,
    payload: ItemUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ItemRead:
    item = await session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="物料不存在")

    old_image_original = item.image_original
    old_image_thumb = item.image_thumb

    for field_name in (
        "name",
        "code",
        "quantity",
        "image_original",
        "image_thumb",
        "notes",
    ):
        value = getattr(payload, field_name)
        if value is not None:
            setattr(item, field_name, value)

    working_properties = dict(item.properties or {})
    if payload.properties is not None:
        working_properties = dict(payload.properties)
    if payload.properties_patch:
        working_properties.update(payload.properties_patch)
    if payload.properties_remove:
        for key in payload.properties_remove:
            working_properties.pop(key, None)
    item.properties = working_properties

    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="更新失败，编码可能重复",
        ) from None

    await log_operation(
        session=session,
        action="update_item",
        target=item.code,
        summary=f"Update item {item.code}",
        detail={"item_id": str(item.id), "table_id": str(item.table_id)},
        operator_id=current_user.id,
    )
    await session.commit()
    await session.refresh(item)

    stale_paths: set[str] = set()
    if old_image_original and old_image_original != item.image_original:
        stale_paths.add(old_image_original)
    if old_image_thumb and old_image_thumb != item.image_thumb:
        stale_paths.add(old_image_thumb)
    for stale_path in stale_paths:
        await _cleanup_media_if_unused(session, stale_path, exclude_item_id=item.id)

    return ItemRead.model_validate(item)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    item = await session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="物料不存在")

    code = item.code
    table_id = item.table_id
    old_image_original = item.image_original
    old_image_thumb = item.image_thumb
    await session.delete(item)
    await log_operation(
        session=session,
        action="delete_item",
        target=code,
        summary=f"Delete item {code}",
        detail={"item_id": str(item_id), "table_id": str(table_id)},
        operator_id=current_user.id,
    )
    await session.commit()

    stale_paths = {path for path in (old_image_original, old_image_thumb) if path}
    for stale_path in stale_paths:
        await _cleanup_media_if_unused(session, stale_path)
