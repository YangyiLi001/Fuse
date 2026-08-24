"""Load and validate the three input CSVs into plain dicts."""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

REQUIRED = {
    "accounts.csv": ["account_id", "account_name", "domain", "industry",
                     "arr_band", "region", "is_customer", "segment_hint"],
    "signals.csv": ["signal_id", "signal_type", "account_id", "account_name",
                    "domain", "region", "timestamp", "severity_hint", "detail"],
    "sellers.csv": ["seller_id", "name", "territory", "tiers", "capacity", "status"],
}


def _read(path: Path, name: str) -> list[dict]:
    with open(path / name, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError(f"{name}: no rows")
    missing = [c for c in REQUIRED[name] if c not in rows[0]]
    if missing:
        raise ValueError(f"{name}: missing columns {missing}")
    return rows


def parse_ts(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def load_all(data_dir: str):
    path = Path(data_dir)
    accounts = _read(path, "accounts.csv")
    for a in accounts:
        a["is_customer"] = a["is_customer"].strip().lower() == "true"

    sellers = _read(path, "sellers.csv")
    for s in sellers:
        s["tiers"] = [t for t in s["tiers"].split("|") if t]
        s["capacity"] = float(s["capacity"] or 0)

    signals = _read(path, "signals.csv")
    for sig in signals:
        sig["account_id"] = sig["account_id"].strip()
        sig["detail"] = json.loads(sig["detail"])
        sig["ts"] = parse_ts(sig["timestamp"])
    return accounts, signals, sellers
