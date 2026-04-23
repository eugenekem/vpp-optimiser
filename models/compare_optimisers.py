import pandas as pd
from datetime import datetime, timedelta
import os
import sys

sys.path.append(".")
from battery import Battery
from optimiser_lp import optimise_battery_lp

# --- Recreate fresh asset instances for fair comparison ---
# (Each optimiser needs its own battery instance starting at 50% SOC)

def fresh_assets():
    return [
        Battery("Battery_1", mw=10, duration_hours=2, region="North Scotland", dno="SSEN Transmission"),
        Battery("Battery_2", mw=25, duration_hours=4, region="North England", dno="Northern Powergrid"),
        Battery("Battery_3", mw=50, duration_hours=4, region="South England", dno="National Grid NGET"),
        Battery("Battery_4", mw=20, duration_hours=4, region="South Scotland", dno="SP Transmission", solar_mw=15),
        Battery("Battery_5", mw=40, duration_hours=4, region="South England", dno="National Grid NGET", solar_mw=30),
    ]

RESERVATION = {
    "Battery_1": 0.50,
    "Battery_2": 0.30,
    "Battery_3": 0.30,
    "Battery_4": 0.30,
    "Battery_5": 0.30,
}


def run_rules_based(price_series, assets):
    """Simple rules-based optimiser — charge below £20, discharge above £70.
    Respects DA capacity reservation rules for fair comparison."""
    CHARGE_THRESHOLD = 20
    DISCHARGE_THRESHOLD = 70

    total_revenue = {a.name: 0 for a in assets}

    for period in price_series.index:
        price = price_series[period]
        for battery in assets:
            committed = 1 - RESERVATION[battery.name]

            if price < CHARGE_THRESHOLD:
                available = battery.available_charge_mw() * committed
                if available > 0:
                    battery.charge(available)
                    total_revenue[battery.name] -= available * 0.5 * price
            elif price > DISCHARGE_THRESHOLD:
                available = battery.available_discharge_mw() * committed
                if available > 0:
                    battery.discharge(available)
                    total_revenue[battery.name] += available * 0.5 * price

    return total_revenue


def run_forward_looking_da(price_series, assets):
    """Forward-looking DA — top 10 cheapest charge periods, top 10 most expensive discharge.
    Respects DA capacity reservation rules."""
    TOP = 10

    sorted_prices = price_series.sort_values()
    charge_periods = set(sorted_prices.head(TOP).index)
    discharge_periods = set(sorted_prices.tail(TOP).index)

    total_revenue = {a.name: 0 for a in assets}

    for period in price_series.index:
        price = price_series[period]
        for battery in assets:
            committed = 1 - RESERVATION[battery.name]

            if period in charge_periods:
                available = battery.available_charge_mw() * committed
                if available > 0:
                    battery.charge(available)
                    total_revenue[battery.name] -= available * 0.5 * price
            elif period in discharge_periods:
                available = battery.available_discharge_mw() * committed
                if available > 0:
                    battery.discharge(available)
                    total_revenue[battery.name] += available * 0.5 * price

    return total_revenue


def run_lp(price_series, assets):
    """LP optimiser from optimiser_lp.py. Respects DA capacity reservation rules."""
    total_revenue = {}
    for battery in assets:
        committed = 1 - RESERVATION[battery.name]
        _, obj_value = optimise_battery_lp(battery, price_series, committed)
        total_revenue[battery.name] = obj_value
    return total_revenue


# --- Run comparison ---

if __name__ == "__main__":
    yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    price_file = f"../data/market_index_{yesterday}.csv"

    if not os.path.exists(price_file):
        print(f"Price file not found: {price_file}")
        sys.exit(1)

    df_prices = pd.read_csv(price_file)
    price_series = df_prices.set_index("settlementPeriod")["price"]

    print(f"\n{'='*70}")
    print(f"  OPTIMISER COMPARISON — {yesterday}")
    print(f"  Price range: £{price_series.min():.2f} to £{price_series.max():.2f}/MWh")
    print(f"  All optimisers respect DA reservation rules (fair comparison)")
    print(f"{'='*70}\n")

    # Run each optimiser with fresh assets
    print("Running rules-based optimiser...")
    rules_results = run_rules_based(price_series, fresh_assets())

    print("Running forward-looking DA optimiser...")
    fwd_results = run_forward_looking_da(price_series, fresh_assets())

    print("Running LP optimiser...")
    lp_results = run_lp(price_series, fresh_assets())

    # --- Results table ---
    print(f"\n{'Asset':<12} {'Rules-based':>15} {'Forward-DA':>15} {'LP':>15} {'LP vs Rules':>15}")
    print("-" * 72)

    total_rules = 0
    total_fwd = 0
    total_lp = 0

    for name in rules_results.keys():
        r = rules_results[name]
        f = fwd_results[name]
        l = lp_results[name]
        uplift = l - r

        total_rules += r
        total_fwd += f
        total_lp += l

        print(f"{name:<12} £{r:>13,.0f} £{f:>13,.0f} £{l:>13,.0f} £{uplift:>+13,.0f}")

    print("-" * 72)
    print(f"{'TOTAL':<12} £{total_rules:>13,.0f} £{total_fwd:>13,.0f} £{total_lp:>13,.0f} £{total_lp - total_rules:>+13,.0f}")
    print("-" * 72)

    # --- Summary ---
    lp_vs_rules_pct = ((total_lp - total_rules) / abs(total_rules) * 100) if total_rules != 0 else 0
    lp_vs_fwd_pct = ((total_lp - total_fwd) / abs(total_fwd) * 100) if total_fwd != 0 else 0

    print(f"\n{'='*70}")
    print(f"  LP uplift vs Rules-based:     £{total_lp - total_rules:+,.0f} ({lp_vs_rules_pct:+.1f}%)")
    print(f"  LP uplift vs Forward-DA:      £{total_lp - total_fwd:+,.0f} ({lp_vs_fwd_pct:+.1f}%)")
    print(f"{'='*70}\n")
