# The same steps an Azure DevOps (or any CI) pipeline runs. See pipelines/azure-pipelines.yml.
# Profile: set DATABRICKS_CONFIG_PROFILE, or rely on DEFAULT.
PY ?= python3
T ?= dev
DEV_CATALOG ?= $(shell $(PY) scripts/bundle_var.py -t dev catalog)
DEV_SCHEMA ?= $(shell $(PY) scripts/bundle_var.py -t dev schema)
SPACE_KEY ?= taxi_agent

.PHONY: pull lint context deploy smoke gate release bootstrap ops

# Developer loop: pull the dev agent (edited in the UI) back into code.
# bundle generate --watch only works for file_path agents, so pull by id into build/.
pull:
	databricks bundle generate genie-space -t dev --existing-id $$($(PY) scripts/space_id.py -t dev --key $(SPACE_KEY)) \
	  --key $(SPACE_KEY)_pull --force -s build/src -d build/generated
	cp build/src/$(SPACE_KEY)_pull.geniespace.json src/$(SPACE_KEY).geniespace.json
	$(PY) scripts/sync_agent.py src/$(SPACE_KEY).geniespace.json --key $(SPACE_KEY) \
	  --from-catalog $(DEV_CATALOG) --from-schema $(DEV_SCHEMA)
	git diff --stat -- resources src

lint:     ; $(PY) scripts/lint_agent.py && databricks bundle validate -t $(T)
deploy:   ; databricks bundle deploy -t $(T)
context:  ; databricks bundle run build_context -t $(T)
smoke:    ; $(PY) scripts/smoke_test.py -t $(T)
gate:     ; $(PY) scripts/benchmark_gate.py -t $(T) --threshold 0.8

# Full promotion, in pipeline order: deploy the warehouse, job and agent, then apply the
# tables and metric views with the job, then test.
release: lint deploy context smoke gate

# First deploy into an empty schema. Genie rejects an agent whose tables don't exist yet,
# so the first deploy stops at the agent; the job builds the tables; the second deploy finishes.
bootstrap:
	-databricks bundle deploy -t $(T)
	databricks bundle run build_context -t $(T)
	databricks bundle deploy -t $(T)

# Part 2: register agents and run the ops jobs.
ops:
	$(PY) scripts/register_agents.py
	cd ops && databricks bundle deploy && databricks bundle run harvest_feedback && databricks bundle run fleet_benchmarks
