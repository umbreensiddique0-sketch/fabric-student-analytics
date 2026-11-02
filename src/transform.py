"""
transform.py
============
Silver layer: read Bronze Parquet, clean + validate, and build the
analytics-ready `student_assignment_fact` table.

Silver contract
----------------
* Clean: parse dates, strip/normalize text, drop duplicate primary keys.
* Validate: enforce referential integrity (FKs); raise on violation.
* Model: one row per *eligible* student-assignment pair, LEFT JOINed to
  submissions so "missing" submissions appear as rows with NULL submission info.

Eligibility rule
---------------
A student is eligible for an assignment when their program matches the
program of the course that owns the assignment (see generate_data.py). This
gives a meaningful, course-specific eligible denominator without an explicit
enrolment table.

Submission state (computed here, reused by the Gold SQL)
-------------------------------------------------------
    on_time : submission row exists and submission_date <= due_date
    late    : submission row exists and submission_date >  due_date
    missing : no submission row exists for an eligible pair

Flags
-----
    is_upcoming : due_date >= REFERENCE_DATE  (not yet due, never overdue)
    is_overdue  : (NOT is_upcoming) AND submission_state == 'missing'

A "late" submission was eventually handed in, so it is NOT counted as overdue.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import BRONZE_DIR, REFERENCE_DATE, SILVER_DIR  # noqa: E402

REF_TS = pd.Timestamp(REFERENCE_DATE)
_BRONZE_META = ["_source_file", "_ingested_at_utc"]


# ---------------------------------------------------------------------------
# Loaders + cleaners
# ---------------------------------------------------------------------------
def _load_bronze(name: str) -> pd.DataFrame:
    return pd.read_parquet(BRONZE_DIR / f"bronze_{name}.parquet")


def _clean_students(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop(columns=_BRONZE_META, errors="ignore")
    df = df.drop_duplicates(subset=["student_id"]).copy()
    df["name"] = df["name"].astype(str).str.strip()
    df["email"] = df["email"].astype(str).str.strip().str.lower()
    df["program"] = df["program"].astype(str).str.strip().str.upper()
    df["status"] = df["status"].astype(str).str.strip().str.lower()
    df["cohort"] = df["cohort"].astype(str).str.strip()
    df["enrollment_date"] = pd.to_datetime(df["enrollment_date"], errors="coerce")
    return df


def _clean_courses(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop(columns=_BRONZE_META, errors="ignore")
    df = df.drop_duplicates(subset=["course_id"]).copy()
    df["course_name"] = df["course_name"].astype(str).str.strip()
    df["instructor"] = df["instructor"].astype(str).str.strip()
    df["program"] = df["program"].astype(str).str.strip().str.upper()
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")
    return df


def _clean_assignments(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop(columns=_BRONZE_META, errors="ignore")
    df = df.drop_duplicates(subset=["assignment_id"]).copy()
    df["title"] = df["title"].astype(str).str.strip()
    df["due_date"] = pd.to_datetime(df["due_date"], errors="coerce")
    return df


def _clean_submissions(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop(columns=_BRONZE_META, errors="ignore")
    df = df.drop_duplicates(subset=["submission_id"]).copy()
    df["submission_date"] = pd.to_datetime(df["submission_date"], errors="coerce")
    df["status"] = df["status"].astype(str).str.strip().str.lower()
    return df


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def _validate_fks(students, courses, assignments, submissions) -> None:
    problems = []
    if not assignments["course_id"].isin(courses["course_id"]).all():
        problems.append("assignments.course_id -> courses.course_id")
    if not submissions["student_id"].isin(students["student_id"]).all():
        problems.append("submissions.student_id -> students.student_id")
    if not submissions["assignment_id"].isin(assignments["assignment_id"]).all():
        problems.append("submissions.assignment_id -> assignments.assignment_id")
    # Eligibility: every submission must come from a student whose program
    # matches the assignment's course program.
    cprog = dict(zip(courses["course_id"], courses["program"]))
    aprog = assignments.set_index("assignment_id")["course_id"].map(cprog)
    sprog = dict(zip(students["student_id"], students["program"]))
    elig = submissions.apply(
        lambda r: sprog.get(r.student_id) == aprog.get(r.assignment_id), axis=1
    )
    if not elig.all():
        problems.append("submissions from ineligible students (program mismatch)")
    if problems:
        raise ValueError("Silver FK validation failed: " + "; ".join(problems))


# ---------------------------------------------------------------------------
# Fact table builder
# ---------------------------------------------------------------------------
def build_student_assignment_fact(
    students: pd.DataFrame,
    courses: pd.DataFrame,
    assignments: pd.DataFrame,
    submissions: pd.DataFrame,
) -> pd.DataFrame:
    # Attach each assignment's course program.
    a = assignments.merge(
        courses[["course_id", "program"]].rename(columns={"program": "course_program"}),
        on="course_id",
        how="left",
    )
    # Clarify student-side columns before the join.
    s = students.rename(columns={"program": "student_program", "status": "student_status"})

    # Eligible pairs: student_program == course_program.
    pairs = s.merge(a, left_on="student_program", right_on="course_program", how="inner")

    # Left-join submissions so missing submissions stay as rows.
    subs = submissions[
        ["submission_id", "student_id", "assignment_id", "submission_date", "score", "status"]
    ].rename(columns={"status": "submission_status"})
    fact = pairs.merge(subs, on=["student_id", "assignment_id"], how="left")

    # submission_state ∈ {on_time, late, missing}
    def _state(row) -> str:
        if pd.isna(row["submission_id"]):
            return "missing"
        sd, due = row["submission_date"], row["due_date"]
        if pd.isna(sd):
            return "missing"
        return "late" if sd > due else "on_time"

    fact["submission_state"] = fact.apply(_state, axis=1)
    fact["is_upcoming"] = fact["due_date"] >= REF_TS
    fact["is_overdue"] = (~fact["is_upcoming"]) & (fact["submission_state"] == "missing")
    return fact


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def transform_silver() -> dict:
    SILVER_DIR.mkdir(parents=True, exist_ok=True)
    processed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    students = _clean_students(_load_bronze("students"))
    courses = _clean_courses(_load_bronze("courses"))
    assignments = _clean_assignments(_load_bronze("assignments"))
    submissions = _clean_submissions(_load_bronze("submissions"))
    _validate_fks(students, courses, assignments, submissions)

    fact = build_student_assignment_fact(students, courses, assignments, submissions)
    fact["_silver_processed_at"] = processed_at

    students.to_parquet(SILVER_DIR / "silver_students.parquet", index=False)
    courses.to_parquet(SILVER_DIR / "silver_courses.parquet", index=False)
    assignments.to_parquet(SILVER_DIR / "silver_assignments.parquet", index=False)
    submissions.to_parquet(SILVER_DIR / "silver_submissions.parquet", index=False)
    fact.to_parquet(SILVER_DIR / "silver_student_assignment_fact.parquet", index=False)

    return {
        "silver_students": int(len(students)),
        "silver_courses": int(len(courses)),
        "silver_assignments": int(len(assignments)),
        "silver_submissions": int(len(submissions)),
        "silver_student_assignment_fact": int(len(fact)),
        "submission_state": {str(k): int(v) for k, v in fact["submission_state"].value_counts().items()},
        "overdue_count": int(fact["is_overdue"].sum()),
        "upcoming_count": int(fact["is_upcoming"].sum()),
    }


if __name__ == "__main__":
    import json

    print("Silver transform:")
    print(json.dumps(transform_silver(), indent=2))
