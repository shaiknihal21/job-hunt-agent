import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.database import SessionLocal
from app.services.auto_agent import format_auto_summary, run_daily_auto_apply

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def scheduled_auto_apply():
    db = SessionLocal()
    try:
        summary = run_daily_auto_apply(db)
        logger.info("Auto-apply cycle complete:\n%s", format_auto_summary(summary))
    except Exception:
        logger.exception("Scheduled auto-apply failed")
    finally:
        db.close()


def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(
            scheduled_auto_apply,
            "interval",
            hours=settings.scan_interval_hours,
            id="auto_apply",
            replace_existing=True,
        )
        scheduler.start()
        logger.info(
            "Scheduler started — auto-apply every %sh (score≥%s, ATS≥%s)",
            settings.scan_interval_hours,
            settings.auto_apply_min_score,
            settings.auto_apply_min_ats_score,
        )


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
