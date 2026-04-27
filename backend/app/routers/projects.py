from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.project import Project, Scene
from app.models.channel import Channel
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectOut, ProjectList,
    SceneUpdate, ContentGenerateRequest
)
from app.services import gemini

router = APIRouter(prefix="/projects", tags=["projects"])


async def _load_project(project_id: str, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.scenes))
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


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db)):
    channel = await db.get(Channel, data.channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    project = Project(**data.model_dump())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


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
    channel = await db.get(Channel, project.channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    content = await gemini.generate_script(
        idea=project.idea or project.title,
        video_type=project.video_type,
        language=channel.language,
        tone=channel.script_tone,
        niche=channel.niche,
        channel_name=channel.name,
        is_islamic=channel.is_islamic,
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
        scene = Scene(
            project_id=project.id,
            order=scene_data.get("order", 0),
            script_text=scene_data.get("script_text", ""),
            script_ar=scene_data.get("script_ar"),
            duration=scene_data.get("duration", 5),
            visual_query=scene_data.get("visual_query", ""),
            visual_type=scene_data.get("visual_type", "stock"),
            transition=scene_data.get("transition", "fade"),
            effects=scene_data.get("effects", []),
        )
        db.add(scene)

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
