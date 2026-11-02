"""
analytics.py
============
Gold layer: execute the analytical SQL queries against the Silver tables using
DuckDB, persist the results as Gold Parquet, and export API-ready JSON in the
exact ``{status, message, data}`` shape.

This is the "analytics" tier of the medallion:
    Silver (cleaned fact)  --SQL-->  Gold (analytical result tables)
                                --> JSON  (API responses)

In Microsoft Fabric this maps to a Lakehouse notebook running SQL against
Silver Delta tables and materialising Gold Delta tables + serving endpoints.
"""

from __future__ import annotations

import datetime
import json
import os
import sys

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import GOLD_DIR, OUTPUT_DIR, REFERENCE_DATE, SILVER_DIR, SQL_DIR  # noqa: E402

# Query name -> SQL file. Order is the API contract order.
QUERIES = {
    "missing_submissions": "missing_submissions.sql",
    "course_submission_rates": "course_submission_rates.sql",
    "overdue_assignments": "overdue_assignments.sql",
}

# Silver views to register in DuckDB for the queries to reference.
SILVER_VIEWS = {
    "fact": "silver_student_assignment_fact.parquet",
    "students": "silver_students.parquet",
    "courses": "silver_courses.parquet",
    "assignments": "silver_assignments.parquet",
    "submissions": "silver_submissions.parquet",
}


def _norm(path) -> str:
    """Normalise a path to forward slashes for safe embedding in SQL."""
    return str(path).replace("\\", "/")


def _register_views(con: duckdb.DuckDBPyConnection) -> None:
    for view, fname in SILVER_VIEWS.items():
        parquet = SILVER_DIR / fname
        if not parquet.exists():
            raise FileNotFoundError(
                f"Silver table missing: {parquet}. Run the Silver transform first."
            )
        con.execute(
            f"CREATE OR REPLACE VIEW {view} AS "
            f"SELECT * FROM read_parquet('{_norm(parquet)}')"
        )


def _json_default(o):
    """JSON fallback for numpy scalars and date/datetime objects."""
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (datetime.date, datetime.datetime)):
        return o.isoformat()
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serialisable")


def _serialize(df: pd.DataFrame) -> list:
    """Convert a result DataFrame into JSON-safe records."""
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            df[c] = df[c].dt.strftime("%Y-%m-%d")
            df[c] = df[c].where(df[c].notna(), None)
        elif df[c].dtype == object:
            # Normalise any leftover Python date objects to ISO strings.
            df[c] = df[c].apply(
                lambda v: v.isoformat() if isinstance(v, (datetime.date, datetime.datetime)) else v
            )
    return df.to_dict(orient="records")


def _write_json(path, payload) -> None:
    path.write_text(
        json.dumps(payload, indent=2, default=_json_default),
        encoding="utf-8",
    )


def run_analytics() -> dict:
    """Run every analytical query, write Gold Parquet + JSON, return a summary."""
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    _register_views(con)

    results = {}
    for name, fname in QUERIES.items():
        sql_path = SQL_DIR / fname
        sql = sql_path.read_text(encoding="utf-8")
        try:
            df = con.execute(sql).df()
        except Exception as exc:  # pragma: no cover - surfaced in JSON
            _write_json(
                OUTPUT_DIR / f"{name}.json",
                {"status": "error", "message": f"{name}: {exc}", "data": []},
            )
            results[name] = {"status": "error", "error": str(exc)}
            continue

        # Gold Parquet (analytical result table)
        df.to_parquet(GOLD_DIR / f"gold_{name}.parquet", index=False)

        # API JSON response - exactly {status, message, data}
        records = _serialize(df)
        payload = {
            "status": "success",
            "message": f"{name}: returned {len(records)} row(s) "
            f"[reference_date={REFERENCE_DATE}]",
            "data": records,
        }
        _write_json(OUTPUT_DIR / f"{name}.json", payload)
        results[name] = {"status": "success", "rows": len(records)}

    return results


if __name__ == "__main__":
    print("Gold analytics:")
    print(json.dumps(run_analytics(), indent=2, default=str))
