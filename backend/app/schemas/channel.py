from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ChannelHookBase(BaseModel):
    text: str
    category: str = "general"


class ChannelCTABase(BaseModel):
    text: str
    cta_type: str = "subscribe"


class ChannelCreate(BaseModel):
    name: str
    niche: str
    language: str = "en"
    voice_id: Optional[str] = None
    primary_color: str = "#FF0000"
    secondary_color: str = "#FFFFFF"
    logo_url: Optional[str] = None
    script_tone: str = "educational"
    safety_level: str = "normal"
    intro_url: Optional[str] = None
    outro_url: Optional[str] = None
    bg_music_url: Optional[str] = None
    is_islamic: bool = False
    extra_config: dict = {}


class ChannelUpdate(ChannelCreate):
    pass


class ChannelOut(ChannelCreate):
    id: str
    created_at: Optional[datetime] = None
    hooks: List[ChannelHookBase] = []
    ctas: List[ChannelCTABase] = []

    model_config = {"from_attributes": True}


class ChannelList(BaseModel):
    id: str
    name: str
    niche: str
    language: str
    is_islamic: bool

    model_config = {"from_attributes": True}
