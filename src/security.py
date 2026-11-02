"""
security.py
===========
Security & governance bonus layer. Demonstrates three controls that map
directly to Microsoft Fabric / OneLake governance concepts:

1. PII masking
   Mask direct identifiers (email) in an analytical output so a "missing
   submissions" report can be shared without exposing personal addresses.

2. Role-based (row/column) access control
   A single `view_students(role, requester_id)` function returns a different
   projection of the students table per role:
       admin       -> all rows, all columns, raw PII
       instructor  -> all rows, PII masked
       student     -> only the requester's own row, PII masked
   This mirrors Fabric's row-level security + column-level masking.

3. Metadata tags / data catalog
   A `data_catalog.json` records classification, PII flag, owner and tags for
   every Silver/Gold table. A secured Parquet file is also written with the
   same tags embedded as Parquet schema key-value metadata.
"""

from __future__ import annotations

import datetime
import json
import os
import sys

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import GOLD_DIR, OUTPUT_DIR, SILVER_DIR  # noqa: E402

# ---------------------------------------------------------------------------
# PII masking
# ---------------------------------------------------------------------------
PII_COLUMNS = ("email",)


def mask_email(email) -> str | None:
    """Mask an email as ``<first>***@<domain>`` (e.g. n***@university.edu)."""
    if pd.isna(email) or not isinstance(email, str) or "@" not in email:
        return None if pd.isna(email) else "***"
    local, _, domain = email.partition("@")
    return f"{local[0]}***@{domain}" if local else f"***@{domain}"


def mask_dataframe(df: pd.DataFrame, pii_cols=PII_COLUMNS) -> pd.DataFrame:
    out = df.copy()
    for c in pii_cols:
        if c in out.columns:
            out[c] = out[c].apply(mask_email)
    return out


# ---------------------------------------------------------------------------
# Role-based access control
# ---------------------------------------------------------------------------
ROLE_POLICY = {
    # role: (mask_pii, restrict_to_own_row, allowed_columns-or-None)
    "admin":      (False, False, None),
    "instructor": (True,  False, None),
    "student":    (True,  True,  None),
}


def view_students(role: str, requester_id: int | None = None) -> pd.DataFrame:
    """Return the students table projected according to `role`."""
    if role not in ROLE_POLICY:
        raise ValueError(f"unknown role: {role}")
    mask_pii, restrict_own, _cols = ROLE_POLICY[role]

    students = pd.read_parquet(SILVER_DIR / "silver_students.parquet")
    view = students.copy()

    if restrict_own:
        if requester_id is None:
            raise ValueError("student role requires a requester_id")
        view = view[view["student_id"] == requester_id]
    if mask_pii:
        view = mask_dataframe(view)
    return view.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Data catalog metadata
# ---------------------------------------------------------------------------
CATALOG = [
    {"table": "silver_students", "layer": "silver", "classification": "confidential",
     "pii": True, "owner": "Registrar", "tags": ["PII", "student", "identifier"]},
    {"table": "silver_courses", "layer": "silver", "classification": "internal",
     "pii": False, "owner": "Academic Office", "tags": ["course", "reference"]},
    {"table": "silver_assignments", "layer": "silver", "classification": "internal",
     "pii": False, "owner": "Academic Office", "tags": ["assignment", "reference"]},
    {"table": "silver_submissions", "layer": "silver", "classification": "confidential",
     "pii": True, "owner": "Registrar", "tags": ["submission", "grade", "PII"]},
    {"table": "silver_student_assignment_fact", "layer": "silver", "classification": "confidential",
     "pii": True, "owner": "Analytics", "tags": ["fact", "PII", "derived"]},
    {"table": "gold_missing_submissions", "layer": "gold", "classification": "confidential",
     "pii": True, "owner": "Analytics", "tags": ["analytics", "PII", "missing"]},
    {"table": "gold_course_submission_rates", "layer": "gold", "classification": "internal",
     "pii": False, "owner": "Analytics", "tags": ["analytics", "aggregated"]},
    {"table": "gold_overdue_assignments", "layer": "gold", "classification": "confidential",
     "pii": True, "owner": "Analytics", "tags": ["analytics", "PII", "overdue"]},
]


def build_catalog() -> dict:
    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "catalog_version": "1.0",
        "tables": CATALOG,
    }


def write_secured_students_parquet() -> str:
    """Write a governed students parquet with classification tags embedded as
    Parquet schema key-value metadata (demonstrates file-level tagging)."""
    students = pd.read_parquet(SILVER_DIR / "silver_students.parquet")
    table = pa.Table.from_pandas(students, preserve_index=False)
    meta = dict(table.schema.metadata or {})
    meta.update({
        b"lakehouse.classification": b"confidential",
        b"lakehouse.pii": b"true",
        b"lakehouse.owner": b"Registrar",
        b"lakehouse.tags": b"PII,student,identifier",
    })
    table = table.replace_schema_metadata(meta)
    out = GOLD_DIR / "gold_students_secured.parquet"
    pq.write_table(table, out)
    return str(out)


# ---------------------------------------------------------------------------
# JSON helpers (reuse analytics shape for consistency)
# ---------------------------------------------------------------------------
def _json_default(o):
    if isinstance(o, (datetime.date, datetime.datetime)):
        return o.isoformat()
    raise TypeError(f"{type(o).__name__} not serialisable")


def _write_json(name: str, payload: dict) -> None:
    (OUTPUT_DIR / f"{name}.json").write_text(
        json.dumps(payload, indent=2, default=_json_default), encoding="utf-8"
    )


def _records(df: pd.DataFrame) -> list:
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            df[c] = df[c].dt.strftime("%Y-%m-%d")
    return df.to_dict(orient="records")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def run_security() -> dict:
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = {}

    # 1) PII masking example: masked "missing submissions" report.
    fact = pd.read_parquet(SILVER_DIR / "silver_student_assignment_fact.parquet")
    missing = fact[(fact["assignment_id"] == 101) & (fact["submission_state"] == "missing")]
    masked = mask_dataframe(
        missing[["student_id", "name", "email", "student_program", "student_status",
                 "assignment_id", "title", "due_date", "submission_state"]]
        .rename(columns={"student_program": "program", "student_status": "status",
                         "title": "assignment_title"})
    )
    _write_json("missing_submissions_masked", {
        "status": "success",
        "message": f"missing_submissions (PII masked): {len(masked)} row(s)",
        "data": _records(masked),
    })
    results["masked_missing_submissions"] = len(masked)

    # 2) Role-based views of the students table.
    admin_view = view_students("admin")
    instr_view = view_students("instructor")
    stud_view = view_students("student", requester_id=1001)
    for role, view in [("admin", admin_view), ("instructor", instr_view), ("student", stud_view)]:
        _write_json(f"students_view_{role}", {
            "status": "success",
            "message": f"students_view_{role}: {len(view)} row(s)",
            "data": _records(view),
        })
    results["role_views"] = {"admin": len(admin_view), "instructor": len(instr_view), "student": len(stud_view)}

    # 3) Catalog metadata + embedded Parquet tags.
    _write_json("data_catalog", build_catalog())
    write_secured_students_parquet()
    results["catalog_tables"] = len(CATALOG)
    results["secured_parquet"] = "gold_students_secured.parquet"

    return results


if __name__ == "__main__":
    print("Security & governance:")
    print(json.dumps(run_security(), indent=2, default=str))
