-- sql/payment_type_breakdown.sql
-- Part C – Query 4: Payment Type Breakdown
--
-- Payment type codes (from NYC TLC data dictionary):
--   1 = Credit card
--   2 = Cash
--   3 = No charge
--   4 = Dispute



WITH payment_labels AS (
    SELECT *
    FROM (VALUES
        (1, 'Credit Card'),
        (2, 'Cash'),
        (3, 'No Charge'),
        (4, 'Dispute'),
        (5, 'Unknown')
    ) AS t(payment_type_id, payment_label)
)
SELECT
    t.payment_type           AS payment_type_code,
    COALESCE(pl.payment_label, 'Other')     AS payment_type_label,
    COUNT(*)                      AS total_trips,
    ROUND(AVG(t.fare_amount), 2)       AS avg_fare_amount,
    ROUND(AVG(t.total_amount), 2)  AS avg_total_amount
FROM analytics.yellow_taxi_clean        AS t
LEFT JOIN payment_labels                AS pl
    ON t.payment_type = pl.payment_type_id
GROUP BY t.payment_type, pl.payment_label
ORDER BY total_trips DESC;