import httpx


BASE_URL = "https://api.sunnah.com/v1"
# Free usage — no key required for basic access


async def get_hadith(collection: str, book: int, hadith_number: int) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(f"{BASE_URL}/hadiths/{collection}:{book}:{hadith_number}")
            data = r.json()
            return {
                "id": data.get("hadithNumber"),
                "collection": collection,
                "arabic": data.get("body", {}).get("ar", ""),
                "english": data.get("body", {}).get("en", ""),
                "reference": f"{collection} {book}:{hadith_number}",
                "grade": data.get("grade", ""),
            }
        except Exception:
            return {}


async def get_random_hadith(collection: str = "bukhari") -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(f"{BASE_URL}/hadiths/random", params={"collection": collection})
            data = r.json()
            return {
                "id": data.get("hadithNumber"),
                "collection": collection,
                "arabic": data.get("body", {}).get("ar", ""),
                "english": data.get("body", {}).get("en", ""),
                "reference": f"{collection} - Hadith {data.get('hadithNumber', '')}",
                "grade": data.get("grade", ""),
            }
        except Exception:
            return {}


COLLECTIONS = [
    {"id": "bukhari", "name": "Sahih al-Bukhari", "hadith_count": 7563},
    {"id": "muslim", "name": "Sahih Muslim", "hadith_count": 7470},
    {"id": "abudawud", "name": "Sunan Abu Dawud", "hadith_count": 5274},
    {"id": "tirmidhi", "name": "Jami at-Tirmidhi", "hadith_count": 3956},
    {"id": "nasai", "name": "Sunan an-Nasa'i", "hadith_count": 5761},
    {"id": "ibnmajah", "name": "Sunan Ibn Majah", "hadith_count": 4341},
    {"id": "riyadussalihin", "name": "Riyad as-Salihin", "hadith_count": 1906},
]
