"""Assert the deterministic analytical numbers the generator was designed to produce."""

from src.config import REFERENCE_DATE


def test_fact_row_count(fact):
    # 50 students x 6 eligible assignments each = 300 eligible pairs
    assert len(fact) == 300


def test_missing_assignment_101(fact):
    missing = (fact["assignment_id"] == 101) & (fact["submission_state"] == "missing")
    assert int(missing.sum()) == 10


def test_overdue_count(fact):
    assert int(fact["is_overdue"].sum()) == 89


def test_upcoming_count(fact):
    # Only Assignment_603 (due after the reference date) is upcoming: 15 CS students.
    assert int(fact["is_upcoming"].sum()) == 15


def test_submission_state_totals(fact):
    counts = fact["submission_state"].value_counts().to_dict()
    assert int(counts["on_time"]) == 151
    assert int(counts["late"]) == 45
    assert int(counts["missing"]) == 104


def test_reference_date_is_fixed():
    assert str(REFERENCE_DATE) == "2025-06-30"
