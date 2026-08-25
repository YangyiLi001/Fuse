"""Route each account bundle to a seller.

Chain: territory + tier -> active sellers -> load-balanced pick.

Capacity is read as a count of accounts: one account work item consumes one unit
however many signals it carries and however large the account is. sellers.csv
never states the unit, so this is an interpretation — a "per week" or "open
opportunities" reading would behave differently. It weights the tie-break only
and never caps anyone: nothing here refuses an assignment because a seller is
full, which is why the load column can run past capacity without complaint.
Fallbacks (each recorded in routing_reason): adjacent tier in the same
territory, then same tier in a neighbouring region of the same market,
then the unassigned queue.
OOO and ramping sellers never receive routes; the gaps they create are
reported in coverage_report.md instead.
"""
from .config import ADJACENT_TIERS, TIER_FROM_ARR


def _market(region: str) -> str:
    """The market a region belongs to, read off its own name.

    US-East, US-West and US-Central share the "US" prefix and are treated as one
    market: same language, overlapping hours, one contract regime, so a rep in one
    can hold an account in another until proper coverage returns. EMEA and APAC
    carry no prefix and therefore form markets of one — deliberately, because
    handing an APAC account to a US rep produces coverage on paper and nothing on
    the phone. Deriving this from the name rather than hard-coding a list of
    regions means a later EU-North / EU-South split groups itself.
    """
    return region.split("-")[0]


def _pick(candidates: list[dict], load: dict) -> dict | None:
    """Lowest load/capacity ratio wins; capacity then seller_id break ties."""
    if not candidates:
        return None
    return min(candidates, key=lambda s: (
        load[s["seller_id"]] / s["capacity"], -s["capacity"], s["seller_id"]))


def route_bundles(bundles: list[dict], sellers: list[dict]) -> dict:
    active = [s for s in sellers if s["status"] == "active" and s["capacity"] > 0]
    load = {s["seller_id"]: 0 for s in active}

    def in_cell(territory: str, tier: str) -> list[dict]:
        return [s for s in active if s["territory"] == territory and tier in s["tiers"]]

    coverage_notes = []
    # Bundles arrive sorted by score desc, so top priorities get first pick.
    for b in bundles:
        acct = b["account"]
        tier = TIER_FROM_ARR[acct["arr_band"]]
        region = acct["region"]
        b["tier"] = tier

        seller = _pick(in_cell(region, tier), load)
        reason = f"{region} / {tier}"

        if not seller:  # fallback 1: adjacent tier, same territory
            for alt in ADJACENT_TIERS[tier]:
                seller = _pick(in_cell(region, alt), load)
                if seller:
                    reason = (f"{region} / {tier}: no active seller — "
                              f"fell back to {alt} tier in-territory")
                    break

        if not seller:  # fallback 2: same tier, neighbouring region, same market
            other = [s for s in active
                     if s["territory"] != region
                     and _market(s["territory"]) == _market(region)
                     and tier in s["tiers"]]
            seller = _pick(other, load)
            if seller:
                reason = (f"{region} / {tier}: no in-territory coverage — "
                          f"cross-region to {seller['territory']}")

        if seller:
            load[seller["seller_id"]] += 1
            b["seller"] = seller
            b["routing_reason"] = reason
        else:
            b["seller"] = None
            b["routing_reason"] = f"{region} / {tier}: no eligible seller"
            coverage_notes.append(
                f"{acct['account_id']} {acct['account_name']} ({region}/{tier}) unassigned")

    return {"load": load, "unassigned_notes": coverage_notes}
