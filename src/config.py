"""
config.py
=========
Single source of truth for shared constants and lakehouse paths used across the
pipeline modules (ingest, transform, analytics, security) and the data generator.

All paths are resolved relative to the project root so the pipeline runs
correctly regardless of the current working directory.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

# Fixed snapshot date for all overdue / reporting logic. Keep in sync with
# .env.example. Changing this date changes every analytical result.
REFERENCE_DATE = date(2025, 6, 30)

# Seed for deterministic synthetic data generation.
RANDOM_SEED = 42

# Toggle PII masking in the security/governance layer (bonus step).
ENABLE_MASKING = True

# ---------------------------------------------------------------------------
# Lakehouse layer directories (resolved from the project root)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent

SOURCE_DIR = ROOT / "data" / "source"
BRONZE_DIR = ROOT / "data" / "bronze"
SILVER_DIR = ROOT / "data" / "silver"
GOLD_DIR = ROOT / "data" / "gold"
OUTPUT_DIR = ROOT / "outputs" / "api_responses"
SQL_DIR = ROOT / "sql"
EVIDENCE_DIR = ROOT / "evidence"

# The four source entities.
SOURCE_TABLES = ["students", "courses", "assignments", "submissions"]
