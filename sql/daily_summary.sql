-- sql/daily_summary.sql
-- Part C – Query 1: Daily Summary
--
-- Aggregates per calendar day:
--   • total trip count
--   • average fare amount
--   • average trip duration (minutes)
--   • average trip distance (miles)


SELECT
    pickup_date          AS date,
    COUNT(*)         AS total_trips,
    ROUND(AVG(fare_amount),          2)    AS avg_fare_amount,
    ROUND(AVG(trip_duration_minutes), 2)   AS avg_trip_duration_minutes,
    ROUND(AVG(trip_distance),         2)    AS avg_trip_distance_miles
FROM analytics.yellow_taxi_clean
GROUP BY pickup_date
ORDER BY pickup_date;
