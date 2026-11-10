"""Week 0 sanity plot: fuel-corrected lap time vs tyre age for one race.

    uv run python scripts/first_look.py --season 2025 --round 16

Opens reports/first_look.html. Each line is one driver's stint; an upward
slope is tyre degradation.
"""

import argparse

import plotly.express as px
import polars as pl

from pitwall.config import CLEAN_DIR, REPORTS_DIR

COMPOUND_COLOURS = {"SOFT": "#e8002d", "MEDIUM": "#ffd12e", "HARD": "#d9d9d9"}

parser = argparse.ArgumentParser()
parser.add_argument("--season", type=int, default=2025)
parser.add_argument("--round", type=int, required=True)
args = parser.parse_args()

laps = pl.read_parquet(CLEAN_DIR / "laps.parquet").filter(
    (pl.col("season") == args.season) & (pl.col("round") == args.round) & pl.col("is_dry")
)
if laps.is_empty():
    raise SystemExit("No laps for that race. Did you run the data build for it?")

event = laps["event"][0]
fig = px.line(
    laps.to_pandas(), x="tyre_life", y="fuel_corrected_s", color="compound",
    line_group=laps.select(pl.format("{}-{}", "driver", "stint")).to_series().to_list(),
    hover_data=["driver", "lap_number"], color_discrete_map=COMPOUND_COLOURS,
    template="plotly_dark", title=f"{args.season} {event}: fuel-corrected pace vs tyre age",
    labels={"tyre_life": "Tyre age (laps)", "fuel_corrected_s": "Fuel-corrected lap time (s)"},
)
fig.update_traces(opacity=0.6)
REPORTS_DIR.mkdir(exist_ok=True)
out = REPORTS_DIR / "first_look.html"
fig.write_html(out)
print(f"wrote {out}")
