from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler(timezone="Asia/Seoul")

def setup_scheduler(schedule_time: str = "08:00"):
    from services.brew_orchestrator import run_brew_pipeline
    scheduler.remove_all_jobs()
    hour, minute = schedule_time.split(":")
    scheduler.add_job(
        run_brew_pipeline,
        trigger=CronTrigger(hour=int(hour), minute=int(minute)),
        id="daily_brew",
        replace_existing=True,
    )

def start_scheduler():
    if not scheduler.running:
        scheduler.start()

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
