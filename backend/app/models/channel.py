from sqlalchemy import String, Text, JSON, Boolean, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy import DateTime
from app.database import Base
import uuid


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    niche: Mapped[str] = mapped_column(String(100), nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    voice_id: Mapped[str] = mapped_column(String(100), nullable=True)
    primary_color: Mapped[str] = mapped_column(String(20), default="#FF0000")
    secondary_color: Mapped[str] = mapped_column(String(20), default="#FFFFFF")
    logo_url: Mapped[str] = mapped_column(String(500), nullable=True)
    script_tone: Mapped[str] = mapped_column(String(50), default="educational")
    safety_level: Mapped[str] = mapped_column(String(20), default="normal")
    intro_url: Mapped[str] = mapped_column(String(500), nullable=True)
    outro_url: Mapped[str] = mapped_column(String(500), nullable=True)
    bg_music_url: Mapped[str] = mapped_column(String(500), nullable=True)
    is_islamic: Mapped[bool] = mapped_column(Boolean, default=False)
    extra_config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), onupdate=func.now())

    hooks: Mapped[list["ChannelHook"]] = relationship("ChannelHook", back_populates="channel", cascade="all, delete")
    ctas: Mapped[list["ChannelCTA"]] = relationship("ChannelCTA", back_populates="channel", cascade="all, delete")
    projects: Mapped[list["Project"]] = relationship("Project", back_populates="channel")


class ChannelHook(Base):
    __tablename__ = "channel_hooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[str] = mapped_column(String(36), ForeignKey("channels.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="general")

    channel: Mapped["Channel"] = relationship("Channel", back_populates="hooks")


class ChannelCTA(Base):
    __tablename__ = "channel_ctas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[str] = mapped_column(String(36), ForeignKey("channels.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    cta_type: Mapped[str] = mapped_column(String(50), default="subscribe")

    channel: Mapped["Channel"] = relationship("Channel", back_populates="ctas")
