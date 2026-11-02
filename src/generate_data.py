"""
generate_data.py
================
Generate four relationally consistent source CSV files for the Student
Analytics Lakehouse (Fabric-inspired) tech test:

    data/source/students.csv
    data/source/courses.csv
    data/source/assignments.csv
    data/source/submissions.csv

The data is fully deterministic (fixed random seed + fixed reference date) so
that every pipeline run and every test is reproducible.

Relational model
----------------
    students(student_id PK, name, email, program, enrollment_date, status, cohort)
    courses(course_id PK, course_name, instructor, program, start_date, end_date)
    assignments(assignment_id PK, course_id FK->courses,
                title, due_date, max_score)
    submissions(submission_id PK, student_id FK->students,
                assignment_id FK->assignments, submission_date, score, status)

Business rule (eligibility)
---------------------------
A student is *eligible* to submit an assignment when their program matches the
program of the course that owns the assignment. This lets us compute a
meaningful, course-specific "eligible-student denominator" for the submission
rate query without needing a separate enrolment table.

Submission state definitions (applied downstream, recorded here)
----------------------------------------------------------------
    on_time : a submission row exists with submission_date <= due_date
    late    : a submission row exists with submission_date >  due_date
    missing : no submission row exists for an eligible student-assignment pair
    overdue : due_date < REFERENCE_DATE AND state == missing
              (a late submission was eventually handed in, so it is "late",
               NOT "overdue")
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta

import numpy as np
import pandas as pd

# Make `src.config` importable whether this file is run as a script
# (python src/generate_data.py) or as a module (python -m src.generate_data).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import RANDOM_SEED, REFERENCE_DATE, SOURCE_DIR

# ---------------------------------------------------------------------------
# Program catalogue
# ---------------------------------------------------------------------------
PROGRAMS = ["DS", "SE", "CS"]
PROGRAM_NAMES = {
    "DS": "Data Science",
    "SE": "Software Engineering",
    "CS": "Cybersecurity",
}

# ---------------------------------------------------------------------------
# Courses (course_id, course_name, instructor, program, start_date, end_date)
# Two courses per program so every program has a distinct eligible pool.
# ---------------------------------------------------------------------------
COURSES = [
    (1, "Intro to Data Science",        "Dr. Adele Mensah",   "DS", date(2025, 1, 15), date(2025, 5, 30)),
    (2, "Machine Learning Foundations", "Prof. Liam Carter",  "DS", date(2025, 2, 1),  date(2025, 6, 15)),
    (3, "Software Architecture",        "Dr. Noor Haddad",    "SE", date(2025, 1, 20), date(2025, 5, 25)),
    (4, "Cloud Native Development",      "Prof. Sara Khan",   "SE", date(2025, 2, 10), date(2025, 6, 20)),
    (5, "Network Security",               "Dr. Marco Rossi",   "CS", date(2025, 1, 15), date(2025, 5, 20)),
    (6, "Ethical Hacking",                "Prof. Yuki Tanaka", "CS", date(2025, 2, 5),  date(2025, 6, 10)),
]

# ---------------------------------------------------------------------------
# Assignments (assignment_id, course_id, title, due_date, max_score)
# All due on/before REFERENCE_DATE except 603 (upcoming) to exercise edge cases.
# Assignment_101 (id=101) is the one some students "miss".
# ---------------------------------------------------------------------------
ASSIGNMENTS = [
    (101, 1, "Assignment_101", date(2025, 3, 15), 100),
    (102, 1, "Assignment_102", date(2025, 4, 20), 100),
    (103, 1, "Assignment_103", date(2025, 5, 25), 100),
    (201, 2, "Assignment_201", date(2025, 4, 10), 100),
    (202, 2, "Assignment_202", date(2025, 5, 15), 100),
    (203, 2, "Assignment_203", date(2025, 6, 10), 50),
    (301, 3, "Assignment_301", date(2025, 3, 10), 100),
    (302, 3, "Assignment_302", date(2025, 4, 15), 100),
    (303, 3, "Assignment_303", date(2025, 5, 20), 100),
    (401, 4, "Assignment_401", date(2025, 3, 25), 100),
    (402, 4, "Assignment_402", date(2025, 5, 5),  100),
    (403, 4, "Assignment_403", date(2025, 6, 12), 100),
    (501, 5, "Assignment_501", date(2025, 3, 5),  100),
    (502, 5, "Assignment_502", date(2025, 4, 10), 50),
    (503, 5, "Assignment_503", date(2025, 5, 15), 100),
    (601, 6, "Assignment_601", date(2025, 3, 20), 100),
    (602, 6, "Assignment_602", date(2025, 4, 25), 100),
    (603, 6, "Assignment_603", date(2025, 7, 15), 100),  # after REFERENCE_DATE -> upcoming
]

# ---------------------------------------------------------------------------
# Name pools (ASCII-safe so generated emails stay clean)
# ---------------------------------------------------------------------------
FIRST_NAMES = [
    "Aisha", "Liam", "Noor", "Marco", "Yuki", "Sara", "Adele", "Omar", "Emma", "Wei",
    "Priya", "Carlos", "Hana", "Diego", "Sofia", "Anya", "Jamal", "Mila", "Mateo", "Nadia",
    "Kenji", "Ava", "Ravi", "Zoe", "Bilal", "Chloe", "Hassan", "Ingrid", "Tomas", "Lena",
]
LAST_NAMES = [
    "Mensah", "Carter", "Haddad", "Rossi", "Tanaka", "Khan", "Okoro", "Farouk", "Lind", "Chen",
    "Sharma", "Diaz", "Park", "Silva", "Costa", "Novak", "Reed", "Petrov", "Nguyen", "Muller",
    "Abe", "Brooks", "Patel", "Wells", "Aziz", "Ford", "Berg", "Lopez", "Wong", "Ito",
]


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------
def build_students(rng: np.random.Generator) -> pd.DataFrame:
    """50 students: 18 DS, 17 SE, 15 CS."""
    program_assign = ["DS"] * 18 + ["SE"] * 17 + ["CS"] * 15
    rows = []
    for i, program in enumerate(program_assign):
        sid = 1001 + i
        first = str(rng.choice(FIRST_NAMES))
        last = str(rng.choice(LAST_NAMES))
        name = f"{first} {last}"
        email = f"{first.lower()}.{last.lower()}{sid}@university.edu"

        # Enrolment between 2024-08-01 and ~2025-01-15
        enroll = date(2024, 8, 1) + timedelta(days=int(rng.integers(0, 167)))

        r = float(rng.random())
        if r < 0.06:
            status = "graduated"
        elif r < 0.12:
            status = "inactive"
        else:
            status = "active"

        cohort = "2024" if enroll.year == 2024 else "2025"
        rows.append((sid, name, email, program, enroll, status, cohort))

    cols = ["student_id", "name", "email", "program",
            "enrollment_date", "status", "cohort"]
    return pd.DataFrame(rows, columns=cols)


def build_courses() -> pd.DataFrame:
    cols = ["course_id", "course_name", "instructor", "program",
            "start_date", "end_date"]
    return pd.DataFrame(COURSES, columns=cols)


def build_assignments() -> pd.DataFrame:
    cols = ["assignment_id", "course_id", "title", "due_date", "max_score"]
    return pd.DataFrame(ASSIGNMENTS, columns=cols)


def build_submissions(
    students: pd.DataFrame,
    assignments: pd.DataFrame,
    courses: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Generate submissions only for eligible (student, assignment) pairs.

    Eligibility: student.program == course.program of the assignment.
    Upcoming assignments (due_date >= REFERENCE_DATE) get no submissions yet.
    Assignment_101 is deliberately left missing for a fixed set of DS students
    so the "students missing Assignment_101" query returns a meaningful list.
    """
    course_program = dict(zip(courses["course_id"], courses["program"]))

    # assignment_id -> (course_id, program, due_date, max_score)
    assign_info = {}
    for a in assignments.itertuples(index=False):
        assign_info[a.assignment_id] = {
            "course_id": a.course_id,
            "program": course_program[a.course_id],
            "due_date": a.due_date,
            "max_score": a.max_score,
        }

    # Guarantee a clean, predictable set of students missing Assignment_101.
    forced_missing_101 = set(range(1001, 1008))  # DS students 1001-1007

    rows = []
    sub_id = 50001
    for s in students.itertuples(index=False):
        eligible = [
            aid for aid, info in assign_info.items()
            if info["program"] == s.program
        ]
        for aid in eligible:
            info = assign_info[aid]
            due = info["due_date"]

            # Upcoming assignments are not yet due -> no submissions recorded.
            if due >= REFERENCE_DATE:
                continue

            # Decide whether this eligible student submits this assignment.
            if aid == 101 and s.student_id in forced_missing_101:
                submit = False
            else:
                submit = float(rng.random()) < 0.72

            if not submit:
                continue

            # ~80% on time (<= due), ~20% late (1-10 days after due).
            if float(rng.random()) < 0.8:
                offset = int(rng.integers(-20, 1))  # -20 .. 0 days
                sdate = due + timedelta(days=offset)
                status = "on_time"
                pct = float(rng.uniform(0.55, 1.0))
            else:
                offset = int(rng.integers(1, 11))  # +1 .. +10 days
                sdate = due + timedelta(days=offset)
                status = "late"
                pct = float(rng.uniform(0.40, 0.85))

            score = round(info["max_score"] * pct, 1)
            rows.append((sub_id, s.student_id, aid, sdate, score, status))
            sub_id += 1

    cols = ["submission_id", "student_id", "assignment_id",
            "submission_date", "score", "status"]
    return pd.DataFrame(rows, columns=cols)


# ---------------------------------------------------------------------------
# Integrity checks
# ---------------------------------------------------------------------------
def check_integrity(
    students: pd.DataFrame,
    courses: pd.DataFrame,
    assignments: pd.DataFrame,
    submissions: pd.DataFrame,
) -> list[str]:
    """Validate foreign keys and report any referential-integrity violations."""
    problems = []

    if not submissions["student_id"].isin(students["student_id"]).all():
        bad = submissions.loc[
            ~submissions["student_id"].isin(students["student_id"]), "student_id"
        ].unique().tolist()
        problems.append(f"submissions reference unknown student_ids: {bad}")

    if not submissions["assignment_id"].isin(assignments["assignment_id"]).all():
        bad = submissions.loc[
            ~submissions["assignment_id"].isin(assignments["assignment_id"]),
            "assignment_id",
        ].unique().tolist()
        problems.append(f"submissions reference unknown assignment_ids: {bad}")

    if not assignments["course_id"].isin(courses["course_id"]).all():
        bad = assignments.loc[
            ~assignments["course_id"].isin(courses["course_id"]), "course_id"
        ].unique().tolist()
        problems.append(f"assignments reference unknown course_ids: {bad}")

    # Business rule: every submission must come from an eligible student
    # (same program as the assignment's course).
    cprog = dict(zip(courses["course_id"], courses["program"]))
    aprog = assignments.set_index("assignment_id")["course_id"].map(cprog)
    sprog = dict(zip(students["student_id"], students["program"]))
    elig = submissions.apply(
        lambda r: sprog.get(r.student_id) == aprog.get(r.assignment_id), axis=1
    )
    if not elig.all():
        problems.append("some submissions come from ineligible students (program mismatch)")

    return problems


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    rng = np.random.default_rng(RANDOM_SEED)
    os.makedirs(SOURCE_DIR, exist_ok=True)

    students = build_students(rng)
    courses = build_courses()
    assignments = build_assignments()
    submissions = build_submissions(students, assignments, courses, rng)

    # --- write source CSVs (ISO date format) ---
    students.to_csv(
        os.path.join(SOURCE_DIR, "students.csv"),
        index=False, date_format="%Y-%m-%d",
    )
    courses.to_csv(
        os.path.join(SOURCE_DIR, "courses.csv"),
        index=False, date_format="%Y-%m-%d",
    )
    assignments.to_csv(
        os.path.join(SOURCE_DIR, "assignments.csv"),
        index=False, date_format="%Y-%m-%d",
    )
    submissions.to_csv(
        os.path.join(SOURCE_DIR, "submissions.csv"),
        index=False, date_format="%Y-%m-%d",
    )

    # --- integrity + summary ---
    print("=" * 64)
    print("Student Analytics Lakehouse - source data generation")
    print(f"Reference date : {REFERENCE_DATE}")
    print(f"Random seed    : {RANDOM_SEED}")
    print("=" * 64)
    print(f"students.csv     : {len(students):>4} rows")
    print(f"courses.csv      : {len(courses):>4} rows")
    print(f"assignments.csv  : {len(assignments):>4} rows")
    print(f"submissions.csv : {len(submissions):>4} rows")
    print("-" * 64)

    problems = check_integrity(students, courses, assignments, submissions)
    if problems:
        print("INTEGRITY CHECK: FAILED")
        for p in problems:
            print(f"  - {p}")
        raise SystemExit(1)
    print("INTEGRITY CHECK: PASSED (all foreign keys + eligibility valid)")

    # Students missing Assignment_101 (DS students with no submission for id 101)
    ds_students = students.loc[students["program"] == "DS", "student_id"]
    submitted_101 = set(
        submissions.loc[submissions["assignment_id"] == 101, "student_id"]
    )
    missing_101 = sorted(set(ds_students) - submitted_101)
    print("-" * 64)
    print(f"Students missing Assignment_101 : {len(missing_101)}  -> {missing_101}")

    # Submission state breakdown
    state_counts = submissions["status"].value_counts().to_dict()
    print(f"Submission states               : {state_counts}")
    print("=" * 64)
    print("Source CSVs written to data/source/")


if __name__ == "__main__":
    main()
