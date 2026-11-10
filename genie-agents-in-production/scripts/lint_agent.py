"""Standards check for Genie agent definitions, run in CI before deploy.

Reads every resources/*.genie.yml and fails if an agent breaks a standard.
These are example standards; a platform team sets its own.
"""
import json
import pathlib
import re
import sys

MIN_BENCHMARKS = 10
root = pathlib.Path(__file__).resolve().parent.parent
failures = 0

for f in sorted((root / "resources").glob("*.genie.yml")):
    text = f.read_text()
    for key in re.findall(r"^    (\w+):\s*$", text, re.M):
        problems = []
        desc = re.search(r"^      description: (.+)$", text, re.M)
        if not desc or len(desc.group(1).strip()) < 20:
            problems.append("needs a description of at least 20 characters")
        m = re.search(r"serialized_space: (\{.*)", text, re.S)
        space = json.loads(m.group(1)) if m else {}
        bms = space.get("benchmarks", {}).get("questions", [])
        if len(bms) < MIN_BENCHMARKS:
            problems.append(f"has {len(bms)} benchmarks, needs at least {MIN_BENCHMARKS}")
        if not space.get("instructions", {}).get("text_instructions"):
            problems.append("has no text instructions")
        mvs = [d["identifier"] for d in space.get("data_sources", {}).get("tables", [])
               if d["identifier"].endswith("_metrics")]
        if not mvs:
            problems.append("uses no metric view named *_metrics (business logic should live in UC)")
        if not space.get("config", {}).get("sample_questions"):
            problems.append("has no sample questions")
        ids = [d["identifier"] for v in space.get("data_sources", {}).values() for d in v]
        hard = [i for i in ids if not i.startswith("${var.catalog}.${var.schema}.")]
        if hard:
            problems.append(f"hardcodes environment names: {hard}")
        status = "OK  " if not problems else "FAIL"
        print(f"[{status}] {key} ({f.name})")
        for pr in problems:
            print(f"        - {pr}")
        failures += bool(problems)

sys.exit(1 if failures else 0)
