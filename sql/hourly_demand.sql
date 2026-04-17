-- sql/hourly_demand.sql
-- Part C – Query 2: Hourly Demand Pattern
--
-- For each hour of the day (0-23):
--    avg_daily_trip_count  
--    avg_fare_amount       



WITH trips_per_hour_per_day AS (
    SELECT
        pickup_hour,
        pickup_date,
        COUNT(*) AS daily_trips,
        AVG(fare_amount) AS avg_fare
    FROM analytics.yellow_taxi_clean
    GROUP BY pickup_hour, pickup_date
)
SELECT
    pickup_hour          AS hour_of_day,
    ROUND(AVG(daily_trips),   2)     AS avg_trip_count_per_day,
    ROUND(AVG(avg_fare),      2)     AS avg_fare_amount
FROM trips_per_hour_per_day
GROUP BY pickup_hour  
ORDER BY pickup_hour;
