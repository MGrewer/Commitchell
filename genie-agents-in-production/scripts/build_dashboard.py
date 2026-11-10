"""Build ops/dashboards/agent_fleet_health.lvdash.json (AI/BI dashboard over the ops views).

Datasets use unqualified view names; the bundle sets dataset_catalog/dataset_schema
per deployment, so the file has no environment names in it.
"""
import json
import pathlib

datasets = {
    "scorecard": "SELECT title AS agent, domain, owner, status, pass_rate, questions_7d, thumbs_down_rate_7d, "
                 "sql_failure_rate_7d, last_run_ts, is_synthetic FROM v_fleet_scorecard WHERE target = 'prod'",
    "kpis": "SELECT COUNT_IF(managed_as_code) AS managed, COUNT_IF(NOT managed_as_code) AS unmanaged, "
            "(SELECT COUNT_IF(status = 'Needs attention') FROM v_fleet_scorecard WHERE target = 'prod') AS needs_attention, "
            "(SELECT AVG(pass_rate) FROM v_fleet_scorecard WHERE target = 'prod') AS avg_pass_rate "
            "FROM v_agent_coverage",
    "bench_trend": "SELECT title AS agent, DATE(run_ts) AS day, AVG(pass_rate) AS pass_rate FROM v_benchmark_trend "
                   "WHERE target = 'prod' GROUP BY ALL",
    "feedback_trend": "SELECT title AS agent, day, thumbs_down_rate, questions FROM v_feedback_daily "
                      "WHERE day >= current_date() - 30",
    "review_queue": "SELECT title AS agent, question, COUNT(*) AS times_thumbed_down, MAX(message_ts) AS last_seen "
                    "FROM v_review_queue GROUP BY ALL",
    "coverage": "SELECT agent, CASE WHEN managed_as_code THEN 'Managed as code' ELSE 'Not managed' END AS management, "
                "queries_30d FROM v_agent_coverage",
    "sql_health": "SELECT title AS agent, SUM(queries) AS queries, SUM(failed_queries) AS failed, "
                  "TRY_DIVIDE(SUM(failed_queries), SUM(queries)) AS failure_rate, AVG(p50_ms) AS p50_ms, "
                  "SUM(warehouse_task_hours) AS warehouse_task_hours FROM v_sql_health "
                  "WHERE title IS NOT NULL GROUP BY ALL",
    "edits": "SELECT event_time, title AS agent, edited_by, action_name FROM v_prod_edits_outside_pipeline",
}

pct = {"type": "number-percent", "decimalPlaces": {"type": "max", "places": 0}}
num = {"type": "number-plain", "abbreviation": "compact", "decimalPlaces": {"type": "max", "places": 0}}


def q(ds, fields, disagg=True):
    return [{"name": "main_query", "query": {"datasetName": ds, "disaggregated": disagg,
             "fields": [{"name": n, "expression": e} for n, e in fields]}}]


def frame(title, desc=""):
    return {"showTitle": True, "title": {"value": title, "fields": []},
            "showDescription": bool(desc), "description": {"value": desc, "fields": []}}


def counter(name, field, title, desc, fmt):
    return {"name": name, "queries": q("kpis", [(field, f"`{field}`")]),
            "spec": {"version": 2, "widgetType": "counter", "frame": frame(title, desc),
                     "encodings": {"value": {"fieldName": field, "format": fmt}}}}


def line(name, ds, y, title, desc, fmt):
    fields = [("day", "`day`"), (f"avg({y})", f"AVG(`{y}`)"), ("agent", "`agent`")]
    return {"name": name, "queries": q(ds, fields, False),
            "spec": {"version": 3, "widgetType": "line", "frame": frame(title, desc),
                     "encodings": {"x": {"fieldName": "day", "scale": {"type": "temporal"}, "axis": {"title": "Day"}},
                                   "y": {"fieldName": f"avg({y})", "scale": {"type": "quantitative"},
                                         "axis": {"title": title}, "format": fmt},
                                   "color": {"fieldName": "agent", "scale": {"type": "categorical"}}}}}


def table(name, ds, cols, title, desc):
    return {"name": name, "queries": q(ds, [(c, f"`{c}`") for c, _, _ in cols]),
            "spec": {"version": 2, "widgetType": "table", "frame": frame(title, desc),
                     "encodings": {"columns": [dict({"fieldName": c, "displayName": d}, **({"format": f} if f else {}))
                                               for c, d, f in cols]}}}


def text(name, lines):
    return {"name": name, "multilineTextboxSpec": {"lines": lines}}


def pos(x, y, w, h):
    return {"x": x, "y": y, "width": w, "height": h}


layout = [
    (text("hdr", ["## Agent Fleet Health\n",
                  "Every Genie agent, one view: benchmarks, feedback, SQL health, and changes outside the pipeline. "
                  "Rows flagged `is_synthetic` are seeded demo history; the Taxi Trips agent is live.\n"]), pos(0, 0, 6, 2)),
    (counter("k_managed", "managed", "Managed as code", "Agents deployed through the pipeline.", num), pos(0, 2, 1, 3)),
    (counter("k_unmanaged", "unmanaged", "Not managed", "Agents in use that are not in the registry.", num), pos(1, 2, 1, 3)),
    (counter("k_attention", "needs_attention", "Needs attention", "Pass rate under 80% or thumbs-down over 25%.", num), pos(2, 2, 2, 3)),
    (counter("k_pass", "avg_pass_rate", "Avg benchmark pass rate", "Latest run per prod agent.", pct), pos(4, 2, 2, 3)),
    (table("t_scorecard", "scorecard", [("agent", "Agent", None), ("domain", "Domain", None), ("status", "Status", None),
                                         ("pass_rate", "Pass rate", pct), ("questions_7d", "Questions (7d)", num),
                                         ("thumbs_down_rate_7d", "Thumbs-down (7d)", pct),
                                         ("sql_failure_rate_7d", "SQL failures (7d)", pct), ("owner", "Owner", None)],
           "Fleet scorecard", "One row per prod agent."), pos(0, 5, 6, 6)),
    (line("l_bench", "bench_trend", "pass_rate", "Benchmark pass rate",
          "Nightly, on deploy, and on upstream table change.", pct), pos(0, 11, 3, 6)),
    (line("l_fb", "feedback_trend", "thumbs_down_rate", "Thumbs-down rate",
          "Share of rated answers rated thumbs-down, per day.", pct), pos(3, 11, 3, 6)),
    (table("t_review", "review_queue", [("agent", "Agent", None), ("question", "Question", None),
                                         ("times_thumbed_down", "Thumbs-down", num), ("last_seen", "Last seen", None)],
           "Review queue (last 14 days)", "Thumbs-down questions: candidates for new benchmarks or instruction fixes, via pull request."),
     pos(0, 17, 6, 7)),
    (table("t_coverage", "coverage", [("agent", "Agent", None), ("management", "Management", None),
                                       ("queries_30d", "SQL queries (30d)", num)],
           "Coverage", "Every agent seen in the inventory or in system.query.history. Unmanaged agents are shown by id only."),
     pos(0, 24, 3, 7)),
    (table("t_sql", "sql_health", [("agent", "Agent", None), ("queries", "Queries", num), ("failure_rate", "Failure rate", pct),
                                    ("p50_ms", "p50 ms", num), ("warehouse_task_hours", "Warehouse task hrs", None)],
           "SQL health (30d)", "From system.query.history. Warehouse time is a proxy for per-agent cost; billing does not split Genie spend by agent."),
     pos(3, 24, 3, 7)),
    (table("t_edits", "edits", [("event_time", "When", None), ("agent", "Agent", None), ("edited_by", "Edited by", None),
                                 ("action_name", "Action", None)],
           "Prod edits outside the pipeline (30d)", "From system.access.audit. Should be empty."), pos(0, 31, 6, 5)),
]

dash = {
    "datasets": [{"name": n, "displayName": n.replace("_", " ").title(), "queryLines": [s]} for n, s in datasets.items()],
    "pages": [{"name": "fleet", "displayName": "Agent Fleet Health", "pageType": "PAGE_TYPE_CANVAS",
               "layout": [{"widget": w, "position": p} for w, p in layout]}],
}
out = pathlib.Path(__file__).resolve().parent.parent / "ops" / "dashboards" / "agent_fleet_health.lvdash.json"
out.write_text(json.dumps(dash, indent=2) + "\n")
print(f"wrote {out}")
