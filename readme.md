# NYC Taxi Analytics Pipeline

A production-grade end-to-end data pipeline that ingests, cleans, and analyses
New York City Yellow Taxi trip records using **DuckDB**, **Python**, and **SQL**.

---

## Project Structure

```
nyc_taxi_pipeline/
├── src/
│   ├── config.py        # All constants and paths – edit here, nowhere else
│   ├── db.py            # DuckDB connection factory
│   ├── logger.py        # Coloured console + file logging
│   ├── ingest.py        # Part A – download & load raw Parquet files
│   ├── transform.py     # Part B – cleaning & derived columns
│   └── analyze.py       # Part C – run SQL queries, export CSVs
├── sql/
│   ├── daily_summary.sql
│   ├── hourly_demand.sql
│   ├── pickup_location_ranking.sql
│   └── payment_type_breakdown.sql
├── tests/
│   └── test_pipeline.py # pytest unit tests (no download required)
├── output/              # CSV files written here after pipeline runs
├── logs/
│   ├── pipeline.log     # Full debug log of every run
│   ├── data_quality.log # Row-level cleaning audit trail
│   └── pipeline_runs.log# One-line per run history
├── data/raw/            # Downloaded Parquet files cached here
├── run_pipeline.py      # Part D – single-command orchestrator
└── requirements.txt
```

---

## Quick Start

### 1. Clone & install dependencies

```bash
git clone <your-repo-url>
cd NYC-Taxi-Pipeline-end-to-end

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Run the full pipeline (one command)

```bash
python run_pipeline.py
```

This will:
1. **Download** Yellow Taxi Parquet files for January and February 2023 (~500 MB total) from the NYC TLC CDN.
2. **Load** raw data into `taxi.duckdb` under the `raw` schema.
3. **Clean** the data and write to the `analytics` schema.
4. **Export** four CSV summary files to `output/`.

> **Note:** The download step is skipped on re-runs if the files already exist locally. The pipeline is fully idempotent.

### 3. Run with daily scheduling

```bash
python run_pipeline.py --schedule           # daily at 02:00 AM
python run_pipeline.py --schedule --at 06:30  # daily at 06:30 AM
```

The process stays alive, logs every run to `logs/pipeline_runs.log`, and re-executes at the configured time.

### 4. Run individual stages

```bash
python -m src.ingest      # Stage 1 only
python -m src.transform   # Stage 2 only
python -m src.analyze     # Stage 3 only
```

### 5. Run tests (no internet required)

```bash
pytest test/ -v
```

---

## Output Files

| File | Description |
|---|---|
| `output/daily_summary.csv` | Date, total trips, avg fare, avg duration, avg distance |
| `output/hourly_demand.csv` | Hour of day (0–23), avg trip count per day, avg fare |
| `output/pickup_location_ranking.csv` | Top 10 pickup zones by volume, avg fare, avg tip % |
| `output/payment_type_breakdown.csv` | Trip count and avg fare by payment method |

---

## Cleaning Steps & Data Quality

All cleaning decisions are logged to `logs/data_quality.log`.

| Step | Filter | Reason |
|---|---|---|
| `negative_or_zero_fare` | `fare_amount > 0` | Invalid transactions; no economic signal |
| `zero_distance` | `trip_distance > 0` | Cost-per-mile cannot be computed |
| `zero_passenger_count` | `passenger_count >= 1` | Meter/sensor error |
| `dropoff_before_pickup` | `dropoff > pickup` | Violates time ordering |
| `outlier_long_trips` | `duration <= 180 min` | GPS or meter malfunction |
| `outlier_high_cost_per_mile` | `cost_per_mile <= $100` | Statistical anomaly |

Derived columns added to the analytics table:

- **`trip_duration_minutes`** – `DATEDIFF('minute', pickup, dropoff)`
- **`cost_per_mile`** – `total_amount / trip_distance`, rounded to 4 dp
- **`pickup_date`** – date portion of `tpep_pickup_datetime`
- **`pickup_hour`** – integer hour (0–23)

---

## Design Decisions & Trade-offs

### Why DuckDB?
DuckDB can read Parquet files natively (`FROM read_parquet(...)`) with zero copying
and runs fully in-process.  For ~500 MB of compressed Parquet it is faster and
simpler than Spark, Postgres, or SQLite.

### Why not Pandas for transformations?
SQL transformations in DuckDB are more readable, easier to audit, and DuckDB's
vectorised engine outperforms Pandas for column-scan aggregations.  Pandas is
only used to write the final CSV files because `df.to_csv()` is convenient.

### Idempotency
Every stage checks whether work has already been done before repeating it:
- Downloads skip if the `.parquet` file exists.
- Ingestion checks `WHERE source_month = ?` before inserting.
- `build_clean_table` does `DROP TABLE IF EXISTS` then rebuilds – fast and correct.

### Tip percentage calculation
Only credit card payments (`payment_type = 1`) are used for average tip percentage.
Cash tips are not captured in the TLC dataset, so including them would bias the
average toward zero.

### Outlier thresholds
The 3-hour / $100-per-mile thresholds are informed by the
[TLC data dictionary](https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf)
and domain knowledge.  They can be adjusted in `src/config.py` without touching
any other file.

---

## AI Assistance Disclosure

Parts of the boilerplate for the logging module and the tqdm download wrapper
were drafted with AI assistance.  All business logic (cleaning rules, SQL
queries, schema design) was written and verified by the author.  Every line of
code is understood and can be explained on request.

---

## Environment

| Requirement | Version |
|---|---|
| Python | ≥ 3.11 |
| DuckDB | 0.10.3 |
| OS | macOS / Linux / Windows (WSL recommended) |
| Disk space | ~2 GB for raw Parquet + DuckDB file |
