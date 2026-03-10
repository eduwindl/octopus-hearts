from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from backend.backup_engine import run_backup_for_all
from backend.config import settings
from database.db import SessionLocal


def scheduled_job():
    db = SessionLocal()
    try:
        run_backup_for_all(db)
    finally:
        db.close()


def main():
    scheduler = BlockingScheduler(timezone=settings.scheduler_timezone)
    scheduler.add_job(scheduled_job, CronTrigger(hour=18, minute=0))
    scheduler.start()


if __name__ == "__main__":
    main()
