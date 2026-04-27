import httpx
from app.config import settings


async def search_videos(query: str, per_page: int = 10) -> list[dict]:
    if not settings.PIXABAY_API_KEY:
        return []
    params = {"key": settings.PIXABAY_API_KEY, "q": query, "per_page": per_page, "video_type": "all"}
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get("https://pixabay.com/api/videos/", params=params)
            data = r.json()
            results = []
            for v in data.get("hits", []):
                videos = v.get("videos", {})
                url = videos.get("large", {}).get("url") or videos.get("medium", {}).get("url", "")
                if url:
                    results.append({
                        "id": str(v["id"]),
                        "url": url,
                        "thumb": v.get("picture_id", ""),
                        "source": "pixabay",
                        "duration": v.get("duration", 0),
                        "attribution": "Video from Pixabay",
                    })
            return results
        except Exception:
            return []


async def search_photos(query: str, per_page: int = 10) -> list[dict]:
    if not settings.PIXABAY_API_KEY:
        return []
    params = {"key": settings.PIXABAY_API_KEY, "q": query, "per_page": per_page, "image_type": "photo"}
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get("https://pixabay.com/api/", params=params)
            data = r.json()
            return [
                {
                    "id": str(p["id"]),
                    "url": p["largeImageURL"],
                    "thumb": p["previewURL"],
                    "source": "pixabay",
                    "attribution": "Photo from Pixabay",
                }
                for p in data.get("hits", [])
            ]
        except Exception:
            return []
