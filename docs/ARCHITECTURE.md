# Architecture — Finance Model Autopilot

Design for turning a monthly, overwrite-in-place forecast workbook into a queryable, change-tracked, driver-attributed system — while the finance team's workflow stays exactly as it is today.

---

## 1. Source of truth (Layer 1)

The workbook (input templates per LOB → calculation chains → segmented P&L rollup via a cost-centre/account mapping table) stays **untouched**.

Cardinal rule: **the pipeline is a reader, never a writer.** Automation cannot corrupt the model because it never edits it. (If form-based ingestion is added later, it slots in as an *alternate source* without changing any layer above.)

Secondary sources: PIC status trackers, free-text notes ("refer to email on 3 Sep…"), and — most importantly — human annotations answering *why* a flagged change is intentional.

## 2. Extraction (Layer 2)

A snapshot job runs at a fixed trigger (month-close minimum; per-save once proven). It reads the workbook and emits one canonical row per observation:

```
(snapshot_id, source_file, as_of_month, source_sheet, lob, entity,
 line_label, dimension, value, cell_ref, value_type ∈ {input, calc, result})
```

### Keying — the most important durability decision

Rows are identified by **semantic key** — `(sheet, label path, LOB, month-column header)` — never by raw cell address.

- `$C$19` breaks when someone inserts a column; "Hotel & SNAP LOB Input / row 'Agoda mix%' / column headed 2026-06" survives.
- This is why month-vs-month diffs don't silently mis-align.

### Dependency map

Built **once** by an analysis pass over the workbook: walk formulas, classify input vs calculated cells, trace which inputs feed which IS lines per LOB. Stored as *data* (it's a table), versioned, re-derived whenever the drift guard fires.

This map is the system's brain — it is what converts "Fees moved +RM1.6m" into "because the ICT assumption changed in the Flights template."

### Layout-drift guard (fail-closed)

Before writing a snapshot, verify every expected key resolved. Any unresolved key → **stop and flag a human**; never write a partial snapshot. Partial history is worse than no history.

## 3. Store (Layer 3)

DuckDB file (or Parquet folder) on SharePoint/OneDrive — a single file, no server. Scale sanity: ~20 templates × hundreds of lines × 12 months × a few scenario versions/year ≈ tens of thousands of rows per year. A server database is overkill; a folder of CSVs works until ad-hoc querying is wanted, at which point DuckDB is `CREATE TABLE AS SELECT * FROM files`.

Three tables:

1. **`snapshots`** — full state per run. **Append-only; never updated, never deleted.** Month-vs-month = same table joined on two `as_of_month` values.
2. **`changes`** — materialized diff per run: `(from_month, to_month, key, old, new, delta, pct, severity)`. Materializing turns "what changed" into a `SELECT`; feeds anomaly detection (e.g. `pct > 300%` → the June-transaction-spike class of event).
3. **`annotations`** — the human "why," joined to `changes` on key. Small, boring, and the table that upgrades the system from *what moved* to *why it moved*. Ships in v1: the why-capture habit takes months to grow.

Stance: **store facts and derived facts, never opinions.** Factor-analysis results are a pure function of two snapshots — compute them at query time (Layer 4), don't persist them.

## 4. Reasoning (Layer 4)

Exactly four tools, each dumb and testable. One agent (LLM) calls them.

| Tool | What it does |
|---|---|
| `query(filters)` | Exact rows/numbers from the store (SQL behind it). |
| `diff(a, b, lob?, line?)` | The change set between two months. |
| `bridge(lob, line, a, b)` | Walk the dependency map; decompose the delta into named driver contributions (volume × price, mix, rate, headcount × cost, allocation-shift — the decomposition patterns repeat). Generalizes what in a real model exists only for one segment's revenue line. The only genuinely hard component; build segment by segment. |
| `search_notes(query)` | **The only RAG.** Embeddings over unstructured islands only: status-tracker notes, annotations, related comms. Deliberately separate so nobody ever semantic-searches a number. |

Invariant: **answers are computed, language is generated.** The agent never estimates a figure in prose; every number in every answer comes from a tool call. This is what makes the output trustworthy for finance.

### Why plain RAG over the spreadsheet is the wrong pattern

- Numbers don't embed: `8,336` and `1,611` are near-identical vectors in context.
- Retrieval confuses adjacent month-columns and sibling tabs; exactness is required and similarity can't provide it.
- Retrieval can't aggregate ("total OPEX across LOBs in Q2" exists in no chunk).
- RAG answers "what does the sheet say," never "why did it move."

The correct reference is **structured store + text-to-SQL / tool-calling agent, with RAG restricted to notes.**

## 5. Interface (Layer 5) — staged, cheapest first

- **v1 — Slack anomaly report, zero UI.** Scheduled job runs diff + bridge, posts plain-language summary: *"Hotel June transactions +716% vs May (1,611→8,336) — UNUSUAL, confirm intended. 14 other changes: […]. Bridges attached."* Team replies "confirmed / bulk deal / oops" → replies write into `annotations`. The workflow *is* the data-capture loop.
- **v2 — "ask the agent" as the dashboard.** The same agent in Slack/DM answers NL questions against the store. No web UI exists yet and the promised experience is already live. This phase discovers the *real* query patterns for free.
- **v3 — web dashboard, only after v2 proves demand.** Thin shell (React/Streamlit) over the four tools, which are already API-shaped (FastAPI over the store + bridge engine). v3 is a skin, not a rebuild.

## Human/automation boundary

Automation owns 100% of capture, tracking, attribution, and repair of extraction breakage. Humans own exactly one thing: the 30-second *why* annotation on flagged changes. That is a feature, not a gap — the knowledge lives in people's heads and no model can reconstruct it. The finance team touches no code, no database, no git.

## Known limits

- An assumption edited *between* snapshots leaves no trace (state-level, not edit-level provenance). If edit-level provenance matters, move the input layer to something with native edit history (e.g. a Google Sheet per LOB — every edit logged, zero technical lift).
- What-if recalculation ("if commission drops 0.5pp…") requires the model logic reimplemented as a tool — later tier, after read-only proves out.

## Build order & effort

| Step | Effort | Notes |
|---|---|---|
| L2 snapshot extraction POC | days | Proof against a real workbook |
| L3 store + schema | days | CSV/Parquet first; DuckDB flip is one line |
| Dependency map | days, judgment-heavy | Input-vs-calc classification in messy formulas |
| `diff` + anomaly report (v1 Slack) | ~1 day after L3 | First user-visible value |
| `bridge` engine | multi-week | Flights-style decomposition generalized, segment by segment |
| `annotations` loop | small | Ship with v1, not later |
| Web dashboard (v3) | after v2 demand | Skin only |

## One-line summary

Don't build a RAG over the Excel. Build a month-snapshot store with a dependency map, put a tool-calling agent on top, RAG only the notes, and ship the first interface as a Slack message. The dashboard is the last 10%.
