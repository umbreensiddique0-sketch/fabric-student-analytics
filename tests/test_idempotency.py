"""Verify that re-running the pipeline reproduces identical results (determinism)."""

import contextlib
import io

import pandas as pd

import run_pipeline
from src import config


def _value_counts(df):
    return dict(sorted(df["submission_state"].value_counts().items()))


def test_rerun_preserves_fact_shape(fact):
    before_count = len(fact)
    before_states = _value_counts(fact)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        run_pipeline.main([])

    fact2 = pd.read_parquet(config.SILVER_DIR / "silver_student_assignment_fact.parquet")
    assert len(fact2) == before_count == 300
    assert _value_counts(fact2) == before_states


def test_rerun_preserves_analytics():
    import json

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        run_pipeline.main([])

    with open(config.OUTPUT_DIR / "missing_submissions.json", encoding="utf-8") as fh:
        missing = json.load(fh)["data"]
    assert len(missing) == 10

    with open(config.OUTPUT_DIR / "course_submission_rates.json", encoding="utf-8") as fh:
        rates = json.load(fh)["data"]
    assert len(rates) == 6
