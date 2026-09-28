# grantee-resolver

Resolves terminated federal grant recipients to their **UEI** (from USAspending.gov) and
**EIN** (from the IRS Exempt Organizations Business Master File). Also snapshots the
official HHS list of terminated grants every night. HHS records a reinstatement only by
removing the row from that list, so diffing snapshots is the only way to see one.

This is a companion dataset to [Grant Witness](https://grantwitness.org), which already
tracks termination and reinstatement status per award for NIH, CDC, SAMHSA, AHRQ, NSF and
EPA. This project keys on their Award IDs and adds organization identifiers, address,
congressional district, NTEE category, and reported revenue, so a lost award can be
compared to the size of the organization that lost it.

**Status (2026-09-28):** CDC file resolved and hand-checked on 2026-09-04. Every YES,
MAYBE and NO row was read against its IRS record. The veto rules that came out of that,
the residual verdicts, and the one match that has moved since are in
`data/resolved/README.md`. The TAGGS snapshot has run nightly since 2026-09-03. HHS
has republished the list about once a week, and each republication appears as a diff in
`data/taggs/changes/`. Nothing here has been validated by the Grant Witness maintainers.

## Principles

- No model decides anything. Matching is deterministic name and address scoring, and
  every match carries its score, tier, and the matched IRS record so a reader can check it.
- Every row has provenance. TAGGS rows carry the PDF page they came from and the file's
  SHA-256. USAspending responses are cached verbatim. Diffs are committed to git.
- Summaries exclude routine terminations by default. HHS's list mixes policy terminations
  ("Departmental Authority", "Termination for Cause") with bilateral and
  mutual-convenience closeouts, which are often ordinary. The full data is always kept.

## Data flow

```
TAGGS PDF ──parse──▶ data/taggs/snapshots/YYYY-MM-DD.csv ──diff──▶ data/taggs/changes/YYYY-MM-DD.json
Grant Witness CSV ──▶ USAspending award API ──▶ UEI, business category, address
                                                   └──▶ IRS BMF (per state) ──▶ EIN, NTEE, revenue
                                                                        └──▶ data/resolved/{agency}.csv
```

HHS updates the PDF about once a week, so most nightly diffs are empty. Snapshots keep
the PDF's text as extracted. The diff ignores formatting-only differences (date padding,
capitalization, line wrapping, mojibake) and counts those rows under `reformatted`
instead of listing them as changes.

## Usage

```sh
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/grantee taggs            # download, parse, snapshot, diff against the previous snapshot
.venv/bin/grantee taggs --rediff   # recompute every committed diff from the committed snapshots
.venv/bin/grantee gw cdc samhsa    # fetch Grant Witness tables
.venv/bin/grantee resolve cdc      # write data/resolved/cdc.csv
```

`.github/workflows/nightly.yml` runs `grantee taggs` daily and commits any new snapshot.
Resolving is run by hand. The IRS replaces its files in place, so a rerun can move a
match, and a moved match should be reviewed before it is committed.

## Grant Witness input

The Grant Witness CSVs are fetched at run time, not committed. The Grant Witness team
archives them at
[signaltrack/gw-grant-disruption-data](https://github.com/signaltrack/gw-grant-disruption-data)
(formerly `gw-data`), which cuts a dated release per pull, and `grantee gw` reads from a
release tag pinned in `grantwitness.py`. So a run is reproducible and the input is
citable, and this repo does not carry a second copy of a file someone else already
archives.

Every fetch writes `data/grantwitness/{agency}.source.json` with the URL, release tag,
SHA-256 of the bytes, and when that content was first seen. Each resolve writes
`data/resolved/{agency}.meta.json` carrying that record, the SHA-256 and IRS posting date
of every state file it matched against, and the run's tier counts. Those sidecars are
committed; the upstream CSVs are not.

To take new upstream data, bump `PINNED_RELEASE` and rerun `grantee resolve`. The
resolved output changes only when someone does that.
Pass `--live` to pull from grantwitness.org instead, or `--tag` for a one-off release.

## Match tiers

| Tier | Meaning |
|---|---|
| `YES` | Normalized name identical in-state (governance words like "Regents of" ignored); or similarity ≥ 0.97 with city match; or ≥ 0.93 with ZIP match |
| `MAYBE` | Name similarity ≥ 0.88, or one name is a word-subset of the other; needs a human look |
| `NO` | Nothing survived the veto rules. `ein` is blank; `bmf_name` shows the closest rejected candidate |
| `GOV` | Recipient looks like a government entity; not expected in the BMF |
| `FOREIGN` | Recipient located outside the US; not in the BMF |
| `NA` | No usable name, or a state code the IRS publishes no file for |

Veto rules (university foundations, alumni associations, chapters, governance words,
low word overlap) and the hand-check that produced them are documented in
`data/resolved/README.md`. Each rule has a regression test: `.venv/bin/python -m pytest`.

## Licenses

Code: MIT. Data produced here: CC0 (see `data/LICENSE`).

Grant Witness states no license on its site, but the team's own archive repo declares the
data CC0-1.0 in its Zenodo deposit metadata, and their FAQ answers "Can I use this data in
my own reporting?" with "Emphatically yes." This project relies on that, cites their
release tag, and does not redistribute their CSVs. Confirming CC0 with the maintainers
directly is still worth doing.

## Related

- [Grant Witness](https://grantwitness.org), the upstream status data
- [signaltrack/gw-grant-disruption-data](https://github.com/signaltrack/gw-grant-disruption-data), their archive of it
- [HHS TAGGS terminated grants PDF](https://taggs.hhs.gov/Content/Data/HHS_Grants_Terminated.pdf)
- Nonprofit Open Data Collective `npmatch`, the matching cascade this simplifies
- GAO-26-108615, the DOGE "Wall of Receipts" reconciliation (already done; not repeated here)
