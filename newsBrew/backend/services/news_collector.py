from dataclasses import dataclass
import html
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


async def _fetch_naver(keyword: str, client_id: str, client_secret: str, max_results: int) -> dict:
    params = {
        "query": keyword,
        "display": min(max_results, 100),
        "sort": "date",
    }
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://openapi.naver.com/v1/search/news.json",
            params=params,
            headers=headers,
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()


def _parse_serpapi(data: dict) -> list[dict]:
    return [
        {
            "title": item.get("title", ""),
            "url": item.get("link", ""),
            "source": item.get("source", ""),
            "published_at": item.get("date", ""),
            "snippet": item.get("snippet", ""),
        }
        for item in data.get("news_results", [])
    ]


def _parse_naver(data: dict) -> list[dict]:
    return [
        {
            "title": html.unescape(item.get("title", "").replace("<b>", "").replace("</b>", "")),
            "url": item.get("link", ""),
            "source": item.get("originallink", ""),
            "published_at": item.get("pubDate", ""),
            "snippet": html.unescape(item.get("description", "").replace("<b>", "").replace("</b>", "")),
        }
        for item in data.get("items", [])
    ]


async def collect_news(
    keyword: str,
    exclude_words: str,
    api_key: str = "",
    max_results: int = 10,
    date_range: str = "d1",
    provider: str = "serpapi",
    naver_client_id: str = "",
    naver_client_secret: str = "",
) -> list[NewsItem]:
    if provider == "naver":
        data = await _fetch_naver(keyword, naver_client_id, naver_client_secret, max_results)
        raw_items = _parse_naver(data)
    else:
        data = await _fetch_serpapi(keyword, api_key, date_range, max_results)
        raw_items = _parse_serpapi(data)

    exclude_list = [w.strip() for w in exclude_words.split(",") if w.strip()]

    items = []
    for item in raw_items:
        title = item["title"]
        if any(ex in title for ex in exclude_list):
            continue
        items.append(NewsItem(
            title=title,
            url=item["url"],
            source=item["source"],
            published_at=item["published_at"],
            snippet=item["snippet"],
        ))
    return items
