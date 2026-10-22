# BUILD_PLAN — what to build, in what order

Self-contained brief for a coding agent. Read `docs/ARCHITECTURE.md` first; this file is the task list, the architecture doc is the design rationale. Do the tasks in order — each one is shippable on its own.

## Context you need that isn't in this repo

- The source workbook (financial data — NEVER commit it, never push it anywhere): a 25MB `.xlsx` named `09. Sep FY2026 Reforecast Base Case (AI Agent).xlsx`, 83 sheets (≈50 visible). It lives on the owner's Mac at `~/Downloads/` (path may change; ask). Treat it as READ-ONLY input in every test.
- Shape of the model: LOB input templates (AirAsia Flights, Hotel & SNAP LOB Input, LOB input - Flybeyond, Insurance, Media, Duty Free, SNAP + cost templates: Payroll & Personnel, Marketing, ICT, Office Expenses, Fees, Other OPEX, Events, Gifting, Interest, Capex) each tagged with FSLI mapping columns (LOB / Entity / Department / Cost Centre) → rollup via `Mapping ( DO NOT AMEND )` sheet → `PnL Summary` (segmented income statement; rows = P&L lines, columns = months keyed `202601`… with Actual/Estimate/Forecast status rows above).
- Existing partial solutions to replace/absorb: `PREV PNL - 08` (manual paste of last month's output = the broken history mechanism), `Factor Analysis *` sheets (real driver decomposition — Capacity × Load Factor × Share × ATV × Comm rate → volume/price impacts — but ONLY for flights/WANO revenue, PP vs CP).
- Known gotchas in the workbook: month columns are keyed by header strings like `202601` found in the first ~20 rows; row labels live in cols A–F (last non-empty = most specific); some sheets have merged/blank label cells; `#DIV/0!`/`#N/A` error values must be skipped; hidden sheets must be ignored.
- Python env used for the POC: python 3.11 + `openpyxl`, `pandas` (via `uv`). No other deps so far. Keep deps minimal.

## Non-negotiable rules (violating these is a failed build)

1. **No financial data in git. Ever.** `.gitignore` already blocks `*.xlsx/*.csv/*.duckdb/*.parquet/observations/`. Do not weaken it. Test fixtures must be synthetic mini-workbooks you generate yourself (see M0).
2. **Never write to the source workbook.** Read-only in code (`openpyxl` load, no save-back path).
3. **Fail-closed on drift.** A snapshot run where any expected key doesn't resolve must abort loudly, not write partial history.
4. Answers to questions come from computed queries, never generated prose numbers.

## Milestones

### M0 — Synthetic fixture + test harness (do first, ~half a day)
Write `tests/make_fixture.py` that generates a tiny fake workbook with the same *patterns*: 2 LOB input sheets with month-column headers (`202601`-style), a PnL Summary shaped sheet, and a Mapping sheet. Every subsequent milestone's tests run against this fixture, plus optionally against the real file locally (path passed by env var, never committed).

### M1 — Snapshot store (~1 day)
Productionize `scripts/snapshot_poc.py` into a package:
- Schema: `(source_file, snapshot_run, as_of_month, source_sheet, lob, entity, line_label, dimension, value, cell_ref, value_type ∈ {input, calc, result})` — the POC captures everything as undifferentiated values; splitting input-vs-calc comes in M3 (add the column now, default `result`, backfill later).
- Sink: tidy CSV/Parquet under `store/snapshots/<run_id>/`; append-only.
- Semantic keying exactly as the POC does (sheet + label path + month-column *header*, not cell address).
- CLI: `python -m autopilot snapshot <workbook> [--sheet ...] --store ./store`.

### M2 — Diff + changes table (~1 day)
`python -m autopilot diff --from 202609 --to 202610 [--lob Hotel] [--line "Net Revenue"]`:
- Join snapshot table on semantic key across two `as_of_month`s → `(from, to, key, old, new, delta, pct, severity)`.
- Severity heuristic: `pct` beyond configurable thresholds (default: >100% = HIGH, >25% = MED) and sign-flips.
- Persist each diff run to `store/changes/` (append-only).

### M3 — Dependency map + input classification (~2–3 days, judgment-heavy)
Second pass over the workbook with `data_only=False` (formulas):
- Classify every captured cell: hardcoded input vs formula; parse formula references → build an edge list `(input cell → intermediate calc → IS line)` per LOB, grounded by the `Mapping` sheet + FSLI columns.
- Store the map as data: `store/map/edges.csv` (columns: `from_sheet,from_key,to_sheet,to_key,relation`).
- Version it; M1's `value_type` column gets backfilled from this map.
- This is the most fragile piece: expect real-world mess. Log unmapped formula patterns rather than guessing silently.

### M4 — Anomaly report (~1 day)
`python -m autopilot report --month 202610` → plain-language markdown of the diff (top changes by |delta|, HIGH-severity flags first, per-LOB grouping) written to `store/reports/`. Output is Slack-pasteable; wiring to Slack is out of scope for this repo (done by the orchestrator agent).

### M5 — Factor bridge — flights first (~3–5 days)
`python -m autopilot bridge --lob "AirAsia Flights" --line "Net Revenue" --from 202609 --to 202610`:
- Decompose the IS delta into driver contributions using the M3 map + the multiplicative decomposition pattern already proven in the workbook's `Factor Analysis FCST N+1` sheet (Capacity × LF × Share × ATV × Comm-rate: sequential substitution, standard variance-bridge math).
- Output: contributions table + residual ("unexplained") line — never force the bridge to tie out silently; a nonzero residual is itself a finding.
- Get flights working end-to-end first; then replicate per segment (Hotel: transactions × source-mix × ABV × discount; OPEX lines: headcount × rate × one-off × allocation-shift). Each new segment = one bridge spec file, not new engine code.

### M6 — Query layer for the NL agent (~1 day)
DuckDB over the store (`CREATE TABLE ... AS SELECT * FROM read_parquet(...)`), plus a tiny read-only CLI/API: `autopilot sql "SELECT ..." --store ./store`. This is the substrate a text-to-SQL agent (or dashboard) sits on. Keep the store openable by both pandas and DuckDB (Parquet, not DuckDB-only, until proven).

## Explicitly out of scope (for now)

- Web dashboard / Streamlit / FastAPI service (M6 output is the API-shaped seam; UI is a later skin).
- Ingestion forms replacing workbook entry. The team keeps typing into Excel.
- Edit-level provenance (between-snapshot changes are invisible by design; state-level snapshots only).
- Writing anything back to Excel. What-if recalculation engine.
- RAG/embeddings over notes — the notes corpus barely exists yet; revisit when `annotations` accumulate. When it comes, it embeds ONLY text notes, never numeric tables.

## Definition of done (per milestone)

Tests green against the M0 fixture; a manual run against the real workbook (locally, on the owner's machine) produces sane output; no data committed (`git status` clean, `.gitignore` untouched); README status table updated.
