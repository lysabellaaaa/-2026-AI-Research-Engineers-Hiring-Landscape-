"""APScheduler-based daily pipeline runner.

Runs the full data pipeline every day at 07:00 local time.
Keeps running until interrupted with Ctrl+C.

Usage:
    python scheduler.py
    python scheduler.py --run-now   # trigger immediately then schedule
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("scheduler")


def pipeline_job():
    """The daily pipeline job — called by APScheduler."""
    log.info("=" * 60)
    log.info(f"Starting daily pipeline: {datetime.now().isoformat()}")
    log.info("=" * 60)
    try:
        from run_once import run_pipeline
        run_pipeline(source_filter=None, generate_report=True)
        log.info("Pipeline completed successfully.")
    except Exception as e:
        log.error(f"Pipeline failed: {e}", exc_info=True)


def main():
    parser = argparse.ArgumentParser(description="Agents Hiring Tracker — Daily Scheduler")
    parser.add_argument("--run-now", action="store_true",
                        help="Run the pipeline immediately, then start scheduler")
    parser.add_argument("--hour", type=int, default=7,
                        help="Hour to run daily (24h, local time). Default: 7")
    parser.add_argument("--minute", type=int, default=0,
                        help="Minute to run daily. Default: 0")
    args = parser.parse_args()

    if args.run_now:
        log.info("--run-now flag set: running pipeline immediately...")
        pipeline_job()

    scheduler = BlockingScheduler(timezone="America/Los_Angeles")
    scheduler.add_job(
        pipeline_job,
        trigger=CronTrigger(hour=args.hour, minute=args.minute),
        id="daily_pipeline",
        name="Agents Hiring Tracker — Daily Pipeline",
        misfire_grace_time=3600,  # 1 hour grace if system was asleep
        coalesce=True,            # Only run once even if missed multiple times
    )

    next_run = scheduler.get_jobs()[0].next_run_time
    log.info(f"Scheduler started. Daily pipeline at {args.hour:02d}:{args.minute:02d} PT")
    log.info(f"Next run: {next_run}")
    log.info("Press Ctrl+C to stop.\n")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
