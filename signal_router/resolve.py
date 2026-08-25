"""Attach each signal to a CRM account, or mark it unmatched.

Match chain is exact-only: account_id -> domain -> account_name. We never
fuzzy-assign — routing an outreach to the wrong company costs more than
letting a human resolve it. Close names ride along as *suggestions* for the
review queue and are never acted on automatically.
"""
import difflib

from .config import FUZZY_SUGGEST_CUTOFF


def resolve(signals: list[dict], accounts: list[dict]) -> None:
    by_id = {a["account_id"]: a for a in accounts}
    by_domain = {a["domain"].strip().lower(): a for a in accounts}
    by_name = {a["account_name"].strip().lower(): a for a in accounts}

    for sig in signals:
        sig["account"] = None
        sig["match_method"] = "unmatched"
        sig["match_confidence"] = "none"
        sig["match_note"] = ""
        sig["fuzzy_suggestions"] = []

        if sig["account_id"] and sig["account_id"] in by_id:
            sig["account"] = by_id[sig["account_id"]]
            sig["match_method"] = "account_id"
            sig["match_confidence"] = "high"
            continue

        dom = sig["domain"].strip().lower()
        if dom in by_domain:
            sig["account"] = by_domain[dom]
            sig["match_method"] = "domain"
            sig["match_confidence"] = "high"
            continue

        name = sig["account_name"].strip().lower()
        if name in by_name:
            acct = by_name[name]
            sig["account"] = acct
            sig["match_method"] = "name"
            if acct["domain"].strip().lower() != dom:
                sig["match_confidence"] = "medium"
                sig["match_note"] = (
                    f"name matches {acct['account_id']} but domain differs "
                    f"({sig['domain']} vs {acct['domain']}) — verify before outreach"
                )
            else:
                sig["match_confidence"] = "high"
            continue

        # No exact match: collect close names as hints for whoever reviews this,
        # never as an assignment. On this dataset every one of them points at a
        # different company (Pulse Grid to Jute Grid, Yew Cloud to Elm Cloud),
        # which is exactly why they stay suggestions.
        cand = difflib.get_close_matches(
            name, by_name.keys(), n=2, cutoff=FUZZY_SUGGEST_CUTOFF)
        sig["fuzzy_suggestions"] = [
            f"{by_name[c]['account_id']} {by_name[c]['account_name']}" for c in cand
        ]
