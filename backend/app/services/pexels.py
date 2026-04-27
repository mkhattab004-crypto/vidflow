import httpx
from app.config import settings


async def search_videos(query: str, per_page: int = 10, orientation: str = "landscape") -> list[dict]:
    if not settings.PEXELS_API_KEY:
        return []
    headers = {"Authorization": settings.PEXELS_API_KEY}
    params = {"query": query, "per_page": per_page, "orientation": orientation}
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get("https://api.pexels.com/videos/search", headers=headers, params=params)
            data = r.json()
            results = []
            for v in data.get("videos", []):
                files = v.get("video_files", [])
                hd = next((f for f in files if f.get("quality") == "hd"), files[0] if files else None)
                if hd:
                    results.append({
                        "id": str(v["id"]),
                        "url": hd["link"],
                        "thumb": v.get("image", ""),
                        "source": "pexels",
                        "duration": v.get("duration", 0),
                        "attribution": f"Video by {v.get('user', {}).get('name', 'Pexels')} on Pexels",
                    })
            return results
        except Exception:
            return []


async def search_photos(query: str, per_page: int = 10) -> list[dict]:
    if not settings.PEXELS_API_KEY:
        return []
    headers = {"Authorization": settings.PEXELS_API_KEY}
    params = {"query": query, "per_page": per_page}
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get("https://api.pexels.com/v1/search", headers=headers, params=params)
            data = r.json()
            return [
                {
                    "id": str(p["id"]),
                    "url": p["src"]["large2x"],
                    "thumb": p["src"]["medium"],
                    "source": "pexels",
                    "attribution": f"Photo by {p.get('photographer', 'Pexels')} on Pexels",
                }
                for p in data.get("photos", [])
            ]
        except Exception:
            return []
