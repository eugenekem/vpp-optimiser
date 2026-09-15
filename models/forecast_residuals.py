import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

sys.path.append(".")
import forecast as F

# --- Empirical forecast-error scenarios ---
#
# Nothing in this codebase has ever stored a forecast's actual per-period
# error - forecast.py::score() computes it internally but only keeps the
# aggregate MAE/RMSE. This rebuilds it: for every historical date, what did
# reg_demand's forecast actually get wrong, period by period?
#
# That error history is the foundation for genuine scenario generation.
# sample_scenarios() draws WHOLE historical days' real error patterns
# (a historical bootstrap) rather than independent per-period noise - it
# preserves realistic within-day correlation (e.g. a systematic morning
# under-prediction), unlike optimiser_id.py's simulate_intraday_prices(),
# which assumes iid Normal(ID_SPREAD_MEAN, ID_SPREAD_STD) noise. Building
# on real data here, not an assumed noise shape, is deliberate.
#
# Usage:
#   python forecast_residuals.py build reg_demand
#   python forecast_residuals.py scenarios 2026-09-14 reg_demand 20

DATA_DIR = "../data"
N_PERIODS = 48
SP_COLS = [f"sp_{i}" for i in range(1, N_PERIODS + 1)]
MIN_ELIGIBLE_DATES = 5  # below this, scenario generation isn't meaningful - caller must fall back

# Real historical GB prices across the whole dataset (773 days) range £-103 to
# £1,353/MWh - the £1,353 spike (2025-01-08, a real cold-snap event the
# forecast completely missed) is itself the all-time max on record. Adding a
# borrowed day's residual to an unrelated day's point forecast can combine
# an extreme miss with an unrelated baseline and produce a scenario price
# far outside anything ever actually observed (e.g. transplanting 2025-01-08's
# -£1,178 residual onto a calm £100/MWh day gives ~-£1,078, which has never
# happened and never could on a day like that). Clipping to a band a bit
# wider than the real observed extremes keeps genuine tail risk (a scenario
# CAN still approach the real historical spike/crash) while ruling out
# combination artifacts that don't correspond to anything the market has
# ever actually done.
PRICE_FLOOR = -200.0
PRICE_CEIL = 1500.0


def residual_path(method):
    return f"{DATA_DIR}/forecast_residuals_{method}.csv"


def build_residual_history(method="reg_demand", history=None):
    """
    Walk-forward, mirroring forecast.py::backtest()'s own loop exactly: for
    every date with a real published price, forecast it (using only prior
    days - forecast_prices() enforces that itself) and keep the full
    per-period error, not just the aggregate score.

    Writes wide-format data/forecast_residuals_{method}.csv - one row per
    date, one column per settlement period (sp_1..sp_48). Short days (46
    periods, spring clock-change) leave sp_47/sp_48 as NaN; long days (50
    periods, autumn clock-change) simply have periods 49-50 dropped - both
    handled at draw time via dropna(), not here.
    """
    dates = history if history is not None else F.available_dates()
    print(f"Building residual history for '{method}' over {len(dates)} candidate days")

    rows = []
    for date in dates:
        actual = F.load_actual(date)
        if actual is None:
            continue
        forecast, info = F.forecast_prices(date, method, history=dates)
        if forecast is None:
            continue

        residual = (forecast - actual).dropna()
        row = {"date": date}
        for sp, val in residual.items():
            if 1 <= sp <= N_PERIODS:
                row[f"sp_{sp}"] = round(val, 4)
        rows.append(row)

    if not rows:
        print("⚠️  No days could be scored - nothing written.")
        return None

    df = pd.DataFrame(rows).set_index("date")
    df = df.reindex(columns=SP_COLS)  # fixed column order, NaN where a period never existed
    df.to_csv(residual_path(method))

    n_vals = df.notna().sum().sum()
    print(f"  {len(df)} days written to {residual_path(method)}")
    print(f"  {n_vals} individual period-residuals ({n_vals / len(df):.1f} avg periods/day)")
    return df


_residual_cache = {}


def load_residual_history(method="reg_demand"):
    """Cached read - shadow.py calls this once per process; a backtest loop calls it once too
    and reuses it across hundreds of sample_scenarios() calls rather than re-reading the CSV."""
    if method not in _residual_cache:
        path = residual_path(method)
        if not os.path.exists(path):
            return None
        _residual_cache[method] = pd.read_csv(path, index_col="date")
    return _residual_cache[method]


def sample_scenarios(target_date, method="reg_demand", n_scenarios=20,
                      residual_history=None, rng=None):
    """
    Bootstrap n_scenarios price paths for target_date: draw n_scenarios
    historical dates' REAL residual patterns (with replacement) and add each
    to target_date's own point forecast.

    Leakage guard re-enforced HERE, not just at build time - this is called
    with arbitrary historical target_dates during backtesting, not only
    "today", so eligibility must be re-checked per call.

    Returns list[pd.Series] (each aligned to the point forecast's own
    settlement periods), or None if there isn't enough residual history yet
    to draw from - caller must fall back to the deterministic forecast.
    """
    residual_history = residual_history if residual_history is not None else load_residual_history(method)
    if residual_history is None:
        return None

    eligible = residual_history.index[residual_history.index < target_date]
    if len(eligible) < MIN_ELIGIBLE_DATES:
        return None

    fc, info = F.forecast_prices(target_date, method, history=F.available_dates())
    if fc is None:
        return None

    rng = rng if rng is not None else np.random.default_rng()
    drawn = rng.choice(eligible.values, size=n_scenarios, replace=True)

    fc_cols = fc.rename(index=lambda sp: f"sp_{sp}")
    scenarios = []
    for d in drawn:
        # fill_value=0: a missing residual for some period (the drawn day was
        # itself short, e.g. a clock-change day) means "no error information
        # for that period", not "drop it" - every scenario must end up with
        # the SAME index (fc's full index) so optimise_battery_lp_cvar can
        # compare them period-for-period. Using fill_value=None here (the
        # earlier, buggy version) silently dropped whichever periods that
        # SPECIFIC draw's residual row happened to lack, so different
        # scenarios in the same list ended up with different shapes.
        residual_row = residual_history.loc[d].fillna(0)
        scenario_wide = fc_cols.add(residual_row, fill_value=0)
        scenario = pd.Series(
            {int(col.split("_")[1]): val for col, val in scenario_wide.items()
             if col.startswith("sp_")}
        ).sort_index()
        scenario = scenario.reindex(fc.index)
        scenario = scenario.clip(lower=PRICE_FLOOR, upper=PRICE_CEIL)
        if not scenario.empty and not scenario.isna().any():
            scenarios.append(scenario)

    return scenarios if scenarios else None


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        method = sys.argv[2] if len(sys.argv) > 2 else "reg_demand"
        build_residual_history(method)
    elif len(sys.argv) > 1 and sys.argv[1] == "scenarios":
        target_date = sys.argv[2]
        method = sys.argv[3] if len(sys.argv) > 3 else "reg_demand"
        n = int(sys.argv[4]) if len(sys.argv) > 4 else 20
        scenarios = sample_scenarios(target_date, method, n)
        if scenarios is None:
            print(f"No scenarios available for {target_date} (insufficient residual history)")
        else:
            print(f"{len(scenarios)} scenarios for {target_date} ({method}):")
            for i, s in enumerate(scenarios[:5]):
                print(f"  scenario {i}: £{s.min():.2f} to £{s.max():.2f}/MWh")
            if len(scenarios) > 5:
                print(f"  ... and {len(scenarios) - 5} more")
    else:
        print("Usage: python forecast_residuals.py build [method]")
        print("       python forecast_residuals.py scenarios <date> [method] [n]")
