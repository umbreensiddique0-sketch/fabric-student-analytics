"""
run_pipeline.py
===============
One-command end-to-end Lakehouse pipeline.

Sequence
--------
    1. generate  (src/generate_data.py) -> data/source/*.csv
    2. ingest    (src/ingest.py)        -> data/bronze/*.parquet
    3. transform (src/transform.py)     -> data/silver/*.parquet
    4. analytics (src/analytics.py)      -> data/gold/*.parquet + outputs/api_responses/*.json

Usage
-----
    python run_pipeline.py                 # full reproducible run
    python run_pipeline.py --skip-generate # reuse existing source CSVs
"""

from __future__ import annotations

import argparse
import os
import sys
import time

# Make `src` importable when running this file directly.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import analytics, generate_data, ingest, security, transform  # noqa: E402


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description="Run the Student Analytics Lakehouse pipeline."
    )
    parser.add_argument(
        "--skip-generate",
        action="store_true",
        help="Reuse existing source CSVs instead of regenerating them.",
    )
    args = parser.parse_args(argv)

    t0 = time.perf_counter()
    print("=" * 64)
    print("Student Analytics Lakehouse -- pipeline run")
    print("=" * 64)

    print("\n[1/5] Generate source data")
    if args.skip_generate:
        print("    skipped (--skip-generate)")
    else:
        generate_data.main()

    print("\n[2/5] Bronze ingestion")
    bronze = ingest.ingest_bronze()
    print(f"    {bronze}")

    print("\n[3/5] Silver transform")
    silver = transform.transform_silver()
    print(f"    {silver}")

    print("\n[4/5] Gold analytics + JSON")
    gold = analytics.run_analytics()
    print(f"    {gold}")

    print("\n[5/5] Security & governance (bonus)")
    sec = security.run_security()
    print(f"    {sec}")

    elapsed = time.perf_counter() - t0
    print("\n" + "=" * 64)
    print(f"Pipeline complete in {elapsed:.2f}s")
    print("Bronze -> data/bronze/ | Silver -> data/silver/ | Gold -> data/gold/")
    print("API responses -> outputs/api_responses/")
    print("=" * 64)


if __name__ == "__main__":
    main()
