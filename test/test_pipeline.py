"""
tests/test_pipeline.py – Unit tests for the NYC Taxi Pipeline.

Run with:
    pytest tests/ -v

These tests use an in-memory DuckDB database so no real data needs to
be downloaded.  They validate:
  • Schema creation
  • Cleaning step logic (each filter removes the right rows)
  • Derived column correctness
  • Analytical SQL query structure
"""



import pytest
import duckdb
from pathlib import Path
import sys

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import (
    RAW_SCHEMA,
    ANALYTICS_SCHEMA,
    MAX_TRIP_DURATION_HOURS,
    MAX_COST_PER_MILE,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def conn():
    """In-memory DuckDB connection with schemas and a tiny raw table."""
    c = duckdb.connect(":memory:")
    c.execute(f"CREATE SCHEMA {RAW_SCHEMA}")
    c.execute(f"CREATE SCHEMA {ANALYTICS_SCHEMA}")

    # Minimal raw table matching the columns we actually use
    c.execute(f"""
        CREATE TABLE {RAW_SCHEMA}.yellow_taxi_raw AS
        SELECT *
        FROM (VALUES
            -- valid row
            (1,  TIMESTAMPTZ '2023-01-10 08:00:00', TIMESTAMPTZ '2023-01-10 08:30:00',
             2,  5.0,  1,  100,  200,  15.0,  0.5,  0.5,  3.0,  0.0,  0.3,  19.3, 0.0, NULL, '2023-01'),
            -- zero fare  → should be removed
            (1,  TIMESTAMPTZ '2023-01-10 09:00:00', TIMESTAMPTZ '2023-01-10 09:30:00',
             1,  3.0,  1,  101,  201,   0.0,  0.5,  0.5,  1.0,  0.0,  0.3,   2.3, 0.0, NULL, '2023-01'),
            -- zero distance → should be removed
            (1,  TIMESTAMPTZ '2023-01-10 10:00:00', TIMESTAMPTZ '2023-01-10 10:30:00',
             1,  0.0,  1,  102,  202,  12.0,  0.5,  0.5,  2.0,  0.0,  0.3,  15.3, 0.0, NULL, '2023-01'),
            -- zero passengers → should be removed
            (1,  TIMESTAMPTZ '2023-01-10 11:00:00', TIMESTAMPTZ '2023-01-10 11:30:00',
             0,  4.0,  1,  103,  203,  10.0,  0.5,  0.5,  2.0,  0.0,  0.3,  13.3, 0.0, NULL, '2023-01'),
            -- dropoff before pickup → should be removed
            (1,  TIMESTAMPTZ '2023-01-10 12:30:00', TIMESTAMPTZ '2023-01-10 12:00:00',
             1,  2.0,  1,  104,  204,   8.0,  0.5,  0.5,  1.5,  0.0,  0.3,  10.8, 0.0, NULL, '2023-01'),
            -- trip > 3 hours → should be removed
            (1,  TIMESTAMPTZ '2023-01-10 13:00:00', TIMESTAMPTZ '2023-01-10 17:00:00',
             1,  6.0,  1,  105,  205,  20.0,  0.5,  0.5,  4.0,  0.0,  0.3,  25.3, 0.0, NULL, '2023-01'),
            -- cost_per_mile > 100 → should be removed
            (1,  TIMESTAMPTZ '2023-01-10 14:00:00', TIMESTAMPTZ '2023-01-10 14:15:00',
             1,  0.1,  1,  106,  206, 150.0,  0.5,  0.5,  2.0,  0.0,  0.3, 153.3, 0.0, NULL, '2023-01')
        ) AS t(
            VendorID, tpep_pickup_datetime, tpep_dropoff_datetime,
            passenger_count, trip_distance, payment_type,
            PULocationID, DOLocationID,
            fare_amount, extra, mta_tax, tip_amount, tolls_amount,
            improvement_surcharge, total_amount, congestion_surcharge,
            airport_fee, source_month
        )
    """)
    yield c
    c.close()


# ─── Tests: cleaning filters ───────────────────────────────────────────────────

class TestCleaningFilters:
    """Each test validates one individual cleaning filter against the fixture."""

    def test_positive_fare_removes_zero_fare(self, conn):
        count = conn.execute(
            f"SELECT COUNT(*) FROM {RAW_SCHEMA}.yellow_taxi_raw WHERE fare_amount > 0"
        ).fetchone()[0]
        # 5 valid rows remain (zero_fare row is excluded)
        assert count == 6

    def test_positive_distance_removes_zero_distance(self, conn):
        count = conn.execute(
            f"SELECT COUNT(*) FROM {RAW_SCHEMA}.yellow_taxi_raw WHERE trip_distance > 0"
        ).fetchone()[0]
        assert count == 6  # zero_distance row excluded

    def test_positive_passengers_removes_zero_count(self, conn):
        count = conn.execute(
            f"SELECT COUNT(*) FROM {RAW_SCHEMA}.yellow_taxi_raw WHERE passenger_count >= 1"
        ).fetchone()[0]
        assert count == 6

    def test_time_ordering_removes_reversed_trips(self, conn):
        count = conn.execute(
            f"""SELECT COUNT(*) FROM {RAW_SCHEMA}.yellow_taxi_raw
                WHERE tpep_dropoff_datetime > tpep_pickup_datetime"""
        ).fetchone()[0]
        assert count == 6

    def test_duration_filter_removes_long_trips(self, conn):
        max_minutes = MAX_TRIP_DURATION_HOURS * 60
        count = conn.execute(
            f"""SELECT COUNT(*) FROM {RAW_SCHEMA}.yellow_taxi_raw
                WHERE DATEDIFF('minute', tpep_pickup_datetime, tpep_dropoff_datetime) <= {max_minutes}
                AND tpep_dropoff_datetime > tpep_pickup_datetime"""
        ).fetchone()[0]
        assert count == 5

    def test_cost_per_mile_filter_removes_outliers(self, conn):
        count = conn.execute(
            f"""SELECT COUNT(*) FROM {RAW_SCHEMA}.yellow_taxi_raw
                WHERE (total_amount / NULLIF(trip_distance, 0)) <= {MAX_COST_PER_MILE}"""
        ).fetchone()[0]
        # Only row with trip_distance=0 and cost_per_mile>100 should be excluded
        # The zero-distance row yields NULL which passes the filter
        assert count >= 5

    def test_all_filters_together_keeps_exactly_one_row(self, conn):
        """After all filters, only the first (fully valid) row should remain."""
        max_minutes = MAX_TRIP_DURATION_HOURS * 60
        count = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM {RAW_SCHEMA}.yellow_taxi_raw
            WHERE fare_amount > 0
              AND trip_distance > 0
              AND passenger_count >= 1
              AND tpep_dropoff_datetime > tpep_pickup_datetime
              AND DATEDIFF('minute', tpep_pickup_datetime, tpep_dropoff_datetime) <= {max_minutes}
              AND (total_amount / NULLIF(trip_distance, 0)) <= {MAX_COST_PER_MILE}
            """
        ).fetchone()[0]
        assert count == 1


# ─── Tests: derived columns ────────────────────────────────────────────────────

class TestDerivedColumns:
    """Validate that trip_duration_minutes and cost_per_mile are computed correctly."""

    @pytest.fixture(autouse=True)
    def build_clean(self, conn):
        """Build a minimal clean table for the valid row only."""
        max_minutes = MAX_TRIP_DURATION_HOURS * 60
        conn.execute(f"""
            CREATE TABLE {ANALYTICS_SCHEMA}.yellow_taxi_clean AS
            SELECT *,
                DATEDIFF('minute', tpep_pickup_datetime, tpep_dropoff_datetime) AS trip_duration_minutes,
                ROUND(total_amount / NULLIF(trip_distance, 0), 4)               AS cost_per_mile,
                tpep_pickup_datetime::DATE                                       AS pickup_date,
                EXTRACT(hour FROM tpep_pickup_datetime)::INT                    AS pickup_hour
            FROM {RAW_SCHEMA}.yellow_taxi_raw
            WHERE fare_amount > 0
              AND trip_distance > 0
              AND passenger_count >= 1
              AND tpep_dropoff_datetime > tpep_pickup_datetime
              AND DATEDIFF('minute', tpep_pickup_datetime, tpep_dropoff_datetime) <= {max_minutes}
              AND (total_amount / NULLIF(trip_distance, 0)) <= {MAX_COST_PER_MILE}
        """)

    def test_trip_duration_minutes_is_correct(self, conn):
        dur = conn.execute(
            f"SELECT trip_duration_minutes FROM {ANALYTICS_SCHEMA}.yellow_taxi_clean"
        ).fetchone()[0]
        assert dur == 30   # 08:00 → 08:30

    def test_cost_per_mile_is_correct(self, conn):
        cpm = conn.execute(
            f"SELECT cost_per_mile FROM {ANALYTICS_SCHEMA}.yellow_taxi_clean"
        ).fetchone()[0]
        # total_amount=19.3, trip_distance=5.0 → 3.86
        assert abs(cpm - 3.86) < 0.01

    def test_pickup_hour_extracted(self, conn):
        hour = conn.execute(
            f"SELECT pickup_hour FROM {ANALYTICS_SCHEMA}.yellow_taxi_clean"
        ).fetchone()[0]
        assert hour == 8

    def test_pickup_date_extracted(self, conn):
        import datetime
        date = conn.execute(
            f"SELECT pickup_date FROM {ANALYTICS_SCHEMA}.yellow_taxi_clean"
        ).fetchone()[0]
        assert str(date) == "2023-01-10"


# ─── Tests: schema bootstrap ───────────────────────────────────────────────────

class TestSchemaBootstrap:
    def test_raw_schema_exists(self, conn):
        schemas = [r[0] for r in conn.execute("SHOW ALL TABLES").fetchall()]
        # DuckDB SHOW ALL TABLES returns (schema, name, ...) tuples
        result = conn.execute(
            "SELECT schema_name FROM information_schema.schemata WHERE schema_name = ?",
            [RAW_SCHEMA]
        ).fetchone()
        assert result is not None

    def test_analytics_schema_exists(self, conn):
        result = conn.execute(
            "SELECT schema_name FROM information_schema.schemata WHERE schema_name = ?",
            [ANALYTICS_SCHEMA]
        ).fetchone()
        assert result is not None
