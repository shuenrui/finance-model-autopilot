# Finance Model Autopilot

Month-vs-month change tracking and driver attribution for segmented financial forecast models — without touching the model itself.

## The problem

A forecast model is a set of input templates (per line of business) full of calculations that roll up into a segmented income statement. Every month, new numbers are typed into the *same cells*, destroying last month's assumptions. Consequences:

- "What changed month vs month?" becomes an archaeology dig.
- A fluctuation on the P&L can't be traced to the assumption edit that caused it.
- Teams cope by manually pasting last month's output P&L into a "prev" sheet — one-deep, stale-prone, and blind to input-level changes.
- Factor analysis (volume/price/mix bridges) is hand-built for one or two segments at best.

## The principle

**The model is a reader's source, never a writer's target. History is captured by snapshotting, not by discipline.** Every month's full state — inputs, calculated lines, IS results — becomes an immutable, semantically-keyed record. After that, "what changed" and "why it moved" are queries, not memory tests.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ 5. INTERFACE  Slack anomaly report · NL query agent ·       │
│              (later) web dashboard                          │
├─────────────────────────────────────────────────────────────┤
│ 4. REASONING  Agent tools: query store · dependency map ·   │
│              factor-bridge calc · RAG over notes            │
├─────────────────────────────────────────────────────────────┤
│ 3. STORE      DuckDB / Parquet: snapshots + changes +       │
│              annotations tables (append-only)               │
├─────────────────────────────────────────────────────────────┤
│ 2. EXTRACT    Monthly snapshot job · layout-drift guard ·   │
│              dependency map (built once, versioned)         │
├─────────────────────────────────────────────────────────────┤
│ 1. SOURCE     The workbook (untouched) · PIC inputs ·       │
│              free-text notes                                │
└─────────────────────────────────────────────────────────────┘
```

Details in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Status

| Component | State |
|---|---|
| Architecture spec | ✅ this repo |
| L2 snapshot extraction (POC) | 🚧 `scripts/snapshot_poc.py` |
| L3 store (DuckDB schema) | ⬜ |
| L2 dependency map | ⬜ |
| L4 bridge engine | ⬜ |
| L5 Slack anomaly report | ⬜ |

**Not in this repo:** the actual workbook or any financial data. Data stays on the private shared drive; this repo is the pipeline spec and code only.
