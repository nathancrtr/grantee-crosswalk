"""IRS Exempt Organizations Business Master File, per state.

https://www.irs.gov/pub/irs-soi/eo_{st}.csv  (EIN, NAME, STREET, CITY, STATE, ZIP, NTEE_CD, REVENUE_AMT, ...)

The IRS replaces these files in place at unversioned URLs (most recently 2026-09-07,
which moved one CDC match). So each download records its SHA-256, the server's
Last-Modified date, and when it was fetched, and resolved outputs carry that record for
every state they matched against.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

URL = "https://www.irs.gov/pub/irs-soi/eo_{st}.csv"


def fetch_state(st: str, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"eo_{st.lower()}.csv"
    if not path.exists():
        url = URL.format(st=st.lower())
        r = requests.get(url, timeout=300)
        r.raise_for_status()
        path.write_bytes(r.content)
        path.with_suffix(".source.json").write_text(json.dumps({
            "url": url,
            "sha256": hashlib.sha256(r.content).hexdigest(),
            "bytes": len(r.content),
            "last_modified": r.headers.get("Last-Modified"),
            "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }, indent=1) + "\n")
    return path


def source(st: str, cache_dir: Path) -> dict:
    """Provenance of the cached file for one state, or {} if it was never fetched."""
    p = cache_dir / f"eo_{st.lower()}.source.json"
    return json.loads(p.read_text()) if p.exists() else {}


def load_state(st: str, cache_dir: Path) -> list[dict]:
    path = fetch_state(st, cache_dir)
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))
