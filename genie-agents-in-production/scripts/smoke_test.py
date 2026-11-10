"""Post-deploy smoke test: ask the deployed agent one question and check it answers with SQL.

  python3 scripts/smoke_test.py -t prod
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from databricks.sdk import WorkspaceClient  # noqa: E402

from genie_ops import space_id_for_target  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("-t", "--target", default="dev")
p.add_argument("--space-id")
p.add_argument("--key", default="taxi_agent")
p.add_argument("--question", default="How many trips are there in total?")
p.add_argument("-p", "--profile", default=os.environ.get("DATABRICKS_CONFIG_PROFILE"))
a = p.parse_args()

w = WorkspaceClient(profile=a.profile) if a.profile else WorkspaceClient()
sid = a.space_id or space_id_for_target(a.target, a.key, a.profile)
print(f"Smoke test: target={a.target} space={sid}\n  Q: {a.question}")
msg = w.genie.start_conversation_and_wait(sid, a.question)
sql = next((x.query.query for x in (msg.attachments or []) if x.query and x.query.query), None)
text = next((x.text.content for x in (msg.attachments or []) if x.text and x.text.content), "")
status = str(msg.status.value if hasattr(msg.status, "value") else msg.status)
print(f"  status: {status}\n  SQL: {(sql or '').splitlines()[0] if sql else None}\n  A: {text[:200]}")
if status != "COMPLETED" or not sql:
    print("SMOKE TEST FAILED")
    sys.exit(1)
print("SMOKE TEST PASSED")
