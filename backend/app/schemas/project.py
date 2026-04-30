from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class SceneOut(BaseModel):
    id: int
    order: int
    script_text: Optional[str] = None
    script_ar: Optional[str] = None
    duration: float = 5.0
    visual_query: Optional[str] = None
    visual_type: str = "stock"
    visual_status: str = "pending"
    visual_url: Optional[str] = None
    visual_source: Optional[str] = None
    on_screen_source: Optional[str] = None
    transition: str = "fade"
    effects: list = []

    model_config = {"from_attributes": True}


class SceneUpdate(BaseModel):
    script_text: Optional[str] = None
    script_ar: Optional[str] = None
    duration: Optional[float] = None
    visual_query: Optional[str] = None
    visual_type: Optional[str] = None
    visual_url: Optional[str] = None
    visual_source: Optional[str] = None
    on_screen_source: Optional[str] = None
    transition: Optional[str] = None
    effects: Optional[list] = None


class ProjectCreate(BaseModel):
    channel_id: Optional[str] = None
    title: str
    idea: Optional[str] = None
    video_type: str = "explainer"
    aspect_ratio: str = "16:9"
    template_config: dict = {}


class QuickGenerateRequest(BaseModel):
    title: str
    niche: str = "educational"
    language: str = "en"
    tone: str = "educational"
    is_islamic: bool = False
    video_type: str = "explainer"
    aspect_ratio: str = "16:9"


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    idea: Optional[str] = None
    video_type: Optional[str] = None
    status: Optional[str] = None
    script: Optional[dict] = None
    description: Optional[str] = None
    pinned_comment: Optional[str] = None
    thumbnail_prompt: Optional[str] = None
    metadata_tags: Optional[list] = None
    sharia_reference: Optional[str] = None
    trust_level: Optional[str] = None
    review1_approved: Optional[bool] = None
    review2_approved: Optional[bool] = None
    review3_approved: Optional[bool] = None
    review_notes: Optional[str] = None
    aspect_ratio: Optional[str] = None
    template_config: Optional[dict] = None
    voice_id: Optional[str] = None
    audio_speed: Optional[float] = None
    audio_url: Optional[str] = None
    output_url: Optional[str] = None


class ProjectOut(BaseModel):
    id: str
    channel_id: Optional[str] = None
    title: str
    idea: Optional[str] = None
    video_type: str
    status: str
    script: dict = {}
    description: Optional[str] = None
    pinned_comment: Optional[str] = None
    thumbnail_prompt: Optional[str] = None
    metadata_tags: list = []
    sharia_reference: Optional[str] = None
    trust_level: Optional[str] = None
    review1_approved: bool = False
    review2_approved: bool = False
    review3_approved: bool = False
    review_notes: Optional[str] = None
    aspect_ratio: str = "16:9"
    template_config: dict = {}
    voice_id: Optional[str] = None
    audio_speed: float = 1.0
    audio_url: Optional[str] = None
    output_url: Optional[str] = None
    output_9_16_url: Optional[str] = None
    output_1_1_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    scenes: List[SceneOut] = []

    model_config = {"from_attributes": True}


class ProjectList(BaseModel):
    id: str
    channel_id: Optional[str] = None
    title: str
    video_type: str
    status: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class IdeaRequest(BaseModel):
    niche: str = "educational"
    language: str = "en"
    tone: str = "educational"
    count: int = 5


class IdeaSuggestion(BaseModel):
    title: str
    angle: str
    video_type: str
    hook: str


class ContentGenerateRequest(BaseModel):
    project_id: str
    channel_id: str
    idea: str
    video_type: str
    language: str
    tone: str
    is_islamic: bool = False


class DuplicateCheckRequest(BaseModel):
    channel_id: Optional[str] = None
    idea: str


class DuplicateCheckResult(BaseModel):
    is_duplicate: bool
    similarity: float
    similar_project_id: Optional[str] = None
    similar_project_title: Optional[str] = None
    suggested_angle: Optional[str] = None
