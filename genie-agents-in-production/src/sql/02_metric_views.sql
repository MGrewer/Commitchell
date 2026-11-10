-- Metric views the agent reads. Bundles have no metric-view resource, so the
-- definition lives here as SQL and the build_context job applies it.
USE CATALOG IDENTIFIER(:catalog);
USE SCHEMA IDENTIFIER(:schema);

CREATE OR REPLACE VIEW trip_metrics
WITH METRICS
LANGUAGE YAML
COMMENT 'Governed taxi trip metrics: trips, revenue, average fare, distance.'
AS $$
version: 1.1
source: trips
dimensions:
  - name: pickup_date
    expr: DATE(tpep_pickup_datetime)
    comment: Calendar date the trip started.
  - name: pickup_hour
    expr: HOUR(tpep_pickup_datetime)
    comment: Hour of day (0-23) the trip started.
  - name: pickup_zip
    expr: pickup_zip
    comment: ZIP code where the trip started.
  - name: dropoff_zip
    expr: dropoff_zip
    comment: ZIP code where the trip ended.
measures:
  - name: trip_count
    expr: COUNT(1)
    comment: Number of trips.
  - name: total_revenue
    expr: SUM(fare_amount)
    comment: Sum of fares in USD.
  - name: avg_fare
    expr: AVG(fare_amount)
    comment: Average fare per trip in USD.
  - name: avg_distance_miles
    expr: AVG(trip_distance)
    comment: Average trip distance in miles.
$$;
