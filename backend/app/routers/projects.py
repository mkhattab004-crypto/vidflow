import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.project import Project, Scene
from app.models.channel import Channel
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectOut, ProjectList,
    SceneUpdate, ContentGenerateRequest, QuickGenerateRequest
)
from app.services import gemini

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])


def _build_scene_for_script_generation(project_id: str, scene_data: dict) -> Scene:
    scene = Scene(
        project_id=project_id,
        order=scene_data.get("order", 0),
        script_text=scene_data.get("script_text", ""),
        script_ar=scene_data.get("script_ar"),
        duration=scene_data.get("duration", 5),
        visual_query=scene_data.get("visual_query", ""),
        visual_type=scene_data.get("visual_type", "stock"),
        visual_url=None,
        visual_source_url=None,
        visual_metadata={},
        visual_locked=False,
        visual_selected_for_project_id=None,
        visual_selected_for_scene_id=None,
        visual_selected_at=None,
        thumbnail_url=None,
        transition=scene_data.get("transition", "fade"),
        effects=scene_data.get("effects", []),
    )
    logger.info(
        "creating scene project_id=%s visual_selected_for_project_id=%s visual_selected_for_scene_id=%s",
        project_id,
        scene.visual_selected_for_project_id,
        scene.visual_selected_for_scene_id,
    )
    return scene


async def _load_project(project_id: str, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.scenes), selectinload(Project.channel))
        .where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("", response_model=list[ProjectList])
async def list_projects(
    channel_id: str = Query(None),
    status: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    q = select(Project).order_by(Project.created_at.desc())
    if channel_id:
        q = q.where(Project.channel_id == channel_id)
    if status:
        q = q.where(Project.status == status)
    result = await db.execute(q)
    return result.scalars().all()

@router.post("/quick-generate/", response_model=ProjectOut, status_code=201, include_in_schema=False)
@router.post("/quick-generate", response_model=ProjectOut, status_code=201)
async def quick_generate(data: QuickGenerateRequest, db: AsyncSession = Depends(get_db)):
    """Create a project and generate its full script in one shot — no channel required."""
    logger.info(f"quick_generate: START title={data.title!r:.60} niche={data.niche} lang={data.language} islamic={data.is_islamic}")

    project = Project(
        channel_id=None,
        title=data.title,
        idea=data.title,
        video_type=data.video_type,
        aspect_ratio=data.aspect_ratio,
        niche=data.niche,
        language=data.language,
        is_islamic=data.is_islamic,
        status="idea",
    )
    db.add(project)
    await db.flush()
    logger.info(f"quick_generate: project row created id={project.id}")

    content = await gemini.generate_script(
        idea=data.title,
        video_type=data.video_type,
        language=data.language,
        tone=data.tone,
        niche=data.niche,
        channel_name="VidFlow",
        is_islamic=data.is_islamic,
    )
    logger.info(f"quick_generate: gemini returned {len(content.get('scenes', []))} scenes")

    project.title = content.get("title", data.title)
    project.description = content.get("description", "")
    project.pinned_comment = content.get("pinned_comment", "")
    project.thumbnail_prompt = content.get("thumbnail_prompt", "")
    project.metadata_tags = content.get("tags", [])
    project.sharia_reference = content.get("sharia_reference")
    project.trust_level = content.get("trust_level")
    project.status = "content_generated"

    for scene_data in content.get("scenes", []):
        db.add(_build_scene_for_script_generation(project.id, scene_data))

    await db.commit()
    logger.info(f"quick_generate: DONE committed project id={project.id} with {len(content.get('scenes', []))} scenes")
    return await _load_project(project.id, db)


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db)):
    if data.channel_id:
        channel = await db.get(Channel, data.channel_id)
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")
    project = Project(**data.model_dump())
    db.add(project)
    await db.commit()
    return await _load_project(project.id, db)

@router.get("/quick-generate")
async def quick_generate_get_blocker():
    raise HTTPException(
        status_code=405,
        detail="quick-generate must be called with POST, not GET"
    )
@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    return await _load_project(project_id, db)


@router.put("/{project_id}", response_model=ProjectOut)
async def update_project(project_id: str, data: ProjectUpdate, db: AsyncSession = Depends(get_db)):
    project = await _load_project(project_id, db)
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(project, k, v)
    await db.commit()
    await db.refresh(project)
    return await _load_project(project_id, db)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)
    await db.commit()


@router.post("/{project_id}/generate-content", response_model=ProjectOut)
async def generate_content(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await _load_project(project_id, db)
    channel = await db.get(Channel, project.channel_id) if project.channel_id else None

    content = await gemini.generate_script(
        idea=project.idea or project.title,
        video_type=project.video_type,
        language=channel.language if channel else (project.language or "en"),
        tone=channel.script_tone if channel else "educational",
        niche=channel.niche if channel else (project.niche or "educational"),
        channel_name=channel.name if channel else "VidFlow",
        is_islamic=channel.is_islamic if channel else (project.is_islamic or False),
    )

    project.title = content.get("title", project.title)
    project.description = content.get("description", "")
    project.pinned_comment = content.get("pinned_comment", "")
    project.thumbnail_prompt = content.get("thumbnail_prompt", "")
    project.metadata_tags = content.get("tags", [])
    project.sharia_reference = content.get("sharia_reference")
    project.trust_level = content.get("trust_level")
    project.status = "content_generated"

    for sc in project.scenes:
        await db.delete(sc)

    for scene_data in content.get("scenes", []):
        db.add(_build_scene_for_script_generation(project.id, scene_data))

    await db.commit()
    return await _load_project(project_id, db)


@router.put("/{project_id}/scenes/{scene_id}", response_model=ProjectOut)
async def update_scene(project_id: str, scene_id: int, data: SceneUpdate, db: AsyncSession = Depends(get_db)):
    scene = await db.get(Scene, scene_id)
    if not scene or scene.project_id != project_id:
        raise HTTPException(status_code=404, detail="Scene not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(scene, k, v)
    await db.commit()
    return await _load_project(project_id, db)


@router.post("/{project_id}/copy")
async def copy_project(project_id: str, db: AsyncSession = Depends(get_db)):
    original = await _load_project(project_id, db)
    import uuid
    new_project = Project(
        channel_id=original.channel_id,
        title=f"Copy of {original.title}",
        idea=original.idea,
        video_type=original.video_type,
        status="idea",
        script=original.script,
        description=original.description,
        pinned_comment=original.pinned_comment,
        thumbnail_prompt=original.thumbnail_prompt,
        metadata_tags=original.metadata_tags,
        aspect_ratio=original.aspect_ratio,
        template_config=original.template_config,
        voice_id=original.voice_id,
    )
    db.add(new_project)
    await db.flush()
    for scene in original.scenes:
        db.add(Scene(
            project_id=new_project.id,
            order=scene.order,
            script_text=scene.script_text,
            script_ar=scene.script_ar,
            duration=scene.duration,
            visual_query=scene.visual_query,
            visual_type=scene.visual_type,
            transition=scene.transition,
            effects=scene.effects,
        ))
    await db.commit()
    return {"new_project_id": new_project.id}


@router.post("/{project_id}/optimize-seo")
async def optimize_seo(project_id: str, db: AsyncSession = Depends(get_db)):
    """Use Gemini to improve title, description, and tags for YouTube SEO."""
    project = await _load_project(project_id, db)
    channel = await db.get(Channel, project.channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    optimized = await gemini.optimize_metadata(
        title=project.title,
        description=project.description or "",
        niche=channel.niche,
        language=channel.language,
    )
    project.title = optimized.get("optimized_title", project.title)
    project.description = optimized.get("optimized_description", project.description)
    project.metadata_tags = optimized.get("tags", project.metadata_tags)
    project.pinned_comment = optimized.get("pinned_comment", project.pinned_comment)

    extra = project.extra_config if hasattr(project, "extra_config") else {}
    script_json = project.script or {}
    script_json["youtube_chapters"] = optimized.get("chapters", [])
    project.script = script_json

    await db.commit()
    logger.info(f"SEO optimized project {project_id}")
    return {"optimized": optimized, "project_id": project_id}


@router.get("/{project_id}/export-bundle")
async def export_bundle(project_id: str, db: AsyncSession = Depends(get_db)):
    """Return full project data in a single payload for archiving."""
    project = await _load_project(project_id, db)
    channel = await db.get(Channel, project.channel_id)
    return {
        "project_id": project_id,
        "channel": {"id": channel.id, "name": channel.name, "niche": channel.niche} if channel else None,
        "title": project.title,
        "idea": project.idea,
        "video_type": project.video_type,
        "status": project.status,
        "description": project.description,
        "pinned_comment": project.pinned_comment,
        "thumbnail_prompt": project.thumbnail_prompt,
        "tags": project.metadata_tags,
        "sharia_reference": project.sharia_reference,
        "trust_level": project.trust_level,
        "scenes": [
            {
                "order": s.order,
                "script_text": s.script_text,
                "script_ar": s.script_ar,
                "duration": s.duration,
                "visual_query": s.visual_query,
                "visual_type": s.visual_type,
                "visual_url": s.visual_url,
                "on_screen_source": s.on_screen_source,
                "transition": s.transition,
                "effects": s.effects,
            }
            for s in project.scenes
        ],
        "template": {
            "aspect_ratio": project.aspect_ratio,
            **project.template_config,
        },
        "voice_id": project.voice_id,
        "audio_speed": project.audio_speed,
        "reviews": {
            "review1": project.review1_approved,
            "review2": project.review2_approved,
            "review3": project.review3_approved,
        },
        "outputs": {
            "16:9": project.output_url,
            "9:16": project.output_9_16_url,
            "1:1": project.output_1_1_url,
        },
        "created_at": project.created_at.isoformat() if project.created_at else None,
    }
