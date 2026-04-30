from sqlalchemy import String, Text, JSON, Integer, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy import DateTime
from app.database import Base
import uuid


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    channel_id: Mapped[str] = mapped_column(String(36), ForeignKey("channels.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    idea: Mapped[str] = mapped_column(Text, nullable=True)
    video_type: Mapped[str] = mapped_column(String(50), default="explainer")
    status: Mapped[str] = mapped_column(String(50), default="idea")
    # Content
    script: Mapped[dict] = mapped_column(JSON, default=dict)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    pinned_comment: Mapped[str] = mapped_column(Text, nullable=True)
    thumbnail_prompt: Mapped[str] = mapped_column(Text, nullable=True)
    metadata_tags: Mapped[list] = mapped_column(JSON, default=list)
    sharia_reference: Mapped[str] = mapped_column(Text, nullable=True)
    trust_level: Mapped[str] = mapped_column(String(50), nullable=True)
    # Review
    review1_approved: Mapped[bool] = mapped_column(default=False)
    review2_approved: Mapped[bool] = mapped_column(default=False)
    review3_approved: Mapped[bool] = mapped_column(default=False)
    review_notes: Mapped[str] = mapped_column(Text, nullable=True)
    # Template
    aspect_ratio: Mapped[str] = mapped_column(String(10), default="16:9")
    template_config: Mapped[dict] = mapped_column(JSON, default=dict)
    # Audio
    voice_id: Mapped[str] = mapped_column(String(100), nullable=True)
    audio_speed: Mapped[float] = mapped_column(Float, default=1.0)
    audio_url: Mapped[str] = mapped_column(String(500), nullable=True)
    # Output
    output_url: Mapped[str] = mapped_column(String(500), nullable=True)
    output_9_16_url: Mapped[str] = mapped_column(String(500), nullable=True)
    output_1_1_url: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), onupdate=func.now())

    channel: Mapped["Channel"] = relationship("Channel", back_populates="projects")
    scenes: Mapped[list["Scene"]] = relationship("Scene", back_populates="project", cascade="all, delete", order_by="Scene.order")
    assets: Mapped[list["Asset"]] = relationship("Asset", back_populates="project", cascade="all, delete")


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"))
    order: Mapped[int] = mapped_column(Integer, default=0)
    script_text: Mapped[str] = mapped_column(Text, nullable=True)
    script_ar: Mapped[str] = mapped_column(Text, nullable=True)
    duration: Mapped[float] = mapped_column(Float, default=5.0)
    visual_query: Mapped[str] = mapped_column(String(500), nullable=True)
    visual_type: Mapped[str] = mapped_column(String(50), default="stock")
    visual_status: Mapped[str] = mapped_column(String(50), default="pending")
    visual_url: Mapped[str] = mapped_column(String(500), nullable=True)
    visual_source: Mapped[str] = mapped_column(String(50), nullable=True)
    on_screen_source: Mapped[str] = mapped_column(String(500), nullable=True)
    audio_url: Mapped[str] = mapped_column(String(500), nullable=True)
    transition: Mapped[str] = mapped_column(String(50), default="fade")
    effects: Mapped[list] = mapped_column(JSON, default=list)

    project: Mapped["Project"] = relationship("Project", back_populates="scenes")


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"))
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship("Project", back_populates="assets")
