-- sql/pickup_location_ranking.sql
-- Part C – Query 3: Top 10 Pick-up Locations


SELECT
    PULocationID        AS pickup_location_id,
    COUNT(*)                  AS total_trips,
    ROUND(AVG(fare_amount),2)    AS avg_fare_amount
FROM analytics.yellow_taxi_clean
GROUP BY PULocationID
ORDER BY total_trips DESC
LIMIT 20;
