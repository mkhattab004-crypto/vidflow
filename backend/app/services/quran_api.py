import httpx


BASE_URL = "https://api.quran.com/api/v4"


async def get_verse(surah: int, ayah: int, translation_id: int = 131) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(
                f"{BASE_URL}/verses/by_key/{surah}:{ayah}",
                params={"translations": translation_id, "fields": "text_uthmani,verse_key"},
            )
            data = r.json()
            verse = data.get("verse", {})
            translations = verse.get("translations", [{}])
            return {
                "verse_key": verse.get("verse_key"),
                "arabic": verse.get("text_uthmani", ""),
                "translation": translations[0].get("text", "") if translations else "",
            }
        except Exception:
            return {}


async def get_chapter(surah: int) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(f"{BASE_URL}/chapters/{surah}", params={"language": "en"})
            data = r.json()
            ch = data.get("chapter", {})
            return {
                "id": ch.get("id"),
                "name_arabic": ch.get("name_arabic"),
                "name_simple": ch.get("name_simple"),
                "verses_count": ch.get("verses_count"),
                "revelation_place": ch.get("revelation_place"),
            }
        except Exception:
            return {}


async def search_verses(query: str, size: int = 10) -> list[dict]:
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(f"{BASE_URL}/search", params={"q": query, "size": size, "language": "en"})
            data = r.json()
            results = []
            for v in data.get("search", {}).get("results", []):
                results.append({
                    "verse_key": v.get("verse_key"),
                    "arabic": v.get("text"),
                    "translation": v.get("translations", [{}])[0].get("text", "") if v.get("translations") else "",
                })
            return results
        except Exception:
            return []


async def get_daily_verse(translation_id: int = 131) -> dict:
    import random
    surah = random.randint(1, 114)
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(f"{BASE_URL}/chapters/{surah}")
            count = r.json().get("chapter", {}).get("verses_count", 7)
            ayah = random.randint(1, max(1, count))
            return await get_verse(surah, ayah, translation_id)
        except Exception:
            return await get_verse(2, 255, translation_id)
