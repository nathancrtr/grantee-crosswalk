"""Diff cases from the first month of nightly TAGGS snapshots (2026-09).

The 2026-09-26 PDF re-rendered nearly every row (dates lost their zero padding,
titles came out as mojibake) and the old diff reported 2,438 changes. Separately,
13 keys cover more than one row, and the old diff kept only the last row per key.
"""
from grantee_resolver.taggs import COLUMNS, diff


def row(**kw):
    r = dict.fromkeys(COLUMNS, "")
    r.update(opdiv="NIH", fain="K01HL151902", obligation_doc="KHL151902A", recipient="BOSTON MEDICAL CENTER",
             state="Massachusetts", action_date="03/25/2025", obligated="$696,928.00", expended="-",
             termination_type="Departmental Authority", source_page="50")
    r.update(kw)
    return r


def test_rerendered_row_is_reformatted_not_changed():
    before = row(title="Alzheimer’s Disease using Ultrasound- Targeted Microbubble", state="MASSACHUSETTS")
    after = row(title="Alzheimerâ€™s Disease using Ultrasound-Targeted Microbubble", state="Massachusetts",
                action_date="3/25/2025", obligated="$696,928", source_page="51")
    d = diff([before], [after])
    assert (d["added"], d["removed"], d["changed"], d["reformatted"]) == ([], [], [], 1)


def test_real_change_reports_only_the_real_fields_with_raw_values():
    d = diff([row(paid="$315,515.00", action_date="06/13/2025")],
             [row(paid="$319,028.00", action_date="6/13/2025")])
    assert d["changed"] == [{"key": "NIH|K01HL151902|KHL151902A", "fields": ["paid"],
                             "before": {"paid": "$315,515.00"}, "after": {"paid": "$319,028.00"}}]


def test_removing_one_of_two_rows_under_a_key_is_a_removal():
    first, second = row(), row(obligated="-", action_date="3/21/2025")
    d = diff([first, second], [first])
    assert d["removed"] == [second] and d["changed"] == [] and d["added"] == []


def test_reordering_rows_under_a_key_is_no_change():
    first, second = row(), row(obligated="-", action_date="3/21/2025")
    d = diff([first, second], [second, first])
    assert (d["added"], d["removed"], d["changed"], d["reformatted"]) == ([], [], [], 0)


def test_new_key_and_dropped_key():
    kept, gone, new = row(), row(fain="R15HD097589", obligation_doc="RHD097589B"), row(fain="R01X", obligation_doc="RX")
    d = diff([kept, gone], [kept, new])
    assert d["added"] == [new] and d["removed"] == [gone] and d["changed"] == []
