#!/bin/bash
# Deploy the unbranded Context Hub next to this demo, governing the prod demo schema.
# Stages a copy under build/ (git-ignored) so the shared unbranded repo stays untouched.
#
#   scripts/deploy_context_hub.sh <profile> <warehouse_id> <catalog> <schema> <lakebase_project>
# Example:
#   scripts/deploy_context_hub.sh my-profile <warehouse-id> my_catalog genie_demo_prod context-hub
#
# The Lakebase project must exist (databricks postgres create-project <id>).
set -euo pipefail
PROFILE=$1; WH=$2; CATALOG=$3; SCHEMA=$4; PROJECT=$5
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$HOME/Documents/GitHub/unbranded/context-hub"
DEST="$ROOT/build/context-hub"
BRANCH="projects/$PROJECT/branches/production"

mkdir -p "$DEST"
rsync -a --exclude node_modules --exclude .databricks --exclude .venv --exclude __pycache__ \
  --exclude backend/dist "$SRC/" "$DEST/"

python3 -I - "$DEST" "$CATALOG" "$SCHEMA" "$BRANCH" <<'PY'
import pathlib, sys
dest, catalog, schema, branch = sys.argv[1:]
app = pathlib.Path(dest, "app.yaml"); t = app.read_text()
t = t.replace('- name: WRITE_CATALOG\n    value: "context_hub_demo"', f'- name: WRITE_CATALOG\n    value: "{catalog}"')
t = t.replace('- name: WRITE_SCHEMA\n    value: ""', f'- name: WRITE_SCHEMA\n    value: "{schema}"')
t = t.replace('- name: LAKEBASE_ENDPOINT\n    value: ""', f'- name: LAKEBASE_ENDPOINT\n    value: "{branch}/endpoints/primary"')
app.write_text(t)
yml = pathlib.Path(dest, "databricks.yml"); y = yml.read_text()
if 'include:\n    - "**"' not in y:  # build/ is git-ignored; bundles skip ignored files unless included
    y = y.replace("sync:\n  exclude:", 'sync:\n  include:\n    - "**"\n  exclude:', 1)
yml.write_text(y)
PY

DB=$(databricks postgres list-databases "$BRANCH" -p "$PROFILE" -o json \
  | python3 -I -c "import json,sys;print([d['name'] for d in json.load(sys.stdin) if d.get('status',{}).get('postgres_database')=='databricks_postgres'][0])")
cd "$DEST"
databricks bundle deploy -p "$PROFILE" --var warehouse_id="$WH" --var lakebase_branch="$BRANCH" --var lakebase_database="$DB"
databricks bundle run context_hub -p "$PROFILE" --var warehouse_id="$WH" --var lakebase_branch="$BRANCH" --var lakebase_database="$DB"
