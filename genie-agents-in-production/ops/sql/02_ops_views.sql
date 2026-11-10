-- Fleet views. Agent identity comes from the registry; health from ops tables + system tables.
CREATE OR REPLACE VIEW {ops_catalog}.{ops_schema}.v_agent_coverage
COMMENT 'Every Genie agent seen (API inventory + agents that ran SQL in the last 30 days) and whether it is managed as code. Titles are shown only for managed agents.' AS
WITH reg AS (SELECT * FROM {ops_catalog}.{ops_schema}.agent_registry
             QUALIFY ROW_NUMBER() OVER (PARTITION BY space_id ORDER BY registered_at DESC) = 1),
seen AS (
  SELECT space_id, MAX(is_synthetic) AS is_synthetic FROM {ops_catalog}.{ops_schema}.space_inventory GROUP BY space_id
  UNION
  SELECT DISTINCT query_source.genie_space_id, FALSE FROM system.query.history
  WHERE query_source.genie_space_id IS NOT NULL AND start_time >= current_date() - 30
    AND workspace_id IN (SELECT DISTINCT workspace_id FROM system.query.history
                         WHERE query_source.genie_space_id IN (SELECT space_id FROM {ops_catalog}.{ops_schema}.agent_registry)
                           AND start_time >= current_date() - 30)),
active AS (SELECT query_source.genie_space_id AS space_id, COUNT(*) AS queries_30d FROM system.query.history
           WHERE query_source.genie_space_id IS NOT NULL AND start_time >= current_date() - 30
             AND workspace_id IN (SELECT DISTINCT workspace_id FROM system.query.history
                         WHERE query_source.genie_space_id IN (SELECT space_id FROM {ops_catalog}.{ops_schema}.agent_registry)
                           AND start_time >= current_date() - 30) GROUP BY 1)
SELECT s.space_id,
       COALESCE(reg.title, 'Unregistered agent …' || RIGHT(s.space_id, 6)) AS agent,
       reg.target, reg.owner, reg.domain,
       reg.space_id IS NOT NULL AS managed_as_code,
       COALESCE(active.queries_30d, 0) AS queries_30d,
       MAX(s.is_synthetic) OR MAX(COALESCE(reg.is_synthetic, FALSE)) AS is_synthetic
FROM seen s LEFT JOIN reg ON s.space_id = reg.space_id LEFT JOIN active ON s.space_id = active.space_id
GROUP BY ALL
;;
CREATE OR REPLACE VIEW {ops_catalog}.{ops_schema}.v_benchmark_trend
COMMENT 'Benchmark pass rate per agent per run.' AS
SELECT r.title, r.domain, b.target, b.run_ts, b.trigger, b.pass_rate, b.num_correct, b.num_questions,
       b.is_synthetic
FROM {ops_catalog}.{ops_schema}.benchmark_runs b
JOIN (SELECT * FROM {ops_catalog}.{ops_schema}.agent_registry
      QUALIFY ROW_NUMBER() OVER (PARTITION BY space_id ORDER BY registered_at DESC) = 1) r
  ON b.space_id = r.space_id
;;
CREATE OR REPLACE VIEW {ops_catalog}.{ops_schema}.v_feedback_daily
COMMENT 'Thumbs up / down per agent per day.' AS
SELECT r.title, r.domain, DATE(f.message_ts) AS day,
       COUNT(*) AS questions,
       COUNT_IF(f.rating = 'POSITIVE') AS thumbs_up,
       COUNT_IF(f.rating = 'NEGATIVE') AS thumbs_down,
       TRY_DIVIDE(COUNT_IF(f.rating = 'NEGATIVE'), COUNT_IF(f.rating IN ('POSITIVE','NEGATIVE'))) AS thumbs_down_rate,
       MAX(CAST(f.is_synthetic AS INT)) = 1 AS is_synthetic
FROM {ops_catalog}.{ops_schema}.feedback f
JOIN (SELECT * FROM {ops_catalog}.{ops_schema}.agent_registry
      QUALIFY ROW_NUMBER() OVER (PARTITION BY space_id ORDER BY registered_at DESC) = 1) r
  ON f.space_id = r.space_id
GROUP BY ALL
;;
CREATE OR REPLACE VIEW {ops_catalog}.{ops_schema}.v_review_queue
COMMENT 'Thumbs-down questions in the last 14 days: candidates for new benchmarks or instruction fixes.' AS
SELECT r.title, r.owner, f.question, f.message_ts, f.is_synthetic
FROM {ops_catalog}.{ops_schema}.feedback f
JOIN (SELECT * FROM {ops_catalog}.{ops_schema}.agent_registry
      QUALIFY ROW_NUMBER() OVER (PARTITION BY space_id ORDER BY registered_at DESC) = 1) r
  ON f.space_id = r.space_id
WHERE f.rating = 'NEGATIVE' AND f.message_ts >= current_timestamp() - INTERVAL 14 DAYS
;;
CREATE OR REPLACE VIEW {ops_catalog}.{ops_schema}.v_sql_health
COMMENT 'SQL Genie ran per agent per day (system.query.history): volume, failures, latency, warehouse time.' AS
SELECT q.query_source.genie_space_id AS space_id, COALESCE(r.title, i.title) AS title,
       DATE(q.start_time) AS day, COUNT(*) AS queries,
       COUNT_IF(q.execution_status = 'FAILED') AS failed_queries,
       TRY_DIVIDE(COUNT_IF(q.execution_status = 'FAILED'), COUNT(*)) AS failure_rate,
       PERCENTILE(q.total_duration_ms, 0.5) AS p50_ms,
       SUM(q.total_task_duration_ms) / 3600000.0 AS warehouse_task_hours
FROM system.query.history q
LEFT JOIN (SELECT * FROM {ops_catalog}.{ops_schema}.agent_registry
           QUALIFY ROW_NUMBER() OVER (PARTITION BY space_id ORDER BY registered_at DESC) = 1) r
  ON q.query_source.genie_space_id = r.space_id
LEFT JOIN (SELECT space_id, MAX_BY(title, snapshot_at) AS title FROM {ops_catalog}.{ops_schema}.space_inventory GROUP BY space_id) i
  ON q.query_source.genie_space_id = i.space_id
WHERE q.query_source.genie_space_id IS NOT NULL AND q.start_time >= current_date() - 30
  AND q.workspace_id IN (SELECT DISTINCT workspace_id FROM system.query.history
                         WHERE query_source.genie_space_id IN (SELECT space_id FROM {ops_catalog}.{ops_schema}.agent_registry)
                           AND start_time >= current_date() - 30)
GROUP BY ALL
;;
CREATE OR REPLACE VIEW {ops_catalog}.{ops_schema}.v_prod_edits_outside_pipeline
COMMENT 'Edits to prod agents by anyone other than the deploying identity (system.access.audit).' AS
SELECT a.event_time, r.title, a.user_identity.email AS edited_by, a.action_name
FROM system.access.audit a
JOIN (SELECT * FROM {ops_catalog}.{ops_schema}.agent_registry WHERE target = 'prod'
      QUALIFY ROW_NUMBER() OVER (PARTITION BY space_id ORDER BY registered_at DESC) = 1) r
  ON a.request_params.space_id = r.space_id
WHERE a.service_name = 'aibiGenie' AND a.action_name IN ('updateSpace', 'genieUpdateSpace')
  AND a.event_time >= current_date() - 30
  AND a.user_identity.email <> r.owner
;;
CREATE OR REPLACE VIEW {ops_catalog}.{ops_schema}.v_fleet_scorecard
COMMENT 'One row per managed agent: latest pass rate, 7-day thumbs-down rate, 7-day SQL failure rate.' AS
WITH reg AS (SELECT * FROM {ops_catalog}.{ops_schema}.agent_registry
             QUALIFY ROW_NUMBER() OVER (PARTITION BY space_id ORDER BY registered_at DESC) = 1),
last_run AS (SELECT space_id, MAX_BY(pass_rate, run_ts) AS pass_rate, MAX(run_ts) AS last_run_ts
             FROM {ops_catalog}.{ops_schema}.benchmark_runs GROUP BY space_id),
fb AS (SELECT space_id, COUNT(*) AS questions_7d,
              TRY_DIVIDE(COUNT_IF(rating = 'NEGATIVE'), COUNT_IF(rating IN ('POSITIVE','NEGATIVE'))) AS thumbs_down_rate_7d
       FROM {ops_catalog}.{ops_schema}.feedback WHERE message_ts >= current_timestamp() - INTERVAL 7 DAYS
       GROUP BY space_id),
sq AS (SELECT space_id, TRY_DIVIDE(SUM(failed_queries), SUM(queries)) AS sql_failure_rate_7d
       FROM {ops_catalog}.{ops_schema}.v_sql_health WHERE day >= current_date() - 7 GROUP BY space_id)
SELECT reg.title, reg.domain, reg.owner, reg.target, last_run.pass_rate, last_run.last_run_ts,
       COALESCE(fb.questions_7d, 0) AS questions_7d, fb.thumbs_down_rate_7d, sq.sql_failure_rate_7d,
       CASE WHEN last_run.pass_rate < 0.8 OR fb.thumbs_down_rate_7d > 0.25 THEN 'Needs attention'
            WHEN COALESCE(fb.questions_7d, 0) = 0 THEN 'Unused' ELSE 'Healthy' END AS status,
       reg.is_synthetic
FROM reg LEFT JOIN last_run USING (space_id) LEFT JOIN fb USING (space_id) LEFT JOIN sq USING (space_id)
