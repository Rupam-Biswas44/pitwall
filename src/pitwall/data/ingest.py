"""Download race laps from FastF1 and store one raw Parquet file per race.

Re-running is cheap: races that already have a raw file are skipped, and FastF1
keeps its own HTTP cache in ./cache.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

import fastf1
import pandas as pd
from fastf1.exceptions import RateLimitExceededError

from pitwall.config import CACHE_DIR, RAW_DIR

log = logging.getLogger(__name__)

# The hourly window resets on a rolling basis; an hour plus a margin is always safe.
RATE_LIMIT_WAIT_S = 62 * 60

LAP_COLUMNS = [
    "Driver", "DriverNumber", "Team", "LapNumber", "Stint", "Compound", "TyreLife",
    "FreshTyre", "LapTime", "Sector1Time", "Sector2Time", "Sector3Time",
    "PitInTime", "PitOutTime", "TrackStatus", "Position", "IsAccurate", "Deleted",
    "LapStartTime",
]
TIME_COLUMNS = ["LapTime", "Sector1Time", "Sector2Time", "Sector3Time", "LapStartTime"]


def _setup() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.configure(cache_dir=str(CACHE_DIR))


def completed_rounds(season: int) -> pd.DataFrame:
    """Race weekends of a season whose race date is in the past."""
    schedule = fastf1.get_event_schedule(season, include_testing=False)
    now = pd.Timestamp(datetime.now(timezone.utc)).tz_localize(None)
    done = schedule[pd.to_datetime(schedule["EventDate"]) < now]
    return done[["RoundNumber", "EventName", "Location", "Country", "EventDate"]]


def laps_to_frame(session, season: int, round_number: int) -> pd.DataFrame:
    """Flatten a loaded FastF1 race session into a plain DataFrame."""
    laps = pd.DataFrame(session.laps)
    laps = laps[[c for c in LAP_COLUMNS if c in laps.columns]].copy()

    for col in TIME_COLUMNS:
        if col in laps:
            laps[col + "_s"] = laps[col].dt.total_seconds()
            laps = laps.drop(columns=col)
    # Only whether the car entered/left the pits matters here, not the timestamp.
    laps["is_pit_in"] = laps.pop("PitInTime").notna()
    laps["is_pit_out"] = laps.pop("PitOutTime").notna()

    laps["season"] = season
    laps["round"] = round_number
    laps["event"] = session.event["EventName"]
    laps["circuit"] = session.event["Location"]
    laps["total_laps"] = int(laps["LapNumber"].max())
    return laps


def download_race(season: int, round_number: int, overwrite: bool = False) -> bool:
    """Download one race. Returns True if a file was written."""
    out = RAW_DIR / f"{season}_{round_number:02d}.parquet"
    if out.exists() and not overwrite:
        log.info("skip %s (exists)", out.name)
        return False

    log.info("downloading %s round %s ...", season, round_number)
    session = fastf1.get_session(season, round_number, "R")
    # Race-control messages are needed later for safety-car modelling.
    session.load(laps=True, telemetry=False, weather=True, messages=True)
    frame = laps_to_frame(session, season, round_number)
    frame.to_parquet(out, index=False)

    # Save race-control messages and weather next to the laps for later weeks.
    session.race_control_messages.assign(season=season, round=round_number).to_parquet(
        RAW_DIR / f"{season}_{round_number:02d}_racecontrol.parquet", index=False
    )
    session.weather_data.assign(season=season, round=round_number).to_parquet(
        RAW_DIR / f"{season}_{round_number:02d}_weather.parquet", index=False
    )
    log.info("saved %s (%d laps)", out.name, len(frame))
    return True


def _with_rate_limit_retry(func, *args, max_waits: int = 6, **kwargs):
    """Call func; if FastF1's hourly API limit is hit, sleep and try again.

    FastF1 allows ~500 API calls per hour. A full season needs more than that,
    so a long download has to pause instead of failing every remaining race.
    """
    for attempt in range(max_waits + 1):
        try:
            return func(*args, **kwargs)
        except RateLimitExceededError:
            if attempt == max_waits:
                raise
            resume = datetime.now() + timedelta(seconds=RATE_LIMIT_WAIT_S)
            log.warning("API limit reached (500 calls/hour). Waiting until %s, then continuing. "
                        "You can also stop now (Ctrl+C) and rerun later: finished races are kept.",
                        resume.strftime("%H:%M"))
            time.sleep(RATE_LIMIT_WAIT_S)


def download_seasons(seasons: list[int], overwrite: bool = False) -> None:
    _setup()
    failed = []
    for season in seasons:
        rounds = _with_rate_limit_retry(completed_rounds, season)
        for _, row in rounds.iterrows():
            rnd = int(row["RoundNumber"])
            try:
                _with_rate_limit_retry(download_race, season, rnd, overwrite=overwrite)
            except Exception as exc:  # one broken race must not stop the whole run
                log.warning("failed %s round %s (%s): %s", season, rnd, row["EventName"], exc)
                failed.append(f"{season} round {rnd}")
    if failed:
        log.warning("%d races failed: %s. Rerun the same command to retry them.",
                    len(failed), ", ".join(failed))
