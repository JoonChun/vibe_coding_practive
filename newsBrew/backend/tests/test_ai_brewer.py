import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from services.ai_brewer import brew_articles, BrewedArticle
from services.news_collector import NewsItem

MOCK_NEWS_ITEMS = [
    NewsItem(title="AI 반도체 수요 급증", url="http://a.com", source="테크", published_at="2h ago", snippet="AI 수요가 증가하고 있다."),
    NewsItem(title="광고성 기사 예시", url="http://b.com", source="광고", published_at="3h ago", snippet="지금 구매하세요!"),
    NewsItem(title="반도체 기술 혁신", url="http://c.com", source="기술", published_at="4h ago", snippet="새로운 기술이 등장했다."),
]

MOCK_AI_RESPONSE = """
[
  {"title": "AI 반도체 수요 급증", "summary": "AI 수요 증가로 반도체 시장이 확대되고 있다.", "importance_score": 9},
  {"title": "반도체 기술 혁신", "summary": "차세대 반도체 기술이 등장해 업계에 혁신을 불러오고 있다.", "importance_score": 7}
]
"""

@pytest.mark.asyncio
async def test_brew_articles_returns_brewed_articles():
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=MagicMock(choices=[MagicMock(message=MagicMock(content=MOCK_AI_RESPONSE))])
    )
    with patch("services.ai_brewer._get_openai_client", return_value=mock_client):
        results = await brew_articles(
            keyword="반도체",
            news_items=MOCK_NEWS_ITEMS,
            api_key="test_key",
            min_importance=6
        )
    assert len(results) == 2
    assert isinstance(results[0], BrewedArticle)
    assert results[0].importance_score == 9
    assert results[0].url == "http://a.com"

@pytest.mark.asyncio
async def test_brew_articles_empty_input():
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=MagicMock(choices=[MagicMock(message=MagicMock(content="[]"))])
    )
    with patch("services.ai_brewer._get_openai_client", return_value=mock_client):
        results = await brew_articles("반도체", [], "test_key", 6)
    assert results == []
