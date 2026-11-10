# Pit Wall

An F1 race strategy simulator built on public timing data: tyre degradation models,
Monte Carlo race simulation, and a post-race **strategy audit** that asks
*"given what was known at that moment, was there a better call?"*

> Status: **Week 1, data pipeline.** Models and UI come next (see roadmap).

## Data sources

| Source | What | Coverage |
|---|---|---|
| [FastF1](https://docs.fastf1.dev) | Lap timing, tyres, pit stops, race control, weather, telemetry | 2018 → now |
| [OpenF1](https://openf1.org) | Same live-timing feed as a REST API, plus team radio; used later for live mode | 2023 → now |
| [Jolpica](https://github.com/jolpica/jolpica-f1) | Results and standings (Ergast successor) | 1950 → now |

All are free and unofficial; not affiliated with Formula 1.

## Setup

Install once: [Git](https://git-scm.com), [VS Code](https://code.visualstudio.com),
[uv](https://docs.astral.sh/uv/getting-started/installation/), and later
[Node.js LTS](https://nodejs.org) for the frontend.

```bash
cd pitwall
uv sync                 # creates .venv with Python + all packages
uv run pytest           # 8 tests should pass
```

## Run the pipeline

```bash
# 1. Quick test: one race (2025 round 16 = Monza)
uv run python -m pitwall.data.build --seasons 2025 --only-round 16
uv run python scripts/first_look.py --season 2025 --round 16   # -> reports/first_look.html

# 2. Full download (slow the first time, then cached)
uv run python -m pitwall.data.build --seasons 2022 2023 2024 2025
```

Output: `data/clean/laps.parquet`, one row per representative race lap. Query it
directly with DuckDB:

```python
import duckdb
duckdb.sql("SELECT circuit, compound, avg(fuel_corrected_s) FROM 'data/clean/laps.parquet' GROUP BY ALL")
```

### What counts as a "clean" lap

Dropped: lap 1, pit-in and pit-out laps, any lap with safety car / VSC / yellow
flags, deleted laps, and laps more than 7% slower than the driver's stint median.
Each kept lap gets a **fuel-corrected time** (currently a fixed 0.055 s per lap
of fuel; estimated from data in Week 3).

## Project layout

```
src/pitwall/
  config.py          paths, seasons, modelling constants
  data/ingest.py     FastF1 -> data/raw/<season>_<round>.parquet (+ race control, weather)
  data/clean.py      raw laps -> representative laps (pure functions, tested)
  data/build.py      CLI that runs both
scripts/first_look.py  degradation plot for one race
tests/               unit + end-to-end tests
```

## Roadmap

- [x] Week 0–1: setup, data pipeline
- [ ] Week 2: exploratory analysis, pit-loss per circuit
- [ ] Week 3–5: tyre degradation model (fuel effect estimated, Bayesian hierarchical)
- [ ] Week 6–8: race simulator, Monte Carlo, backtest on 2025
- [ ] Week 9–10: strategy optimizer, strategy audit, RL agent (stretch)
- [ ] Week 9–13: FastAPI backend + Next.js / React Three Fiber "pit wall" UI
- [ ] Week 14–16: deploy, write-up, demo video

Train on 2022–2024, test on 2025; 2026 (new regulations) is a separate
out-of-distribution test.
