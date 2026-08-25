# Fuse — signal-to-seller routing

Takes raw GTM signals, scores them from their payloads, bundles them per
account, and routes each bundle to the right seller — with an auditable score
ledger and a human-review queue for everything that can't be routed safely.

## Run

No dependencies and no virtualenv — Python 3.10+ standard library only. Use
`python3`; on macOS and most Linux distributions there is no bare `python`.

```bash
python3 -m signal_router                    # reads data/, writes output/
python3 -m signal_router --data-dir data --out output
python3 tests/test_pipeline.py              # conservation + behaviour checks
```

## Inputs

`data/accounts.csv`, `data/signals.csv`, `data/sellers.csv` — as provided
(converted from the attached xlsx, content unchanged).

## Outputs (`output/`)

A sample run is committed so the results can be read without running anything;
re-running overwrites it in place.

| File | Audience | What it is |
|---|---|---|
| `queues/S0X_<name>.md` | each seller | their accounts, sorted by priority, with why-now facts, a score ledger, and a suggested opener |
| `dashboard.html` | sellers / managers | single static page, four tabs: team overview, seller queues, unmatched queue, and an **Assign** board for triaging what the router could not place |
| `routes.csv` | RevOps | flat audit table: every routed signal with score breakdown and routing reason |
| `unmatched_queue.csv` | SDR / RevOps | every signal that matches no CRM account, with a recommended action and close-name suggestions — never an assignment |
| `coverage_report.md` | RevOps | territory holes, single points of failure, post-routing load, data-quality flags |
| `scoring_audit.md` | reviewer | flat audit table: every signal's payload → score components → owner, grouped by type; bundle → seller with the aggregation math |

## The Assign board

The `Assign` tab lists everything with no owner — unmatched signals plus any account
the router could not place — and lets a manager drag each card onto a seller (or pick
one from the card's dropdown). Choices persist in that browser via `localStorage`, so
they survive a reload but are **not** shared with anyone else and are invisible to the
pipeline.


## Where the knobs are

Everything tunable lives in `signal_router/config.py`: scoring weights,
per-type recency half-lives, the ARR→tier mapping, and the semantic
assumptions (e.g. how `job_change: departed` is interpreted). Change a value,
rerun, diff the output. See `DESIGN.md` for why each default is what it is.
