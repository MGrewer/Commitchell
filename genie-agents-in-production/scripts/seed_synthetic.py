"""Seed 30 days of SYNTHETIC fleet history so trend charts read on a fresh workspace.

Every row is flagged is_synthetic = TRUE; say so on screen. Real rows from the live
agent append on top. Re-running replaces the synthetic rows (deletes by flag only).

Story in the data:
  - Fleet Maintenance: healthy until an upstream table change 5 days ago, then its
    pass rate drops and thumbs-down climbs (the upstream-change trigger catches it).
  - Service Tickets: deployed, but nobody has used it in the last week.
  - Dealer Sales, Supplier Quality, and the real Taxi Trips agent: healthy.
"""
import argparse
import datetime as dt
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
from databricks.sdk import WorkspaceClient  # noqa: E402

from ops_store import insert, sql  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--ops", help="ops_catalog.ops_schema (default: from the prod bundle variables)")
p.add_argument("--warehouse-id", help="default: from the prod bundle variables")
p.add_argument("--taxi-prod-space-id", required=True)
p.add_argument("-p", "--profile", default=os.environ.get("DATABRICKS_CONFIG_PROFILE"))
a = p.parse_args()
if not a.ops or not a.warehouse_id:
    import subprocess
    def var(name):
        return subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "bundle_var.py"), "-t", "prod", name],
                              capture_output=True, text=True, check=True).stdout.strip()
    a.ops = a.ops or f"{var('ops_catalog')}.{var('ops_schema')}"
    a.warehouse_id = a.warehouse_id or var("warehouse_id")
w = WorkspaceClient(profile=a.profile) if a.profile else WorkspaceClient()
rng = random.Random(20261110)
today = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None, minute=0, second=0, microsecond=0)

agents = [  # space_id, title, domain, owner, base pass rate, daily questions, story
    ("synthetic-fleet-maint", "Fleet Maintenance", "Operations", "ops-analytics@example.com", 0.93, 40, "breaks"),
    ("synthetic-dealer-sales", "Dealer Sales", "Sales", "sales-analytics@example.com", 0.9, 65, "healthy"),
    ("synthetic-supplier-qual", "Supplier Quality", "Manufacturing", "quality-analytics@example.com", 0.86, 25, "healthy"),
    ("synthetic-service-tix", "Service Tickets", "Customer Service", "cx-analytics@example.com", 0.88, 12, "unused"),
]
questions = {
    "Fleet Maintenance": ["Which vehicles are overdue for service?", "Average downtime by depot last month?",
                          "Top 5 failure codes this quarter?", "Parts cost by vehicle type?"],
    "Dealer Sales": ["Units sold by region this month?", "Top dealers by revenue?", "Average discount by model?",
                     "Quote-to-order conversion by region?"],
    "Supplier Quality": ["Defect rate by supplier?", "Which suppliers missed on-time delivery?",
                         "Returns by part family?", "Inspection failures last week?"],
    "Service Tickets": ["Open tickets by priority?", "Average time to close by team?"],
    "Taxi Trips": ["How many trips by pickup hour?", "Average fare by pickup ZIP?", "Busiest dropoff ZIP?",
                   "Total revenue by day?"],
}

for t in ["agent_registry", "space_inventory", "benchmark_runs", "benchmark_results", "feedback"]:
    sql(w, a.warehouse_id, f"DELETE FROM {a.ops}.{t} WHERE is_synthetic")

reg, inv, runs, fb = [], [], [], []
for sid, title, domain, owner, base, daily, story in agents:
    reg.append({"space_id": sid, "agent_key": title.lower().replace(" ", "_"), "title": title, "target": "prod",
                "owner": owner, "domain": domain, "git_sha": "synthetic",
                "source_tables": [f"example.{domain.lower().replace(' ', '_')}.facts"],
                "registered_at": today - dt.timedelta(days=30), "is_synthetic": True})
    inv.append({"space_id": sid, "title": title, "warehouse_id": None, "create_time": None, "update_time": None,
                "snapshot_at": today, "is_synthetic": True})

fleet = [(s, t, b, d, st) for s, t, _, _, b, d, st in agents] + \
        [(a.taxi_prod_space_id, "Taxi Trips", 0.96, 30, "healthy")]
for sid, title, base, daily, story in fleet:
    for day in range(30, 0, -1):
        ts = today - dt.timedelta(days=day, hours=-6)
        broken = story == "breaks" and day <= 5
        rate = max(0.0, min(1.0, (0.58 if broken else base) + rng.uniform(-0.04, 0.04)))
        nq = 20
        runs.append({"run_id": f"synthetic-{sid}-{day}", "space_id": sid, "target": "prod", "run_ts": ts,
                     "trigger": "upstream_change" if (broken and day == 5) else "nightly", "git_sha": "synthetic",
                     "num_questions": nq, "num_correct": round(rate * nq), "num_needs_review": rng.randint(0, 1),
                     "pass_rate": round(rate * nq) / nq, "is_synthetic": True})
        n = 0 if (story == "unused" and day <= 8) else max(0, int(daily * rng.uniform(0.7, 1.2)))
        down_p = 0.38 if broken else 0.07
        for i in range(n):
            r = rng.random()
            rating = "NEGATIVE" if r < down_p else ("POSITIVE" if r < down_p + 0.35 else None)
            fb.append({"space_id": sid, "conversation_id": f"synthetic-{sid}-{day}-{i}",
                       "message_id": f"synthetic-{sid}-{day}-{i}", "question": rng.choice(questions[title]),
                       "rating": rating, "message_ts": ts - dt.timedelta(hours=rng.randint(0, 20)),
                       "harvested_at": today, "is_synthetic": True})

print("registry", insert(w, a.warehouse_id, f"{a.ops}.agent_registry", reg))
print("inventory", insert(w, a.warehouse_id, f"{a.ops}.space_inventory", inv))
print("runs", insert(w, a.warehouse_id, f"{a.ops}.benchmark_runs", runs))
print("feedback", insert(w, a.warehouse_id, f"{a.ops}.feedback", fb))
