# Changes in the Arch build branch

Adds one company (Arch Insurance) and carries forward the shared-generator
fixes made while building it. Everything below is relative to the repo's
previous `main`.

## New
- `ARCH` config in `scripts/company.py`: underwriting-portfolio command center
  + premium / rate / loss-trend what-if, 7 lines of business, Q3 statement data.
- `sql/cat_appetite.sql`: hero-plugin source (net PML vs board appetite by
  cat / RDS scenario). Plugin lives in `dkotenko1/plugins`
  (`arch-cat-appetite-board`).
- `assets/arch_logo_{white,navy,blue}.datauri.txt` (from the company's own SVGs).

## Shared generator changes
- `_STMT_SOURCES` registry: a company's PDF statement is data, no per-company
  branch in `statement_activity_sql` / `rewards_summary_sql` / `account_summary_sql`.
- Config keys: `scale` (headline unit override), `money_dp`, `insight_margin`
  (wording of the formula insight), `logo_prefix`; `CARD_UNITS = "count"`;
  `statement_opt()` for optional statement labels.
- `loan_book.sql` / `scenario_base.sql`: 6dp instead of cents; scenario base
  fans out across states like the loan book so page 2 ties to page 1.
- `brand.py`: `ensure_white_readable()` keeps white KPI text legible on light
  brand accents.
- `sigmaapi.py`: CLI mappings for workbook/report page listing and export.
- `build_sofi.py` / `build_statement.py`: API-drift and rendering fixes carried
  from recent builds (see the diff).

## Gotchas found
- Apostrophes in config strings (workers' comp, Lloyd's) break the generated
  product-card SQL; avoid them until escaping is added.
- `kpi_units` is a MaxIf over state-month rows: it is a peak-state figure,
  not a total.
- sofi/delta logo assets are not in the repo, so those two cannot be built
  from a clean clone.

## Agent actions and workflows (second PR)
- Scenario Copilot now has a chat rail on the modeler page and tools to create a
  scenario, set drivers for one line, submit and approve; Appetite Advisor
  (config key `advisor`) reads the hero table and saves remediation proposals.
- Every write tool is `requiresApproval`; agents verify the write target after
  approve or skip.
- Visible Scenario audit log and Remediation proposals tables.
- Companion docs: `COMPANION-SKILLS.md`, `AGENT-ACTIONS.md`, `scripts/preflight.sh`.

## Plugin SDK loading (found 2026-10-21)
- The authoring pattern in HANDOFF section 9 loaded the SDK without React and looked up
  `window.sigmaComputing.plugin.client`. No SDK version defines that global and the browser
  build throws without a React global, so a plugin written this way always falls back to
  sample data and never binds. HANDOFF now loads pinned React + SDK and reads
  `window.SigmaPlugin.client`.
- `scripts/plugin_harness/`: a host simulator for testing a plugin's data path without a
  Sigma org. Other plugins in `dkotenko1/plugins` using the old pattern are NOT changed here.
