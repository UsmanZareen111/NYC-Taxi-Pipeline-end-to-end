"""
ingest.py  Part A: Data Ingestion & Storage.

Downloads Yellow Taxi Parquet files from the NYC TLC CDN and loads
them into DuckDB's raw schema without any modifications.

Usage (standalone):
    python -m src.ingest
"""


import sys
import time
from pathlib import Path

import requests

from src.config import (
    DATA_DIR,
    LOG_FILE,
    DATA_QUALITY_LOG,
    RAW_SCHEMA,
    TARGET_MONTHS,
    parquet_filename,
    parquet_url,
)
from src.db import get_connection
from src.logger import get_logger, get_quality_logger

log     = get_logger(__name__, LOG_FILE)
dq_log  = get_quality_logger(DATA_QUALITY_LOG)

# DuckDB table that holds all ingested months (unioned)
RAW_TABLE = f"{RAW_SCHEMA}.yellow_taxi_raw"

#  Download 

def download_file(url, dest, chunk_size = 1000 * 10000):
    """
    Stream-download *url* to *dest*.

    Skips the download if the file already exists (idempotent).
    
    """
    if dest.exists():
        log.info("File already exists, skipping download: %s", dest.name)
        return dest

    log.info("Downloading %s → %s", url, dest)
    try:
        resp = requests.get(url, stream=True, timeout=120)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.error("Download failed for %s: %s", url, exc)
        raise

    total = int(resp.headers.get("content-length", 0))
    dest.parent.mkdir(parents=True, exist_ok=True)

    with open(dest, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=chunk_size):
            fh.write(chunk)
           

    log.info("Download complete: %s (%.1f MB)", dest.name, dest.stat().st_size / 1e6)
    return dest


# Load into DuckDB 

def load_parquet_to_raw(parquet_path, month_label) :
    """
    Read *parquet_path* and INSERT its rows into the raw table.

    The table is created (with the Parquet schema) on first call and
    appended on subsequent calls, making the function safe to re-run.

    Returns the number of rows inserted.
    """
    conn = get_connection()

    # Read row count before insert so we know exactly how many we added
    before = _row_count(conn, RAW_TABLE)

    # DuckDB can read Parquet directly – no Pandas round-trip needed
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {RAW_TABLE} AS
        SELECT *, '{month_label}' AS source_month
        FROM read_parquet('{parquet_path}')
        WHERE FALSE                         -- DDL only, no rows yet
    """)

    # Append rows for this month (skip if already loaded – idempotent)
    already_loaded = conn.execute(
        f"SELECT COUNT(*) FROM {RAW_TABLE} WHERE source_month = ?", [month_label]
    ).fetchone()[0]

    if already_loaded > 0:
        log.info(
            "Month %s already loaded (%s rows), skipping insert.",
            month_label, f"{already_loaded:,}"
        )
        return already_loaded

    conn.execute(f"""
        INSERT INTO {RAW_TABLE}
        SELECT *, '{month_label}' AS source_month
        FROM read_parquet('{parquet_path}')
    """)

    after = _row_count(conn, RAW_TABLE)
    rows_added = after - before
    log.info("Loaded %s rows for month %s.", f"{rows_added:,}", month_label)
    dq_log.info("[INGEST] month=%-7s  rows_loaded=%s", month_label, f"{rows_added:,}")
    return rows_added

def _row_count(conn, table):
    """Return 0 if *table* doesn't exist yet, else its row count."""
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except Exception:
        return 0


#  Orchestration 
def run_ingestion():
    """
    Download and ingest all configured months.

    Returns a dict  {month_label: rows_ingested}.
    """
    log.info("=" * 60)
    log.info("STAGE 1 – Ingestion starting")
    log.info("=" * 60)

    t0 = time.perf_counter()
    results = {}

    for spec in TARGET_MONTHS:
        year, month, label = spec["year"], spec["month"], spec["label"]
        filename = parquet_filename(year, month)
        url      = parquet_url(year, month)
        dest     = DATA_DIR / filename

        # 1. Download
        download_file(url, dest)

        # 2. Load into DuckDB
        rows = load_parquet_to_raw(dest, label)
        results[label] = rows

    elapsed = time.perf_counter() - t0
    total_rows = sum(results.values())

    log.info("-" * 60)
    log.info("Ingestion complete in %.1f s | total rows: %s", elapsed, f"{total_rows:,}")
    for label, rows in results.items():
        log.info("  %-10s  %s rows", label, f"{rows:,}")
    log.info("-" * 60)
    return results


# Entry point 
if __name__ == "__main__":
    try:
        run_ingestion()
    except Exception as exc:
        log.critical("Ingestion failed: %s", exc, exc_info=True)
        sys.exit(1)


