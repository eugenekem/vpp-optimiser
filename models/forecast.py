import pandas as pd
import numpy as np
import os
import sys
import glob
import re
from datetime import datetime, timedelta

# --- Day-Ahead Price Forecasting ---
#
# Predicts tomorrow's 48 half-hourly DA prices BEFORE they are published,
# and measures whether the prediction is any good.
#
# Nothing here drives trades. Accuracy is proven first.
#
# Two hard rules:
#   1. Forecasts are written to data/forecast_{date}.csv — NEVER
#      market_index_{date}.csv, which would make fetch_if_missing() think
#      real data exists and silently poison the replay/shadow results.
#   2. A forecast for day D may only use days strictly BEFORE D.
#      Any leakage makes every accuracy number below a lie.
#
# Usage:
#   python forecast.py                # predict tomorrow
#   python forecast.py 2026-06-20     # predict a specific date
#   python forecast.py backtest       # walk-forward score of all methods
#   python forecast.py score          # score saved forecasts that now have actuals

DATA_DIR = "../data"
ACCURACY_LOG = f"{DATA_DIR}/forecast_accuracy.csv"
METHODS = ["naive", "mean_7", "weekday"]
WINDOW = 7
N_EXTREME = 4  # how many cheapest/priciest periods we care about hitting


# ---------------------------------------------------------------- data access

def available_dates():
    """All dates with a real published DA price file, sorted chronologically."""
    paths = glob.glob(f"{DATA_DIR}/market_index_*.csv")
    dates = []
    for p in paths:
        m = re.search(r"market_index_(\d{4}-\d{2}-\d{2})\.csv$", p)
        if m:
            dates.append(m.group(1))
    return sorted(dates)


def load_actual(date):
    """Real published prices for a date as a Series indexed by settlementPeriod."""
    path = f"{DATA_DIR}/market_index_{date}.csv"
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    return df.set_index("settlementPeriod")["price"].sort_index()


def is_weekend(date):
    return datetime.strptime(date, "%Y-%m-%d").weekday() >= 5


# ------------------------------------------------------------------ forecasts

def forecast_prices(target_date, method="mean_7", history=None):
    """
    Predict the 48 half-hourly prices for target_date.

    Only uses dates strictly before target_date — this is the leakage guard.

    Returns (price_series, info_dict) or (None, info_dict) if there isn't
    enough history to forecast from.
    """
    history = history if history is not None else available_dates()
    prior = [d for d in history if d < target_date]

    info = {"method": method, "n_train_days": 0, "staleness_days": None}

    if not prior:
        return None, info

    # How stale is the freshest data we're forecasting from?
    latest = prior[-1]
    info["staleness_days"] = (
        datetime.strptime(target_date, "%Y-%m-%d")
        - datetime.strptime(latest, "%Y-%m-%d")
    ).days

    if method == "naive":
        train_dates = prior[-1:]
    elif method == "mean_7":
        train_dates = prior[-WINDOW:]
    elif method == "weekday":
        want_weekend = is_weekend(target_date)
        same_type = [d for d in prior if is_weekend(d) == want_weekend]
        train_dates = same_type[-WINDOW:]
        if not train_dates:  # e.g. no weekend days seen yet
            train_dates = prior[-WINDOW:]
    else:
        raise ValueError(f"Unknown method: {method}")

    series = [load_actual(d) for d in train_dates]
    series = [s for s in series if s is not None]
    if not series:
        return None, info

    info["n_train_days"] = len(series)

    # Average each settlement period across the training days.
    forecast = pd.concat(series, axis=1).mean(axis=1).sort_index()
    forecast.name = "price"
    return forecast, info


def save_forecast(target_date, method="mean_7"):
    """Write a forecast to its own file — never the market_index_ filename."""
    forecast, info = forecast_prices(target_date, method)
    if forecast is None:
        print(f"  ⚠️  Not enough history before {target_date} to forecast")
        return None

    out = pd.DataFrame({
        "settlementPeriod": forecast.index,
        "price": forecast.values.round(2),
    })
    out["method"] = method
    out["generated_on"] = datetime.today().strftime("%Y-%m-%d")
    out["n_train_days"] = info["n_train_days"]

    path = f"{DATA_DIR}/forecast_{target_date}.csv"
    out.to_csv(path, index=False)

    print(f"  Forecast for {target_date} using '{method}' "
          f"({info['n_train_days']} training days, "
          f"freshest data {info['staleness_days']}d before target)")
    print(f"  Range: £{forecast.min():.2f} to £{forecast.max():.2f}/MWh")
    print(f"  Saved to {path}")
    return path


# -------------------------------------------------------------------- scoring

def score(forecast, actual):
    """
    Compare a forecast against what actually happened.

    MAE/RMSE say how wrong in money terms. The hit rates matter more for a
    battery: what pays is buying in the genuinely cheapest periods and selling
    in the priciest, so identifying WHICH periods those are beats getting the
    price level right.
    """
    common = forecast.index.intersection(actual.index)
    f = forecast.loc[common]
    a = actual.loc[common]

    err = f - a
    cheap_hits = len(set(f.nsmallest(N_EXTREME).index) & set(a.nsmallest(N_EXTREME).index))
    peak_hits = len(set(f.nlargest(N_EXTREME).index) & set(a.nlargest(N_EXTREME).index))

    return {
        "mae": round(err.abs().mean(), 2),
        "rmse": round(np.sqrt((err ** 2).mean()), 2),
        "cheap_hits": cheap_hits,
        "peak_hits": peak_hits,
        "n_periods": len(common),
    }


def backtest():
    """
    Walk forward through the history: predict each day using only the days
    before it, then check against what actually happened.

    This is what tells us tonight whether any of these methods work, instead
    of waiting weeks for forecasts to age.
    """
    dates = available_dates()
    print(f"Walk-forward backtest over {len(dates)} available days")
    print(f"({dates[0]} to {dates[-1]})")
    print("=" * 72)

    rows = []
    for date in dates:
        actual = load_actual(date)
        if actual is None:
            continue
        for method in METHODS:
            forecast, info = forecast_prices(date, method, history=dates)
            if forecast is None:
                continue
            row = {"date": date, "method": method}
            row.update(score(forecast, actual))
            row["n_train_days"] = info["n_train_days"]
            row["staleness_days"] = info["staleness_days"]
            rows.append(row)

    if not rows:
        print("⚠️  No days could be scored.")
        return None

    df = pd.DataFrame(rows)
    df.to_csv(ACCURACY_LOG, index=False)

    summary = df.groupby("method").agg(
        days=("date", "count"),
        mae=("mae", "mean"),
        rmse=("rmse", "mean"),
        cheap_hits=("cheap_hits", "mean"),
        peak_hits=("peak_hits", "mean"),
    ).reindex(METHODS).dropna(how="all")

    naive_mae = summary.loc["naive", "mae"] if "naive" in summary.index else None

    print(f"\n{'method':<10} {'days':>5} {'MAE':>9} {'RMSE':>9} "
          f"{'cheap':>7} {'peak':>7} {'skill':>8}")
    print("-" * 72)
    for method, r in summary.iterrows():
        if naive_mae:
            skill = (naive_mae - r["mae"]) / naive_mae * 100
            skill_str = f"{skill:+.1f}%"
        else:
            skill_str = "—"
        print(f"{method:<10} {int(r['days']):>5} "
              f"£{r['mae']:>8.2f} £{r['rmse']:>8.2f} "
              f"{r['cheap_hits']:>6.1f}/{N_EXTREME} {r['peak_hits']:>5.1f}/{N_EXTREME} "
              f"{skill_str:>8}")

    print("-" * 72)
    print(f"cheap/peak = of the {N_EXTREME} genuinely cheapest/priciest periods,")
    print(f"             how many the forecast also picked (higher is better)")
    print(f"skill      = MAE improvement vs the naive 'copy yesterday' benchmark")
    print(f"\nSaved per-day detail to {ACCURACY_LOG}")

    best = summary["mae"].idxmin()
    if best == "naive":
        print(f"\n⚠️  No method beat naive. That is a real result, not a failure —")
        print(f"   it means copying yesterday is currently as good as anything else.")
    else:
        print(f"\nBest by MAE: {best}")

    return df


def score_saved():
    """Score any saved forecast files that now have real prices to check against."""
    paths = sorted(glob.glob(f"{DATA_DIR}/forecast_*.csv"))
    rows = []
    for p in paths:
        m = re.search(r"forecast_(\d{4}-\d{2}-\d{2})\.csv$", p)
        if not m:
            continue
        date = m.group(1)
        actual = load_actual(date)
        if actual is None:
            print(f"  {date}: no actuals published yet — skipping")
            continue
        df_f = pd.read_csv(p)
        forecast = df_f.set_index("settlementPeriod")["price"].sort_index()
        row = {"date": date, "method": df_f["method"].iloc[0] if "method" in df_f else "unknown"}
        row.update(score(forecast, actual))
        rows.append(row)
        print(f"  {date} [{row['method']}]: MAE £{row['mae']} | "
              f"cheap {row['cheap_hits']}/{N_EXTREME} | peak {row['peak_hits']}/{N_EXTREME}")

    if not rows:
        print("No saved forecasts have actuals to score against yet.")
        return None

    df = pd.DataFrame(rows)
    write_header = not os.path.exists(ACCURACY_LOG)
    df.to_csv(ACCURACY_LOG, mode="a", header=write_header, index=False)
    print(f"\nAppended {len(rows)} row(s) to {ACCURACY_LOG}")
    return df


# ----------------------------------------------------------------------- main

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None

    if arg == "backtest":
        backtest()
    elif arg == "score":
        print("Scoring saved forecasts against published prices")
        print("=" * 60)
        score_saved()
    else:
        target = arg or (datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        method = sys.argv[2] if len(sys.argv) > 2 else "mean_7"
        print(f"Day-Ahead Price Forecast — {target}")
        print("=" * 60)
        save_forecast(target, method)
