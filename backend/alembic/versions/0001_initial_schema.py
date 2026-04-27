"""Initial schema: channels, projects, scenes, assets

Revision ID: 0001
Revises:
Create Date: 2026-04-27
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "channels",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("niche", sa.String(100), nullable=False),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("voice_id", sa.String(100), nullable=True),
        sa.Column("primary_color", sa.String(20), server_default="#FF0000"),
        sa.Column("secondary_color", sa.String(20), server_default="#FFFFFF"),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("script_tone", sa.String(50), server_default="educational"),
        sa.Column("safety_level", sa.String(20), server_default="normal"),
        sa.Column("intro_url", sa.String(500), nullable=True),
        sa.Column("outro_url", sa.String(500), nullable=True),
        sa.Column("bg_music_url", sa.String(500), nullable=True),
        sa.Column("is_islamic", sa.Boolean(), server_default="false"),
        sa.Column("extra_config", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    op.create_table(
        "channel_hooks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("channel_id", sa.String(36), sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(50), server_default="general"),
    )

    op.create_table(
        "channel_ctas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("channel_id", sa.String(36), sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("cta_type", sa.String(50), server_default="subscribe"),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("channel_id", sa.String(36), sa.ForeignKey("channels.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("idea", sa.Text(), nullable=True),
        sa.Column("video_type", sa.String(50), server_default="explainer"),
        sa.Column("status", sa.String(50), server_default="idea"),
        sa.Column("script", sa.JSON(), server_default="{}"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("pinned_comment", sa.Text(), nullable=True),
        sa.Column("thumbnail_prompt", sa.Text(), nullable=True),
        sa.Column("metadata_tags", sa.JSON(), server_default="[]"),
        sa.Column("sharia_reference", sa.Text(), nullable=True),
        sa.Column("trust_level", sa.String(50), nullable=True),
        sa.Column("review1_approved", sa.Boolean(), server_default="false"),
        sa.Column("review2_approved", sa.Boolean(), server_default="false"),
        sa.Column("review3_approved", sa.Boolean(), server_default="false"),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("aspect_ratio", sa.String(10), server_default="16:9"),
        sa.Column("template_config", sa.JSON(), server_default="{}"),
        sa.Column("voice_id", sa.String(100), nullable=True),
        sa.Column("audio_speed", sa.Float(), server_default="1.0"),
        sa.Column("audio_url", sa.String(500), nullable=True),
        sa.Column("output_url", sa.String(500), nullable=True),
        sa.Column("output_9_16_url", sa.String(500), nullable=True),
        sa.Column("output_1_1_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index("ix_projects_channel_id", "projects", ["channel_id"])
    op.create_index("ix_projects_status", "projects", ["status"])
    op.create_index("ix_projects_created_at", "projects", ["created_at"])

    op.create_table(
        "scenes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order", sa.Integer(), server_default="0"),
        sa.Column("script_text", sa.Text(), nullable=True),
        sa.Column("script_ar", sa.Text(), nullable=True),
        sa.Column("duration", sa.Float(), server_default="5.0"),
        sa.Column("visual_query", sa.String(500), nullable=True),
        sa.Column("visual_type", sa.String(50), server_default="stock"),
        sa.Column("visual_status", sa.String(50), server_default="pending"),
        sa.Column("visual_url", sa.String(500), nullable=True),
        sa.Column("visual_source", sa.String(50), nullable=True),
        sa.Column("on_screen_source", sa.String(500), nullable=True),
        sa.Column("audio_url", sa.String(500), nullable=True),
        sa.Column("transition", sa.String(50), server_default="fade"),
        sa.Column("effects", sa.JSON(), server_default="[]"),
    )
    op.create_index("ix_scenes_project_id", "scenes", ["project_id"])

    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_type", sa.String(50), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("meta", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("assets")
    op.drop_table("scenes")
    op.drop_index("ix_projects_created_at", "projects")
    op.drop_index("ix_projects_status", "projects")
    op.drop_index("ix_projects_channel_id", "projects")
    op.drop_table("projects")
    op.drop_table("channel_ctas")
    op.drop_table("channel_hooks")
    op.drop_table("channels")
