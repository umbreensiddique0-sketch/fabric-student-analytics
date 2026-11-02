"""Schema, primary-key uniqueness, and referential-integrity checks for Silver."""

import pandas as pd

from src.config import REFERENCE_DATE

REF_TS = pd.Timestamp(REFERENCE_DATE)


# --- primary keys ---
def test_student_pk_unique(silver_students):
    assert silver_students["student_id"].is_unique
    assert silver_students["student_id"].notna().all()


def test_course_pk_unique(silver_courses):
    assert silver_courses["course_id"].is_unique
    assert silver_courses["course_id"].notna().all()


def test_assignment_pk_unique(silver_assignments):
    assert silver_assignments["assignment_id"].is_unique


def test_submission_pk_unique(silver_submissions):
    assert silver_submissions["submission_id"].is_unique


# --- foreign keys ---
def test_assignment_course_fk(silver_assignments, silver_courses):
    assert silver_assignments["course_id"].isin(silver_courses["course_id"]).all()


def test_submission_student_fk(silver_submissions, silver_students):
    assert silver_submissions["student_id"].isin(silver_students["student_id"]).all()


def test_submission_assignment_fk(silver_submissions, silver_assignments):
    assert silver_submissions["assignment_id"].isin(silver_assignments["assignment_id"]).all()


# --- fact table schema + business rules ---
def test_fact_has_expected_columns(fact):
    for col in [
        "student_id", "assignment_id", "course_id",
        "student_program", "course_program",
        "due_date", "submission_state", "is_overdue", "is_upcoming",
    ]:
        assert col in fact.columns, f"fact missing column {col}"


def test_fact_eligibility_rule(fact):
    """Every fact row pairs a student whose program matches the course program."""
    assert (fact["student_program"] == fact["course_program"]).all()


def test_submission_state_domain(fact):
    assert set(fact["submission_state"].unique()) <= {"on_time", "late", "missing"}


def test_overdue_logic_consistency(fact):
    """is_overdue must equal (not is_upcoming) AND submission_state == 'missing'."""
    expected = (~fact["is_upcoming"]) & (fact["submission_state"] == "missing")
    assert (fact["is_overdue"] == expected).all()


def test_overdue_implies_past_due(fact):
    overdue = fact[fact["is_overdue"]]
    assert (overdue["due_date"] < REF_TS).all()


def test_upcoming_implies_not_overdue(fact):
    upcoming = fact[fact["is_upcoming"]]
    assert (upcoming["is_overdue"] == False).all()  # noqa: E712


def test_no_null_identifiers(fact):
    assert fact["student_id"].notna().all()
    assert fact["assignment_id"].notna().all()
