import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_password_hash
from app.deps import require_admin
from app.models import User
from app.schemas import UserCreateRequest, UserReadResponse
from app.services.logs import log_operation

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserReadResponse])
async def list_users(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
) -> list[UserReadResponse]:
    result = await session.execute(select(User).order_by(User.created_at.desc()))
    rows = list(result.scalars().all())
    return [UserReadResponse.model_validate(row) for row in rows]


@router.post("", response_model=UserReadResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateRequest,
    session: AsyncSession = Depends(get_session),
    admin_user: User = Depends(require_admin),
) -> UserReadResponse:
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名不能为空")

    user = User(
        username=username,
        password_hash=get_password_hash(payload.password),
        role="operator",
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在") from None

    await log_operation(
        session=session,
        action="create_user",
        target=user.username,
        summary=f"Create account {user.username}",
        detail={"user_id": str(user.id), "role": user.role},
        operator_id=admin_user.id,
    )
    await session.commit()
    await session.refresh(user)
    return UserReadResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    admin_user: User = Depends(require_admin),
) -> None:
    if admin_user.id == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除当前登录账号")

    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    if user.role == "admin":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="管理员账号不允许删除")

    username = user.username
    await session.delete(user)
    await log_operation(
        session=session,
        action="delete_user",
        target=username,
        summary=f"Delete account {username}",
        detail={"user_id": str(user_id)},
        operator_id=admin_user.id,
    )
    await session.commit()
