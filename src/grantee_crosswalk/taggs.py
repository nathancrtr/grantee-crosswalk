"""Parse the HHS TAGGS "Grants Terminated" PDF into rows, and diff snapshots.

Source: https://taggs.hhs.gov/Content/Data/HHS_Grants_Terminated.pdf
HHS removes reinstated awards from this list rather than marking them, so the
only way to observe a reinstatement here is to snapshot the file and diff it.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

import ftfy
import pdfplumber
import requests

from . import USER_AGENT

TAGGS_URL = "https://taggs.hhs.gov/Content/Data/HHS_Grants_Terminated.pdf"
COLUMNS = [
    "opdiv", "fain", "obligation_doc", "recipient", "state", "country",
    "action_date", "obligated", "expended", "paid", "unliquidated", "title",
    "termination_type", "for_cause",
]
# Termination types HHS uses. "Bilateral" and "Mutual Convenience" are frequently
# routine (e.g. a PI relinquishes an award when moving institutions), so headline
# views should default to POLICY_TYPES.
POLICY_TYPES = {"Departmental Authority", "Termination for Cause"}


def download(dest: Path) -> tuple[Path, str]:
    """Download the PDF; return (path, sha256)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(TAGGS_URL, timeout=120, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    dest.write_bytes(r.content)
    return dest, hashlib.sha256(r.content).hexdigest()


def money(s: str) -> float | None:
    s = (s or "").replace("$", "").replace(",", "").strip()
    if s in ("", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse(pdf_path: Path) -> list[dict]:
    rows: list[dict] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            for table in page.extract_tables():
                for raw in table:
                    if not raw or len(raw) < 13:
                        continue
                    if raw[0] is None or raw[0].startswith("OPDIV"):
                        continue
                    cells = [(c or "").replace("\n", " ").strip() for c in raw]
                    cells = (cells + [""] * len(COLUMNS))[: len(COLUMNS)]
                    row = dict(zip(COLUMNS, cells))
                    row["source_page"] = page_no  # provenance: page of the PDF this row came from
                    rows.append(row)
    return rows


def row_key(r: dict) -> str:
    return f"{r['opdiv']}|{r['fain']}|{r['obligation_doc']}"


def write_snapshot(rows: list[dict], out_dir: Path, day: date | None = None) -> Path:
    day = day or date.today()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{day.isoformat()}.csv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS + ["source_page"])
        w.writeheader()
        w.writerows(rows)
    return path


def load_snapshot(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


MONEY_COLUMNS = {"obligated", "expended", "paid", "unliquidated"}


def comparable(col: str, v: str):
    """A cell's value with HHS's formatting churn removed, for comparison only.

    Each weekly regeneration of the PDF can change date padding, capitalization,
    where a long title wraps, and whether its text comes out as mojibake
    ("Alzheimerâ€™s"). None of that is a change to the award. Snapshots keep
    the raw text; only the diff compares through this.
    """
    v = v or ""
    if col == "action_date":
        try:
            return datetime.strptime(v.strip(), "%m/%d/%Y").date()
        except ValueError:
            pass
    if col in MONEY_COLUMNS:
        return money(v)
    v = unicodedata.normalize("NFKC", ftfy.fix_text(v)).casefold()
    return re.sub(r"\s+", "", v)


def _fields(a: dict, b: dict) -> list[str]:
    return [c for c in COLUMNS if comparable(c, a.get(c)) != comparable(c, b.get(c))]


def diff(prev: list[dict], curr: list[dict]) -> dict:
    """Rows added (new terminations), removed (likely reinstated or corrected), changed.

    A key can cover several rows (13 keys do as of 2026-09), so rows are matched
    within a key rather than looked up by it. Rows equal after `comparable` pair off
    first and count toward `reformatted` if their raw text differs. The rest pair in
    file order as changes, and any surplus on one side is an addition or removal.
    """
    before, after = defaultdict(list), defaultdict(list)
    for r in prev:
        before[row_key(r)].append(r)
    for r in curr:
        after[row_key(r)].append(r)
    added, removed, changed, reformatted = [], [], [], 0
    for k in sorted(before.keys() | after.keys()):
        a, b = list(before[k]), []
        for r in after[k]:
            same = next((i for i, x in enumerate(a) if not _fields(x, r)), None)
            if same is None:
                b.append(r)
                continue
            x = a.pop(same)
            reformatted += any(x[c] != r[c] for c in COLUMNS)
        for x, y in zip(a, b):
            fields = _fields(x, y)
            changed.append({"key": k, "fields": fields, "before": {c: x[c] for c in fields}, "after": {c: y[c] for c in fields}})
        removed += a[len(b):]
        added += b[len(a):]
    return {"added": added, "removed": removed, "changed": changed, "reformatted": reformatted}


def write_diff(d: dict, out_dir: Path, day: date | None = None) -> Path:
    day = day or date.today()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{day.isoformat()}.json"
    path.write_text(json.dumps(d, indent=1))
    return path
