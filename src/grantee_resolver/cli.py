from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from . import grantwitness, resolve, taggs

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def cmd_taggs(args):
    if args.rediff:
        return rediff_taggs()
    pdf, sha = taggs.download(DATA / "cache" / "HHS_Grants_Terminated.pdf")
    rows = taggs.parse(pdf)
    snap_dir = DATA / "taggs" / "snapshots"
    prev_files = sorted(snap_dir.glob("*.csv"))
    today = date.today()
    path = taggs.write_snapshot(rows, snap_dir, today)
    result = {"date": today.isoformat(), "rows": len(rows), "sha256": sha, "snapshot": str(path.relative_to(ROOT))}
    prev = [p for p in prev_files if p != path]
    if prev:
        d = taggs.diff(taggs.load_snapshot(prev[-1]), taggs.load_snapshot(path))
        d["against"] = prev[-1].name
        d["sha256"] = sha
        dpath = taggs.write_diff(d, DATA / "taggs" / "changes", today)
        result.update(added=len(d["added"]), removed=len(d["removed"]), changed=len(d["changed"]),
                      reformatted=d["reformatted"], diff=str(dpath.relative_to(ROOT)))
    print(json.dumps(result, indent=1))


def rediff_taggs():
    """Recompute every committed diff from the committed snapshots, keeping each day's PDF hash."""
    snap_dir, changes = DATA / "taggs" / "snapshots", DATA / "taggs" / "changes"
    for p in sorted(changes.glob("*.json")):
        old = json.loads(p.read_text())
        d = taggs.diff(taggs.load_snapshot(snap_dir / old["against"]), taggs.load_snapshot(snap_dir / f"{p.stem}.csv"))
        d["against"], d["sha256"] = old["against"], old["sha256"]
        taggs.write_diff(d, changes, date.fromisoformat(p.stem))
        print(p.stem, {k: len(v) if isinstance(v, list) else v for k, v in d.items() if k != "sha256"})


def cmd_gw(args):
    for a in args.agencies:
        p = grantwitness.fetch(a, DATA / "grantwitness", live=args.live, tag=args.tag)
        print(json.dumps(grantwitness.source(p), indent=1))


def cmd_resolve(args):
    gw_path = DATA / "grantwitness" / f"{args.agency}.csv"
    if not gw_path.exists():
        grantwitness.fetch(args.agency, DATA / "grantwitness", live=args.live, tag=args.tag)
    stats = resolve.resolve(args.agency, gw_path, DATA / "cache", DATA / "resolved" / f"{args.agency}.csv", args.limit)
    print(json.dumps(stats, indent=1))


def _gw_source_args(p):
    p.add_argument("--live", action="store_true", help="fetch from grantwitness.org instead of the pinned release")
    p.add_argument("--tag", default=grantwitness.PINNED_RELEASE, help="Grant Witness archive release tag to fetch")


def main():
    ap = argparse.ArgumentParser(prog="grantee")
    sub = ap.add_subparsers(required=True)
    s = sub.add_parser("taggs", help="snapshot + diff the HHS terminated-grants PDF")
    s.add_argument("--rediff", action="store_true", help="recompute committed diffs from committed snapshots; no download")
    s.set_defaults(fn=cmd_taggs)
    s = sub.add_parser("gw", help="fetch Grant Witness tables from the pinned Grant Witness archive release")
    s.add_argument("agencies", nargs="*", default=["cdc"]); _gw_source_args(s); s.set_defaults(fn=cmd_gw)
    s = sub.add_parser("resolve", help="resolve a Grant Witness table to UEI/EIN")
    s.add_argument("agency"); s.add_argument("--limit", type=int); _gw_source_args(s); s.set_defaults(fn=cmd_resolve)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
