import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal, Base, engine
from app.core.security import get_password_hash, verify_password
from app.models import User
from app.routers.auth import router as auth_router
from app.routers.config_schema import router as config_router
from app.routers.integration import router as integration_router
from app.routers.items import router as items_router
from app.routers.stock import router as stock_router
from app.routers.system_ops import router as system_ops_router
from app.routers.tables import router as tables_router
from app.routers.upload import router as upload_router
from app.routers.users import router as users_router
from app.services.migration import bind_legacy_items_to_default_table, ensure_default_table, migrate_schema


async def init_database() -> None:
    for attempt in range(1, 11):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                await migrate_schema(conn)
            return
        except Exception:
            if attempt == 10:
                raise
            await asyncio.sleep(2)


async def init_data() -> None:
    async with AsyncSessionLocal() as session:
        default_table = await ensure_default_table(session)
        await session.commit()

    async with engine.begin() as conn:
        await bind_legacy_items_to_default_table(conn, default_table.id)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == settings.admin_username))
        user = result.scalar_one_or_none()
        if not user:
            session.add(
                User(
                    username=settings.admin_username,
                    password_hash=get_password_hash(settings.admin_password),
                    role="admin",
                )
            )
        else:
            if user.role != "admin":
                user.role = "admin"
            if not verify_password(settings.admin_password, user.password_hash):
                user.password_hash = get_password_hash(settings.admin_password)
        await session.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Path(settings.images_dir, "originals").mkdir(parents=True, exist_ok=True)
    Path(settings.images_dir, "thumbs").mkdir(parents=True, exist_ok=True)
    await init_database()
    await init_data()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.mount("/media", StaticFiles(directory=settings.images_dir, check_dir=False), name="media")

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(tables_router)
app.include_router(items_router)
app.include_router(stock_router)
app.include_router(upload_router)
app.include_router(config_router)
app.include_router(integration_router)
app.include_router(system_ops_router)


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    # Keep the health endpoint lightweight for container health checks.
    return {"status": "ok"}


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {"message": "进销存后端服务已启动"}
