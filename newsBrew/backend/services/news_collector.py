from dataclasses import dataclass
import httpx


@dataclass
class NewsItem:
    title: str
    url: str
    source: str
    published_at: str
    snippet: str


async def _fetch_serpapi(keyword: str, api_key: str, date_range: str, max_results: int) -> dict:
    params = {
        "engine": "google_news",
        "q": keyword,
        "api_key": api_key,
        "num": max_results,
        "tbs": f"qdr:{date_range}",
        "hl": "ko",
        "gl": "kr",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://serpapi.com/search", params=params, timeout=30.0)
        resp.raise_for_status()
        return resp.json()


async def collect_news(
    keyword: str,
    exclude_words: str,
    api_key: str,
    max_results: int = 10,
    date_range: str = "d1",
) -> list[NewsItem]:
    data = await _fetch_serpapi(keyword, api_key, date_range, max_results)
    news_results = data.get("news_results", [])

    exclude_list = [w.strip() for w in exclude_words.split(",") if w.strip()]

    items = []
    for item in news_results:
        title = item.get("title", "")
        if any(ex in title for ex in exclude_list):
            continue
        items.append(NewsItem(
            title=title,
            url=item.get("link", ""),
            source=item.get("source", ""),
            published_at=item.get("date", ""),
            snippet=item.get("snippet", ""),
        ))
    return items
