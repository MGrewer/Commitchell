"""Pipeline gate: run an agent's benchmarks and fail if the pass rate is too low.

  python3 scripts/benchmark_gate.py -t prod --threshold 0.8
Exit code 0 = pass, 1 = below threshold. Uses Beta eval-run APIs.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from databricks.sdk import WorkspaceClient  # noqa: E402

from genie_ops import run_benchmarks, space_id_for_target  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("-t", "--target", default="dev")
p.add_argument("--space-id")
p.add_argument("--key", default="taxi_agent")
p.add_argument("--threshold", type=float, default=0.8)
p.add_argument("-p", "--profile", default=os.environ.get("DATABRICKS_CONFIG_PROFILE"))
a = p.parse_args()

w = WorkspaceClient(profile=a.profile) if a.profile else WorkspaceClient()
sid = a.space_id or space_id_for_target(a.target, a.key, a.profile)
print(f"Benchmark gate: target={a.target} space={sid} threshold={a.threshold:.0%}")
run = run_benchmarks(w, sid)
for r in run.results:
    mark = "PASS" if r["assessment"] == "GOOD" else ("REVIEW" if r["assessment"] == "NEEDS_REVIEW" else "FAIL")
    print(f"  [{mark:6}] {r['question']}")
print(f"Pass rate {run.pass_rate:.0%} ({run.num_correct}/{run.num_questions}), "
      f"{run.num_needs_review} need review")
if run.pass_rate < a.threshold:
    print("GATE FAILED: pass rate below threshold")
    sys.exit(1)
print("GATE PASSED")
