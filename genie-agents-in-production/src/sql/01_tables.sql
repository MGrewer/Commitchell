-- Tables the agent reads. Runs as a SQL file task in the build_context job.
-- :catalog and :schema come from the task parameters (bundle variables per target).
-- The catalog and schema already exist; the platform team owns them.
USE CATALOG IDENTIFIER(:catalog);
USE SCHEMA IDENTIFIER(:schema);

-- In a real project this table comes from your pipeline. The demo seeds it from samples.
CREATE TABLE IF NOT EXISTS trips
COMMENT 'NYC taxi trips (sample data). One row per trip.'
AS SELECT * FROM samples.nyctaxi.trips;

ALTER TABLE trips ALTER COLUMN fare_amount COMMENT 'Fare in USD.';
ALTER TABLE trips ALTER COLUMN trip_distance COMMENT 'Trip distance in miles.';
