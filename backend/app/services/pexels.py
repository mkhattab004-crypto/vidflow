import httpx
from app.config import settings


async def search_videos(query: str, per_page: int = 10, orientation: str = "landscape") -> list[dict]:
    if not settings.PEXELS_API_KEY:
        return []

    def _pick_video_file(files: list[dict]) -> dict | None:
        if not files:
            return None

        def _dimension_score(width: int, height: int) -> tuple[int, int]:
            # Prefer width in [960, 1920], then closest to 1280.
            in_range = 0 if 960 <= width <= 1920 else 1
            return (in_range, abs(width - 1280), abs(height - 720))

        ranked: list[tuple[tuple, dict]] = []
        for f in files:
            file_type = (f.get("file_type") or "").lower()
            link = (f.get("link") or "").strip()
            quality = (f.get("quality") or "").lower()
            width = int(f.get("width") or 0)
            height = int(f.get("height") or 0)

            is_mp4_type = file_type == "video/mp4"
            is_mp4_link = ".mp4" in link.lower()
            quality_rank = 0 if quality == "sd" else 1 if quality == "hd" else 2
            dim_rank = _dimension_score(width, height)
            pixel_count = width * height if width and height else 10**12

            rank = (
                0 if is_mp4_type else 1,
                0 if is_mp4_link else 1,
                quality_rank,
                dim_rank,
                pixel_count,
            )
            ranked.append((rank, f))

        ranked.sort(key=lambda item: item[0])

        # Safe fallback: prefer any MP4-looking file before generic first item.
        for _, file_obj in ranked:
            if (file_obj.get("file_type") or "").lower() == "video/mp4" or ".mp4" in (file_obj.get("link") or "").lower():
                return file_obj

        return ranked[0][1] if ranked else None

    headers = {"Authorization": settings.PEXELS_API_KEY}
    params = {"query": query, "per_page": per_page, "orientation": orientation}
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get("https://api.pexels.com/videos/search", headers=headers, params=params)
            data = r.json()
            results = []
            for v in data.get("videos", []):
                selected = _pick_video_file(v.get("video_files", []))
                if selected and selected.get("link"):
                    results.append({
                        "id": str(v["id"]),
                        "url": selected["link"],
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
