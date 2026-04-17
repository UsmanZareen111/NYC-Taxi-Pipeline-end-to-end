"""
config.py  Central configuration for the NYC Taxi Pipeline.
"""

import os
from pathlib import Path

#  Paths ─
BASE_DIR    = Path(__file__).resolve().parent.parent
DATA_DIR    = BASE_DIR / "data" / "raw"
OUTPUT_DIR  = BASE_DIR / "output"
LOG_DIR     = BASE_DIR / "logs"
DB_PATH     = BASE_DIR / "taxi.duckdb"

# Ensure directories exist at import time
for _d in (DATA_DIR, OUTPUT_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

#  Source data 
# Two consecutive months of Yellow Taxi 2023 data
TLC_BASE_URL = (
    "https://d37ci6vzurychx.cloudfront.net/trip-data"
)
TARGET_MONTHS = [
    {"year": 2023, "month": 1, "label": "2023-01"},
    {"year": 2023, "month": 2, "label": "2023-02"},
]

def parquet_filename(year: int, month: int) -> str:
    return f"yellow_tripdata_{year}-{month:02d}.parquet"

def parquet_url(year: int, month: int) -> str:
    return f"{TLC_BASE_URL}/{parquet_filename(year, month)}"

# DuckDB schema 
RAW_SCHEMA       = "raw"
ANALYTICS_SCHEMA = "analytics"

#  Cleaning thresholds 
MAX_TRIP_DURATION_HOURS = 3        # trips longer than this are outliers
MAX_COST_PER_MILE       = 100.0    # $/mile above this is suspect
MIN_FARE_AMOUNT         = 0.0      # must be strictly positive
MIN_TRIP_DISTANCE       = 0.0      # must be strictly positive
MIN_PASSENGER_COUNT     = 1        # must have at least one passenger

#  Output CSV filenames 
CSV_DAILY_SUMMARY      = OUTPUT_DIR / "daily_summary.csv"
CSV_HOURLY_DEMAND      = OUTPUT_DIR / "hourly_demand.csv"
CSV_PICKUP_RANKING     = OUTPUT_DIR / "pickup_location_ranking.csv"
CSV_PAYMENT_BREAKDOWN  = OUTPUT_DIR / "payment_type_breakdown.csv"

#  Logging
LOG_FILE          = LOG_DIR / "pipeline.log"
DATA_QUALITY_LOG  = LOG_DIR / "data_quality.log"
LOG_LEVEL         = os.getenv("LOG_LEVEL", "INFO")
