from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.channel import Channel, ChannelHook, ChannelCTA
from app.schemas.channel import ChannelCreate, ChannelUpdate, ChannelOut, ChannelList, ChannelHookBase, ChannelCTABase
import os, uuid, shutil
from app.config import settings

router = APIRouter(prefix="/channels", tags=["channels"])


async def _load_channel(channel_id: str, db: AsyncSession) -> Channel:
    result = await db.execute(
        select(Channel)
        .options(selectinload(Channel.hooks), selectinload(Channel.ctas))
        .where(Channel.id == channel_id)
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


@router.get("", response_model=list[ChannelList])
async def list_channels(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Channel).order_by(Channel.name))
    return result.scalars().all()


@router.post("", response_model=ChannelOut, status_code=201)
async def create_channel(data: ChannelCreate, db: AsyncSession = Depends(get_db)):
    channel = Channel(**data.model_dump())
    db.add(channel)
    await db.commit()
    return await _load_channel(channel.id, db)


@router.get("/{channel_id}", response_model=ChannelOut)
async def get_channel(channel_id: str, db: AsyncSession = Depends(get_db)):
    return await _load_channel(channel_id, db)


@router.put("/{channel_id}", response_model=ChannelOut)
async def update_channel(channel_id: str, data: ChannelUpdate, db: AsyncSession = Depends(get_db)):
    channel = await db.get(Channel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(channel, k, v)
    await db.commit()
    return await _load_channel(channel_id, db)


@router.delete("/{channel_id}", status_code=204)
async def delete_channel(channel_id: str, db: AsyncSession = Depends(get_db)):
    channel = await db.get(Channel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    await db.delete(channel)
    await db.commit()


@router.post("/{channel_id}/logo")
async def upload_logo(channel_id: str, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    channel = await db.get(Channel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    upload_dir = os.path.join(settings.UPLOAD_DIR, "logos")
    os.makedirs(upload_dir, exist_ok=True)
    ext = file.filename.split(".")[-1] if "." in file.filename else "png"
    fname = f"{channel_id}.{ext}"
    path = os.path.join(upload_dir, fname)
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    channel.logo_url = f"/static/logos/{fname}"
    await db.commit()
    return {"logo_url": channel.logo_url}


@router.post("/{channel_id}/hooks", status_code=201)
async def add_hook(channel_id: str, data: ChannelHookBase, db: AsyncSession = Depends(get_db)):
    hook = ChannelHook(channel_id=channel_id, **data.model_dump())
    db.add(hook)
    await db.commit()
    await db.refresh(hook)
    return hook


@router.delete("/{channel_id}/hooks/{hook_id}", status_code=204)
async def delete_hook(channel_id: str, hook_id: int, db: AsyncSession = Depends(get_db)):
    hook = await db.get(ChannelHook, hook_id)
    if not hook or hook.channel_id != channel_id:
        raise HTTPException(status_code=404, detail="Hook not found")
    await db.delete(hook)
    await db.commit()


@router.post("/{channel_id}/ctas", status_code=201)
async def add_cta(channel_id: str, data: ChannelCTABase, db: AsyncSession = Depends(get_db)):
    cta = ChannelCTA(channel_id=channel_id, **data.model_dump())
    db.add(cta)
    await db.commit()
    await db.refresh(cta)
    return cta


@router.delete("/{channel_id}/ctas/{cta_id}", status_code=204)
async def delete_cta(channel_id: str, cta_id: int, db: AsyncSession = Depends(get_db)):
    cta = await db.get(ChannelCTA, cta_id)
    if not cta or cta.channel_id != channel_id:
        raise HTTPException(status_code=404, detail="CTA not found")
    await db.delete(cta)
    await db.commit()
