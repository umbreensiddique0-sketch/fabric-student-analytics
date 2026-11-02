"""Shared pytest fixtures for the Student Analytics Lakehouse.

A session-scoped autouse fixture runs the full pipeline once (with stdout
suppressed) so every test operates on freshly produced Bronze/Silver/Gold
artifacts. Result DataFrames and JSON responses are exposed as fixtures.
"""

import contextlib
import io
import json
import os
import sys

import pandas as pd
import pytest

# Make the project root importable.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import run_pipeline  # noqa: E402
from src import config  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _run_pipeline_once():
    """Run the whole pipeline once for the test session (stdout suppressed)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        run_pipeline.main([])
    yield buf


# ---------------------------------------------------------------------------
# Silver layer fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def fact() -> pd.DataFrame:
    return pd.read_parquet(config.SILVER_DIR / "silver_student_assignment_fact.parquet")


@pytest.fixture(scope="session")
def silver_students() -> pd.DataFrame:
    return pd.read_parquet(config.SILVER_DIR / "silver_students.parquet")


@pytest.fixture(scope="session")
def silver_courses() -> pd.DataFrame:
    return pd.read_parquet(config.SILVER_DIR / "silver_courses.parquet")


@pytest.fixture(scope="session")
def silver_assignments() -> pd.DataFrame:
    return pd.read_parquet(config.SILVER_DIR / "silver_assignments.parquet")


@pytest.fixture(scope="session")
def silver_submissions() -> pd.DataFrame:
    return pd.read_parquet(config.SILVER_DIR / "silver_submissions.parquet")


@pytest.fixture(scope="session")
def bronze_submissions() -> pd.DataFrame:
    return pd.read_parquet(config.BRONZE_DIR / "bronze_submissions.parquet")


# ---------------------------------------------------------------------------
# JSON API response fixtures
# ---------------------------------------------------------------------------
def _load_json(name: str) -> dict:
    with open(config.OUTPUT_DIR / f"{name}.json", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def json_missing() -> dict:
    return _load_json("missing_submissions")


@pytest.fixture(scope="session")
def json_rates() -> dict:
    return _load_json("course_submission_rates")


@pytest.fixture(scope="session")
def json_overdue() -> dict:
    return _load_json("overdue_assignments")
