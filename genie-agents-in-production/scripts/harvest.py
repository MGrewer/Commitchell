"""Ops job: snapshot every Genie agent in the workspace, then harvest questions and
ratings from managed agents into the central feedback table.

Runs as a scheduled job. Reading all users' conversations (include_all) is an
admin-level decision for the customer; no user identity is stored.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(globals().get("__file__", sys.argv[0]))))
from databricks.sdk import WorkspaceClient  # noqa: E402

from ops_store import insert, now, sql, ts_ms  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--ops", required=True, help="ops_catalog.ops_schema")
p.add_argument("--warehouse-id", required=True)
p.add_argument("-p", "--profile", default=os.environ.get("DATABRICKS_CONFIG_PROFILE"))
a = p.parse_args()
w = WorkspaceClient(profile=a.profile) if a.profile else WorkspaceClient()

# 1. Inventory: every agent, managed or not.
inv, token, snap = [], None, now()
while True:
    page = w.genie.list_spaces(page_token=token)
    for s in page.spaces or []:
        inv.append({"space_id": s.space_id, "title": s.title, "warehouse_id": s.warehouse_id,
                    "create_time": None, "update_time": None, "snapshot_at": snap, "is_synthetic": False})
    token = page.next_page_token
    if not token:
        break
print(f"inventory: {insert(w, a.warehouse_id, f'{a.ops}.space_inventory', inv)} agents")

# 2. Feedback from managed agents, skipping messages already harvested.
managed = [r[0] for r in sql(w, a.warehouse_id, f"SELECT DISTINCT space_id FROM {a.ops}.agent_registry WHERE NOT is_synthetic")]
for sid in managed:
    seen = {r[0]: r[1] for r in sql(w, a.warehouse_id,
            f"SELECT message_id, MAX_BY(rating, harvested_at) FROM {a.ops}.feedback WHERE space_id = '{sid}' GROUP BY message_id")}
    rows, token = [], None
    while True:
        convs = w.genie.list_conversations(sid, include_all=True, page_token=token)
        for c in convs.conversations or []:
            mt = None
            while True:
                msgs = w.genie.list_conversation_messages(sid, c.conversation_id, page_token=mt)
                for m in msgs.messages or []:
                    rating = m.feedback.rating.value if m.feedback and m.feedback.rating else None
                    if not m.content or (m.message_id in seen and seen[m.message_id] == rating):
                        continue
                    rows.append({"space_id": sid, "conversation_id": c.conversation_id, "message_id": m.message_id,
                                 "question": m.content, "rating": rating, "message_ts": ts_ms(m.created_timestamp),
                                 "harvested_at": now(), "is_synthetic": False})
                mt = msgs.next_page_token
                if not mt:
                    break
        token = convs.next_page_token
        if not token:
            break
    print(f"{sid}: {insert(w, a.warehouse_id, f'{a.ops}.feedback', rows)} new or re-rated messages")
