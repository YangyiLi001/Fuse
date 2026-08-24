"""All tunable numbers and semantic assumptions in one place.

This file doubles as the assumption log referenced by DESIGN.md: every value
here is a business judgment, not an implementation detail. Change a number,
rerun, diff the output.
"""

# ---------------------------------------------------------------------------
# Semantic assumptions (things a clarifying answer from the team could flip)
# ---------------------------------------------------------------------------
ASSUMPTIONS = {
    # signals.csv job_change: direction="departed" carries a new_title, which is
    # ambiguous. Default reading: the person LEFT this account (churn risk on
    # customers, dead contact on prospects). Flip to False to read "departed
    # previous_company and joined this account" (opportunity, same as arrived).
    "DEPARTED_MEANS_LEFT_ACCOUNT": True,
    # severity_hint contradicts the payloads (a $200M Series A tagged "low",
    # a +354% usage spike tagged "low"), so it gets zero weight.
    "SEVERITY_HINT_WEIGHT": 0.0,
    # Signals that can't be exactly matched to an account go to a human-review
    # queue. We never fuzzy-assign ("queue" | "fuzzy" is intentionally NOT
    # implemented — wrong-account outreach is worse than delayed outreach).
    "UNMATCHED_POLICY": "queue",
}

# accounts.csv segment_hint (AI-Native / Enterprise-Expansion) shares no
# vocabulary with sellers.csv tiers (Strategic / Enterprise / Mid-Market),
# so tier is derived from ARR band. Biggest single assumption in the system.
TIER_FROM_ARR = {
    "$250M+": "Strategic",
    "$50M-$250M": "Enterprise",
    "$10M-$50M": "Mid-Market",
    "$1M-$10M": "Mid-Market",
    "<$1M": "Mid-Market",
}

# When the exact (territory, tier) cell has no active seller, fall back to an
# adjacent tier in the same territory before crossing US regions.
ADJACENT_TIERS = {
    "Strategic": ["Enterprise"],
    "Enterprise": ["Strategic", "Mid-Market"],
    "Mid-Market": ["Enterprise"],
}
US_REGIONS = ["US-East", "US-West", "US-Central"]

# ---------------------------------------------------------------------------
# Scoring: score = (base + intensity_pts + fit_pts) * recency_decay
# ---------------------------------------------------------------------------
SCORING = {
    # Type prior: how actionable a signal of this type is, before looking at
    # the payload. Real product usage > active competitive motion > fresh
    # budget > people moves > third-party intent data.
    "base": {
        "usage_spike": 40,
        "competitor_evaluation": 35,
        "funding_event": 30,
        "job_change": 25,
        "intent_topic": 20,
    },
    "intensity_max_pts": 30,
    # Normalization constants — these ARE the cross-type ranking levers.
    "usage": {"pct_full_score": 300, "log10_req_full_score": 5.0,
              "pct_weight": 0.6, "volume_weight": 0.4},
    "funding": {"amount_full_score_musd": 150},
    "intent": {
        # Topics closest to Fireworks' ICP get a bump (capped at 1.0 overall).
        "icp_topic_boost": 1.1,
        "icp_topics": {
            "gpu alternatives",
            "llm inference cost optimization",
            "model serving latency",
            "open-source llm hosting",
        },
    },
    "competitor": {
        "action_weight": {
            "comparison_search": 1.0,
            "benchmark_download": 0.9,
            "docs_read": 0.7,
            "pricing_page_visit": 0.6,
        },
        # Engagement freshness: 1 - days_since_last_signal/60, floored.
        "days_scale": 60,
        "freshness_floor": 0.4,
    },
    "job_change": {
        "seniority_weight": {
            "cto": 1.0, "head": 0.9, "vp": 0.9,
            "chief": 0.85, "director": 0.8, "staff": 0.6,
        },
        "default_seniority": 0.7,
        "arrived_factor": 1.0,
        "departed_customer_factor": 1.0,   # churn risk — stays urgent
        "departed_prospect_factor": 0.4,   # the contact is simply gone
    },
    # Account-context points added to the base+intensity sum. The
    # (is_customer, signal_type) pair decides which sales play this is, so the
    # matrix is stated in full — an earlier version defined only the customer
    # rows, which silently scored every prospect interaction at zero and made
    # "prospect is comparing us to Anyscale" worth the same as "prospect read a
    # G2 page". ARR is deliberately light here: it already drives tier in
    # routing, and within one seller's queue it mostly cancels out.
    "fit": {
        # (is_customer, signal_type) -> (pts, play name shown to the seller)
        "customer_type_pts": {
            (True,  "competitor_evaluation"): (12, "churn risk"),
            (False, "competitor_evaluation"): (8, "displacement"),
            (True,  "usage_spike"): (10, "expansion"),
            (False, "usage_spike"): (0, "usage without an account (data gap)"),
            (True,  "funding_event"): (8, "budget unlocked"),
            (False, "funding_event"): (7, "new budget"),
            (True,  "job_change"): (5, "champion change"),
            (False, "job_change"): (3, "new decision maker"),
            (True,  "intent_topic"): (3, "expansion research"),
            (False, "intent_topic"): (1, "early research"),
        },
        "arr_pts": {"$250M+": 3, "$50M-$250M": 2, "$10M-$50M": 1,
                    "$1M-$10M": 0, "<$1M": 0},
        "ai_native_pts": 2,
    },
    # Recency: exponential decay with a per-type half-life. What decays is the
    # action window, not the fact: a customer whose traffic quadrupled is still
    # worth a call three days later, so these are deliberately generous. Earlier
    # values (7/10/14/21/30) were roughly half these and pushed the single
    # strongest signal in the sample (SIG021, +354%) out of the top 8 purely on
    # a 3-day age gap.
    "half_life_days": {
        "usage_spike": 14,
        "competitor_evaluation": 14,
        "intent_topic": 21,
        "funding_event": 30,
        "job_change": 45,
    },
    # Multi-signal accounts: best signal counts fully, the rest add evidence.
    "bundle": {"second_weight": 0.30, "third_weight": 0.15,
               "competitor_plus_intent_bonus": 5},
    # Priority bands are percentile cuts, not fixed scores: P1 is the top 20%
    # of a run, P2 the next 30%. Absolute thresholds had to be re-tuned every
    # time a weight moved, which made the bands meaningless as a unit. A cut is
    # extended through ties so two bundles on the same score never land in
    # different bands. Trade-off worth knowing: percentile bands always produce
    # a P1 set, even on a quiet day — they rank the available work rather than
    # measuring absolute urgency (see DESIGN.md).
    "bands": {"p1_pct": 0.20, "p2_pct": 0.50},
}

# Fuzzy suggestions for the unmatched queue are hints for a human, never an
# auto-assignment. Below this similarity we don't even suggest.
FUZZY_SUGGEST_CUTOFF = 0.6
