from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.project import Project
from app.schemas.project import IdeaRequest, IdeaSuggestion, DuplicateCheckRequest, DuplicateCheckResult
from app.services import gemini

router = APIRouter(prefix="/ideas", tags=["ideas"])


@router.post("/suggest", response_model=list[IdeaSuggestion])
async def suggest_ideas(data: IdeaRequest, db: AsyncSession = Depends(get_db)):
    ideas = await gemini.generate_ideas(
        niche=data.niche,
        language=data.language,
        tone=data.tone,
        count=data.count,
    )
    return ideas


@router.post("/check-duplicate", response_model=DuplicateCheckResult)
async def check_duplicate(data: DuplicateCheckRequest, db: AsyncSession = Depends(get_db)):
    q = select(Project.id, Project.title).order_by(Project.created_at.desc()).limit(100)
    if data.channel_id:
        q = q.where(Project.channel_id == data.channel_id)
    result = await db.execute(q)
    existing = result.all()
    titles = [r.title for r in existing]

    dup_result = await gemini.check_duplicate(data.idea, titles)

    similar_id = None
    similar_title = dup_result.get("most_similar_title")
    if similar_title:
        for r in existing:
            if r.title == similar_title:
                similar_id = r.id
                break

    return DuplicateCheckResult(
        is_duplicate=dup_result.get("is_duplicate", False),
        similarity=dup_result.get("similarity", 0.0),
        similar_project_id=similar_id,
        similar_project_title=similar_title,
        suggested_angle=dup_result.get("suggested_angle"),
    )


VIDEO_TYPES = [
    {"id": "story", "label": "Story", "label_ar": "قصة"},
    {"id": "explainer", "label": "Explainer", "label_ar": "شرح"},
    {"id": "listicle", "label": "Listicle", "label_ar": "قائمة"},
    {"id": "quote", "label": "Quote", "label_ar": "اقتباس"},
    {"id": "verse_tafsir", "label": "Verse + Tafsir", "label_ar": "آية وتفسير"},
    {"id": "hadith", "label": "Hadith", "label_ar": "حديث"},
    {"id": "biography", "label": "Biography", "label_ar": "سيرة"},
    {"id": "mystery", "label": "Mystery", "label_ar": "غموض"},
    {"id": "comparison", "label": "Comparison", "label_ar": "مقارنة"},
    {"id": "countdown", "label": "Short Countdown", "label_ar": "عد تنازلي"},
]


@router.get("/video-types")
async def get_video_types():
    return VIDEO_TYPES
