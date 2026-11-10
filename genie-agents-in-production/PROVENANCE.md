# Provenance

- **Authors:** Mitchell Grewer (Databricks Field Engineering), built with Marvin (AI assistant).
- **Origin:** Original work by the authors above, built as generic content from the start. Contains no customer-authored code and nothing derived from customer code.
- **Third-party / Databricks components:** Databricks Asset Bundles, Genie Conversation and benchmark eval APIs (Beta) via `databricks-sdk`, AI/BI dashboards, SQL alerts. Optional: [Context Hub](../context-hub/) from this repo. The fleet dashboard follows the look of [Genie Adoption & Consumption](../genie-adoption-consumption/).
- **Data:** `samples.nyctaxi.trips` (copied into the demo schemas), `system.query.history`, `system.access.audit`, and seeded synthetic fleet history flagged `is_synthetic`.
