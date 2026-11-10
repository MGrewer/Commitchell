-- Central Genie ops tables. One location per workspace; every row carries target.
CREATE SCHEMA IF NOT EXISTS {ops_catalog}.{ops_schema} COMMENT 'Central telemetry for Genie agents: registry, benchmarks, feedback'
;;
CREATE TABLE IF NOT EXISTS {ops_catalog}.{ops_schema}.agent_registry (
  space_id STRING, agent_key STRING, title STRING, target STRING, owner STRING, domain STRING,
  git_sha STRING, source_tables ARRAY<STRING>, registered_at TIMESTAMP, is_synthetic BOOLEAN)
COMMENT 'Agents managed as code. Written by scripts/register_agents.py after each deploy.'
;;
CREATE TABLE IF NOT EXISTS {ops_catalog}.{ops_schema}.space_inventory (
  space_id STRING, title STRING, warehouse_id STRING, create_time TIMESTAMP, update_time TIMESTAMP,
  snapshot_at TIMESTAMP, is_synthetic BOOLEAN)
COMMENT 'Every Genie agent in the workspace, managed or not. Snapshot from the Genie API.'
;;
CREATE TABLE IF NOT EXISTS {ops_catalog}.{ops_schema}.benchmark_runs (
  run_id STRING, space_id STRING, target STRING, run_ts TIMESTAMP, trigger STRING, git_sha STRING,
  num_questions INT, num_correct INT, num_needs_review INT, pass_rate DOUBLE, is_synthetic BOOLEAN)
COMMENT 'One row per benchmark eval run (Beta Genie eval API).'
;;
CREATE TABLE IF NOT EXISTS {ops_catalog}.{ops_schema}.benchmark_results (
  run_id STRING, space_id STRING, target STRING, run_ts TIMESTAMP, question_id STRING, question STRING,
  assessment STRING, expected_sql STRING, actual_sql STRING, is_synthetic BOOLEAN)
COMMENT 'Per-question benchmark results. assessment: GOOD, BAD, NEEDS_REVIEW.'
;;
CREATE TABLE IF NOT EXISTS {ops_catalog}.{ops_schema}.feedback (
  space_id STRING, conversation_id STRING, message_id STRING, question STRING, rating STRING,
  message_ts TIMESTAMP, harvested_at TIMESTAMP, is_synthetic BOOLEAN)
COMMENT 'User questions and ratings harvested from the Genie Conversation API. No user identity is stored.'
