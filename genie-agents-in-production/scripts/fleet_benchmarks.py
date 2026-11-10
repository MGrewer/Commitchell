"""Ops job: run benchmarks for every managed agent and store results centrally.

Triggers (see resources/ops.jobs.yml): nightly, after deploy, and when a source
table changes. --tables limits the run to agents that read the changed tables.
Uses Beta Genie eval-run APIs.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(globals().get("__file__", sys.argv[0]))))
from databricks.sdk import WorkspaceClient  # noqa: E402

from genie_ops import run_benchmarks  # noqa: E402
from ops_store import insert, now, sql  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--ops", required=True, help="ops_catalog.ops_schema")
p.add_argument("--warehouse-id", required=True)
p.add_argument("--target", default="prod")
p.add_argument("--trigger", default="nightly")
p.add_argument("--tables", default="", help="comma-separated changed tables; empty = all agents")
p.add_argument("-p", "--profile", default=os.environ.get("DATABRICKS_CONFIG_PROFILE"))
a = p.parse_args()
w = WorkspaceClient(profile=a.profile) if a.profile else WorkspaceClient()

agents = sql(w, a.warehouse_id, f"""
  SELECT space_id, title, git_sha, to_json(source_tables) FROM {a.ops}.agent_registry
  WHERE target = '{a.target}' AND NOT is_synthetic
  QUALIFY ROW_NUMBER() OVER (PARTITION BY space_id ORDER BY registered_at DESC) = 1""")
changed = {t.strip().lower() for t in a.tables.split(",") if t.strip()}
for sid, title, sha, tables_json in agents:
    if changed and not changed & {t.lower() for t in json.loads(tables_json)}:
        continue
    print(f"benchmarking {title} ({sid}) trigger={a.trigger}")
    run = run_benchmarks(w, sid)
    ts = now()
    insert(w, a.warehouse_id, f"{a.ops}.benchmark_runs", [{
        "run_id": run.eval_run_id, "space_id": sid, "target": a.target, "run_ts": ts, "trigger": a.trigger,
        "git_sha": sha, "num_questions": run.num_questions, "num_correct": run.num_correct,
        "num_needs_review": run.num_needs_review, "pass_rate": run.pass_rate, "is_synthetic": False}])
    insert(w, a.warehouse_id, f"{a.ops}.benchmark_results", [{
        "run_id": run.eval_run_id, "space_id": sid, "target": a.target, "run_ts": ts,
        "question_id": r["question_id"], "question": r["question"], "assessment": r["assessment"],
        "expected_sql": r["expected_sql"], "actual_sql": r["actual_sql"], "is_synthetic": False}
        for r in run.results])
    print(f"  pass rate {run.pass_rate:.0%}")
