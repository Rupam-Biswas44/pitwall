"""Command-line entry point for the data pipeline.

Examples
--------
    uv run python -m pitwall.data.build --seasons 2025 --only-round 16   # one race, quick test
    uv run python -m pitwall.data.build --seasons 2022 2023 2024 2025    # full download
    uv run python -m pitwall.data.build --clean-only                     # rebuild clean table
"""

from __future__ import annotations

import argparse
import logging

import duckdb
import polars as pl

from pitwall.config import CLEAN_DIR, RAW_DIR
from pitwall.data import ingest
from pitwall.data.clean import clean_laps


def build_clean_table() -> pl.DataFrame:
    lap_files = sorted(p for p in RAW_DIR.glob("*.parquet") if p.stem.count("_") == 1)
    if not lap_files:
        raise SystemExit(f"No raw race files in {RAW_DIR}. Run the download first.")
    raw = pl.concat([pl.read_parquet(p) for p in lap_files], how="diagonal_relaxed")
    clean = clean_laps(raw)
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    clean.write_parquet(CLEAN_DIR / "laps.parquet")
    print(f"raw laps: {raw.height:,}  ->  clean laps: {clean.height:,} "
          f"({clean.height / raw.height:.0%} kept) from {len(lap_files)} races")
    return clean


def summary() -> None:
    """Quick sanity check with DuckDB straight on the Parquet file."""
    path = (CLEAN_DIR / "laps.parquet").as_posix()
    print(duckdb.sql(f"""
        SELECT season, compound, count(*) AS laps,
               round(avg(tyre_life), 1) AS avg_tyre_age
        FROM '{path}' WHERE is_dry
        GROUP BY ALL ORDER BY season, compound
    """))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seasons", type=int, nargs="+", default=[2025])
    parser.add_argument("--only-round", type=int, help="download a single round (quick test)")
    parser.add_argument("--clean-only", action="store_true", help="skip download")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # FastF1 has its own console handler; stop its messages printing twice through ours,
    # and hide routine data-quality notes (they are handled by the cleaning step).
    ff1_log = logging.getLogger("fastf1")
    ff1_log.propagate = False
    ff1_log.setLevel(logging.ERROR)

    if not args.clean_only:
        if args.only_round:
            ingest._setup()
            for season in args.seasons:
                ingest.download_race(season, args.only_round, overwrite=args.overwrite)
        else:
            ingest.download_seasons(args.seasons, overwrite=args.overwrite)

    build_clean_table()
    summary()


if __name__ == "__main__":
    main()
