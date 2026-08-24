# Coverage & data-quality report

## Sellers excluded from routing
- S07 Rachel Park (US-Central): status=OOO, capacity=18.0, tiers=Strategic
- S11 Anika Reddy (APAC): status=ramp, capacity=0.0, tiers=none

## Territory × tier holes (active sellers only)
- US-Central / Strategic: no active seller — routes fall back to an adjacent tier or cross-region
- APAC is a single point of failure — only S10 Hiro Tanaka is active
- US-Central is a single point of failure — only S06 Diego Morales is active

## Load after routing
- S01 Alex Rivera: 2 accounts (capacity 30)
- S02 Priya Shah: 2 accounts (capacity 40)
- S03 Marcus Lee: 0 accounts (capacity 20)
- S04 Jordan Kim: 1 accounts (capacity 30)
- S05 Sam Chen: 0 accounts (capacity 45)
- S06 Diego Morales: 10 accounts (capacity 35)
- S08 Tom O'Brien: 5 accounts (capacity 25)
- S09 Lena Vogt: 3 accounts (capacity 40)
- S10 Hiro Tanaka: 5 accounts (capacity 50)
- S12 Chris Walsh: 1 accounts (capacity 22)

## Data-quality flags
- 15 of 50 signals could not be matched to any account (see unmatched_queue.csv)
- **All 4 usage_spike signals are unmatched despite payloads claiming is_customer=true** — billing↔CRM linkage is broken; this hides the highest-value signals from sellers
- Name-only matches with domain mismatch (verify before outreach): SIG022
- severity_hint is ignored by scoring: it contradicts payloads (e.g. $200M round tagged 'low', +354% usage spike tagged 'low')