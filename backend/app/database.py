from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase
from app.config import settings
import logging


engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def create_tables():
    async with engine.begin() as conn:
        from app.models import channel, project  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)


async def migrate_scenes_schema():
    logger.info("checking scenes schema columns")
    scene_column_statements = [
        ("visual_source_url", "ALTER TABLE scenes ADD COLUMN IF NOT EXISTS visual_source_url TEXT NULL"),
        ("visual_metadata", "ALTER TABLE scenes ADD COLUMN IF NOT EXISTS visual_metadata JSONB NOT NULL DEFAULT '{}'::jsonb"),
        ("visual_locked", "ALTER TABLE scenes ADD COLUMN IF NOT EXISTS visual_locked BOOLEAN NOT NULL DEFAULT FALSE"),
        ("visual_selected_for_project_id", "ALTER TABLE scenes ADD COLUMN IF NOT EXISTS visual_selected_for_project_id UUID NULL"),
        ("visual_selected_for_scene_id", "ALTER TABLE scenes ADD COLUMN IF NOT EXISTS visual_selected_for_scene_id UUID NULL"),
        ("visual_selected_at", "ALTER TABLE scenes ADD COLUMN IF NOT EXISTS visual_selected_at TIMESTAMP NULL"),
        ("thumbnail_url", "ALTER TABLE scenes ADD COLUMN IF NOT EXISTS thumbnail_url TEXT NULL"),
    ]

    async with engine.begin() as conn:
        for column_name, stmt in scene_column_statements:
            before_exists = await conn.execute(
                text(
                    """
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'scenes' AND column_name = :column_name
                    """
                ),
                {"column_name": column_name},
            )
            was_present = before_exists.scalar() == 1
            await conn.execute(text(stmt))
            if not was_present:
                logger.info("added missing scene column %s", column_name)

        type_rows = await conn.execute(
            text(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'scenes'
                  AND column_name IN ('visual_selected_for_project_id', 'visual_selected_for_scene_id')
                """
            )
        )
        column_types = {row.column_name: row.data_type for row in type_rows}

        if column_types.get("visual_selected_for_project_id") != "uuid":
            logger.info("coercing scenes.visual_selected_for_project_id to UUID")
            await conn.execute(
                text(
                    """
                    ALTER TABLE scenes
                    ALTER COLUMN visual_selected_for_project_id TYPE UUID
                    USING NULLIF(visual_selected_for_project_id::text, '')::uuid
                    """
                )
            )

        if column_types.get("visual_selected_for_scene_id") != "uuid":
            logger.info("coercing scenes.visual_selected_for_scene_id to UUID")
            await conn.execute(
                text(
                    """
                    ALTER TABLE scenes
                    ALTER COLUMN visual_selected_for_scene_id TYPE UUID
                    USING NULLIF(visual_selected_for_scene_id::text, '')::uuid
                    """
                )
            )

        full_type_rows = await conn.execute(
            text(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'scenes'
                  AND column_name IN (
                    'visual_query',
                    'visual_source_url',
                    'visual_metadata',
                    'visual_locked',
                    'visual_selected_at',
                    'thumbnail_url'
                  )
                """
            )
        )
        full_column_types = {row.column_name: row.data_type for row in full_type_rows}

        visual_query_type = full_column_types.get("visual_query")
        logger.info("checking visual_query column type: %s", visual_query_type)
        if visual_query_type != "text":
            await conn.execute(text("ALTER TABLE scenes ALTER COLUMN visual_query TYPE TEXT"))
            logger.info("visual_query column migrated to TEXT")

        if full_column_types.get("visual_source_url") not in {"text", "character varying"}:
            logger.info("coercing scenes.visual_source_url to TEXT")
            await conn.execute(text("ALTER TABLE scenes ALTER COLUMN visual_source_url TYPE TEXT USING visual_source_url::text"))

        if full_column_types.get("thumbnail_url") not in {"text", "character varying"}:
            logger.info("coercing scenes.thumbnail_url to TEXT")
            await conn.execute(text("ALTER TABLE scenes ALTER COLUMN thumbnail_url TYPE TEXT USING thumbnail_url::text"))

        if full_column_types.get("visual_metadata") not in {"json", "jsonb"}:
            logger.info("coercing scenes.visual_metadata to JSONB")
            await conn.execute(text("ALTER TABLE scenes ALTER COLUMN visual_metadata TYPE JSONB USING COALESCE(visual_metadata::jsonb, '{}'::jsonb)"))
        await conn.execute(text("ALTER TABLE scenes ALTER COLUMN visual_metadata SET DEFAULT '{}'::jsonb"))

        if full_column_types.get("visual_locked") != "boolean":
            logger.info("coercing scenes.visual_locked to BOOLEAN")
            await conn.execute(text("ALTER TABLE scenes ALTER COLUMN visual_locked TYPE BOOLEAN USING visual_locked::boolean"))
        await conn.execute(text("ALTER TABLE scenes ALTER COLUMN visual_locked SET DEFAULT FALSE"))

        if full_column_types.get("visual_selected_at") != "timestamp with time zone":
            logger.info("coercing scenes.visual_selected_at to TIMESTAMPTZ")
            await conn.execute(text("ALTER TABLE scenes ALTER COLUMN visual_selected_at TYPE TIMESTAMPTZ USING visual_selected_at::timestamptz"))

    logger.info("scene schema migration complete")
