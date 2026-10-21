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
