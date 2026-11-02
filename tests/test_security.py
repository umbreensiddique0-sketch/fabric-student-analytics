"""Tests for the security & governance bonus layer (masking, RBAC, catalog)."""

import json
import re

import pyarrow.parquet as pq
import pytest

from src import config, security


# --- PII masking ---
def test_mask_email_masks_local_part():
    assert security.mask_email("noor.wells1001@university.edu") == "n***@university.edu"


def test_mask_email_handles_none():
    assert security.mask_email(None) is None


def test_masked_report_redacts_emails():
    data = json.load(open(config.OUTPUT_DIR / "missing_submissions_masked.json",
                          encoding="utf-8"))["data"]
    assert len(data) > 0
    for row in data:
        assert re.match(r"^[a-z]\*\*\*@", row["email"]), row["email"]


# --- role-based access control ---
def test_admin_view_full_pii():
    view = security.view_students("admin")
    assert len(view) == 50
    assert "@" in view.iloc[0]["email"]
    assert "***" not in view.iloc[0]["email"]


def test_instructor_view_masks_pii():
    view = security.view_students("instructor")
    assert len(view) == 50
    assert "***" in view.iloc[0]["email"]


def test_student_view_single_row_masked():
    view = security.view_students("student", requester_id=1001)
    assert len(view) == 1
    assert int(view.iloc[0]["student_id"]) == 1001
    assert "***" in view.iloc[0]["email"]
    assert "wells1001@" not in view.iloc[0]["email"]


def test_student_role_requires_requester():
    with pytest.raises(ValueError):
        security.view_students("student")


def test_unknown_role_rejected():
    with pytest.raises(ValueError):
        security.view_students("superuser")


# --- metadata catalog + embedded parquet tags ---
def test_data_catalog_lists_tables():
    catalog = json.load(open(config.OUTPUT_DIR / "data_catalog.json", encoding="utf-8"))
    assert catalog["catalog_version"] == "1.0"
    assert len(catalog["tables"]) >= 8
    silver_students = [t for t in catalog["tables"] if t["table"] == "silver_students"][0]
    assert silver_students["pii"] is True
    assert "PII" in silver_students["tags"]


def test_secured_parquet_embeds_classification_tags():
    meta = pq.read_schema(config.GOLD_DIR / "gold_students_secured.parquet").metadata
    assert meta is not None
    assert meta.get(b"lakehouse.classification") == b"confidential"
    assert meta.get(b"lakehouse.pii") == b"true"
