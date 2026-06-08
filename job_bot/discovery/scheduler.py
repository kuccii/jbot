from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()


def start_scheduler(orchestrator, interval_hours: int = 24):
    scheduler.add_job(orchestrator.run_all, "interval", hours=interval_hours)
    scheduler.start()
