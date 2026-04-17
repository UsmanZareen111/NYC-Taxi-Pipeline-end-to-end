"""
run_pipeline.py – Part D: Orchestration entry point.

Runs the full pipeline (ingest → transform → analyze) with a single command:

    python run_pipeline.py              # one-shot run
    python run_pipeline.py --schedule   # run now, then daily at 02:00

The --schedule flag uses Python's `schedule` library to re-run the pipeline
every 24 hours and appends a summary entry to logs/pipeline_runs.log.
"""
from gettext import install

import argparse
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import schedule

# Make sure src/ is importable when run from project root
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import LOG_DIR, LOG_FILE
from src.db import close_connection, get_connection
from src.ingest import run_ingestion
from src.transform import run_transformation
from src.analyze import run_analysis
from src.logger import get_logger

log = get_logger("pipeline", LOG_FILE)

RUNS_LOG = LOG_DIR / "pipeline_runs.log"


# ─── Pipeline ──────────────────────────────────────────────────────────────────

def run_pipeline():
    """
    Execute all three pipeline stages end-to-end.

    Returns True on success, False on failure.
    Appends a one-line summary to pipeline_runs.log regardless of outcome.
    """
    started_at = datetime.now()
    log.info("")
    log.info(60*"═")
    log.info("||          NYC TAXI PIPELINE   %s          ||", started_at.strftime("%Y-%m-%d %H:%M"))
    log.info(60*"═")

    t0 = time.perf_counter()
    status = "SUCCESS"

    try:
        # Stage 1 – Ingest raw data
        ingest_results = run_ingestion()

        # Stage 2 – Clean & transform
        removal_log = run_transformation()

        # Stage 3 – Analytical outputs (CSV export)
        output_paths = run_analysis()

        elapsed = time.perf_counter() - t0
        log.info("")
        log.info("  Pipeline finished successfully in %.1f s", elapsed)
        log.info("    Outputs:")
        for p in output_paths:
            log.info("      %s", p)

    except Exception as exc:
        elapsed = time.perf_counter() - t0
        status  = f"FAILED – {exc}"
        log.critical("  Pipeline failed after %.1f s: %s", elapsed, exc)
        log.debug(traceback.format_exc())
        _append_run_log(started_at, elapsed, status)
        return False
    finally:
        # Always release the DB connection so scheduled re-runs start fresh
        close_connection()

    _append_run_log(started_at, elapsed, status)
    return True


def _append_run_log(started_at, elapsed, status):
    """Append a single line to the pipeline run history log."""
    RUNS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(RUNS_LOG, "a", encoding="utf-8") as fh:
        fh.write(
            f"{started_at.isoformat(timespec='seconds')}  "
            f"duration={elapsed:7.1f}s  "
            f"status={status}\n"
        )


# ─── Scheduling ─────────────────────────────────────────────────────────────────

def run_scheduled(run_time):
    """
    Run the pipeline immediately, then schedule it to repeat daily.

    *run_time* is a 24-hour HH:MM string (default 02:00).
    """
    log.info("Scheduler started.  Pipeline will re-run daily at %s.", run_time)
    log.info("Press Ctrl-C to stop.\n")

    # Run once immediately
    run_pipeline()

    # Schedule recurring daily run
    schedule.every().day.at(run_time).do(run_pipeline)

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        log.info("Scheduler stopped by user.")


# ─── CLI ───────────────────────────────────────────────────────────────────────

def main() :
    parser = argparse.ArgumentParser(
        description="NYC Taxi Analytics Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_pipeline.py                # one-shot run
  python run_pipeline.py --schedule     # run now + schedule daily at 02:00
  python run_pipeline.py --schedule --at 06:30   # run now + schedule at 06:30
        """,
    )
    parser.add_argument(
        "--schedule", "-s",
        action="store_true",
        help="Keep the process alive and re-run the pipeline daily.",
    )
    parser.add_argument(
        "--at",
        default="02:00",
        metavar="HH:MM",
        help="Time of day (24h) for the scheduled daily run (default: 02:00).",
    )
    args = parser.parse_args()

    if args.schedule:
        run_scheduled(run_time=args.at)
    else:
        success = run_pipeline()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
