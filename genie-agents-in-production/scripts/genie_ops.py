"""Shared helpers for the pipeline scripts and the ops jobs.

Uses the Databricks SDK (tested with databricks-sdk 0.108.0). The benchmark
eval-run APIs are Beta.
"""
from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field

from databricks.sdk import WorkspaceClient


@dataclass
class BenchmarkRun:
    space_id: str
    eval_run_id: str
    status: str
    num_questions: int
    num_done: int
    num_correct: int
    num_needs_review: int
    results: list[dict] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.num_correct / self.num_questions if self.num_questions else 0.0


def space_id_for_target(target: str, key: str = "taxi_agent", profile: str | None = None) -> str:
    """Resolve a deployed Genie space id from `databricks bundle summary`."""
    cmd = ["databricks", "bundle", "summary", "-t", target, "-o", "json"]
    if profile:
        cmd += ["-p", profile]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    sid = json.loads(out)["resources"]["genie_spaces"][key].get("id")
    if not sid:
        raise SystemExit(f"genie space '{key}' is not deployed to target '{target}'")
    return sid


def run_benchmarks(w: WorkspaceClient, space_id: str, timeout_s: int = 900,
                   poll_s: int = 10, with_details: bool = True) -> BenchmarkRun:
    """Start a benchmark eval run, wait for it, and collect per-question results."""
    run = w.genie.genie_create_eval_run(space_id)
    run_id = run.eval_run_id
    deadline = time.time() + timeout_s
    while True:
        run = w.genie.genie_get_eval_run(space_id, run_id)
        status = str(run.eval_run_status.value if hasattr(run.eval_run_status, "value") else run.eval_run_status)
        print(f"  eval run {run_id}: {status} {run.num_done}/{run.num_questions} done, {run.num_correct} correct")
        if status not in ("RUNNING", "PENDING", "QUEUED", "None"):
            break
        if time.time() > deadline:
            raise TimeoutError(f"eval run {run_id} did not finish in {timeout_s}s")
        time.sleep(poll_s)

    results = []
    token = None
    while True:
        page = w.genie.genie_list_eval_results(space_id, run_id, page_token=token)
        for r in page.eval_results or []:
            row = {"result_id": r.result_id, "question_id": r.benchmark_question_id,
                   "question": r.question, "expected_sql": r.benchmark_answer, "assessment": None,
                   "actual_sql": None}
            if with_details:
                d = w.genie.genie_get_eval_result_details(space_id, run_id, r.result_id)
                a = getattr(d, "assessment", None)
                row["assessment"] = str(a.value if hasattr(a, "value") else a)
                actual = getattr(d, "actual_response", None) or []
                row["actual_sql"] = actual[0].response if actual else None
            results.append(row)
        token = page.next_page_token
        if not token:
            break

    return BenchmarkRun(space_id, run_id, status, run.num_questions or 0, run.num_done or 0,
                        run.num_correct or 0, run.num_needs_review or 0, results)
