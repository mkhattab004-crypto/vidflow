"""
n8n webhook integration for automation triggers.
Sends events to n8n for: video completed, weekly report, scheduling.
"""
import httpx
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)


async def _post(payload: dict, webhook_url: str) -> bool:
    if not webhook_url:
        logger.debug("n8n webhook URL not configured — skipping")
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(webhook_url, json=payload)
            r.raise_for_status()
            return True
    except Exception as e:
        logger.warning(f"n8n webhook failed: {e}")
        return False


async def notify_video_ready(project_id: str, title: str, channel_name: str, output_url: Optional[str]) -> bool:
    """Trigger n8n flow when a video finishes rendering."""
    return await _post(
        {
            "event": "video_ready",
            "project_id": project_id,
            "title": title,
            "channel": channel_name,
            "output_url": output_url,
        },
        settings.N8N_WEBHOOK_URL or "",
    )


async def notify_review_needed(project_id: str, title: str, review_level: int, channel_name: str) -> bool:
    """Trigger n8n flow when a project needs review."""
    return await _post(
        {
            "event": "review_needed",
            "project_id": project_id,
            "title": title,
            "review_level": review_level,
            "channel": channel_name,
        },
        settings.N8N_WEBHOOK_URL or "",
    )


async def send_weekly_report(stats: dict) -> bool:
    """Send weekly summary report via n8n."""
    return await _post(
        {"event": "weekly_report", **stats},
        settings.N8N_WEBHOOK_URL or "",
    )


async def trigger_generation_schedule(channel_id: str, channel_name: str, niche: str) -> bool:
    """Trigger scheduled generation for a channel."""
    return await _post(
        {
            "event": "scheduled_generation",
            "channel_id": channel_id,
            "channel_name": channel_name,
            "niche": niche,
        },
        settings.N8N_WEBHOOK_URL or "",
    )
