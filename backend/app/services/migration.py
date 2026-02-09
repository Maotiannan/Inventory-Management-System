import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.models import InventoryTable


async def _run_ddl(conn: AsyncConnection, sql: str) -> None:
    await conn.execute(text(sql))


async def migrate_schema(conn: AsyncConnection) -> None:
    await _run_ddl(conn, "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'operator'")
    await _run_ddl(conn, "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()")
    await _run_ddl(conn, "UPDATE users SET role = 'operator' WHERE role IS NULL OR role = ''")

    await _run_ddl(conn, "ALTER TABLE items ADD COLUMN IF NOT EXISTS table_id UUID")
    await _run_ddl(conn, "ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS api_key VARCHAR(255)")
    await _run_ddl(conn, "ALTER TABLE operation_logs ADD COLUMN IF NOT EXISTS detail JSONB DEFAULT '{}'::jsonb")

    await _run_ddl(
        conn,
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'items_code_key') THEN
            ALTER TABLE items DROP CONSTRAINT items_code_key;
          END IF;
        END
        $$;
        """,
    )
    await _run_ddl(conn, "CREATE UNIQUE INDEX IF NOT EXISTS uq_items_table_code ON items (table_id, code)")
    await _run_ddl(
        conn,
        """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_items_table_id') THEN
            ALTER TABLE items
            ADD CONSTRAINT fk_items_table_id
            FOREIGN KEY (table_id) REFERENCES inventory_tables (id) ON DELETE RESTRICT;
          END IF;
        END
        $$;
        """,
    )


async def ensure_default_table(session: AsyncSession) -> InventoryTable:
    result = await session.execute(select(InventoryTable).where(InventoryTable.name == "默认表"))
    table = result.scalar_one_or_none()
    if table:
        return table

    table = InventoryTable(
        id=uuid.uuid4(),
        name="默认表",
        schema={
            "fields": [
                {"key": "规格", "label": "规格", "type": "text", "options": []},
                {"key": "单位", "label": "单位", "type": "text", "options": []},
            ]
        },
    )
    session.add(table)
    await session.flush()
    return table


async def bind_legacy_items_to_default_table(conn: AsyncConnection, default_table_id: uuid.UUID) -> None:
    await _run_ddl(conn, f"UPDATE items SET table_id = '{default_table_id}'::uuid WHERE table_id IS NULL")
    await _run_ddl(conn, "ALTER TABLE items ALTER COLUMN table_id SET NOT NULL")
