from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import Keyword, Archive, Setting
from database.database import AsyncSessionLocal
from services.news_collector import collect_news
from services.ai_brewer import brew_articles
from services.email_sender import send_brew_email
from services.sheets import archive_to_sheets
from ws.manager import manager

async def _load_settings_dict(db: AsyncSession) -> dict:
    result = await db.execute(select(Setting))
    return {r.key: r.value for r in result.scalars().all()}

async def run_brew_pipeline():
    brew_date = date.today().isoformat()
    await manager.broadcast("INFO", f"🍺 브루잉 시작: {brew_date}")

    async with AsyncSessionLocal() as db:
        settings = await _load_settings_dict(db)
        keywords_result = await db.execute(select(Keyword))
        keywords = keywords_result.scalars().all()

    if not keywords:
        await manager.broadcast("WARN", "등록된 키워드가 없습니다.")
        return

    keyword_results = {}

    for kw in keywords:
        await manager.broadcast("INFO", f"🔍 [{kw.word}] 뉴스 수집 중...")
        try:
            news_items = await collect_news(
                keyword=kw.word,
                exclude_words=kw.exclude_words or "",
                api_key=settings.get("serpapi_key", ""),
                max_results=15,
                date_range="d1",
            )
            await manager.broadcast("INFO", f"📰 [{kw.word}] {len(news_items)}건 수집 완료")

            await manager.broadcast("INFO", f"🤖 [{kw.word}] AI 요약 중...")
            brewed = await brew_articles(
                keyword=kw.word,
                news_items=news_items,
                api_key=settings.get("openai_key", ""),
                min_importance=5,
            )
            await manager.broadcast("INFO", f"✅ [{kw.word}] {len(brewed)}건 요약 완료")
            keyword_results[kw.word] = brewed

        except Exception as e:
            await manager.broadcast("ERROR", f"❌ [{kw.word}] 오류: {str(e)}")
            keyword_results[kw.word] = []

    async with AsyncSessionLocal() as db:
        for keyword, articles in keyword_results.items():
            for a in articles:
                db.add(Archive(
                    date=brew_date, keyword=keyword,
                    title=a.title, url=a.url, source=a.source,
                    published_at=a.published_at, summary=a.summary,
                    importance_score=a.importance_score,
                ))
        await db.commit()

    await manager.broadcast("INFO", "💾 아카이브 DB 저장 완료")

    if settings.get("google_sheet_id") and settings.get("google_service_account_json"):
        await manager.broadcast("INFO", "📊 Google Sheets 아카이빙 중...")
        try:
            await archive_to_sheets(
                settings["google_service_account_json"],
                settings["google_sheet_id"],
                brew_date,
                keyword_results,
            )
            await manager.broadcast("INFO", "📊 Google Sheets 저장 완료")
        except Exception as e:
            await manager.broadcast("ERROR", f"Google Sheets 오류: {str(e)}")

    await manager.broadcast("INFO", "📧 이메일 발송 중...")
    try:
        await send_brew_email(
            api_key=settings.get("resend_key", ""),
            recipient_emails=settings.get("recipient_emails", ""),
            brew_date=brew_date,
            keyword_results=keyword_results,
        )
        await manager.broadcast("INFO", "✉️ 이메일 발송 완료")
    except Exception as e:
        await manager.broadcast("ERROR", f"이메일 발송 실패: {str(e)}")

    await manager.broadcast("INFO", "🎉 브루잉 완료!")
