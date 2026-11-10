"""End-to-end: fake FastF1 session -> raw Parquet -> clean table."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import polars as pl

from pitwall.data import build, ingest


def fake_session(n_laps=12):
    drivers = []
    for drv, team, base in [("AAA", "Team A", 90.0), ("BBB", "Team B", 90.4)]:
        for lap in range(1, n_laps + 1):
            stint = 1 if lap <= 6 else 2
            drivers.append({
                "Driver": drv, "DriverNumber": "1", "Team": team,
                "LapNumber": float(lap), "Stint": float(stint),
                "Compound": "MEDIUM" if stint == 1 else "HARD",
                "TyreLife": float(lap if stint == 1 else lap - 6),
                "FreshTyre": True,
                "LapTime": pd.Timedelta(seconds=base + 0.05 * lap),
                "Sector1Time": pd.Timedelta(seconds=30), "Sector2Time": pd.Timedelta(seconds=30),
                "Sector3Time": pd.Timedelta(seconds=30),
                "PitInTime": pd.Timedelta(seconds=500) if lap == 6 else pd.NaT,
                "PitOutTime": pd.Timedelta(seconds=520) if lap == 7 else pd.NaT,
                "TrackStatus": "1", "Position": 1.0, "IsAccurate": True, "Deleted": False,
                "LapStartTime": pd.Timedelta(seconds=90 * lap),
            })
    laps = pd.DataFrame(drivers)
    laps.loc[laps.index[0], "Position"] = np.nan  # real data has gaps
    return SimpleNamespace(laps=laps, event={"EventName": "Fake GP", "Location": "Nowhere"})


def test_ingest_to_clean(tmp_path, monkeypatch):
    raw_dir, clean_dir = tmp_path / "raw", tmp_path / "clean"
    raw_dir.mkdir()
    monkeypatch.setattr(build, "RAW_DIR", raw_dir)
    monkeypatch.setattr(build, "CLEAN_DIR", clean_dir)

    frame = ingest.laps_to_frame(fake_session(), 2025, 3)
    assert {"LapTime_s", "is_pit_in", "is_pit_out", "total_laps"} <= set(frame.columns)
    frame.to_parquet(raw_dir / "2025_03.parquet", index=False)
    # side files must be ignored by the lap loader
    pd.DataFrame({"x": [1]}).to_parquet(raw_dir / "2025_03_weather.parquet")

    clean = build.build_clean_table()
    # per driver: 12 laps - lap 1 - pit-in (6) - pit-out (7) = 9
    assert clean.height == 18
    assert set(clean["compound"]) == {"MEDIUM", "HARD"}
    assert clean.filter(pl.col("lap_number").is_in([1, 6, 7])).is_empty()
    assert (clean_dir / "laps.parquet").exists()
