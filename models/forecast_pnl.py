import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime

sys.path.append(".")
from battery import assets
from config import (ID_RESERVATION, BM_RESERVATION, SOC_INIT, DURATION,
                    COST_DEGRADATION, COST_FEE, COST_IMPACT)
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


def settle(schedule, actual_prices, with_costs=False):
    """
    Pay a dispatch schedule at the prices that actually happened.

    Revenue on discharge, cost on charge, both at the real settled price —
    regardless of what price the schedule was built on.

    with_costs applies the execution costs from config.py: degradation on
    discharged MWh, plus fees and own-bid price impact in both directions.
    """
    df = schedule[schedule["settlement_period"].isin(actual_prices.index)].copy()
    if df.empty:
        return None
    paid = df["settlement_period"].map(actual_prices)

    d_adj = (COST_IMPACT + COST_FEE + COST_DEGRADATION) if with_costs else 0.0
    c_adj = (COST_IMPACT + COST_FEE) if with_costs else 0.0

    disch = df["action"] == "discharge"
    chg = df["action"] == "charge"
    revenue = (df.loc[disch, "power_mw"] * (paid[disch] - d_adj) * DURATION).sum()
    cost = (df.loc[chg, "power_mw"] * (paid[chg] + c_adj) * DURATION).sum()
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
        totals = {"free": 0.0, "blind": 0.0, "aware": 0.0}
        for battery in assets:
            da_committed = 1 - (ID_RESERVATION[battery.name] + BM_RESERVATION[battery.name])
            kw = dict(committed_capacity=da_committed,
                      initial_soc_mwh=SOC_INIT * battery.capacity_mwh)

            # Cost-blind schedule: the optimiser ignores costs (as before).
            # Settled both without costs (the old headline) and with costs
            # (what that same schedule would really have earned).
            sched_blind, _, _ = optimise_battery_lp(battery, prices, **kw)

            # Cost-aware schedule: costs are inside the objective, so thin
            # spreads that cannot cover them are simply not traded.
            sched_aware, _, _ = optimise_battery_lp(
                battery, prices,
                cost_discharge=COST_IMPACT + COST_FEE + COST_DEGRADATION,
                cost_charge=COST_IMPACT + COST_FEE,
                **kw)

            free = settle(sched_blind, actual, with_costs=False)
            blind = settle(sched_blind, actual, with_costs=True)
            aware = settle(sched_aware, actual, with_costs=True)
            if None in (free, blind, aware):
                return None
            totals["free"] += free
            totals["blind"] += blind
            totals["aware"] += aware

        results[arm] = totals

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
            flat = {"date": date}
            for arm, t in res.items():
                for variant, v in t.items():
                    flat[f"{arm}__{variant}"] = v
            rows.append(flat)

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

    print(f"\nCosts applied: degradation £{COST_DEGRADATION:.2f}/MWh discharged, "
          f"fees £{COST_FEE:.2f}/MWh, impact £{COST_IMPACT:.2f}/MWh (both ways)")

    ceiling_free = df["perfect__free"].sum()
    ceiling_aware = df["perfect__aware"].sum()

    print(f"\n{'arm':<12} {'no costs':>14} {'costs, blind':>15} "
          f"{'costs, aware':>15} {'capture':>9}")
    print("-" * 76)
    for arm in ARMS:
        free = df[f"{arm}__free"].sum()
        blind = df[f"{arm}__blind"].sum()
        aware = df[f"{arm}__aware"].sum()
        cap = aware / ceiling_aware * 100 if ceiling_aware else float("nan")
        label = arm + (" *" if arm == "perfect" else "")
        print(f"{label:<12} £{free:>13,.0f} £{blind:>14,.0f} "
              f"£{aware:>14,.0f} {cap:>8.1f}%")
    print("-" * 76)
    print("no costs     = the old headline: costless trading at the index price")
    print("costs, blind = same schedule, but costs actually charged")
    print("costs, aware = optimiser knows the costs and skips uneconomic cycling")
    print("capture      = share of the cost-aware perfect-foresight ceiling")
    print("* perfect = optimised on actual prices. NOT tradeable — the ceiling only.")

    # How much of the old headline survives once trading is not free?
    best = "reg_demand" if "reg_demand" in ARMS else "regression"
    b_free, b_blind, b_aware = (df[f"{best}__free"].sum(),
                                df[f"{best}__blind"].sum(),
                                df[f"{best}__aware"].sum())
    print(f"\n--- {best}: what costs actually do ---")
    print(f"  costless headline        £{b_free:>13,.0f}")
    print(f"  after costs, cost-blind  £{b_blind:>13,.0f}  "
          f"({(b_blind-b_free)/abs(b_free)*100:+.1f}%)")
    print(f"  after costs, cost-aware  £{b_aware:>13,.0f}  "
          f"({(b_aware-b_free)/abs(b_free)*100:+.1f}% vs costless)")
    if b_blind:
        print(f"  value of cost-awareness  £{b_aware-b_blind:>13,.0f}  "
              f"({(b_aware-b_blind)/abs(b_blind)*100:+.1f}% vs trading blind)")

    reg, base = df[f"{best}__aware"].sum(), df["mean_7__aware"].sum()
    if base:
        print(f"\n{best} vs mean_7, both cost-aware: "
              f"{(reg-base)/abs(base)*100:+.1f}% P&L (£{reg-base:,.0f})")

    print(f"\nSaved per-day detail to {OUT_PATH}")


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(limit)
