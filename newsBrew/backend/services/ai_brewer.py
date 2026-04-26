import json
import re
from dataclasses import dataclass
from openai import AsyncOpenAI
from google import genai
from services.news_collector import NewsItem


@dataclass
class BrewedArticle:
    title: str
    url: str
    source: str
    published_at: str
    summary: str
    importance_score: int


BREW_PROMPT = """당신은 뉴스 큐레이터입니다. 아래 뉴스 목록을 분석하여:
1. 광고성, 홍보성 기사를 제외합니다.
2. 각 기사의 중요도를 1~10점으로 평가합니다.
3. 핵심 내용을 개조식 2~3줄로 요약합니다.

입력 형식: JSON 배열 (title, url, snippet 포함)
출력 형식: JSON 배열 [{{"title": "...", "summary": "...", "importance_score": 숫자}}]

뉴스 목록:
{news_json}

JSON 배열만 출력하세요."""


def _extract_json(raw: str) -> list:
    json_match = re.search(r'\[.*\]', raw, re.DOTALL)
    if not json_match:
        return []
    return json.loads(json_match.group())


async def _brew_with_openai(news_json: str, api_key: str) -> list:
    client = AsyncOpenAI(api_key=api_key)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": BREW_PROMPT.format(news_json=news_json)}],
        temperature=0.2,
    )
    return _extract_json(response.choices[0].message.content.strip())


async def _brew_with_gemini(news_json: str, api_key: str, model: str) -> list:
    client = genai.Client(api_key=api_key)
    response = await client.aio.models.generate_content(
        model=model,
        contents=BREW_PROMPT.format(news_json=news_json),
    )
    return _extract_json(response.text.strip())


async def brew_articles(
    keyword: str,
    news_items: list[NewsItem],
    api_key: str,
    min_importance: int = 5,
    provider: str = "openai",
    gemini_model: str = "gemini-2.0-flash-preview-04-17",
) -> list[BrewedArticle]:
    if not news_items:
        return []

    news_json = json.dumps([
        {"title": n.title, "url": n.url, "snippet": n.snippet}
        for n in news_items
    ], ensure_ascii=False)

    if provider == "gemini":
        ai_results = await _brew_with_gemini(news_json, api_key, gemini_model)
    else:
        ai_results = await _brew_with_openai(news_json, api_key)

    url_map = {n.title: n for n in news_items}
    brewed = []
    for item in ai_results:
        if item.get("importance_score", 0) < min_importance:
            continue
        original = url_map.get(item["title"])
        if not original:
            continue
        brewed.append(BrewedArticle(
            title=item["title"],
            url=original.url,
            source=original.source,
            published_at=original.published_at,
            summary=item.get("summary", ""),
            importance_score=item["importance_score"],
        ))

    return sorted(brewed, key=lambda x: x.importance_score, reverse=True)
