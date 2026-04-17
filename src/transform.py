
import sys
import time
from dataclasses import dataclass

import duckdb

from src.config import (
    LOG_FILE,
    DATA_QUALITY_LOG,
    RAW_SCHEMA,
    ANALYTICS_SCHEMA,
    MAX_TRIP_DURATION_HOURS,
    MAX_COST_PER_MILE,
)
from src.db import get_connection
from src.logger import get_logger, get_quality_logger

log    = get_logger(__name__, LOG_FILE)
dq_log = get_quality_logger(DATA_QUALITY_LOG)

RAW_TABLE       = f"{RAW_SCHEMA}.yellow_taxi_raw"
STAGING_VIEW    = "taxi_staging"          # in-memory intermediate
CLEAN_TABLE     = f"{ANALYTICS_SCHEMA}.yellow_taxi_clean"


#  Step registry 

@dataclass
class CleaningStep:
    name: str
    reason: str
    filter_sql: str   # SQL expression that keeps GOOD rows (WHERE clause)


CLEANING_STEPS= [
    CleaningStep(
        name="negative_or_zero_fare",
        reason="Trips with zero or negative fare_amount are invalid transactions",
        filter_sql="fare_amount > 0",
    ),
    CleaningStep(
        name="zero_distance",
        reason="Trips with zero trip_distance cannot have cost_per_mile computed",
        filter_sql="trip_distance > 0",
    ),
    CleaningStep(
        name="zero_passenger_count",
        reason="Trips with zero or NULL passenger_count are likely sensor errors",
        filter_sql="passenger_count >= 1",
    ),
    CleaningStep(
        name="dropoff_before_pickup",
        reason="tpep_dropoff_datetime < tpep_pickup_datetime violates time ordering",
        filter_sql="tpep_dropoff_datetime > tpep_pickup_datetime",
    ),
    CleaningStep(
        name="outlier_long_trips",
        reason=f"Trips longer than {MAX_TRIP_DURATION_HOURS}h are likely GPS/meter errors",
        filter_sql=f"""
            DATEDIFF('minute', tpep_pickup_datetime, tpep_dropoff_datetime)
            <= {MAX_TRIP_DURATION_HOURS * 60}
        """,
    ),
    CleaningStep(
        name="outlier_high_cost_per_mile",
        reason=f"cost_per_mile > ${MAX_COST_PER_MILE} is statistically anomalous",
        filter_sql=f"(total_amount / NULLIF(trip_distance, 0)) <= {MAX_COST_PER_MILE}",
    ),
]


#Transformation logic

def count(conn, from_clause):
    return conn.execute(f"SELECT COUNT(*) FROM {from_clause}").fetchone()[0]


def apply_cleaning_steps(conn):
    """
    Apply each CleaningStep sequentially.

    Builds up a chain of CTEs so DuckDB can optimise the full plan.
    Returns a dict of {step_name: rows_removed}.
    """
    total_raw = count(conn, RAW_TABLE)
    log.info("Raw row count before cleaning: %s", f"{total_raw:,}")
    dq_log.info("=" * 70)
    dq_log.info("[TRANSFORM] Starting cleaning  raw rows: %s", f"{total_raw:,}")
    dq_log.info("=" * 70)

    removal_log  = {}
    current_table = RAW_TABLE   

    cumulative_filter = "TRUE"
    prev_count = total_raw

    for step in CLEANING_STEPS:
        cumulative_filter = f"({cumulative_filter}) AND ({step.filter_sql})"
        current_count = conn.execute(
            f"SELECT COUNT(*) FROM {RAW_TABLE} WHERE {cumulative_filter}"
        ).fetchone()[0]

        removed = prev_count - current_count
        removal_log[step.name] = removed
        pct = (removed / total_raw * 100) if total_raw else 0

        log.info("  [%-30s]  removed %s rows (%.2f%%) – %s",
                 step.name, f"{removed:,}", pct, step.reason)
        dq_log.info(
            "  step=%-30s  removed=%8s  (%.2f%%)  reason=%s",
            step.name, f"{removed:,}", pct, step.reason
        )

        prev_count = current_count

    total_removed = total_raw - prev_count
    log.info("Total rows removed: %s / %s  (%.1f%%)",
             f"{total_removed:,}", f"{total_raw:,}", total_removed / total_raw * 100)
    dq_log.info("-" * 70)
    dq_log.info("[TRANSFORM] Total removed: %s  →  clean rows: %s",
                f"{total_removed:,}", f"{prev_count:,}")
    dq_log.info("=" * 70)

    return removal_log, cumulative_filter, prev_count


def build_clean_table(conn, final_filter):
    """
    Write the cleaned + enriched dataset to analytics.yellow_taxi_clean.

    Derived columns added:
      • trip_duration_minutes  integer minutes from pickup → dropoff
      • cost_per_mile         = total_amount / trip_distance
    """
    log.info("Building analytics clean table…")

    conn.execute(f"DROP TABLE IF EXISTS {CLEAN_TABLE}")
    conn.execute(f"""
        CREATE TABLE {CLEAN_TABLE} AS
        SELECT
            -- original columns
            VendorID,
            tpep_pickup_datetime,
            tpep_dropoff_datetime,
            passenger_count,
            trip_distance,
            RatecodeID,
            store_and_fwd_flag,
            PULocationID,
            DOLocationID,
            payment_type,
            fare_amount,
            extra,
            mta_tax,
            tip_amount,
            tolls_amount,
            improvement_surcharge,
            total_amount,
            congestion_surcharge,
            airport_fee,
            source_month,

            -- derived columns
            DATEDIFF('minute', tpep_pickup_datetime, tpep_dropoff_datetime)
                AS trip_duration_minutes,

            ROUND(total_amount / NULLIF(trip_distance, 0), 4)
                AS cost_per_mile,

            -- date parts for easy aggregation
            tpep_pickup_datetime::DATE                  AS pickup_date,
            EXTRACT(hour FROM tpep_pickup_datetime)::INT AS pickup_hour

        FROM {RAW_TABLE}
        WHERE {final_filter}
    """)

    clean_count = count(conn, CLEAN_TABLE)
    log.info("Clean table built: %s rows in %s", f"{clean_count:,}", CLEAN_TABLE)
    
    
#Orchestration

def run_transformation():
    log.info("=" * 60)
    log.info("STAGE 2  Transformation starting")
    log.info("=" * 60)

    t0   = time.perf_counter()
    conn = get_connection()

    removal_log, final_filter, clean_rows = apply_cleaning_steps(conn)
    build_clean_table(conn, final_filter)

    elapsed = time.perf_counter() - t0
    log.info("Transformation complete in %.1f s", elapsed)
    return removal_log

# Entry point 
if __name__ == "__main__":
    try:
        run_transformation()
    except Exception as exc:
        log.critical("Transformation failed: %s", exc, exc_info=True)
        sys.exit(1)
        
        
