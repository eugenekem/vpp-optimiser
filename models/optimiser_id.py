import pulp
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys

sys.path.append(".")
from battery import assets

# --- Intraday Optimiser ---
#
# The intraday layer re-optimises the capacity *reserved* from DA.
# DA committed a portion of each battery — the remainder is available here.
#
# Price approximation:
#   Intraday price = DA price + spread
#   Spread ~ Normal(mean=0, std=5) per settlement period
#
# This simulates intraday prices moving around DA prices with moderate noise.
# In a later phase, replace with real intraday continuous prices when available.

# DA reservation rules (must match optimiser_lp.py)
DA_RESERVATION = {
    "Battery_1": 0.50,  # 50% reserved for intraday + BM
    "Battery_2": 0.30,
    "Battery_3": 0.30,
    "Battery_4": 0.30,
    "Battery_5": 0.30,
}

# Intraday spread parameters
SPREAD_MEAN = 0.0    # £/MWh — intraday prices centred on DA
SPREAD_STD  = 5.0    # £/MWh — typical intraday volatility around DA
RANDOM_SEED = 42     # Fix seed for reproducibility in Phase 1 replay


def simulate_intraday_prices(da_prices, seed=RANDOM_SEED):
    """
    Simulate intraday prices by adding a normal spread to DA prices.

    Parameters
    ----------
    da_prices : pd.Series
        DA price series indexed by settlement period.
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    pd.Series
        Simulated intraday price series, same index as da_prices.
    """
    rng = np.random.default_rng(seed)
    spread = rng.normal(loc=SPREAD_MEAN, scale=SPREAD_STD, size=len(da_prices))
    id_prices = da_prices + spread
    return pd.Series(id_prices.values, index=da_prices.index)


def optimise_battery_id(battery, id_prices, reserved_fraction):
    """
    Solve the LP dispatch problem for the reserved intraday capacity slice.

    The intraday layer only optimises the capacity reserved from DA.
    Battery operating parameters (SOC bounds, efficiency) are identical to DA.

    Parameters
    ----------
    battery : Battery
        Battery asset object.
    id_prices : pd.Series
        Simulated intraday price series indexed by settlement period.
    reserved_fraction : float
        Fraction of battery capacity available for intraday (= DA reservation %).

    Returns
    -------
    tuple[pd.DataFrame, float]
        Schedule DataFrame and objective value (net revenue £).
    """
    T = list(id_prices.index)
    DURATION = 0.5  # 30-minute settlement periods

    # Intraday gets the reserved slice only
    id_capacity_mw = battery.mw * reserved_fraction

    prob = pulp.LpProblem(f"id_dispatch_{battery.name}", pulp.LpMaximize)

    # Decision variables — bounded to reserved capacity only
    charge = pulp.LpVariable.dicts("charge", T, lowBound=0, upBound=id_capacity_mw)
    discharge = pulp.LpVariable.dicts("discharge", T, lowBound=0, upBound=id_capacity_mw)

    # SOC bounded to full battery envelope
    # Intraday shares the same physical battery — SOC limits apply to total capacity
    soc = pulp.LpVariable.dicts(
        "soc",
        T,
        lowBound=battery.soc_min * battery.capacity_mwh,
        upBound=battery.soc_max * battery.capacity_mwh
    )

    # Objective: maximise net revenue from intraday slice
    prob += pulp.lpSum([
        discharge[t] * id_prices[t] * DURATION - charge[t] * id_prices[t] * DURATION
        for t in T
    ]), "id_net_revenue"

    # Energy balance constraints
    initial_soc = 0.50 * battery.capacity_mwh

    for i, t in enumerate(T):
        if i == 0:
            prob += soc[t] == initial_soc + charge[t] * DURATION * battery.efficiency - discharge[t] * DURATION / battery.efficiency
        else:
            prev_t = T[i - 1]
            prob += soc[t] == soc[prev_t] + charge[t] * DURATION * battery.efficiency - discharge[t] * DURATION / battery.efficiency

    # Solve
    solver = pulp.PULP_CBC_CMD(msg=False)
    prob.solve(solver)

    # Extract results
    results = []
    for t in T:
        c = charge[t].varValue if charge[t].varValue else 0
        d = discharge[t].varValue if discharge[t].varValue else 0
        s = soc[t].varValue if soc[t].varValue else 0

        if c > 0.01:
            action = "charge"
            power = c
        elif d > 0.01:
            action = "discharge"
            power = d
        else:
            action = "hold"
            power = 0

        results.append({
            "settlement_period": t,
            "da_price": 0,        # filled in after
            "id_price": round(id_prices[t], 2),
            "spread": round(id_prices[t], 2),   # filled in after
            "asset": battery.name,
            "action": action,
            "power_mw": round(power, 2),
            "soc": round(s / battery.capacity_mwh * 100, 1),
            "energy_mwh": round(s, 2)
        })

    return pd.DataFrame(results), pulp.value(prob.objective)


# --- Run for all 5 assets ---

if __name__ == "__main__":
    yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    price_file = f"../data/market_index_{yesterday}.csv"

    if not os.path.exists(price_file):
        print(f"Price file not found: {price_file}")
        print("Run fetch_da_prices.py first")
    else:
        df_prices = pd.read_csv(price_file)
        da_prices = df_prices.set_index("settlementPeriod")["price"]

        # Simulate intraday prices
        id_prices = simulate_intraday_prices(da_prices, seed=RANDOM_SEED)

        print(f"Running intraday optimiser on {yesterday}")
        print(f"DA price range:  £{da_prices.min():.2f} to £{da_prices.max():.2f}/MWh")
        print(f"ID price range:  £{id_prices.min():.2f} to £{id_prices.max():.2f}/MWh")
        print(f"Mean spread:     £{(id_prices - da_prices).mean():.2f}/MWh")
        print(f"Spread std:      £{(id_prices - da_prices).std():.2f}/MWh")
        print("=" * 60)

        all_results = []
        total_id_revenue = 0

        for battery in assets:
            reserved = DA_RESERVATION[battery.name]
            results, obj_value = optimise_battery_id(battery, id_prices, reserved)

            # Fill in DA price and spread columns
            results["da_price"] = da_prices.values
            results["spread"] = (id_prices - da_prices).values.round(2)

            all_results.append(results)
            total_id_revenue += obj_value

            charges = len(results[results["action"] == "charge"])
            discharges = len(results[results["action"] == "discharge"])
            holds = len(results[results["action"] == "hold"])

            print(f"\n{battery.name} (reserved: {reserved*100:.0f}% = {battery.mw * reserved:.0f} MW):")
            print(f"  ID net revenue:    £{obj_value:,.2f}")
            print(f"  Charge periods:    {charges}")
            print(f"  Discharge periods: {discharges}")
            print(f"  Hold periods:      {holds}")
            print(f"  Final SOC:         {results['soc'].iloc[-1]}%")

        print(f"\n{'=' * 60}")
        print(f"  PORTFOLIO ID NET REVENUE: £{total_id_revenue:,.2f}")
        print(f"{'=' * 60}")

        # Save results
        df_all = pd.concat(all_results, ignore_index=True)
        df_all.to_csv(f"../data/id_schedule_{yesterday}.csv", index=False)
        print(f"\nSaved to data/id_schedule_{yesterday}.csv")
