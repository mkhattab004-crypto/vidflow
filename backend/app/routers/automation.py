from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.channel import Channel
from app.models.project import Project
from app.services import n8n_service

router = APIRouter(prefix="/automation", tags=["automation"])


class ScheduleRequest(BaseModel):
    channel_id: str
    frequency: str = "weekly"  # daily / weekly / custom


class WebhookTestRequest(BaseModel):
    event_type: str = "test"


@router.post("/schedule")
async def schedule_channel(req: ScheduleRequest, db: AsyncSession = Depends(get_db)):
    channel = await db.get(Channel, req.channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    ok = await n8n_service.trigger_generation_schedule(
        channel_id=channel.id,
        channel_name=channel.name,
        niche=channel.niche,
    )
    return {"scheduled": ok, "channel": channel.name, "frequency": req.frequency}


@router.post("/webhook/test")
async def test_webhook(req: WebhookTestRequest):
    ok = await n8n_service._post({"event": req.event_type, "test": True}, "")
    return {"sent": ok}


@router.get("/stats/weekly")
async def weekly_stats(db: AsyncSession = Depends(get_db)):
    from datetime import datetime, timedelta
    week_ago = datetime.utcnow() - timedelta(days=7)

    total_projects = await db.scalar(select(func.count(Project.id)))
    week_projects = await db.scalar(
        select(func.count(Project.id)).where(Project.created_at >= week_ago)
    )
    done_projects = await db.scalar(
        select(func.count(Project.id)).where(Project.status == "done")
    )
    total_channels = await db.scalar(select(func.count(Channel.id)))

    stats = {
        "total_projects": total_projects or 0,
        "projects_this_week": week_projects or 0,
        "done_projects": done_projects or 0,
        "total_channels": total_channels or 0,
    }
    await n8n_service.send_weekly_report(stats)
    return stats


@router.get("/stats/dashboard")
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Quick stats for the dashboard."""
    total = await db.scalar(select(func.count(Project.id)))
    by_status = {}
    statuses = ["idea", "content_generated", "rendering", "rendered", "done"]
    for s in statuses:
        count = await db.scalar(select(func.count(Project.id)).where(Project.status == s))
        by_status[s] = count or 0

    channel_count = await db.scalar(select(func.count(Channel.id)))
    return {
        "total_projects": total or 0,
        "total_channels": channel_count or 0,
        "by_status": by_status,
    }
