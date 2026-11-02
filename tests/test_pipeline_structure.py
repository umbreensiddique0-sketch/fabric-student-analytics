"""Verify that every layer of the medallion produced its expected artifacts."""

from src import config


def test_source_csvs_exist():
    for t in config.SOURCE_TABLES:
        assert (config.SOURCE_DIR / f"{t}.csv").exists(), f"missing source {t}.csv"


def test_bronze_parquets_exist():
    for t in config.SOURCE_TABLES:
        assert (config.BRONZE_DIR / f"bronze_{t}.parquet").exists()


def test_silver_parquets_exist():
    for name in [
        "silver_students",
        "silver_courses",
        "silver_assignments",
        "silver_submissions",
        "silver_student_assignment_fact",
    ]:
        assert (config.SILVER_DIR / f"{name}.parquet").exists()


def test_gold_parquets_exist():
    for name in [
        "gold_missing_submissions",
        "gold_course_submission_rates",
        "gold_overdue_assignments",
    ]:
        assert (config.GOLD_DIR / f"{name}.parquet").exists()


def test_json_outputs_exist():
    for name in ["missing_submissions", "course_submission_rates", "overdue_assignments"]:
        assert (config.OUTPUT_DIR / f"{name}.json").exists()


def test_bronze_preserves_metadata(bronze_submissions):
    assert "_source_file" in bronze_submissions.columns
    assert "_ingested_at_utc" in bronze_submissions.columns
