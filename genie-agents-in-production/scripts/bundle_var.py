"""Print a resolved bundle variable: python3 scripts/bundle_var.py -t dev catalog"""
import argparse
import json
import os
import subprocess

p = argparse.ArgumentParser()
p.add_argument("-t", "--target", default="dev")
p.add_argument("name")
p.add_argument("-p", "--profile", default=os.environ.get("DATABRICKS_CONFIG_PROFILE"))
a = p.parse_args()
cmd = ["databricks", "bundle", "validate", "-t", a.target, "-o", "json"] + (["-p", a.profile] if a.profile else [])
v = json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)["variables"][a.name]
print(v.get("value", v.get("default")))
