"""Register deployed agents in the central registry (run after each deploy).

The registry is what makes fleet monitoring possible: which agents are managed as
code, who owns them, which tables they read (used to re-benchmark on upstream change).
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from databricks.sdk import WorkspaceClient  # noqa: E402

from ops_store import insert, now  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--targets", default="dev,prod")
p.add_argument("--domain", default="Mobility")
p.add_argument("-p", "--profile", default=os.environ.get("DATABRICKS_CONFIG_PROFILE"))
a = p.parse_args()
w = WorkspaceClient(profile=a.profile) if a.profile else WorkspaceClient()
prof = ["-p", a.profile] if a.profile else []
sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip() or None
owner = w.current_user.me().user_name

rows, ops = [], None
for t in a.targets.split(","):
    summ = json.loads(subprocess.run(["databricks", "bundle", "summary", "-t", t, "-o", "json"] + prof,
                                     capture_output=True, text=True, check=True).stdout)
    val = json.loads(subprocess.run(["databricks", "bundle", "validate", "-t", t, "-o", "json"] + prof,
                                    capture_output=True, text=True, check=True).stdout)
    v = {k: x.get("value", x.get("default")) for k, x in val["variables"].items()}
    ops = (v["ops_catalog"], v["ops_schema"], v["ops_warehouse_id"])
    for key, res in summ["resources"].get("genie_spaces", {}).items():
        sid = res.get("id")
        if not sid:
            continue
        sp = w.genie.get_space(sid, include_serialized_space=True)
        tables = [d["identifier"] for ds in json.loads(sp.serialized_space)["data_sources"].values() for d in ds]
        rows.append({"space_id": sid, "agent_key": key, "title": sp.title, "target": t, "owner": owner,
                     "domain": a.domain, "git_sha": sha, "source_tables": tables, "registered_at": now(),
                     "is_synthetic": False})
        print(f"registered {key} [{t}] {sid} tables={tables}")

if rows:
    insert(w, ops[2], f"{ops[0]}.{ops[1]}.agent_registry", rows)
