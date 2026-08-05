import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime

sys.path.append(".")
from battery import assets
from config import ID_RESERVATION, BM_RESERVATION, SOC_INIT, DURATION
from optimiser_lp import optimise_battery_lp
import forecast as F

# --- Does forecast accuracy actually convert into money? ---
#
# forecast.py showed the regression method is ~18% more accurate (MAE) than
# copying yesterday. That does NOT automatically mean more profit: a battery
# earns by charging in the cheapest periods and discharging in the priciest,
# so WHICH periods you pick matters more than the price level you predicted.
#
# This answers the question in pounds.
#
# For each day and each pricing method:
#   1. Build a dispatch schedule using the FORECAST prices (what you would
#      actually commit to, day-ahead, knowing only the forecast).
#   2. Settle that schedule at the ACTUAL published prices (what you really
#      get paid).
#
# The "perfect" arm optimises on actual prices — the crystal-ball ceiling.
# It is NOT a tradeable result; it exists only to measure what fraction of
# the theoretical maximum each real method captures.
#
# Capture ratio = realised P&L / perfect-foresight P&L. That ratio is the
# headline number: how much of the available money the forecast actually wins.
#
# DA layer only. The forecast is a day-ahead price forecast; ID prices are
# simulated and BM uses SSP/SBP, so including them would muddy the result.
#
# Usage:
#   python forecast_pnl.py            # all available days
#   python forecast_pnl.py 60         # most recent 60 days only

DATA_DIR = "../data"
OUT_PATH = f"{DATA_DIR}/forecast_pnl.csv"
ARMS = ["perfect", "naive", "mean_7", "regression", "reg_demand"]


def settle(schedule, actual_prices):
    """
    Pay a dispatch schedule at the prices that actually happened.

    Revenue on discharge, cost on charge, both at the real settled price —
    regardless of what price the schedule was built on.
    """
    df = schedule[schedule["settlement_period"].isin(actual_prices.index)].copy()
    if df.empty:
        return None
    paid = df["settlement_period"].map(actual_prices)

    disch = df["action"] == "discharge"
    chg = df["action"] == "charge"
    revenue = (df.loc[disch, "power_mw"] * paid[disch] * DURATION).sum()
    cost = (df.loc[chg, "power_mw"] * paid[chg] * DURATION).sum()
    return revenue - cost


def run_day(date, history):
    """
    One day, every arm. Returns a dict of arm -> realised P&L, or None if the
    day cannot be evaluated by every arm (so comparisons stay like-for-like).
    """
    actual = F.load_actual(date)
    if actual is None or actual.empty:
        return None

    # Build each arm's price view. 'perfect' cheats deliberately.
    price_views = {"perfect": actual}
    for method in ARMS:
        if method == "perfect":
            continue
        fc, _ = F.forecast_prices(date, method, history=history)
        if fc is None:
            return None  # skip the whole day rather than compare unequal arms
        price_views[method] = fc

    results = {}
    for arm, prices in price_views.items():
        total = 0.0
        for battery in assets:
            da_committed = 1 - (ID_RESERVATION[battery.name] + BM_RESERVATION[battery.name])
            schedule, _, _ = optimise_battery_lp(
                battery, prices,
                committed_capacity=da_committed,
                initial_soc_mwh=SOC_INIT * battery.capacity_mwh,
            )
            pnl = settle(schedule, actual)
            if pnl is None:
                return None
            total += pnl
        results[arm] = total

    return results


def main(limit=None):
    # Always keep the FULL history for training; `limit` only restricts which
    # days we evaluate. Passing a truncated history would starve the
    # regression of its 90-day window and silently skip every day.
    history = F.available_dates()
    dates = history[-limit:] if limit else history

    print(f"Forecast-to-P&L test over {len(dates)} candidate days")
    print("Dispatch built on forecast prices, settled at actual prices.")
    print("=" * 72)

    rows, skipped = [], 0
    t0 = datetime.now()

    for i, date in enumerate(dates, 1):
        try:
            res = run_day(date, history)
        except Exception as e:
            print(f"  {date}: error {type(e).__name__}: {e}")
            skipped += 1
            continue

        if res is None:
            skipped += 1
        else:
            rows.append({"date": date, **res})

        if i % 25 == 0 or i == len(dates):
            el = (datetime.now() - t0).total_seconds()
            rate = el / i
            print(f"  [{i:>4}/{len(dates)}] {date} | scored {len(rows)}, "
                  f"skipped {skipped} | ~{rate*(len(dates)-i)/60:.0f} min left")

    if not rows:
        print("\n⚠️  No days could be scored.")
        return

    df = pd.DataFrame(rows)
    df.to_csv(OUT_PATH, index=False)

    print("\n" + "=" * 72)
    print(f"RESULTS — {len(df)} days scored, {skipped} skipped")
    print("=" * 72)

    perfect_total = df["perfect"].sum()

    print(f"\n{'arm':<12} {'total P&L':>16} {'per day':>13} {'capture':>10}")
    print("-" * 72)
    for arm in ARMS:
        total = df[arm].sum()
        capture = total / perfect_total * 100 if perfect_total else float("nan")
        label = arm + (" *" if arm == "perfect" else "")
        print(f"{label:<12} £{total:>15,.0f} £{total/len(df):>12,.0f} {capture:>9.1f}%")
    print("-" * 72)
    print("* perfect = optimised on actual prices (crystal ball).")
    print("  NOT a tradeable result — it is the ceiling, used to measure capture.")
    print("  capture = share of that ceiling each real method actually won.")

    # The question that matters: does the more accurate forecast earn more?
    reg, base = df["regression"].sum(), df["mean_7"].sum()
    if base:
        delta = (reg - base) / abs(base) * 100
        print(f"\nregression vs mean_7: {delta:+.1f}% P&L "
              f"(£{reg - base:,.0f} over {len(df)} days)")
        print("Compare against the +18.0% MAE improvement — if P&L barely moves,")
        print("better price accuracy is NOT translating into better decisions.")

    print(f"\nSaved per-day detail to {OUT_PATH}")


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(limit)
