"""Suggested first-touch lines for sellers.

Deterministic templates filled with payload facts by default. With --llm and
FIREWORKS_API_KEY set, each opener is polished through the Fireworks chat API
(we are pitching Fireworks, after all); any failure falls back to the template.
"""
import json
import os
import urllib.request

FIREWORKS_URL = "https://api.fireworks.ai/inference/v1/chat/completions"
FIREWORKS_MODEL = "accounts/fireworks/models/llama-v3p3-70b-instruct"


def template_opener(sig: dict) -> str:
    t, d = sig["signal_type"], sig["detail"]
    acct = sig["account"]
    is_cust = bool(acct and acct["is_customer"])
    name = acct["account_name"] if acct else sig["account_name"]

    if t == "funding_event":
        return (f"Congrats on the {d['round']} (${d['amount_usd_m']}M)! Teams "
                f"usually scale inference right after a raise — worth 20 minutes "
                f"on capacity and cost planning before you lock in a stack?")
    if t == "usage_spike":
        return (f"Your {d['endpoint']} traffic is up {d['pct_increase_vs_baseline']}% "
                f"({d['requests_7d']:,} requests last week). Happy to review "
                f"throughput/pricing tiers so the bill doesn't surprise anyone.")
    if t == "intent_topic":
        return (f"Saw {name} researching {d['topic']} — we've helped similar teams "
                f"on exactly that. Can I share benchmarks relevant to your workload?")
    if t == "competitor_evaluation":
        if is_cust:
            return (f"Doing a quick check-in — want to make sure you're getting what "
                    f"you need from us. If you're benchmarking against {d['competitor']}, "
                    f"I'd rather walk you through our numbers directly.")
        return (f"If you're evaluating {d['competitor']}, happy to send an honest "
                f"side-by-side on price, latency and model coverage — takes 15 minutes.")
    if t == "job_change":
        if d["direction"] == "arrived":
            return (f"Welcome {d['person']} as {d['new_title']}! New platform leaders "
                    f"usually revisit the inference stack in their first 90 days — "
                    f"can I get 20 minutes on the calendar?")
        if is_cust:
            return (f"Heads-up: {d['person']} ({d['new_title']}) has moved on. "
                    f"Re-map stakeholders this week — who's inheriting the platform?")
        return (f"{d['person']} has left — worth finding the new owner of the "
                f"AI-infrastructure decision before re-engaging.")
    return "Reach out referencing the recent activity."


def polish_with_llm(opener: str, sig: dict) -> str:
    key = os.environ.get("FIREWORKS_API_KEY")
    if not key:
        return opener
    acct = sig["account"]
    context = {
        "signal_type": sig["signal_type"],
        "detail": sig["detail"],
        "account": {k: acct[k] for k in ("account_name", "industry", "arr_band",
                                         "is_customer")} if acct else None,
    }
    body = json.dumps({
        "model": FIREWORKS_MODEL,
        "max_tokens": 120,
        "temperature": 0.4,
        "messages": [
            {"role": "system", "content":
                "You improve one-line sales openers for Fireworks AI (inference "
                "platform). Keep every factual number, stay under 45 words, no "
                "exclamation spam, return only the rewritten opener."},
            {"role": "user", "content":
                f"Signal context: {json.dumps(context)}\nDraft: {opener}"},
        ],
    }).encode()
    req = urllib.request.Request(
        FIREWORKS_URL, data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            out = json.loads(resp.read())
        text = out["choices"][0]["message"]["content"].strip()
        return text or opener
    except Exception:
        return opener  # never let polish break the pipeline


def attach_openers(signals: list[dict], use_llm: bool = False) -> None:
    for sig in signals:
        opener = template_opener(sig)
        if use_llm:
            opener = polish_with_llm(opener, sig)
        sig["opener"] = opener
