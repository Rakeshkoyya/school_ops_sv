"""APScheduler configuration for recurring tasks."""

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.services.recurring_task import RecurringTaskService

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: AsyncIOScheduler | None = None


def get_db_session() -> Session:
    """Get a database session for scheduler jobs."""
    return SessionLocal()


def generate_recurring_tasks_job():
    """
    Job to generate recurring tasks.
    Runs at midnight every day.
    """
    logger.info("Starting recurring task generation job")
    
    db = get_db_session()
    try:
        service = RecurringTaskService(db)
        count = service.generate_tasks_for_date()
        logger.info(f"Generated {count} recurring tasks")
    except Exception as e:
        logger.exception(f"Error generating recurring tasks: {e}")
        db.rollback()
    finally:
        db.close()


def init_scheduler() -> AsyncIOScheduler:
    """Initialize and configure the scheduler."""
    global scheduler
    
    scheduler = AsyncIOScheduler(
        timezone="Asia/Kolkata",  # IST timezone
        job_defaults={
            "coalesce": True,  # Combine missed runs
            "max_instances": 1,  # Only one instance of each job at a time
            "misfire_grace_time": 3600,  # Allow 1 hour grace period for missed jobs
        }
    )
    
    # Add recurring task generation job - runs at 00:05 IST daily
    scheduler.add_job(
        generate_recurring_tasks_job,
        trigger=CronTrigger(hour=0, minute=5),
        id="generate_recurring_tasks",
        name="Generate recurring tasks",
        replace_existing=True,
    )
    
    logger.info("Scheduler initialized with recurring task generation job (IST timezone)")
    return scheduler


def start_scheduler():
    """Start the scheduler."""
    global scheduler
    if scheduler is None:
        scheduler = init_scheduler()
    
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


def stop_scheduler():
    """Stop the scheduler gracefully."""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped")


def trigger_recurring_task_generation():
    """
    Manually trigger recurring task generation.
    Useful for testing or manual intervention.
    """
    generate_recurring_tasks_job()
