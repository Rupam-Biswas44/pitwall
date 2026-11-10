import polars as pl
import pytest

from pitwall.config import FUEL_EFFECT_S_PER_LAP
from pitwall.data.clean import clean_laps


def make_raw(rows: list[dict]) -> pl.DataFrame:
    """Build a raw-laps frame shaped like ingest.laps_to_frame output."""
    base = {
        "season": 2025, "round": 1, "event": "Test GP", "circuit": "Testville",
        "Driver": "AAA", "DriverNumber": "1", "Team": "Team A", "total_laps": 10,
        "Stint": 1.0, "Compound": "MEDIUM", "FreshTyre": True, "Position": 1.0,
        "TrackStatus": "1", "is_pit_in": False, "is_pit_out": False,
        "IsAccurate": True, "Deleted": False,
    }
    return pl.DataFrame([{**base, **r} for r in rows])


def stint(n_laps=8, start_lap=2, base=90.0, **overrides):
    return [
        {"LapNumber": float(start_lap + i), "TyreLife": float(start_lap + i),
         "LapTime_s": base + 0.05 * i, **overrides}
        for i in range(n_laps)
    ]


def test_keeps_clean_green_laps():
    out = clean_laps(make_raw(stint()))
    assert out.height == 8


def test_drops_lap_one_pit_laps_and_safety_car():
    rows = stint()
    rows.append({"LapNumber": 1.0, "TyreLife": 1.0, "LapTime_s": 95.0})
    rows[2]["is_pit_in"] = True
    rows[3]["is_pit_out"] = True
    rows[4]["TrackStatus"] = "14"   # safety car came out during the lap
    rows[5]["TrackStatus"] = "6"    # VSC
    out = clean_laps(make_raw(rows))
    assert 1 not in out["lap_number"].to_list()
    assert out.height == 4


def test_drops_deleted_and_missing_times():
    rows = stint()
    rows[0]["Deleted"] = True
    rows[1]["LapTime_s"] = None
    assert clean_laps(make_raw(rows)).height == 6


def test_drops_outliers_within_stint():
    rows = stint()
    rows[4]["LapTime_s"] = 120.0   # spun / stuck in traffic
    out = clean_laps(make_raw(rows))
    assert 120.0 not in out["lap_time_s"].to_list()
    assert out.height == 7


def test_fuel_correction_and_features():
    out = clean_laps(make_raw(stint(n_laps=1, start_lap=4)))
    row = out.row(0, named=True)
    assert row["laps_remaining"] == 6
    assert row["fuel_corrected_s"] == pytest.approx(90.0 - FUEL_EFFECT_S_PER_LAP * 6)
    assert row["is_dry"] is True


def test_wet_compound_flagged():
    out = clean_laps(make_raw(stint(Compound="intermediate")))
    assert out["compound"][0] == "INTERMEDIATE"
    assert not out["is_dry"].any()


def test_outlier_median_is_per_stint_not_per_race():
    # A slow second stint must not be flagged just because stint 1 was faster.
    rows = stint() + stint(start_lap=10, base=97.0, Stint=2.0)
    out = clean_laps(make_raw(rows))
    assert out.filter(pl.col("stint") == 2).height == 8
