"""Author the Taxi Trips Genie agent definition (src/taxi_agent.geniespace.json).

One-time authoring helper. After the first deploy, the source of truth is the
.geniespace.json file, refreshed from the UI with `bundle generate genie-space`.

Catalog and schema are written as bundle variables (${var.catalog}, ${var.schema})
so the same file deploys to dev and prod.
"""
import hashlib
import json
import pathlib

CAT = "${var.catalog}.${var.schema}"
TRIPS = f"{CAT}.trips"
MV = f"{CAT}.trip_metrics"


def hid(label: str) -> str:
    """Stable 32-hex id from a label, so re-running gives the same ids."""
    return hashlib.md5(label.encode()).hexdigest()


def by_id(items):
    return sorted(items, key=lambda x: x["id"])


sample_questions = [
    "How many trips were there by pickup hour?",
    "What is the average fare by pickup ZIP?",
    "Which pickup ZIPs had the most revenue?",
]

instructions = [
    "Use the trip_metrics metric view for counts, revenue, average fare and average distance. "
    "Query it with MEASURE(), for example MEASURE(trip_count).",
    "Revenue means the sum of fare_amount in USD. Tips and tolls are not in this data.",
    "Use the trips table only for row-level questions, such as the longest single trip.",
    "When a question says 'busiest', rank by trip_count.",
]

example_sqls = [
    ("How many trips started each hour of the day?",
     f"SELECT pickup_hour, MEASURE(trip_count) AS trips FROM {MV} GROUP BY pickup_hour ORDER BY pickup_hour"),
    ("What was total revenue by pickup date?",
     f"SELECT pickup_date, MEASURE(total_revenue) AS revenue FROM {MV} GROUP BY pickup_date ORDER BY pickup_date"),
    ("What is the longest trip in miles?",
     f"SELECT tpep_pickup_datetime, pickup_zip, dropoff_zip, trip_distance FROM {TRIPS} ORDER BY trip_distance DESC LIMIT 1"),
]

benchmarks = [
    ("How many trips are there in total?",
     f"SELECT MEASURE(trip_count) AS trips FROM {MV}"),
    ("What is the total revenue?",
     f"SELECT MEASURE(total_revenue) AS revenue FROM {MV}"),
    ("What is the average fare?",
     f"SELECT MEASURE(avg_fare) AS avg_fare FROM {MV}"),
    ("What is the average trip distance in miles?",
     f"SELECT MEASURE(avg_distance_miles) AS avg_distance FROM {MV}"),
    ("Which hour of the day has the most trips?",
     f"SELECT pickup_hour, MEASURE(trip_count) AS trips FROM {MV} GROUP BY pickup_hour ORDER BY trips DESC LIMIT 1"),
    ("What are the top 5 pickup ZIPs by revenue?",
     f"SELECT pickup_zip, MEASURE(total_revenue) AS revenue FROM {MV} GROUP BY pickup_zip ORDER BY revenue DESC LIMIT 5"),
    ("How many trips started in ZIP 10001?",
     f"SELECT MEASURE(trip_count) AS trips FROM {MV} WHERE pickup_zip = 10001"),
    ("What is the average fare by pickup hour?",
     f"SELECT pickup_hour, MEASURE(avg_fare) AS avg_fare FROM {MV} GROUP BY pickup_hour ORDER BY pickup_hour"),
    ("How many trips were there per day?",
     f"SELECT pickup_date, MEASURE(trip_count) AS trips FROM {MV} GROUP BY pickup_date ORDER BY pickup_date"),
    ("What is the busiest dropoff ZIP?",
     f"SELECT dropoff_zip, MEASURE(trip_count) AS trips FROM {MV} GROUP BY dropoff_zip ORDER BY trips DESC LIMIT 1"),
]

space = {
    "version": 2,
    "config": {
        "sample_questions": by_id(
            [{"id": hid("sq:" + q), "question": [q]} for q in sample_questions]
        )
    },
    "data_sources": {
        "metric_views": [{"identifier": MV}],
        "tables": [{"identifier": TRIPS}],
    },
    "instructions": {
        "text_instructions": [{"id": hid("ti:main"), "content": [line + "\n" for line in instructions[:-1]] + instructions[-1:]}],
        "example_question_sqls": by_id(
            [{"id": hid("ex:" + q), "question": [q], "sql": [s]} for q, s in example_sqls]
        ),
    },
    "benchmarks": {
        "questions": by_id(
            [
                {"id": hid("bm:" + q), "question": [q], "answer": [{"format": "SQL", "content": [s]}]}
                for q, s in benchmarks
            ]
        )
    },
}

out = pathlib.Path(__file__).resolve().parent.parent / "src" / "taxi_agent.geniespace.json"
out.write_text(json.dumps(space, indent=2) + "\n")
print(f"wrote {out}")
