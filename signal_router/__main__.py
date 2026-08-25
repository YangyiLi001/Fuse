"""Entry point: python3 -m signal_router [--data-dir data] [--out output] [--llm]"""
import argparse
from collections import Counter

from .load import load_all
from .openers import attach_openers
from .render import render_all
from .resolve import resolve
from .route import route_bundles
from .score import assign_bands, bundle_by_account, score_signals


def main() -> None:
    ap = argparse.ArgumentParser(description="Signal-to-seller routing prototype")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--out", default="output")
    ap.add_argument("--llm", action="store_true",
                    help="polish openers via Fireworks API (needs FIREWORKS_API_KEY; "
                         "falls back to templates on any failure)")
    args = ap.parse_args()

    accounts, signals, sellers = load_all(args.data_dir)
    resolve(signals, accounts)
    score_signals(signals)
    attach_openers(signals, use_llm=args.llm)

    matched = [s for s in signals if s["account"]]
    unmatched = sorted((s for s in signals if not s["account"]),
                       key=lambda s: (-s["score"], s["signal_id"]))
    assign_bands(unmatched)
    bundles = bundle_by_account(matched)
    routing_meta = route_bundles(bundles, sellers)
    render_all(bundles, unmatched, sellers, routing_meta, args.out)

    bands = Counter(b["priority"] for b in bundles)
    print(f"{len(signals)} signals → {len(matched)} matched into {len(bundles)} "
          f"account bundles, {len(unmatched)} to the unmatched queue")
    print(f"priorities: P1={bands.get('P1', 0)} P2={bands.get('P2', 0)} "
          f"P3={bands.get('P3', 0)}")
    print(f"outputs written to {args.out}/ "
          f"(routes.csv, queues/, unmatched_queue.csv, coverage_report.md, dashboard.html)")


if __name__ == "__main__":
    main()
