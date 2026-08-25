# DESIGN — Fuse (signal-to-seller routing)

## Background 
Signals arrive daily against accounts and
sellers, and nothing decides who acts on what. **This is a prototype that takes raw signals,
scores them, and routes each to the right seller.**

Stripped to its shape, the task is two hops — attach each event to a company, then
attach that company to a person:

```
  ┌───────────────┐        ┌────────────────────┐        ┌────────────────┐
  │    signals    │  ──▶   │      account       │  ──▶   │     seller     │
  └───────────────┘        └────────────────────┘        └────────────────┘
    what happened            who it happened to            who acts on it
```

Neither hop is given. The signal often does not name an account, and the account
file and the seller file describe the world in different vocabularies. This is
how the prototype closes both:

```
 usage_spike      ╮                                                               ╭─▶ seller
 job_change       │  ┌──────────┐    ┌───────┐    ┌──────────┐    ┌───────────┐   │
 intent_topic     ├─▶│ resolve  │ ─▶ │scoring│ ─▶ │  bundle  │ ─▶ │   routing │───┼─▶ seller
 funding_event    │  └──────────┘    └───────┘    └──────────┘    └───────────┘   │
 competitor_eval  ╯   to account      payload      by account      region+tier    ╰─▶ seller
                           │                                            │
                           │ no account match                           │ no eligible seller
                           ▼                                            ▼
                      human review                                  unassigned
                           │                                            │
                           ╰─────▶Assign board — a person places it ◀───╯
```

Each seller ends the run with one ranked queue — P1 to act on today, P2 this
week, P3 to watch — and every item in it carries a named owner.


## Scoring

`score = (base + intensity + fit) × recency`. The value terms are additive so the
result reads as a ledger; recency multiplies so a stale signal cannot ride a high
base to the top.

**base** What kind of signal is this? Some kinds are worth attention before you even read them.
**intensity** (0–30) How strong is this particular one? A traffic spike of 354% is not a spike of 78%.
**fit** (0–17) What does it mean for this account? The same event reads differently for a customer than for a prospect.
**recency** Is there still time? Not "how old is the fact" but "how much of the window to act on it is left".

One signal end to end, with every number traced back to the table it came from
(`scoring_audit.md` prints the same trace in text):

![SIG043 scored, every number traced to its source](docs/scoring-trace.png)

 `severity_hint` gets **zero weight** — it contradicts
its own payloads ($200M round tagged `low`, +354% spike `low`, 0.54 intent `high`).
Accounts bundle into one item, best signal counting fullest; bands are **percentile
cuts, not fixed scores** (P1 the top 20%) because fixed thresholds needed re-tuning
whenever a weight moved. They rank today's available work, not absolute urgency.

## Routing

An account has a **place** and a **size**; a seller covers one place and some
sizes; the router matches them. Place needs no translation — `accounts.csv` calls
the column `region` and `sellers.csv` calls it `territory`, but the five values are
identical. Size is where they disagree: an account states a revenue band
(`$50M-$250M`), a seller states a label (`Enterprise`), and nothing in the data
connects the two. Mapping band to label is **the biggest assumption here**.


![The routing ladder: first rung with a person on it wins, and the rung is recorded](docs/routing-ladder.png)

Capacity is taken to be a count of accounts — one work item is one unit whatever
its size or signal count — and it weights the tie-break rather than capping
anyone. `sellers.csv` never says what the unit is, so that reading is an
assumption; Every step writes its reason into `routes.csv`, so a fallback is
visible rather than absorbed. 

## Failure modes

1. **The identity join.** 15 of 50 signals match nothing, including all four usage
   spikes — whose payloads claim `is_customer: true`, so the billing↔CRM link is
   broken upstream. Volume worsens this long before scoring accuracy matters.
2. **No account-owner concept.** Nine customers route by region + tier as though
   net-new; `accounts.csv` has no owner field, so a churn alert can land on anyone
   but the account's AE.
3. **Load follows territory, not effort.** The router balances inside a cell but
   cannot balance across them. This run three active reps covered the region that
   produced one work item while one rep absorbed ten, and the account base does not
   explain it
4. **Ambiguous semantics.** `job_change.direction` never says what it is relative
   to. We read "departed" as a real departure because the cheaper failure is a
   wasted check, not congratulating someone who has left — it inverts 7 of 11 job
   changes if wrong. One flag, guarded by a test.
5. **Hand-tuned constants** encode my judgment, not evidence.
6. **Static snapshot.** No dedup, no binding capacity, no reassignment on return.

## What I'd do differently

The weights are asserted, not fitted. With the same time again I would log what a
seller actually did with each routed item from the first run, so a week of real
outcomes could replace my judgment instead of sitting behind it.

## Future extensions

Solid is what runs today. Dashed is what could happen for next.

```
                       ┌─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐    ┌─ ─ ─ ─ ─ ─ ─ ─ ─ ┐
                       │ enrich & auto-create │    │  account brief   │
                       └─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘    └─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
                                   ▼                         ▼
  ┌─────────────┐        ┌──────────────────┐        ┌──────────────┐
  │   signals   │  ──▶   │     account      │  ──▶   │    seller    │
  └─────────────┘        └──────────────────┘        └──────────────┘
         ▲                                                   │
         └─ ─ ─ ─ ─ ─ ─ ─  outcome captured ─ ─ ─ ─ ─ ─ ─ ─ ─┘
```


## AI usage

Built with Claude Code. It was strongest at profiling the data fast — the
unroutable signals, the `severity_hint` contradictions, the vocabulary mismatch and
the coverage holes were all found and verified before any code — and at writing the
pipeline and tests once the shape was settled.

**The shape and the judgment calls were mine.** I set the stage boundaries and the
rule that resolution refuses rather than guesses.  And I set the rule
that decides where writing belongs: the dashboard shows state, this document carries
interpretation — a paragraph the model had added to the dashboard, editorialising
about this run's sample size, came back out.

**Deciding what the output had to be drove most of the product.** A team overview so
a manager sees the day's P1 set, who owns each item and where load actually sits;
per-seller queues beneath it; and — because a queue that quietly drops work is worse
than no queue — an Assign board where every unmatched or unassigned signal is
dragged onto a named seller and exported as CSV, so a human decision leaves the
browser instead of dying in it. **The defects surfaced when I questioned the output, not when the model checked its
own work.** is why the worked example now traces every number back to the table it came
from, rather than presenting the answer and asking to be believed.
