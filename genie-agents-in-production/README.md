# Genie Agents in Production: CI/CD and Scaled Observability

A working reference for running Genie agents like a product. Part 1 promotes a Genie agent and its metric view from dev to prod with Databricks Asset Bundles. Part 2 runs a central observability layer over every agent: continuous benchmarks, harvested feedback, system-table telemetry, alerts, and a fleet health dashboard.

**Who it is for:** platform, DevOps, and analytics teams who will own Genie agents once business users depend on them.

**The idea in one line:** individual best practices make one agent good; DevOps and observability keep fifty agents good.

## What's in it

| Path | What it is |
|---|---|
| `databricks.yml` | Bundle variables and the dev and prod targets (schema per target; catalog from your overrides). |
| `resources/warehouse.yml` | The agent's SQL warehouse, one per target (`sql_warehouses` resource). |
| `resources/build_context.job.yml` | Job that runs `src/sql` on the bundle's warehouse with `catalog` and `schema` as SQL parameters. |
| `resources/taxi_agent.genie.yml` | The Genie agent, defined inline so `${var.catalog}` and `${var.schema}` resolve per target. |
| `src/sql/` | The agent's Unity Catalog context as DDL: `01_tables.sql` (demo seed table) and `02_metric_views.sql` (`trip_metrics`). |
| `scripts/` | Pipeline steps: `lint_agent.py`, `smoke_test.py`, `benchmark_gate.py`, `sync_agent.py`, `register_agents.py`. |
| `Makefile` | The pipeline, runnable by hand: `make pull`, `make release T=prod`. |
| `pipelines/azure-pipelines.yml` | Azure DevOps template running the same steps (shown, not required). |
| `ops/` | **A separate bundle owned by the platform team** (`ops/databricks.yml`): ops jobs (harvest, fleet benchmarks, re-benchmark on upstream change), alerts, and the Agent Fleet Health dashboard. Agent teams own agent bundles; one ops bundle watches all of them. |
| `ops/sql/` | Central ops tables and views (`genie_ops` schema). |
| `scripts/demo_bad_change.py` | Demo beat: adds a plausible but wrong instruction ("fares are stored in cents") so the benchmark gate fails. `--revert` restores it. |
| `scripts/seed_synthetic.py` | Seeds 30 days of synthetic fleet history so trends read on a fresh workspace. Every seeded row is flagged `is_synthetic`. |
| `docs/rehearsal-prod-release.txt` | Captured output of a full prod release, as a fallback if a live step is slow. |

## Things we learned building it (CLI 1.21.0, 2026-11-06)

- **Variables only resolve in an inline agent definition.** `${var.catalog}` works in `serialized_space` inside the resource YAML. It fails in a separate `.geniespace.json` referenced by `file_path` (deploy error: `invalid dependency "${var.catalog}"`). So the JSON is the working copy and `scripts/sync_agent.py` writes it inline.
- **`bundle generate genie-space --watch` only works for `file_path` agents.** `make pull` exports by id instead, swaps dev names for variables, and normalizes order, so a pull with no UI change produces an empty diff.
- **Genie rejects an agent whose tables don't exist yet.** Bundles have no table or metric-view resource, so the DDL lives in `src/sql` and the `build_context` job runs it. On a brand-new schema, use `make bootstrap T=<target>` (deploy, run the job, deploy again). After that, `make release` deploys and then runs the job.
- **Folder permissions flow into the agent.** Deployed under `/Workspace/Shared`, every user inherited CAN_MANAGE on the prod agent. Deploy into a restricted folder (the deploying service principal's) so users get CAN_RUN only.
- **Benchmark eval runs are Beta.** `genie-create-eval-run`, `genie-get-eval-run`, `genie-list-eval-results`, `genie-get-eval-result-details`. Each result has an `assessment` (GOOD, BAD, NEEDS_REVIEW).
- **Ratings are readable.** `list-conversations --include-all` plus `list-conversation-messages` return each message's `feedback.rating`. Reading every user's conversations is an admin-level decision; this demo stores questions and ratings, never who asked.
- **The Genie API lists only agents the caller can see.** For full inventory run the harvester as a workspace admin, or use `system.query.history`, where `query_source.genie_space_id` shows every agent that ran SQL.
- **Billing doesn't split Genie spend by agent.** `system.billing.usage` carries `usage_metadata.genie` with surface and channel only. Warehouse time per agent from `system.query.history` is the proxy. Unity Gateway budgets can alert on Genie spend by the `databricks-product = genie` tag (account admin).
- **Metric views protect answers from bad prompt edits.** An instruction saying "fares are stored in cents" did not change any answer, because Genie used the governed `MEASURE(total_revenue)`. A filter instruction ("exclude trips under 1 mile") did break half the benchmarks, and the gate caught it.
- **Table-update triggers need a data commit, and time to settle.** A table-properties change did not fire the trigger. A data write (`UPDATE`) did, about 2 minutes later with `wait_after_last_change_seconds: 60`. A change made right after the trigger was created was missed, so unpause the trigger well before you need it. Triggers can also watch metric views, so a shared metric view change can re-test every agent that uses it.

## Talk track (about 55 minutes)

### Part 1: Genie agents as code (25 to 30 minutes)

1. **Two halves of an agent.** Open the dev agent. The definition (tables, instructions, example SQL, benchmarks) and the context it reads (the metric view, UC comments) have to move together, or prod answers differently from dev.
2. **UI to code.** Edit an instruction in the dev UI, run `make pull`, show `git diff`: one line changed, and the catalog is still `${var.catalog}`.
3. **What changes per environment.** Show `databricks.yml` targets: same files, a schema per target here (a catalog per target works the same way). Then the three kinds of file: resources (`resources/`: warehouse, job, agent), SQL (`src/sql`: tables, metric views), variables (`databricks.yml`).
4. **The pipeline by hand.** Show `pipelines/azure-pipelines.yml`, then run `make release T=prod`:
   - `lint`: standards every agent must meet before deploy (description, 10+ benchmarks, instructions, metric view, no hardcoded names).
   - `deploy`: `bundle deploy -t prod` (warehouse, job, agent).
   - `context`: `bundle run build_context -t prod` (tables, then metric views).
   - `smoke`: ask prod one question.
   - `gate`: run the benchmarks (Beta) and fail under 80%.
5. **A bad change, caught.** `python3 scripts/demo_bad_change.py --apply` adds "always exclude trips shorter than 1 mile", which sounds reasonable but changes every count. `make deploy gate T=dev` fails. (A "fares are stored in cents" instruction did NOT break it: Genie answered from the governed metric view. Business logic in a metric view protects answers from bad prompt edits.) Revert with `--revert`. (The standards check also blocks hardcoded catalog names; we tripped it ourselves while building this.)
6. **Prod is locked.** Users have CAN_RUN; only the deployer manages it. Mention the Shared-folder trap.

### Part 2: Scale and observability (25 to 30 minutes)

Framing: what one developer can do, vs what only the platform can do.

| One developer, one agent | The platform, every agent |
|---|---|
| Runs benchmarks in the UI when they remember | Benchmarks on every deploy, nightly, and when an upstream table changes |
| Reads thumbs-down in one agent | Feedback from every agent in one table, with alerts |
| Knows their own agent's tables | Knows which agents to re-test when a shared table changes |
| Follows standards by habit | Standards checked before deploy |
| Can't see agents nobody manages | Inventory of every agent, managed or not |

1. **Fleet Health dashboard.** Scorecard, then point at Fleet Maintenance: healthy for weeks, then its pass rate drops and thumbs-down climbs five days ago (seeded story: an upstream table change).
2. **Upstream change, live.** Write to the prod `trips` table; the `genie-ops-benchmarks-on-upstream-change` job fires about 2 minutes later and re-benchmarks only agents that read that table.
3. **Feedback loop.** Thumbs-down a prod answer, run the harvest job, show it in the Review queue. A person decides whether it becomes a benchmark or an instruction fix, and it goes back through a pull request. Benchmarks measure; they don't teach.
4. **Coverage.** Agents in use that nobody manages, found from `system.query.history`.
5. **Alerts.** Four alerts in the same bundle: pass rate, thumbs-down, SQL failures, prod edited outside the pipeline.
6. **Context quality (2 minutes).** Context Hub, pointed at the prod demo schema: the `trips` table the agent reads has no column descriptions. Propose them (or take an AI draft), approve both steps, apply. Then run the fleet benchmarks: the metadata change went through a governed path, and the agent was re-tested. Context Hub is a reference app you adopt and own, not a product.
7. **Cost, honestly.** Spend by surface from billing; warehouse time per agent as a proxy; Unity Gateway budget alerts for Genie spend.

## Run sheet

Before the session:
- `make release T=prod` once (warms the warehouse, confirms the gate).
- `python3 scripts/seed_synthetic.py --taxi-prod-space-id $(python3 scripts/space_id.py -t prod)` if the history is older than a few days.
- Unpause the upstream trigger at least 15 minutes before the session: `cd ops && databricks bundle deploy --var upstream_trigger_pause=UNPAUSED`. Pause it after.
- Open tabs: dev agent, prod agent, Fleet Health dashboard, Jobs list filtered to `genie-ops`.

If a job fails with `OSError: [Errno 5] Input/output error` reading a script from workspace files, rerun it; we saw this once and the retry passed.

Live upstream change:
```
UPDATE <catalog>.<schema>.trips SET fare_amount = fare_amount WHERE pickup_zip = 10001   -- value-neutral data commit
```

## Setup

Prerequisites: Databricks CLI 1.21+, Python with `databricks-sdk==0.108.0` (from your approved package index), an existing catalog with the dev and prod schemas, and permission to create SQL warehouses.

1. Set your values per target, without editing committed files: write `.databricks/bundle/<target>/variable-overrides.json` (git-ignored) in this folder for `dev` and `prod`, and in `ops/` for `prod`, for example `{"catalog": "my_catalog", "ops_catalog": "my_catalog", "ops_warehouse_id": "<id>"}`. The ops bundle also needs `upstream_tables`. Or pass `--var` on every command.
2. `make bootstrap T=dev` and `make bootstrap T=prod` the first time; `make release T=<target>` after that.
3. `python3 scripts/apply_context.py -t prod --ops` (ops tables and views).
4. `python3 scripts/register_agents.py`.
5. `cd ops && databricks bundle deploy` (ops jobs, alerts, dashboard; set `upstream_tables` from the registry).
6. Optional: `scripts/seed_synthetic.py` for demo history.
7. Optional: Context Hub governing the prod demo schema: create a Lakebase project (`databricks postgres create-project context-hub`), then `scripts/deploy_context_hub.sh <profile> <warehouse_id> <catalog> genie_demo_prod context-hub`.

## Cleanup

- `databricks bundle destroy -t prod` and `-t dev` (agents), then `cd ops && databricks bundle destroy` (jobs, alerts, dashboard).
- Context Hub: `databricks apps delete context-hub`, then drop its Postgres tables by name (see the unbranded Context Hub DEPLOY.md) and delete the Lakebase project.
- Drop tables and views by name: `trips`, `trip_metrics` in each demo schema; `agent_registry`, `space_inventory`, `benchmark_runs`, `benchmark_results`, `feedback` and the `v_*` views in the ops schema. Then drop the empty schemas. Never `CASCADE`.

## Credits

Built by Mitchell Grewer (Databricks Field Engineering) with Marvin. The fleet dashboard follows the look of the Genie Adoption & Consumption dashboard by Mitchell Grewer and Sumit Prakash.
