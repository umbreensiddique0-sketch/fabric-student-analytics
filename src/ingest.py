"""
ingest.py
=========
Bronze layer: ingest raw source CSVs into Parquet, preserving source records
exactly as-is and attaching lightweight ingestion metadata.

Bronze contract
----------------
* No cleaning, no type coercion, no filtering - raw fidelity.
* Add `_source_file` (provenance) and `_ingested_at_utc` (load timestamp).
* Output: data/bronze/bronze_<table>.parquet

In a real Microsoft Fabric Lakehouse this step maps to a notebook / pipeline
that lands CSV files from a source into the Bronze Delta table unmodified.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import pandas as pd

# Allow running as a script (`python src/ingest.py`) or as a module.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import BRONZE_DIR, SOURCE_DIR, SOURCE_TABLES  # noqa: E402


def ingest_bronze() -> dict:
    """Land each source CSV into a Bronze Parquet file with metadata."""
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    ingested_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    summary = {}
    for name in SOURCE_TABLES:
        src = SOURCE_DIR / f"{name}.csv"
        if not src.exists():
            raise FileNotFoundError(
                f"Source file missing: {src}. Run `python -m src.generate_data` first."
            )
        df = pd.read_csv(src)  # raw: dates stay as strings, types inferred
        df["_source_file"] = src.name
        df["_ingested_at_utc"] = ingested_at

        out = BRONZE_DIR / f"bronze_{name}.parquet"
        df.to_parquet(out, index=False)
        summary[name] = len(df)
    return summary


if __name__ == "__main__":
    import json

    print("Bronze ingestion:")
    print(json.dumps(ingest_bronze(), indent=2))
