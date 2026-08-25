# DESIGN — Fuse, signal-to-seller routing

**Problem.** Signals arrive daily — usage spikes, job changes, intent
topics, funding rounds, competitor evaluations — against 300 accounts and 12
sellers, and nothing decides who acts on what.

```
signals.csv ──▶  resolve   ──▶  score  ──▶   bundle   ──▶ route   ──▶     queues/
                exact only     payload     by account     region         per seller
                               points                     + tier
                    │                                       │                │
                    │ no exact match                        │                │
                    ▼                                       ▼                ▼
              human review                             unassigned     manually assign
                unmatched
```

The straight path is routine; the branches are the design. Where identity or
coverage is uncertain the system stops rather than guessing, says so, and hands the
work to a person to place. 

## Principles

1. **Every number is a business judgment** — all of them in `config.py`, with the
   reasoning beside them.
2. **Rank and explain together.** A number nobody can audit is a number nobody
   trusts, and a seller who distrusts the queue stops opening it.
3. **Refuse rather than guess.** Wrong-company outreach costs more than a delay.
4. **The data's defects are deliverables.** What the system *cannot* do is often
   the most useful thing it can say.
5. **Sellers think in accounts**, so signals bundle per account.

## Scoring

`score = (base + intensity + fit) × recency`. The value terms are additive so the
result reads as a ledger; recency multiplies so a stale signal cannot ride a high
base to the top.

**base** is an actionability prior — usage 40 > competitor 35 > funding 30 > job
change 25 > intent 20 — so "real usage beats third-party intent" is stated, not
buried in a normalizer. **intensity** (0–30) reads the payload and nothing else.
**fit** (0–17) is mostly the `(is_customer, signal_type)` matrix, because that pair
decides *which play this is* — `churn risk` (+12), `displacement` (+8), `expansion`
(+10) — and the play's name is what the seller sees. **recency** uses per-type
half-lives of 14d to 45d: what decays is the *action window*, not the fact.

One signal end to end, as `scoring_audit.md` prints it:

```
SIG043  Solace Build (A251) · EMEA · $50M–$250M · prospect · AI-Native
        {"competitor":"Anyscale","action":"comparison_search","days_since_last_signal":19}

  base       competitor_evaluation                      35.0
  intensity  1.00 action × 0.68 freshness × 30          20.5
  fit        displacement 8 + ARR 2 + AI-Native 2       12.0
                                           subtotal     67.5
  recency    1.1 days old, 14-day half-life           ×0.9477
                                              score     64.0   → P1, Tom O'Brien
```

Components round before the total, so re-doing that arithmetic lands on the printed
score; a test checks all 50. `severity_hint` gets **zero weight** — it contradicts
its own payloads ($200M round tagged `low`, +354% spike `low`, 0.54 intent `high`).
Accounts bundle into one item, best signal counting fullest; bands are **percentile
cuts, not fixed scores** (P1 the top 20%) because fixed thresholds needed re-tuning
whenever a weight moved. They rank today's available work, not absolute urgency.

## Routing

Territory is the account's region. Tier comes from ARR band because `segment_hint`
(AI-Native / Enterprise-Expansion) shares no vocabulary with seller tiers
(Strategic / Enterprise / Mid-Market) — **the biggest assumption here**, isolated
in one dict.

```
account (region, ARR band)
 │  tier = f(ARR band)
 ▼
 active seller in (region, tier)?  ──yes──▶  assign · lowest load ÷ capacity
 │ no
 adjacent tier, same territory?    ──yes──▶  assign · reason names the fallback 
 │ no
 same tier, another US region?     ──yes──▶  assign · reason names the crossing 
 │ no
 unassigned ──────────────────────────────▶  coverage_report.md                  
```

Every step writes its reason into `routes.csv`, so a fallback is visible rather
than absorbed. OOO and ramping sellers are excluded from every cell — the three
bracketed fallbacks are all US-Central accounts big enough to be Strategic, in the
one territory whose Strategic rep is out.

## Failure modes

1. **The identity join.** 15 of 50 signals match nothing, including all four usage
   spikes — whose payloads claim `is_customer: true`, so the billing↔CRM link is
   broken upstream. Volume worsens this long before scoring accuracy matters.
2. **No account-owner concept.** Nine customers route by region + tier as though
   net-new; `accounts.csv` has no owner field, so a churn alert can land on anyone
   but the account's AE.
3. **Ambiguous semantics.** `job_change.direction` never says what it is relative
   to. We read "departed" as a real departure because the cheaper failure is a
   wasted check
4. **Hand-tuned constants** encode my judgment, not evidence.
5. **Static snapshot.** No dedup, no binding capacity, no reassignment on return.

## What I'd do differently

1. Put an identity service ahead of resolution and raise the billing↔CRM break as its own
alert. 
2. Persist state so capacity binds for the unassigned signals. 
3. Integrate with CRM or Slack that can create accounts directly.

## AI usage

Built with Claude Code. It was strongest at profiling the data fast — the
unroutable signals, the `severity_hint` contradictions, the vocabulary mismatch and
the coverage holes were all found and verified before any code — and at writing the
pipeline and tests once the shape was settled.

**The shape was mine.** I set the stage boundaries and the rule that resolution
refuses rather than guesses, and I chose the additive-ledger scoring form over the
model's first proposal, a three-factor multiplication that buried the ranking
levers inside normalization constants. Deciding what the output had to be drove
most of the product: a **team overview** so a manager sees the day's P1 set, who
owns each item and where load actually sits; per-seller queues beneath it; and —
because a queue that quietly drops work is worse than no queue — an **Assign
board** where every unmatched or unassigned signal is dragged onto a named seller
and exported as CSV, so a human decision leaves the browser instead of dying in it.
Region is on every card there because it is the only routing dimension those
signals still have. I also cut the model's per-card "why this was routed to you"
note: sellers don't need the rationale, so it lives in `routes.csv` for RevOps.

Three corrections were mine as well: recency half-lives set to half what they
should have been, which dropped the sample's strongest signal out of the top eight;
a `fit` matrix defining only the customer rows, silently scoring 25 of 35 signals
at zero; and a ledger printed at a precision where its own arithmetic didn't close.


