import pytest
from unittest.mock import AsyncMock, patch
from services.news_collector import collect_news, NewsItem

MOCK_SERPAPI_RESPONSE = {
    "news_results": [
        {
            "title": "AI 반도체 시장 폭발적 성장",
            "link": "https://example.com/news/1",
            "source": "테크크런치",
            "date": "2 hours ago",
            "snippet": "AI 반도체 수요가 급증하고 있다."
        },
        {
            "title": "삼성전자 HBM 공급 확대",
            "link": "https://example.com/news/2",
            "source": "매일경제",
            "date": "5 hours ago",
            "snippet": "삼성전자가 HBM 공급을 확대한다."
        }
    ]
}

@pytest.mark.asyncio
async def test_collect_news_returns_news_items():
    with patch("services.news_collector._fetch_serpapi", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = MOCK_SERPAPI_RESPONSE
        results = await collect_news(
            keyword="반도체",
            exclude_words="광고",
            api_key="test_key",
            max_results=10,
            date_range="d1"
        )
    assert len(results) == 2
    assert isinstance(results[0], NewsItem)
    assert results[0].title == "AI 반도체 시장 폭발적 성장"
    assert results[0].url == "https://example.com/news/1"

@pytest.mark.asyncio
async def test_collect_news_filters_exclude_words():
    mock_response = {
        "news_results": [
            {"title": "반도체 광고 특집", "link": "http://a.com", "source": "광고매체", "date": "1h ago", "snippet": "광고"},
            {"title": "반도체 기술 동향", "link": "http://b.com", "source": "기술매체", "date": "2h ago", "snippet": "기술"},
        ]
    }
    with patch("services.news_collector._fetch_serpapi", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_response
        results = await collect_news(
            keyword="반도체",
            exclude_words="광고",
            api_key="test_key",
            max_results=10,
            date_range="d1"
        )
    assert len(results) == 1
    assert results[0].title == "반도체 기술 동향"

@pytest.mark.asyncio
async def test_collect_news_empty_results():
    with patch("services.news_collector._fetch_serpapi", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {"news_results": []}
        results = await collect_news("없는키워드", "", "test_key", 10, "d1")
    assert results == []
