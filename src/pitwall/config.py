"""Project-wide paths and modelling constants."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "cache"          # FastF1 HTTP cache (large, never commit)
RAW_DIR = ROOT / "data" / "raw"     # one Parquet file per race, as downloaded
CLEAN_DIR = ROOT / "data" / "clean" # analysis-ready tables
REPORTS_DIR = ROOT / "reports"      # generated plots / HTML

# 2022-2025 = ground-effect era, comparable cars. 2026 is a new rules era:
# keep it as a separate out-of-distribution test set.
TRAIN_SEASONS = [2022, 2023, 2024]
TEST_SEASONS = [2025]
NEW_ERA_SEASONS = [2026]

# Fuel effect: lap-time cost of carrying fuel, in seconds per lap of fuel remaining.
# ~0.03 s/kg x ~1.7 kg/lap is a common public rule of thumb. This is an ASSUMPTION;
# in Week 3 we estimate it from data instead of hard-coding it.
FUEL_EFFECT_S_PER_LAP = 0.055

# A lap slower than this multiple of the driver's stint median is treated as
# disturbed (traffic, mistake, yellow flag in one sector) and dropped.
OUTLIER_FACTOR = 1.07

DRY_COMPOUNDS = {"SOFT", "MEDIUM", "HARD"}
