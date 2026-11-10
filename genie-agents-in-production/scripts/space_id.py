"""Print the deployed Genie space id for a bundle target: python3 scripts/space_id.py -t prod"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from genie_ops import space_id_for_target  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("-t", "--target", default="dev")
p.add_argument("--key", default="taxi_agent")
p.add_argument("-p", "--profile", default=os.environ.get("DATABRICKS_CONFIG_PROFILE"))
a = p.parse_args()
print(space_id_for_target(a.target, a.key, a.profile))
