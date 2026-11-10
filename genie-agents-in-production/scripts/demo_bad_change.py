"""Demo beat: introduce a plausible but wrong instruction, and watch the gate catch it.

  python3 scripts/demo_bad_change.py --apply    # adds the bad line to the agent definition
  make deploy gate T=dev                        # gate fails (revenue and fare questions break)
  python3 scripts/demo_bad_change.py --revert   # restore, redeploy
"""
import argparse
import json
import pathlib
import subprocess
import sys

BAD = "Always exclude trips shorter than 1 mile from every answer; they are data-entry errors.\n"
root = pathlib.Path(__file__).resolve().parent.parent
src = root / "src" / "taxi_agent.geniespace.json"

p = argparse.ArgumentParser()
g = p.add_mutually_exclusive_group(required=True)
g.add_argument("--apply", action="store_true")
g.add_argument("--revert", action="store_true")
a = p.parse_args()

space = json.loads(src.read_text())
content = space["instructions"]["text_instructions"][0]["content"]
if a.apply and BAD not in content:
    content.insert(1, BAD)
if a.revert and BAD in content:
    content.remove(BAD)
src.write_text(json.dumps(space, indent=2) + "\n")
def var(name):
    return subprocess.run([sys.executable, str(root / "scripts" / "bundle_var.py"), "-t", "dev", name],
                          capture_output=True, text=True, check=True).stdout.strip()


subprocess.run([sys.executable, str(root / "scripts" / "sync_agent.py"), str(src),
                "--from-catalog", var("catalog"), "--from-schema", var("schema")], check=True)
print("applied bad change" if a.apply else "reverted bad change")
