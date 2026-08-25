"""Conservation and behavior checks for the routing pipeline (stdlib unittest)."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from signal_router.load import load_all  # noqa: E402
from signal_router.openers import attach_openers  # noqa: E402
from signal_router.resolve import resolve  # noqa: E402
from signal_router.route import route_bundles  # noqa: E402
from signal_router.score import bundle_by_account, score_signals  # noqa: E402


def run_pipeline():
    accounts, signals, sellers = load_all(ROOT / "data")
    resolve(signals, accounts)
    score_signals(signals)
    attach_openers(signals)
    matched = [s for s in signals if s["account"]]
    unmatched = [s for s in signals if not s["account"]]
    bundles = bundle_by_account(matched)
    meta = route_bundles(bundles, sellers)
    return signals, bundles, unmatched, sellers, meta


class TestPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (cls.signals, cls.bundles, cls.unmatched,
         cls.sellers, cls.meta) = run_pipeline()

    def test_every_signal_appears_exactly_once(self):
        routed = [s["signal_id"] for b in self.bundles for s in b["signals"]]
        queued = [s["signal_id"] for s in self.unmatched]
        self.assertEqual(sorted(routed + queued),
                         sorted(s["signal_id"] for s in self.signals))
        self.assertEqual(len(self.signals), 50)

    def test_no_routes_to_inactive_sellers(self):
        bad = {s["seller_id"] for s in self.sellers
               if s["status"] != "active" or s["capacity"] <= 0}
        for b in self.bundles:
            if b["seller"]:
                self.assertNotIn(b["seller"]["seller_id"], bad)

    def test_territory_or_documented_fallback(self):
        for b in self.bundles:
            if not b["seller"]:
                continue
            same_region = b["seller"]["territory"] == b["account"]["region"]
            self.assertTrue(same_region or "fell back" in b["routing_reason"]
                            or "cross-region" in b["routing_reason"],
                            b["routing_reason"])

    def test_sig022_is_medium_confidence_name_match(self):
        sig = next(s for s in self.signals if s["signal_id"] == "SIG022")
        self.assertEqual(sig["match_method"], "name")
        self.assertEqual(sig["match_confidence"], "medium")

    def test_multi_signal_account_ranks_first(self):
        # A164: competitor eval + two intent topics must be the top bundle.
        self.assertEqual(self.bundles[0]["account"]["account_id"], "A164")
        self.assertEqual(self.bundles[0]["priority"], "P1")

    def test_severity_hint_is_ignored(self):
        # $200M round tagged severity "low" must still outscore most fundings.
        scores = {s["signal_id"]: s["score"] for s in self.signals
                  if s["signal_type"] == "funding_event"}
        self.assertGreater(scores["SIG037"],
                           sorted(scores.values())[len(scores) // 2])

    def test_all_usage_spikes_are_unmatched(self):
        # Known dataset property: billing/CRM linkage is broken for all four.
        usage = [s for s in self.signals if s["signal_type"] == "usage_spike"]
        self.assertEqual(len(usage), 4)
        self.assertTrue(all(s["match_method"] == "unmatched" for s in usage))

    def test_departed_flag_flip_changes_scores(self):
        from signal_router import config
        sig = next(s for s in self.signals
                   if s["signal_type"] == "job_change"
                   and s["detail"]["direction"] == "departed"
                   and s["account"] and not s["account"]["is_customer"])
        old = sig["score"]
        config.ASSUMPTIONS["DEPARTED_MEANS_LEFT_ACCOUNT"] = False
        try:
            score_signals(self.signals)
            self.assertGreater(sig["score"], old)
        finally:
            config.ASSUMPTIONS["DEPARTED_MEANS_LEFT_ACCOUNT"] = True
            score_signals(self.signals)

    def test_bands_are_percentile_cuts(self):
        from signal_router.config import SCORING
        n = len(self.bundles)
        p1 = [b for b in self.bundles if b["priority"] == "P1"]
        # top ~20%, allowing the tie-extension and rounding to move it a little
        self.assertAlmostEqual(len(p1) / n, SCORING["bands"]["p1_pct"], delta=0.06)
        # bands never interleave: every P1 outranks every P2, and so on
        order = [b["priority"] for b in self.bundles]
        self.assertEqual(order, sorted(order, key=["P1", "P2", "P3"].index))

    def test_no_band_splits_a_tie(self):
        for a, b in zip(self.bundles, self.bundles[1:]):
            if a["score"] == b["score"]:
                self.assertEqual(a["priority"], b["priority"])

    def test_fit_matrix_covers_every_observed_combination(self):
        # A half-filled matrix silently scores prospects at zero — the bug this
        # test exists to prevent.
        from signal_router.config import SCORING
        matrix = SCORING["fit"]["customer_type_pts"]
        for sig in self.signals:
            if sig["account"]:
                key = (sig["account"]["is_customer"], sig["signal_type"])
                self.assertIn(key, matrix, f"{key} falls through to 0")

    def test_every_printed_ledger_closes(self):
        # The ledger is the trust mechanism: a reader must be able to re-do the
        # arithmetic from the printed components and land on the printed score.
        for sig in self.signals:
            p = sig["score_parts"]
            redone = round((p["base"] + p["intensity"] + p["fit"]
                            + p["severity"]) * p["recency"], 1)
            self.assertEqual(redone, sig["score"], sig["signal_id"])

    def test_severity_hint_knob_is_live(self):
        # config.py is only an assumption log if its knobs actually move the
        # output. This one sat unread for a while; the test exists so it can't
        # go dead again.
        from signal_router import config
        sig = next(s for s in self.signals if s["severity_hint"] == "high")
        before = sig["score"]
        config.ASSUMPTIONS["SEVERITY_HINT_WEIGHT"] = 1.0
        try:
            score_signals(self.signals)
            self.assertGreater(sig["score"], before)
        finally:
            config.ASSUMPTIONS["SEVERITY_HINT_WEIGHT"] = 0.0
            score_signals(self.signals)
        self.assertEqual(sig["score"], before)

    def test_config_knobs_are_all_live(self):
        """Every knob must actually move the output.

`SEVERITY_HINT_WEIGHT` sat in config.py unread at one point, which
        makes the file a wish-list rather than the assumption log it claims to
        be. Perturb each knob and require the output to change.
        """
        from signal_router import config
        import copy

        def fingerprint():
            accounts, signals, _ = load_all(ROOT / "data")
            resolve(signals, accounts)
            score_signals(signals)
            return tuple((s["score"], s["match_method"]) for s in signals)

        base = fingerprint()
        saved = copy.deepcopy(config.SCORING), copy.deepcopy(config.ASSUMPTIONS)
        knobs = [
            (config.SCORING["base"], "funding_event", 90),
            (config.SCORING["funding"], "amount_full_score_musd", 20),
            (config.SCORING["usage"], "pct_full_score", 50),
            (config.SCORING["usage"], "log10_req_full_score", 2.0),
            (config.SCORING["usage"], "pct_weight", 0.1),
            (config.SCORING["intent"], "icp_topic_boost", 3.0),
            (config.SCORING["competitor"], "days_scale", 5),
            (config.SCORING["competitor"], "freshness_floor", 0.95),
            (config.SCORING["competitor"]["action_weight"], "docs_read", 0.01),
            (config.SCORING["job_change"]["seniority_weight"], "cto", 0.01),
            (config.SCORING["job_change"], "departed_prospect_factor", 0.99),
            (config.SCORING["fit"], "ai_native_pts", 40),
            (config.SCORING, "intensity_max_pts", 90),
            (config.SCORING["half_life_days"], "funding_event", 1),
            (config.ASSUMPTIONS, "SEVERITY_HINT_WEIGHT", 1.0),
            (config.ASSUMPTIONS, "DEPARTED_MEANS_LEFT_ACCOUNT", False),
        ]
        try:
            for node, key, value in knobs:
                original = node[key]
                node[key] = value
                changed = fingerprint() != base
                node[key] = original
                self.assertTrue(changed, f"{key} is a dead knob")
        finally:
            config.SCORING.clear(); config.SCORING.update(saved[0])
            config.ASSUMPTIONS.clear(); config.ASSUMPTIONS.update(saved[1])
            score_signals(self.signals)

    def test_deterministic_output(self):
        import tempfile
        outs = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as td:
                subprocess.run(
                    [sys.executable, "-m", "signal_router",
                     "--data-dir", str(ROOT / "data"), "--out", td],
                    cwd=ROOT, check=True, capture_output=True)
                outs.append((Path(td) / "routes.csv").read_bytes())
        self.assertEqual(outs[0], outs[1])


if __name__ == "__main__":
    unittest.main()
