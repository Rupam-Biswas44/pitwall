"""Turn raw FastF1 laps into an analysis-ready table of representative race laps.

A lap is kept only if it reflects the car's real pace on its current tyres:
no lap 1, no in/out laps, no safety car / VSC / yellow flags, not deleted,
and not a big outlier within the driver's stint.
"""

from __future__ import annotations

import polars as pl

from pitwall.config import DRY_COMPOUNDS, FUEL_EFFECT_S_PER_LAP, OUTLIER_FACTOR

# FastF1 TrackStatus is a string of the status codes seen during the lap,
# e.g. "1" = all green, "4" = safety car, "6"/"7" = VSC, "2" = yellow.
GREEN_ONLY = r"^1+$"

OUTPUT_COLUMNS = [
    "season", "round", "event", "circuit", "driver", "team", "lap_number", "total_laps",
    "laps_remaining", "stint", "compound", "tyre_life", "fresh_tyre", "position",
    "lap_time_s", "fuel_corrected_s", "is_dry",
]


def standardise(raw: pl.DataFrame) -> pl.DataFrame:
    """Rename FastF1 columns to snake_case and fix types."""
    return raw.select(
        pl.col("season").cast(pl.Int32),
        pl.col("round").cast(pl.Int32),
        pl.col("event"),
        pl.col("circuit"),
        pl.col("Driver").alias("driver"),
        pl.col("Team").alias("team"),
        pl.col("LapNumber").cast(pl.Int32).alias("lap_number"),
        pl.col("total_laps").cast(pl.Int32),
        pl.col("Stint").cast(pl.Int32).alias("stint"),
        pl.col("Compound").str.to_uppercase().alias("compound"),
        pl.col("TyreLife").cast(pl.Int32).alias("tyre_life"),
        pl.col("FreshTyre").alias("fresh_tyre"),
        pl.col("Position").cast(pl.Int32).alias("position"),
        pl.col("LapTime_s").alias("lap_time_s"),
        pl.col("TrackStatus").cast(pl.Utf8).alias("track_status"),
        pl.col("is_pit_in"),
        pl.col("is_pit_out"),
        pl.col("IsAccurate").alias("is_accurate"),
        pl.col("Deleted").fill_null(False).alias("deleted"),
    )


def filter_representative(laps: pl.DataFrame) -> pl.DataFrame:
    """Keep only laps that represent clean race pace."""
    basic = laps.filter(
        pl.col("lap_time_s").is_not_null()
        & pl.col("stint").is_not_null()
        & pl.col("tyre_life").is_not_null()
        & (pl.col("lap_number") > 1)
        & ~pl.col("is_pit_in")
        & ~pl.col("is_pit_out")
        & pl.col("track_status").fill_null("").str.contains(GREEN_ONLY)
        & ~pl.col("deleted")
    )
    stint_key = ["season", "round", "driver", "stint"]
    return (
        basic.with_columns(pl.col("lap_time_s").median().over(stint_key).alias("_stint_median"))
        .filter(pl.col("lap_time_s") <= pl.col("_stint_median") * OUTLIER_FACTOR)
        .drop("_stint_median")
    )


def add_features(laps: pl.DataFrame) -> pl.DataFrame:
    laps_remaining = pl.col("total_laps") - pl.col("lap_number")
    return laps.with_columns(
        laps_remaining.alias("laps_remaining"),
        # Remove the cost of fuel weight so the remaining trend is mostly tyre wear.
        (pl.col("lap_time_s") - FUEL_EFFECT_S_PER_LAP * laps_remaining).alias("fuel_corrected_s"),
        pl.col("compound").is_in(list(DRY_COMPOUNDS)).alias("is_dry"),
    )


def clean_laps(raw: pl.DataFrame) -> pl.DataFrame:
    """Full cleaning pipeline: raw FastF1 laps -> representative laps."""
    return add_features(filter_representative(standardise(raw))).select(OUTPUT_COLUMNS).sort(
        ["season", "round", "driver", "lap_number"]
    )
