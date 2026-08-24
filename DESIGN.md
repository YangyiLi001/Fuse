# DESIGN — Fuse, signal-to-seller routing

**Problem.** Fifty raw GTM signals a day — usage spikes, job changes, intent
topics, funding rounds, competitor evaluations — against 300 accounts and 12
sellers, and nothing decides who acts on what. Fuse scores each signal from its
payload, bundles them by account, routes each account to a seller, and writes a
queue the seller works top-down. One command, stdlib only. Outputs are listed in
`README.md`.

## Principles

1. **Every number is a business judgment — keep them in one file.** `config.py`
   holds every weight and assumption with its reasoning beside it: an assumption
   log, not a settings file.
2. **Rank and explain together.** Every score prints as a ledger
   (`30 base + 30 intensity + 7 fit → ×0.86 recency = 57.5`); every route records
   why. A number nobody can audit is a number nobody trusts.
3. **Refuse rather than guess.** Identity matching is exact-only; wrong-company
   outreach costs more than a day's delay, so anything uncertain goes to a human.
4. **The data's defects are deliverables.** What the system *cannot* do is often
   the most useful thing it can say.
5. **Sellers think in accounts.** Three signals about one company arrive as one
   task.

## Scoring

```
score = (base_type + intensity + fit) × recency
```

The additive part is an auditable ledger; recency is a multiplicative gate, so a
stale signal cannot ride a high base to the top.

- **base_type** — actionability prior: usage 40 > competitor 35 > funding 30 >
  job change 25 > intent 20. Real usage beats third-party intent, stated rather
  than buried in a normalizer.
- **intensity (0–30)** — payload only: lift and volume, round size, intent score,
  competitor action × freshness, seniority × direction.
- **fit (0–17)** — mostly the `(is_customer, signal_type)` matrix, because that
  pair decides *which play this is*: `churn risk` (+12), `displacement` (+8),
  `expansion` (+10). Every cell is named and shown to the seller.
- **recency** — per-type half-lives, 14d to 45d. What decays is the *action
  window*, not the fact.

`severity_hint` gets **zero weight**: it contradicts its own payloads — a $200M
round tagged `low`, a +354% spike tagged `low`, a 0.54 intent tagged `high`.

Accounts bundle into one item, the best signal counting fullest. Bands are
**percentile cuts, not fixed scores** (P1 the top 20%), because fixed thresholds
needed re-tuning whenever a weight moved; the trade-off is that they rank today's
available work, not absolute urgency.

## Routing

Territory is the account's region. Tier comes from ARR band because `segment_hint`
(AI-Native / Enterprise-Expansion) shares no vocabulary with seller tiers
(Strategic / Enterprise / Mid-Market) — **the biggest assumption in the system**,
isolated in one dict.

Candidates are active sellers covering that (territory, tier); ties break on load
÷ capacity. Fallbacks, each recorded: adjacent tier in-territory → same tier
across US regions → unassigned. OOO and ramping sellers receive nothing, and the
gaps that creates surface in `coverage_report.md` as a finding.

## Failure modes

1. **The identity join.** 15 of 50 signals match no account, including all four
   usage spikes — whose payloads claim `is_customer: true`, so the billing↔CRM
   link is broken upstream. This worsens with volume long before scoring accuracy
   matters.
2. **No account-owner concept.** Nine existing customers route by region + tier
   as though net-new, because `accounts.csv` has no owner field — so a churn
   alert can land on anyone but the account's AE.
3. **Ambiguous semantics.** `job_change.direction` never says what it is relative
   to. We read "departed" as a real departure because the cheaper failure is a
   wasted check, not congratulating someone who left; it inverts 7 of 11 signals
   if wrong. One flag, guarded by a test.
4. **Hand-tuned constants** encode my judgment, not evidence.
5. **Static snapshot.** No memory across runs: no dedup, no real capacity limit,
   no reassignment when a rep returns.

## What I'd do differently

Log seller outcomes per routed signal and fit the weights instead of asserting
them. Put an identity service ahead of resolution and raise the billing↔CRM break
as its own alert. Persist state so capacity becomes a real constraint. Deliver
into CRM or Slack rather than files.

## AI usage

Built with Claude Code. Strongest at profiling the data fast — the unroutable
signals, the `severity_hint` contradictions, the vocabulary mismatch and the
coverage holes were all found and verified before any code — and at generating
the pipeline and tests once the design was settled. It needed real steering three
times: its first scoring model hid the ranking levers inside normalization
constants; its recency half-lives were half what they should have been, dropping
the strongest signal in the sample out of the top eight; and its `fit` matrix
defined only the customer rows, silently scoring 25 of 35 signals at zero. Each
was caught by interrogating the output, not by reading the code.

*Derivations, rejected alternatives and the full data audit: `NOTES.md`.*
