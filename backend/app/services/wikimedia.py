import httpx


async def search_images(query: str, limit: int = 10) -> list[dict]:
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrlimit": limit,
        "prop": "imageinfo",
        "iiprop": "url|size|mime",
        "iiurlwidth": 1280,
        "format": "json",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get("https://commons.wikimedia.org/w/api.php", params=params)
            data = r.json()
            results = []
            pages = data.get("query", {}).get("pages", {})
            for page in pages.values():
                info = page.get("imageinfo", [{}])[0]
                url = info.get("thumburl") or info.get("url", "")
                if url and "image" in info.get("mime", "image"):
                    results.append({
                        "id": str(page.get("pageid", "")),
                        "url": url,
                        "thumb": info.get("thumburl", url),
                        "source": "wikimedia",
                        "attribution": f"Wikimedia Commons - {page.get('title', '')}",
                    })
            return results
        except Exception:
            return []
