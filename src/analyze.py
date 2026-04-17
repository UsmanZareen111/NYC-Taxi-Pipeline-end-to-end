"""
analyze.py Part C: Analytical Output.

Runs each SQL file from the sql/ directory against the analytics schema
and exports the results to CSV files under output/.
"""


import sys
import time
from pathlib import Path

from src.config import LOG_FILE, OUTPUT_DIR
from src.db import get_connection
from src.logger import get_logger

log = get_logger(__name__, LOG_FILE)

# Map: output CSV name → SQL file (relative to project root)
SQL_DIR = Path(__file__).resolve().parent.parent / "sql"

QUERIES = [
    ("daily_summary",           SQL_DIR / "daily_summary.sql"),
    ("hourly_demand",           SQL_DIR / "hourly_demand.sql"),
    ("pickup_location_ranking", SQL_DIR / "pickup_location_ranking.sql"),
    ("payment_type_breakdown",  SQL_DIR / "payment_type_breakdown.sql"),
]


def run_query_to_csv(name, sql_path):
    """
    Execute the SQL in *sql_path* and write results to output/<name>.csv.

    Returns the path of the written CSV.
    """
    if not sql_path.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_path}")

    sql = sql_path.read_text(encoding="utf-8")
    conn = get_connection()

    log.info("Running query: %s", name)
    t0 = time.perf_counter()

    rel = conn.execute(sql)
    df  = rel.df()

    elapsed = time.perf_counter() - t0
    log.info("  → %s rows returned in %.2f s", f"{len(df):,}", elapsed)

    # Export to CSV
    out_path = OUTPUT_DIR / f"{name}.csv"
    df.to_csv(out_path, index=False)
    log.info("  → Saved to %s", out_path)

    return out_path


def run_analysis() :
    """Run all analytical queries and return a list of output CSV paths."""
    log.info("=" * 60)
    log.info("STAGE 3 – Analysis starting")
    log.info("=" * 60)

    t0      = time.perf_counter()
    outputs = []

    for name, sql_path in QUERIES:
        try:
            path = run_query_to_csv(name, sql_path)
            outputs.append(path)
        except Exception as exc:
            log.error("Query '%s' failed: %s", name, exc, exc_info=True)
            raise

    elapsed = time.perf_counter() - t0
    log.info("-" * 60)
    log.info("Analysis complete in %.1f s – %d CSVs written", elapsed, len(outputs))
    for p in outputs:
        log.info("  %s", p)
    log.info("-" * 60)

    return outputs


if __name__ == "__main__":
    try:
        run_analysis()
    except Exception as exc:
        log.critical("Analysis failed: %s", exc, exc_info=True)
        sys.exit(1)
