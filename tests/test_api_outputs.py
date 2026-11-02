"""Validate the {status, message, data} API JSON responses."""

import json

from src import config


def _load(name):
    with open(config.OUTPUT_DIR / f"{name}.json", encoding="utf-8") as fh:
        return json.load(fh)


def test_missing_response_shape():
    r = _load("missing_submissions")
    assert set(r.keys()) == {"status", "message", "data"}
    assert r["status"] == "success"
    assert isinstance(r["data"], list)


def test_missing_response_content():
    data = _load("missing_submissions")["data"]
    assert len(data) == 10
    assert all(row["assignment_id"] == 101 for row in data)
    assert all(row["submission_state"] == "missing" for row in data)
    assert all(row["assignment_title"] == "Assignment_101" for row in data)


def test_rates_response_shape():
    r = _load("course_submission_rates")
    assert set(r.keys()) == {"status", "message", "data"}
    assert r["status"] == "success"


def test_rates_response_content():
    data = _load("course_submission_rates")["data"]
    assert len(data) == 6
    for row in data:
        assert 0 <= row["submission_rate_pct"] <= 100
        assert row["eligible_students"] > 0
        # eligible_pairs == eligible_students x assignments_due
        assert row["eligible_pairs"] == row["eligible_students"] * row["assignments_due"]
        assert row["submitted_pairs"] <= row["eligible_pairs"]


def test_overdue_response_shape():
    r = _load("overdue_assignments")
    assert set(r.keys()) == {"status", "message", "data"}
    assert r["status"] == "success"


def test_overdue_response_content():
    data = _load("overdue_assignments")["data"]
    assert len(data) >= 1
    for row in data:
        assert row["overdue_count"] >= 1
        assert isinstance(row["overdue_assignment_ids"], list)
        assert len(row["overdue_assignment_ids"]) == row["overdue_count"]
        assert len(row["overdue_assignment_titles"]) == row["overdue_count"]
