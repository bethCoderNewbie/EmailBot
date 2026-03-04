"""
EmailBot — main entry point.

Runs a scheduler that fires on SCHEDULE_DAYS at SCHEDULE_TIME.
Also supports --now flag to trigger immediately (useful for testing).
"""
import argparse
import logging
import sys
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

import config
import state
from gmail_client import fetch_emails, mark_as_read
from newsletter import build_and_send
from summarizer import summarize_emails

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def run_digest() -> None:
    """Core pipeline: fetch → summarise → send → persist state."""
    now_epoch    = int(datetime.now(timezone.utc).timestamp())
    last_epoch   = state.get_last_run_epoch()
    already_seen = state.get_processed_ids()

    log.info("Fetching emails (since epoch=%s) …", last_epoch)
    emails = fetch_emails(since_epoch=last_epoch)

    # De-duplicate against already-processed IDs
    emails = [e for e in emails if e["id"] not in already_seen]

    if not emails:
        log.info("No new emails. Skipping newsletter.")
        state.save_run(now_epoch, [])
        return

    log.info("Found %d new email(s). Summarising …", len(emails))
    summary_md = summarize_emails(emails)

    period_start = (
        datetime.fromtimestamp(last_epoch).strftime("%b %d, %Y")
        if last_epoch
        else "the beginning"
    )
    period_end = datetime.now().strftime("%b %d, %Y")

    log.info("Sending newsletter …")
    build_and_send(emails, summary_md, period_start, period_end)

    # Mark processed emails as read in Gmail
    mark_as_read([e["id"] for e in emails])

    state.save_run(now_epoch, [e["id"] for e in emails])
    log.info("Done. %d email(s) processed.", len(emails))


def main() -> None:
    parser = argparse.ArgumentParser(description="EmailBot digest scheduler")
    parser.add_argument(
        "--now", action="store_true",
        help="Run the digest immediately instead of waiting for schedule",
    )
    args = parser.parse_args()

    if args.now:
        log.info("Running digest immediately (--now flag).")
        run_digest()
        return

    # Build cron expression from config
    # SCHEDULE_DAYS: list of weekday ints (0=Mon … 6=Sun)
    days_of_week = ",".join(str(d) for d in config.SCHEDULE_DAYS)
    hour, minute = config.SCHEDULE_TIME.split(":")

    trigger = CronTrigger(
        day_of_week=days_of_week,
        hour=int(hour),
        minute=int(minute),
    )

    scheduler = BlockingScheduler()
    scheduler.add_job(run_digest, trigger, name="email_digest")

    log.info(
        "Scheduler started. Digest will run on days=%s at %s.",
        days_of_week, config.SCHEDULE_TIME,
    )
    log.info("Press Ctrl+C to stop.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
