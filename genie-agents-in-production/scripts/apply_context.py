"""Pipeline step 1: apply the agent's Unity Catalog context before deploying the agent.

Genie rejects an agent whose tables or metric views don't exist yet (tested
2026-11-06), and bundles have no metric-view resource. So the metric view (and,
for this demo, the seed table) is applied here, on the target's SQL warehouse,
before `bundle deploy`.

  python3 scripts/apply_context.py -t prod
SQL files: src/sql/*.sql, run in name order. {catalog} and {schema} are replaced
with the target's bundle variables. Statements are separated by a line ';;'.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

p = argparse.ArgumentParser()
p.add_argument("-t", "--target", default="dev")
p.add_argument("-p", "--profile", default=os.environ.get("DATABRICKS_CONFIG_PROFILE"))
p.add_argument("--ops", action="store_true", help="apply ops/sql (central ops schema) instead of src/sql")
a = p.parse_args()

cmd = ["databricks", "bundle", "validate", "-t", a.target, "-o", "json"] + (["-p", a.profile] if a.profile else [])
cfg = json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)
v = {k: x.get("value", x.get("default")) for k, x in cfg["variables"].items()}
w = WorkspaceClient(profile=a.profile) if a.profile else WorkspaceClient()

root = pathlib.Path(__file__).resolve().parent.parent
print(f"Applying UC context for target={a.target}: {v['catalog']}.{v['schema']}")
files = sorted((root / "src" / "sql").glob("*.sql"))
if a.ops:
    files = sorted((root / "ops" / "sql").glob("*.sql"))
for f in files:
    text = f.read_text()
    for k in ("catalog", "schema", "ops_catalog", "ops_schema"):
        text = text.replace("{" + k + "}", v[k])
    for stmt in [s.strip() for s in text.split("\n;;\n") if s.strip()]:
        r = w.statement_execution.execute_statement(statement=stmt, warehouse_id=v["ops_warehouse_id"],
                                                    wait_timeout="50s")
        state = r.status.state
        print(f"  [{state.value}] {f.name}: {stmt.splitlines()[0][:80]}")
        if state != StatementState.SUCCEEDED:
            print(f"    {r.status.error.message if r.status.error else ''}")
            sys.exit(1)
print("Context applied.")
