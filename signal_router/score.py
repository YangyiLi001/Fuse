"""Score signals from their payloads and bundle them per account.

score = (base_type + intensity_pts + fit_pts) * recency_decay

The additive part prints as a ledger anyone can audit; recency is a
multiplicative gate so a stale signal can't ride a high base to the top.
severity_hint is ignored (weight 0): it contradicts the payloads in this
dataset (see DESIGN.md).
"""
import math
from datetime import datetime, timezone

from .config import ASSUMPTIONS, SCORING


def _intensity_frac(sig: dict) -> tuple[float, str]:
    """Return (0..1 fraction of intensity points, one-line explanation)."""
    t, d = sig["signal_type"], sig["detail"]

    if t == "usage_spike":
        c = SCORING["usage"]
        pct = min(1.0, d["pct_increase_vs_baseline"] / c["pct_full_score"])
        vol = min(1.0, math.log10(max(d["requests_7d"], 1)) / c["log10_req_full_score"])
        frac = c["pct_weight"] * pct + c["volume_weight"] * vol
        return frac, f"+{d['pct_increase_vs_baseline']}% vs baseline, {d['requests_7d']:,} req/7d"

    if t == "funding_event":
        c = SCORING["funding"]
        frac = min(1.0, d["amount_usd_m"] / c["amount_full_score_musd"])
        return frac, f"{d['round']} ${d['amount_usd_m']}M"

    if t == "intent_topic":
        c = SCORING["intent"]
        frac = d["intensity_score"]
        note = f"topic '{d['topic']}' at {d['intensity_score']:.2f} via {d['source']}"
        if d["topic"].lower() in c["icp_topics"]:
            frac = min(1.0, frac * c["icp_topic_boost"])
            note += " (ICP topic)"
        return frac, note

    if t == "competitor_evaluation":
        c = SCORING["competitor"]
        action = c["action_weight"].get(d["action"], 0.6)
        fresh = max(c["freshness_floor"], 1 - d["days_since_last_signal"] / c["days_scale"])
        return action * fresh, f"{d['competitor']}: {d['action'].replace('_', ' ')}"

    if t == "job_change":
        c = SCORING["job_change"]
        title = d["new_title"].lower()
        sen = c["default_seniority"]
        for key, w in c["seniority_weight"].items():
            if key in title:
                sen = w
                break
        is_cust = bool(sig["account"] and sig["account"]["is_customer"])
        if d["direction"] == "arrived" or not ASSUMPTIONS["DEPARTED_MEANS_LEFT_ACCOUNT"]:
            factor, what = c["arrived_factor"], f"{d['person']} joined as {d['new_title']}"
        elif is_cust:
            factor = c["departed_customer_factor"]
            what = f"{d['person']} ({d['new_title']}) departed — champion risk"
        else:
            factor = c["departed_prospect_factor"]
            what = f"{d['person']} departed — contact gone"
        return sen * factor, what

    return 0.0, "unknown signal type"


def _fit_pts(sig: dict) -> tuple[float, str]:
    """Account-context points, plus the name of the sales play they encode."""
    acct = sig["account"]
    if not acct:
        return 0.0, ""  # no context; used only to order the unmatched queue
    c = SCORING["fit"]
    pts, play = c["customer_type_pts"].get(
        (acct["is_customer"], sig["signal_type"]), (0, ""))
    pts += c["arr_pts"].get(acct["arr_band"], 0)
    if acct["segment_hint"] == "AI-Native":
        pts += c["ai_native_pts"]
    return pts, play


def _event_time(sig: dict) -> datetime:
    """Funding decays from the earlier of signal ts and announced_date."""
    if sig["signal_type"] == "funding_event" and "announced_date" in sig["detail"]:
        ann = datetime.strptime(sig["detail"]["announced_date"], "%Y-%m-%d")
        ann = ann.replace(tzinfo=timezone.utc)
        return min(sig["ts"], ann)
    return sig["ts"]


def score_signals(signals: list[dict]) -> None:
    # Anchor "now" to the newest signal so the sample dataset doesn't decay to
    # zero the day the reviewer runs it. In production this is wall-clock time.
    anchor = max(s["ts"] for s in signals)
    for sig in signals:
        base = SCORING["base"][sig["signal_type"]]
        frac, why = _intensity_frac(sig)
        fit, play = _fit_pts(sig)
        age_days = (anchor - _event_time(sig)).total_seconds() / 86400
        half_life = SCORING["half_life_days"][sig["signal_type"]]
        # Round the components first, then score from the rounded values, so the
        # printed ledger reproduces the printed total exactly. Scoring from full
        # precision and rounding only for display leaves a reader who re-does the
        # arithmetic 0.1 off the stated score — which is the fastest way to lose
        # trust in a number whose whole job is to be checkable.
        intensity = round(SCORING["intensity_max_pts"] * frac, 1)
        recency = round(0.5 ** (max(age_days, 0) / half_life), 4)
        sig["score"] = round((base + intensity + fit) * recency, 1)
        sig["score_parts"] = {
            "base": base, "intensity": intensity, "fit": fit,
            "recency": recency, "age_days": round(age_days, 1),
        }
        sig["why_now"] = why
        sig["play"] = play


def bundle_by_account(signals: list[dict]) -> list[dict]:
    """One work item per account; multiple signals stack as evidence."""
    c = SCORING["bundle"]
    groups: dict[str, list[dict]] = {}
    for sig in signals:
        if sig["account"]:
            groups.setdefault(sig["account"]["account_id"], []).append(sig)

    bundles = []
    for acct_id, sigs in groups.items():
        sigs.sort(key=lambda s: -s["score"])
        score = sigs[0]["score"]
        if len(sigs) > 1:
            score += c["second_weight"] * sigs[1]["score"]
        if len(sigs) > 2:
            score += c["third_weight"] * sigs[2]["score"]
        types = {s["signal_type"] for s in sigs}
        combo = {"competitor_evaluation", "intent_topic"} <= types
        if combo:
            score += c["competitor_plus_intent_bonus"]
        bundles.append({
            "account": sigs[0]["account"],
            "signals": sigs,
            "score": round(score, 1),
            "combo_bonus": combo,
        })

    bundles.sort(key=lambda b: (-b["score"], b["account"]["account_id"]))
    assign_bands(bundles)
    return bundles


def assign_bands(items: list[dict]) -> None:
    """Label items P1/P2/P3 by percentile rank. Items must already be sorted by
    score descending. Each cut is extended through ties so two items on the same
    score never land in different bands."""
    c, n = SCORING["bands"], len(items)
    if not n:
        return

    def cut(pct: float) -> int:
        i = max(1, round(n * pct))
        while i < n and items[i]["score"] == items[i - 1]["score"]:
            i += 1
        return i

    p1 = cut(c["p1_pct"])
    p2 = max(p1, cut(c["p2_pct"]))
    for i, x in enumerate(items):
        x["priority"] = "P1" if i < p1 else "P2" if i < p2 else "P3"
