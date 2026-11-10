"""Write rows to the central ops tables over the SQL warehouse (works locally and in jobs)."""
from __future__ import annotations

import datetime as dt

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState


def lit(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, (dt.datetime, dt.date)):
        return f"TIMESTAMP'{v.isoformat(sep=' ')[:26]}'"
    if isinstance(v, (list, tuple)):
        return "ARRAY(" + ", ".join(lit(x) for x in v) + ")" if v else "CAST(ARRAY() AS ARRAY<STRING>)"
    return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"


def sql(w: WorkspaceClient, warehouse_id: str, statement: str):
    r = w.statement_execution.execute_statement(statement=statement, warehouse_id=warehouse_id, wait_timeout="50s")
    if r.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(f"{r.status.error.message if r.status.error else r.status.state}: {statement[:200]}")
    return (r.result.data_array if r.result else None) or []


def insert(w: WorkspaceClient, warehouse_id: str, table: str, rows: list[dict], batch: int = 200):
    if not rows:
        return 0
    cols = list(rows[0].keys())
    for i in range(0, len(rows), batch):
        values = ",\n".join("(" + ", ".join(lit(r[c]) for c in cols) + ")" for r in rows[i:i + batch])
        sql(w, warehouse_id, f"INSERT INTO {table} ({', '.join(cols)}) VALUES\n{values}")
    return len(rows)


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def ts_ms(ms) -> dt.datetime | None:
    return dt.datetime.fromtimestamp(int(ms) / 1000, dt.timezone.utc).replace(tzinfo=None) if ms else None
