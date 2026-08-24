"""Write all outputs: routes.csv, per-seller queues, unmatched queue,
coverage report, and the single-file HTML dashboard."""
import csv
import html
from pathlib import Path

from .config import SCORING, TIER_FROM_ARR


def _ledger(sig: dict) -> str:
    p = sig["score_parts"]
    return (f"{p['base']} base + {p['intensity']} intensity + {p['fit']} fit "
            f"→ ×{p['recency']} recency ({p['age_days']}d old) = {sig['score']}")


def write_routes_csv(bundles: list[dict], out: Path) -> None:
    cols = ["priority", "bundle_score", "account_id", "account_name", "region",
            "tier", "arr_band", "is_customer", "seller_id", "seller_name",
            "routing_reason", "signal_id", "signal_type", "signal_score",
            "score_ledger", "play", "match_method", "match_confidence", "why_now"]
    with open(out / "routes.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for b in bundles:
            a, s = b["account"], b["seller"]
            for sig in b["signals"]:
                w.writerow([
                    b["priority"], b["score"], a["account_id"], a["account_name"],
                    a["region"], b["tier"], a["arr_band"], a["is_customer"],
                    s["seller_id"] if s else "UNASSIGNED",
                    s["name"] if s else "", b["routing_reason"],
                    sig["signal_id"], sig["signal_type"], sig["score"],
                    _ledger(sig), sig["play"], sig["match_method"],
                    sig["match_confidence"], sig["why_now"]])


def _unmatched_action(sig: dict) -> str:
    if sig["signal_type"] == "usage_spike":
        return ("DATA FIX FIRST: payload says is_customer=true but the company "
                "is missing from accounts.csv — repair billing↔CRM linkage, "
                "then route as expansion")
    return (f"Net-new company not in CRM — create account, assign "
            f"to {sig['region']} SDR/owner")


def write_unmatched_csv(unmatched: list[dict], out: Path) -> None:
    cols = ["priority", "signal_id", "signal_type", "account_name", "domain",
            "region", "signal_score", "recommended_action", "possible_matches",
            "why_now"]
    with open(out / "unmatched_queue.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for sig in unmatched:
            w.writerow([
                sig["priority"], sig["signal_id"], sig["signal_type"],
                sig["account_name"], sig["domain"], sig["region"], sig["score"],
                _unmatched_action(sig),
                "; ".join(sig["fuzzy_suggestions"]) or "none", sig["why_now"]])


def write_seller_queues(bundles: list[dict], sellers: list[dict], out: Path) -> None:
    qdir = out / "queues"
    qdir.mkdir(parents=True, exist_ok=True)
    by_seller: dict[str, list[dict]] = {}
    for b in bundles:
        if b["seller"]:
            by_seller.setdefault(b["seller"]["seller_id"], []).append(b)

    for s in sellers:
        blist = by_seller.get(s["seller_id"])
        if not blist:
            continue
        fname = f"{s['seller_id']}_{s['name'].lower().replace(' ', '_').replace(chr(39), '')}.md"
        lines = [f"# {s['name']} — signal queue",
                 f"_{s['territory']} · {'/'.join(s['tiers'])} · "
                 f"{len(blist)} accounts, sorted by priority_", ""]
        for b in blist:
            a = b["account"]
            status = "customer" if a["is_customer"] else "prospect"
            lines.append(f"## [{b['priority']}] {a['account_name']} — {b['score']}")
            lines.append(f"{a['industry']} · {a['arr_band']} ARR · {status} · {a['region']}")
            lines.append("")
            for sig in b["signals"]:
                lines.append(f"- **{sig['signal_type']}** ({sig['signal_id']}): "
                             f"{sig['why_now']}")
                lines.append(f"  - score: {_ledger(sig)}")
                if sig["match_confidence"] == "medium":
                    lines.append(f"  - ⚠ {sig['match_note']}")
            if b["combo_bonus"]:
                lines.append("- **pattern**: competitor evaluation + intent research "
                             "on the same account — active deal motion, move fast")
            lines.append("")
            lines.append(f"> **Opener:** {b['signals'][0]['opener']}")
            lines.append("")
        (qdir / fname).write_text("\n".join(lines), encoding="utf-8")


def coverage_report(bundles, unmatched, sellers, routing_meta, out: Path) -> None:
    lines = ["# Coverage & data-quality report", ""]

    lines.append("## Sellers excluded from routing")
    for s in sellers:
        if s["status"] != "active":
            lines.append(f"- {s['seller_id']} {s['name']} ({s['territory']}): "
                         f"status={s['status']}, capacity={s['capacity']}, "
                         f"tiers={'/'.join(s['tiers']) or 'none'}")
    lines.append("")

    lines.append("## Territory × tier holes (active sellers only)")
    for note in _coverage_flags(sellers):
        lines.append(f"- {note}")
    lines.append("")

    lines.append("## Load after routing")
    active = [s for s in sellers if s["status"] == "active" and s["capacity"] > 0]
    load = routing_meta["load"]
    for s in active:
        n = load[s["seller_id"]]
        lines.append(f"- {s['seller_id']} {s['name']}: {n} accounts "
                     f"(capacity {s['capacity']:.0f})")
    if routing_meta["unassigned_notes"]:
        lines.append("")
        lines.append("## Unassigned")
        lines += [f"- {n}" for n in routing_meta["unassigned_notes"]]
    lines.append("")

    lines.append("## Data-quality flags")
    lines.append(f"- {len(unmatched)} of {len(unmatched) + sum(len(b['signals']) for b in bundles)} "
                 f"signals could not be matched to any account (see unmatched_queue.csv)")
    n_usage = sum(1 for s in unmatched if s["signal_type"] == "usage_spike")
    if n_usage:
        lines.append(f"- **All {n_usage} usage_spike signals are unmatched despite "
                     f"payloads claiming is_customer=true** — billing↔CRM linkage "
                     f"is broken; this hides the highest-value signals from sellers")
    med = [sig["signal_id"] for b in bundles for sig in b["signals"]
           if sig["match_confidence"] == "medium"]
    if med:
        lines.append(f"- Name-only matches with domain mismatch (verify before "
                     f"outreach): {', '.join(med)}")
    lines.append("- severity_hint is ignored by scoring: it contradicts payloads "
                 "(e.g. $200M round tagged 'low', +354% usage spike tagged 'low')")
    (out / "coverage_report.md").write_text("\n".join(lines), encoding="utf-8")


def _coverage_flags(sellers: list[dict]) -> list[str]:
    active = [s for s in sellers if s["status"] == "active" and s["capacity"] > 0]
    flags = []
    for r in sorted({s["territory"] for s in sellers}):
        for tier in ["Strategic", "Enterprise", "Mid-Market"]:
            if not any(s["territory"] == r and tier in s["tiers"] for s in active):
                flags.append(f"{r} / {tier}: no active seller — routes fall back "
                             f"to an adjacent tier or cross-region")
    for r in sorted({s["territory"] for s in sellers}):
        reps = [s for s in active if s["territory"] == r]
        if len(reps) == 1:
            flags.append(f"{r} is a single point of failure — only "
                         f"{reps[0]['seller_id']} {reps[0]['name']} is active")
    return flags


def _audit_facts(sig: dict) -> str:
    """Raw payload facts, one line, no interpretation."""
    t, d = sig["signal_type"], sig["detail"]
    if t == "usage_spike":
        return f"+{d['pct_increase_vs_baseline']}% vs baseline, {d['requests_7d']:,} req/7d"
    if t == "funding_event":
        return f"{d['round']} ${d['amount_usd_m']}M (announced {d['announced_date']})"
    if t == "intent_topic":
        return f"'{d['topic']}' {d['intensity_score']:.2f} via {d['source']}"
    if t == "competitor_evaluation":
        return f"{d['competitor']} {d['action']}, {d['days_since_last_signal']}d since last"
    if t == "job_change":
        return f"{d['person']}: {d['new_title']}, {d['direction']}"
    return ""


def write_scoring_audit(bundles, unmatched, out: Path) -> None:
    """Flat review file: every signal's inputs -> score parts -> owner,
    grouped by type so like compares with like; then bundle -> seller."""
    owner = {}
    for b in bundles:
        lbl = b["seller"]["seller_id"] if b["seller"] else "UNASSIGNED"
        for sig in b["signals"]:
            owner[sig["signal_id"]] = lbl
    all_sigs = [s for b in bundles for s in b["signals"]] + list(unmatched)
    hl = SCORING["half_life_days"]
    bw = SCORING["bundle"]

    lines = [
        "# Scoring & routing audit",
        "",
        "Formula: `score = (base + intensity + fit) × recency`; "
        f"recency = 0.5^(age/half-life), anchor = newest signal (2026-08-16).",
        f"Half-lives (days): " + ", ".join(f"{k} {v}" for k, v in hl.items()) + ".",
        f"Bands are percentile cuts on each sorted list: P1 = top "
        f"{SCORING['bands']['p1_pct']:.0%}, P2 = next "
        f"{SCORING['bands']['p2_pct'] - SCORING['bands']['p1_pct']:.0%}, "
        f"cuts extended through ties. severity_hint is unused.",
        "",
        "## Per-signal scores (grouped by type, sorted by score)",
    ]
    for stype in ["usage_spike", "competitor_evaluation", "funding_event",
                  "job_change", "intent_topic"]:
        rows = sorted([s for s in all_sigs if s["signal_type"] == stype],
                      key=lambda s: -s["score"])
        lines += ["", f"### {stype} (base {SCORING['base'][stype]})", "",
                  "| signal | account | payload | play | cust | arr_band "
                  "| age_d | base | inten | fit | ×rec | score | seller |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for s in rows:
            a, sp = s["account"], s["score_parts"]
            lines.append(
                f"| {s['signal_id']} "
                f"| {a['account_name'] if a else s['account_name'] + ' (not in CRM)'} "
                f"| {_audit_facts(s)} "
                f"| {s['play'] or '—'} "
                f"| {'cust' if a and a['is_customer'] else 'prosp' if a else '?'} "
                f"| {a['arr_band'] if a else '—'} "
                f"| {sp['age_days']} | {sp['base']} | {sp['intensity']} "
                f"| {sp['fit']} | {sp['recency']} | **{s['score']}** "
                f"| {owner.get(s['signal_id'], 'unmatched')} |")

    lines += ["", "## Bundle → seller (sorted by bundle score)", "",
              "| account | prio | bundle | calc | region → tier | seller | reason |",
              "|---|---|---|---|---|---|---|"]
    for b in bundles:
        a, sigs = b["account"], b["signals"]
        calc = [str(sigs[0]["score"])]
        if len(sigs) > 1:
            calc.append(f"+ {bw['second_weight']}×{sigs[1]['score']}")
        if len(sigs) > 2:
            calc.append(f"+ {bw['third_weight']}×{sigs[2]['score']}")
        if b["combo_bonus"]:
            calc.append(f"+ {bw['competitor_plus_intent_bonus']} combo")
        s = b["seller"]
        lines.append(
            f"| {a['account_name']} ({a['account_id']}) | {b['priority']} "
            f"| **{b['score']}** | {' '.join(calc)} "
            f"| {a['region']} → {b['tier']} "
            f"| {s['seller_id'] + ' ' + s['name'] if s else 'UNASSIGNED'} "
            f"| {b['routing_reason']} |")
    (out / "scoring_audit.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Dashboard: one static file, three views (team / sellers / unmatched)
# ---------------------------------------------------------------------------
_CSS = """
:root{
  --bg:#f7f5fc; --card:#fff; --ink:#1d1730; --mut:#6d6684; --line:#e7e2f3;
  --brand:#6d28d9; --brand-ink:#4c1d95; --brand-soft:#f4efff; --brand-line:#d8caf6;
  --p1:#c2255c; --p2:#a8690c; --p3:#7a7391; --fix:#a04000;
}
*{box-sizing:border-box;margin:0}
body{font:14px/1.45 -apple-system,'Segoe UI',sans-serif;background:var(--bg);
  color:var(--ink);padding:24px;max-width:1180px;margin:0 auto}
.brandbar{display:flex;align-items:baseline;gap:10px}
h1{font-size:21px;letter-spacing:-.2px}
h1 .mark{color:var(--brand)}
.tag{font-size:12px;color:var(--brand-ink);background:var(--brand-soft);
  border:1px solid var(--brand-line);border-radius:20px;padding:2px 10px}
.sub{color:var(--mut);margin:4px 0 16px}
h2{font-size:15px;margin:22px 0 10px}
h2 .cnt{color:var(--mut);font-weight:400;font-size:13px}
h3{font-size:14px}
.tabs{display:flex;gap:6px;margin-bottom:20px;border-bottom:1px solid var(--line);
  padding-bottom:10px;flex-wrap:wrap}
.tabbtn{padding:7px 14px;border:1px solid var(--line);border-radius:8px;
  background:var(--card);cursor:pointer;font-weight:600;font-size:13px;color:var(--mut)}
.tabbtn:hover{border-color:var(--brand-line);color:var(--brand-ink)}
.tabbtn.on{background:var(--brand);color:#fff;border-color:var(--brand)}
.page{display:none}.page.on{display:block}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;
  padding:14px;cursor:pointer}
.tile:hover{border-color:var(--brand-line)}
.tile.sel{outline:2px solid var(--brand)}
.tile .n{font-size:26px;font-weight:700}
.tile .l{color:var(--mut);font-size:12px;margin-top:2px}
.tile .l2{color:var(--mut);font-size:11px;margin-top:3px;opacity:.8}
.tile.tp1 .n{color:var(--p1)}.tile.tp2 .n{color:var(--p2)}
.tile.tp3 .n{color:var(--p3)}.tile.tun .n{color:var(--fix)}
.badge{font-size:11px;font-weight:700;color:#fff;border-radius:4px;padding:1px 6px;
  white-space:nowrap}
.P1{background:var(--p1)}.P2{background:var(--p2)}.P3{background:var(--p3)}
.FIX{background:var(--fix)}
.play{font-size:11px;font-weight:600;color:var(--brand-ink);background:var(--brand-soft);
  border:1px solid var(--brand-line);border-radius:4px;padding:1px 6px;white-space:nowrap}
.frow{display:flex;gap:10px;align-items:baseline;background:var(--card);
  border:1px solid var(--line);border-radius:8px;padding:10px 12px;margin-bottom:8px;
  flex-wrap:wrap}
.frow .who{color:var(--mut);font-size:12.5px;margin-left:auto;white-space:nowrap}
.frow .fact{flex-basis:100%;color:var(--mut);font-size:12.5px}
table{border-collapse:collapse;background:var(--card);width:100%;font-size:12.5px}
td,th{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}
th{background:var(--brand-soft);color:var(--brand-ink)}
.wrap{overflow-x:auto;border-radius:8px}
.num{text-align:right}
ul.flags{margin:0 0 0 18px;font-size:13px}
ul.flags li{margin-bottom:4px}
details.seller{background:var(--card);border:1px solid var(--line);border-radius:10px;
  margin-bottom:10px}
details.seller summary{cursor:pointer;padding:12px 14px;display:flex;gap:10px;
  align-items:baseline;list-style:none;flex-wrap:wrap}
details.seller summary::-webkit-details-marker{display:none}
details.seller summary::before{content:'▸';color:var(--brand)}
details.seller[open] summary::before{content:'▾'}
summary .meta{color:var(--mut);font-size:12.5px}
summary .counts{margin-left:auto;display:flex;gap:6px}
.body{padding:0 14px 8px 14px}
.card{border-top:1px solid var(--line);padding:10px 0}
.row1{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
.score{color:var(--mut);font-size:12px;margin-left:auto}
.facts{color:var(--mut);font-size:12px}
.sig{font-size:12.5px;margin:6px 0 0 2px}
.opener{font-size:12.5px;background:var(--brand-soft);border-left:3px solid var(--brand);
  padding:6px 8px;border-radius:0 6px 6px 0;margin-top:8px}
.warn{color:var(--fix);font-size:12px}
.note{color:var(--mut);font-size:12.5px;margin:4px 0 12px}
/* ---- assign board ---- */
.bar{display:flex;gap:8px;align-items:center;margin-bottom:14px;flex-wrap:wrap}
.btn{padding:6px 12px;border-radius:7px;border:1px solid var(--brand-line);
  background:var(--card);color:var(--brand-ink);font-weight:600;font-size:12.5px;
  cursor:pointer}
.btn:hover{background:var(--brand-soft)}
.btn.primary{background:var(--brand);color:#fff;border-color:var(--brand)}
.stat{color:var(--mut);font-size:12.5px;margin-left:auto}
.board{display:grid;grid-template-columns:minmax(300px,1fr) minmax(320px,1.15fr);gap:14px}
.col{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}
.col > h3{margin-bottom:8px}
.zone{border:1px dashed var(--brand-line);border-radius:9px;padding:8px;margin-bottom:9px;
  background:var(--bg)}
.zone.over{background:var(--brand-soft);border-color:var(--brand);border-style:solid}
.zone .zh{display:flex;gap:8px;align-items:baseline;font-size:13px;font-weight:600;
  margin-bottom:6px;flex-wrap:wrap}
.zone .zh .meta{font-weight:400;color:var(--mut);font-size:12px}
.zone .zh .load{margin-left:auto;color:var(--mut);font-size:12px}
.item{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--brand);
  border-radius:7px;padding:8px 10px;margin-bottom:7px;cursor:grab}
.item:active{cursor:grabbing}
.item.dragging{opacity:.4}
.item .t{display:flex;gap:7px;align-items:baseline;flex-wrap:wrap}
.item .d{color:var(--mut);font-size:12px;margin-top:3px}
.rgn{font-size:11px;font-weight:700;color:#25506b;background:#e6f1f8;
  border:1px solid #c2dced;border-radius:4px;padding:1px 6px;white-space:nowrap}
.zone.match{border-color:var(--brand);background:var(--brand-soft)}
.zone.match .zh::after{content:'matches region';font-size:11px;color:var(--brand-ink);
  background:#fff;border:1px solid var(--brand-line);border-radius:4px;padding:1px 6px}
.item .xreg{display:none;font-size:11.5px;color:var(--fix);margin-top:4px}
.item.xreg-on .xreg{display:block}
.item select{margin-top:6px;font-size:12px;padding:3px 5px;border-radius:6px;
  border:1px solid var(--line);background:var(--card);color:var(--ink);max-width:100%}
.empty{color:var(--mut);font-size:12.5px;padding:6px 2px}
textarea{width:100%;min-height:150px;font:12px/1.5 ui-monospace,Menlo,monospace;
  border:1px solid var(--line);border-radius:8px;padding:10px;margin-top:12px;
  background:var(--card);color:var(--ink)}
"""

_JS = """
function show(id){
  document.querySelectorAll('.page').forEach(function(p){
    p.classList.toggle('on', p.id === id);});
  document.querySelectorAll('.tabbtn').forEach(function(t){
    t.classList.toggle('on', t.dataset.p === id);});
}
function pick(band){
  ['P1','P2','P3'].forEach(function(x){
    document.getElementById('list-' + x).style.display = (x === band) ? '' : 'none';
    document.getElementById('tile-' + x).classList.toggle('sel', x === band);
  });
}
/* ---------- assignment board: drag/drop + localStorage ---------- */
var KEY = 'fuse.assignments.v1';
var A = {}, ITEMS = [];
function loadA(){
  try { A = JSON.parse(localStorage.getItem(KEY) || '{}'); }
  catch (e) { A = {}; }
}
function saveA(){
  try { localStorage.setItem(KEY, JSON.stringify(A)); }
  catch (e) { /* private mode / blocked storage: board still works this session */ }
}
function renderA(){
  document.querySelectorAll('.zone').forEach(function(z){
    z.querySelectorAll('.item').forEach(function(i){ i.remove(); });
  });
  var counts = {};
  ITEMS.forEach(function(it){
    var target = A[it.dataset.id] || 'pool';
    var z = document.querySelector('.zone[data-seller="' + target + '"]')
         || document.querySelector('.zone[data-seller="pool"]');
    z.appendChild(it);
    it.querySelector('select').value = target;
    it.classList.toggle('xreg-on',
      !!z.dataset.territory && z.dataset.territory !== it.dataset.region);
    counts[target] = (counts[target] || 0) + 1;
  });
  document.querySelectorAll('.zone').forEach(function(z){
    var s = z.dataset.seller, n = counts[s] || 0;
    var e = z.querySelector('.empty');
    if (e) e.style.display = n ? 'none' : '';
    var l = z.querySelector('.load');
    if (l) l.textContent = l.dataset.base
      ? (Number(l.dataset.base) + n) + ' total (' + l.dataset.base + ' routed + ' + n + ' manual)'
      : n + ' item' + (n === 1 ? '' : 's');
  });
  var done = Object.keys(A).length;
  document.getElementById('stat').textContent =
    done + ' of ' + ITEMS.length + ' assigned';
}
function setA(id, seller){
  if (seller === 'pool') { delete A[id]; } else { A[id] = seller; }
  saveA(); renderA();
}
function resetA(){ A = {}; saveA(); renderA();
  document.getElementById('exportbox').value = ''; }
function exportA(){
  var rows = ['item_type,item_id,item_name,region,assigned_seller_id,' +
              'assigned_seller_name,territory,region_match'];
  ITEMS.forEach(function(it){
    var s = A[it.dataset.id];
    if (!s) return;
    var z = document.querySelector('.zone[data-seller="' + s + '"]');
    var terr = z ? (z.dataset.territory || '') : '';
    rows.push([it.dataset.kind, it.dataset.ref, it.dataset.name, it.dataset.region,
               s, z ? z.dataset.name : '', terr,
               terr === it.dataset.region ? 'yes' : 'NO'].map(function(v){
      return /[",]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }).join(','));
  });
  var box = document.getElementById('exportbox');
  box.value = rows.length > 1 ? rows.join('\\n')
    : 'Nothing assigned yet — drag an item onto a seller first.';
  box.scrollIntoView({behavior: 'smooth', block: 'nearest'});
  if (rows.length > 1 && navigator.clipboard) navigator.clipboard.writeText(box.value);
}
document.addEventListener('DOMContentLoaded', function(){
  ITEMS = Array.prototype.slice.call(
    document.querySelectorAll('#itemstore .item'));
  ITEMS.forEach(function(it){
    it.addEventListener('dragstart', function(e){
      e.dataTransfer.setData('text/plain', it.dataset.id);
      it.classList.add('dragging');
      document.querySelectorAll('.zone[data-territory]').forEach(function(z){
        z.classList.toggle('match', z.dataset.territory === it.dataset.region);
      });
    });
    it.addEventListener('dragend', function(){
      it.classList.remove('dragging');
      document.querySelectorAll('.zone').forEach(function(z){
        z.classList.remove('match');
      });
    });
    it.querySelector('select').addEventListener('change', function(e){
      setA(it.dataset.id, e.target.value);
    });
  });
  document.querySelectorAll('.zone').forEach(function(z){
    z.addEventListener('dragover', function(e){ e.preventDefault(); z.classList.add('over'); });
    z.addEventListener('dragleave', function(){ z.classList.remove('over'); });
    z.addEventListener('drop', function(e){
      e.preventDefault(); z.classList.remove('over');
      setA(e.dataTransfer.getData('text/plain'), z.dataset.seller);
    });
  });
  loadA(); renderA();
});
"""


def _bundle_card(b: dict) -> str:
    a = b["account"]
    status = "customer" if a["is_customer"] else "prospect"
    plays = sorted({s["play"] for s in b["signals"] if s["play"]})
    parts = [
        f"<div class=card><div class=row1>"
        f"<span class='badge {b['priority']}'>{b['priority']}</span>"
        f"<b>{html.escape(a['account_name'])}</b>"
        + "".join(f"<span class=play>{html.escape(p)}</span>" for p in plays)
        + f"<span class=score>{b['score']}</span></div>"
        f"<div class=facts>{html.escape(a['industry'])} · {a['arr_band']} · "
        f"{status}</div>"]
    for sig in b["signals"]:
        warn = (" <span class=warn>⚠ verify match</span>"
                if sig["match_confidence"] == "medium" else "")
        parts.append(f"<div class=sig>• <b>{sig['signal_type']}</b>: "
                     f"{html.escape(sig['why_now'])}{warn}</div>")
    if b["combo_bonus"]:
        parts.append("<div class=sig>• <b>pattern</b>: competitor eval + intent "
                     "on one account — active deal motion</div>")
    parts.append(f"<div class=opener>{html.escape(b['signals'][0]['opener'])}"
                 f"</div></div>")
    return "".join(parts)


def _assign_items(bundles, unmatched) -> list[dict]:
    """Everything that has no owner yet: unmatched signals and any bundle the
    router could not place."""
    items = []
    for b in bundles:
        if not b["seller"]:
            a = b["account"]
            items.append({
                "id": "acct:" + a["account_id"], "kind": "account",
                "ref": a["account_id"], "name": a["account_name"],
                "region": a["region"], "priority": b["priority"],
                "score": b["score"],
                "detail": f"{b['tier']} · {a['region']} · {b['routing_reason']}",
            })
    for sig in unmatched:
        items.append({
            "id": "sig:" + sig["signal_id"], "kind": "signal",
            "ref": sig["signal_id"], "name": sig["account_name"],
            "region": sig["region"], "priority": sig["priority"],
            "score": sig["score"],
            "detail": f"{sig['signal_type']} · {sig['domain']} · {sig['why_now']}",
        })
    items.sort(key=lambda i: (["P1", "P2", "P3"].index(i["priority"]), -i["score"]))
    return items


def write_dashboard(bundles, unmatched, sellers, out: Path) -> None:
    n_sig = sum(len(b["signals"]) for b in bundles)
    by_prio = {"P1": [], "P2": [], "P3": []}
    for b in bundles:
        by_prio[b["priority"]].append(b)
    by_seller: dict[str, list[dict]] = {}
    for b in bundles:
        if b["seller"]:
            by_seller.setdefault(b["seller"]["seller_id"], []).append(b)
    un_by_prio = {"P1": [], "P2": [], "P3": []}
    for sig in unmatched:
        un_by_prio[sig["priority"]].append(sig)
    items = _assign_items(bundles, unmatched)
    routable = [s for s in sellers if s["status"] == "active" and s["capacity"] > 0]

    p = [f"<title>Fuse — signal routing</title><style>{_CSS}</style>",
         "<div class=brandbar><h1><span class=mark>◈</span> Fuse</h1>"
         "<span class=tag>signal → seller routing</span></div>",
         f"<div class=sub>{n_sig} routed signals across {len(bundles)} accounts · "
         f"{len(unmatched)} unmatched · anchor date 2026-08-16</div>",
         "<div class=tabs>",
         "<button class='tabbtn on' data-p=team onclick=\"show('team')\">"
         "Team overview</button>",
         "<button class=tabbtn data-p=sellers onclick=\"show('sellers')\">"
         "Seller queues</button>",
         f"<button class=tabbtn data-p=unmatched onclick=\"show('unmatched')\">"
         f"Unmatched ({len(unmatched)})</button>",
         f"<button class=tabbtn data-p=assign onclick=\"show('assign')\">"
         f"Assign ({len(items)})</button>",
         "</div>"]

    # ---- page 1: team overview -------------------------------------------
    band_labels = [("tp1", "P1", "act today"), ("tp2", "P2", "this week"),
                   ("tp3", "P3", "monitor")]
    p.append("<div class='page on' id=team>")
    p.append("<div class=tiles>")
    for cls, band, label in band_labels:
        sel = " sel" if band == "P1" else ""
        nsig = sum(len(b["signals"]) for b in by_prio[band])
        p.append(f"<div class='tile {cls}{sel}' id=tile-{band} "
                 f"onclick=\"pick('{band}')\">"
                 f"<div class=n>{len(by_prio[band])}</div>"
                 f"<div class=l>{band} accounts — {label}</div>"
                 f"<div class=l2>{nsig} signal{'s' if nsig != 1 else ''}</div></div>")
    p.append(f"<div class='tile tun' onclick=\"show('unmatched')\">"
             f"<div class=n>{len(unmatched)}</div>"
             f"<div class=l>unmatched signals — need human review</div>"
             f"<div class=l2>open the Unmatched tab →</div></div>")
    p.append("</div>")
    p.append(f"<div class=note>{n_sig + len(unmatched)} signals total: {n_sig} "
             f"matched, bundled into {len(bundles)} account work items (several "
             f"signals on one account = one item), plus {len(unmatched)} "
             f"unmatched. Click a tile to list that band.</div>")

    for _, band, label in band_labels:
        hidden = "" if band == "P1" else " style=display:none"
        p.append(f"<div id=list-{band}{hidden}>")
        p.append(f"<h2>{band} accounts <span class=cnt>— {label}, with owner "
                 f"and top signal</span></h2>")
        for b in by_prio[band]:
            a, s = b["account"], b["seller"]
            top = b["signals"][0]
            who = (f"→ {html.escape(s['name'])} ({s['seller_id']})"
                   if s else "UNASSIGNED")
            play = (f"<span class=play>{html.escape(top['play'])}</span>"
                    if top["play"] else "")
            p.append(f"<div class=frow><span class='badge {band}'>{band}</span>"
                     f"<b>{html.escape(a['account_name'])}</b>{play}"
                     f"<span class=facts>{b['score']}</span>"
                     f"<span class=who>{who}</span>"
                     f"<span class=fact>{top['signal_type']}: "
                     f"{html.escape(top['why_now'])}</span></div>")
        if not by_prio[band]:
            p.append(f"<div class=note>no {band} accounts</div>")
        p.append("</div>")

    p.append("<h2>Seller load</h2><div class=wrap><table>")
    p.append("<tr><th>Seller</th><th>Territory · tiers</th><th class=num>P1</th>"
             "<th class=num>P2</th><th class=num>P3</th><th class=num>Total</th>"
             "<th class=num>Capacity</th></tr>")
    for s in routable:
        blist = by_seller.get(s["seller_id"], [])
        cnt = {"P1": 0, "P2": 0, "P3": 0}
        for b in blist:
            cnt[b["priority"]] += 1
        p.append(f"<tr><td>{html.escape(s['name'])} ({s['seller_id']})</td>"
                 f"<td>{s['territory']} · {'/'.join(s['tiers'])}</td>"
                 f"<td class=num>{cnt['P1'] or ''}</td>"
                 f"<td class=num>{cnt['P2'] or ''}</td>"
                 f"<td class=num>{cnt['P3'] or ''}</td>"
                 f"<td class=num><b>{len(blist)}</b></td>"
                 f"<td class=num>{s['capacity']:.0f}</td></tr>")
    p.append("</table></div>")

    p.append("<h2>Coverage flags</h2><ul class=flags>")
    for s in sellers:
        if s["status"] != "active" or s["capacity"] <= 0:
            p.append(f"<li>{s['seller_id']} {html.escape(s['name'])} excluded "
                     f"from routing ({s['status']}, capacity {s['capacity']:.0f})</li>")
    for f in _coverage_flags(sellers):
        p.append(f"<li>{html.escape(f)}</li>")
    n_usage = sum(1 for s in unmatched if s["signal_type"] == "usage_spike")
    if n_usage:
        p.append(f"<li><b>All {n_usage} usage-spike signals are unroutable</b> — "
                 f"payloads say is_customer=true but the companies are missing "
                 f"from the CRM (see Unmatched tab)</li>")
    p.append("</ul></div>")

    # ---- page 2: seller queues (collapsed by default) --------------------
    p.append("<div class=page id=sellers>")
    p.append("<div class=note>Click a seller to expand their queue. "
             "Accounts are sorted by priority.</div>")
    for s in routable:
        blist = by_seller.get(s["seller_id"])
        cnt = {"P1": 0, "P2": 0, "P3": 0}
        for b in (blist or []):
            cnt[b["priority"]] += 1
        badges = "".join(f"<span class='badge {k}'>{v} {k}</span>"
                         for k, v in cnt.items() if v)
        n = len(blist or [])
        p.append(f"<details class=seller><summary>"
                 f"<b>{html.escape(s['name'])}</b> ({s['seller_id']})"
                 f"<span class=meta>{s['territory']} · {'/'.join(s['tiers'])} · "
                 f"{n} account{'s' if n != 1 else ''}</span>"
                 f"<span class=counts>{badges}</span></summary><div class=body>")
        if blist:
            for b in blist:
                p.append(_bundle_card(b))
        else:
            p.append("<div class=empty>Nothing routed to this seller in this run.</div>")
        p.append("</div></details>")
    p.append("</div>")

    # ---- page 3: unmatched queue, grouped by priority --------------------
    p.append("<div class=page id=unmatched>")
    p.append("<div class=note>Signals that match no CRM account. Never "
             "auto-routed — a human confirms identity first. Grouped by the "
             "same priority bands as the routed queue.</div>")
    for band, label in [("P1", "Act now"), ("P2", "This week"), ("P3", "Monitor")]:
        sigs = un_by_prio[band]
        if not sigs:
            continue
        p.append(f"<h2><span class='badge {band}'>{band}</span> {label} "
                 f"<span class=cnt>— {len(sigs)}</span></h2>")
        p.append("<div class=wrap><table>")
        p.append("<tr><th>Signal</th><th>Company</th><th>What happened</th>"
                 "<th>Recommended action</th></tr>")
        for sig in sigs:
            action = _unmatched_action(sig)
            fix = ""
            if sig["signal_type"] == "usage_spike":
                fix = "<span class='badge FIX'>DATA FIX</span> "
                action = action.replace("DATA FIX FIRST: ", "")
            sug = (f"<br><span class=facts>similar: "
                   f"{html.escape('; '.join(sig['fuzzy_suggestions']))}</span>"
                   if sig["fuzzy_suggestions"] else "")
            p.append(f"<tr><td>{sig['signal_id']}<br>"
                     f"<span class=facts>{sig['signal_type']}</span></td>"
                     f"<td>{html.escape(sig['account_name'])}<br>"
                     f"<span class=facts>{sig['domain']} · {sig['region']}</span></td>"
                     f"<td>{html.escape(sig['why_now'])}</td>"
                     f"<td>{fix}{html.escape(action)}{sug}</td></tr>")
        p.append("</table></div>")
    p.append("</div>")

    # ---- page 4: assignment board ---------------------------------------
    p.append("<div class=page id=assign>")
    p.append("<div class=note>Everything the router could not place on its own: "
             "unmatched signals, plus any account with no eligible seller. Drag a "
             "card onto a seller — or use the dropdown on the card. Choices are "
             "kept in this browser only; <b>Export</b> copies them as CSV you can "
             "save as <code>data/manual_assignments.csv</code> to feed back into "
             "the next run.</div>")
    p.append("<div class=bar>"
             "<button class='btn primary' onclick=exportA()>Export assignments</button>"
             "<button class=btn onclick=resetA()>Reset</button>"
             "<span class=stat id=stat></span></div>")

    opts = ('<option value="pool">— unassigned —</option>' + "".join(
        f'<option value="{s["seller_id"]}">{html.escape(s["name"])} '
        f'({s["seller_id"]}, {s["territory"]})</option>' for s in routable))
    p.append("<div id=itemstore style=display:none>")
    for it in items:
        p.append(
            f"<div class=item draggable=true data-id=\"{it['id']}\" "
            f"data-kind=\"{it['kind']}\" data-ref=\"{it['ref']}\" "
            f"data-name=\"{html.escape(it['name'], quote=True)}\" "
            f"data-region=\"{it['region']}\">"
            f"<div class=t><span class='badge {it['priority']}'>{it['priority']}</span>"
            f"<b>{html.escape(it['name'])}</b>"
            f"<span class=rgn>{it['region']}</span>"
            f"<span class=facts>{it['score']}</span></div>"
            f"<div class=d>{html.escape(it['detail'])}</div>"
            f"<select>{opts}</select>"
            f"<div class=xreg>⚠ outside this seller's territory</div></div>")
    p.append("</div>")

    p.append("<div class=board>")
    p.append('<div class=col><h3>Needs an owner '
             f'<span class=cnt>— {len(items)}</span></h3>'
             '<div class=zone data-seller=pool data-name="">'
             '<div class=empty>Everything here has been assigned.</div></div></div>')
    p.append("<div class=col><h3>Sellers</h3>")
    for s in routable:
        base = len(by_seller.get(s["seller_id"], []))
        p.append(f'<div class=zone data-seller="{s["seller_id"]}" '
                 f'data-territory="{s["territory"]}" '
                 f'data-name="{html.escape(s["name"], quote=True)}">'
                 f'<div class=zh><b>{html.escape(s["name"])}</b>'
                 f'<span class=meta>{s["seller_id"]} · {s["territory"]} · '
                 f'{"/".join(s["tiers"])}</span>'
                 f'<span class=load data-base="{base}"></span></div>'
                 f'<div class=empty>Drop a card here.</div></div>')
    p.append("</div></div>")
    p.append('<textarea id=exportbox placeholder="Export output appears here '
             '(and is copied to your clipboard)."></textarea>')
    p.append("</div>")

    p.append(f"<script>{_JS}</script>")
    (out / "dashboard.html").write_text("".join(p), encoding="utf-8")



def render_all(bundles, unmatched, sellers, routing_meta, out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_routes_csv(bundles, out)
    write_unmatched_csv(unmatched, out)
    write_seller_queues(bundles, sellers, out)
    coverage_report(bundles, unmatched, sellers, routing_meta, out)
    write_scoring_audit(bundles, unmatched, out)
    write_dashboard(bundles, unmatched, sellers, out)
