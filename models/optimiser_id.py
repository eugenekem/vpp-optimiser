import pulp
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys

sys.path.append(".")
from battery import assets
from config import ID_RESERVATION, DURATION, SOC_INIT, ID_SPREAD_MEAN, ID_SPREAD_STD, ID_RANDOM_SEED

# --- Intraday Optimiser ---
#
# Re-optimises the ID capacity slice using simulated intraday prices.
# Intraday price = DA price + Normal(mean=0, std=5) spread per period.
# Capacity slice defined in config.py — ID_RESERVATION per asset.


def simulate_intraday_prices(da_prices, seed=ID_RANDOM_SEED):
    rng = np.random.default_rng(seed)
    spread = rng.normal(loc=ID_SPREAD_MEAN, scale=ID_SPREAD_STD, size=len(da_prices))
    return pd.Series(da_prices.values + spread, index=da_prices.index)


def optimise_battery_id(battery, id_prices, reserved_fraction):
    T = list(id_prices.index)
    id_capacity_mw = battery.mw * reserved_fraction

    prob = pulp.LpProblem(f"id_dispatch_{battery.name}", pulp.LpMaximize)

    charge = pulp.LpVariable.dicts("charge", T, lowBound=0, upBound=id_capacity_mw)
    discharge = pulp.LpVariable.dicts("discharge", T, lowBound=0, upBound=id_capacity_mw)
    soc = pulp.LpVariable.dicts(
        "soc", T,
        lowBound=battery.soc_min * battery.capacity_mwh,
        upBound=battery.soc_max * battery.capacity_mwh
    )

    prob += pulp.lpSum([
        discharge[t] * id_prices[t] * DURATION - charge[t] * id_prices[t] * DURATION
        for t in T
    ]), "id_net_revenue"

    initial_soc = SOC_INIT * battery.capacity_mwh

    for i, t in enumerate(T):
        if i == 0:
            prob += soc[t] == initial_soc + charge[t] * DURATION * battery.efficiency - discharge[t] * DURATION / battery.efficiency
        else:
            prev_t = T[i - 1]
            prob += soc[t] == soc[prev_t] + charge[t] * DURATION * battery.efficiency - discharge[t] * DURATION / battery.efficiency

    solver = pulp.PULP_CBC_CMD(msg=False)
    prob.solve(solver)

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
            "da_price": 0,
            "id_price": round(id_prices[t], 2),
            "spread": 0,
            "asset": battery.name,
            "action": action,
            "power_mw": round(power, 2),
            "soc": round(s / battery.capacity_mwh * 100, 1),
            "energy_mwh": round(s, 2)
        })

    return pd.DataFrame(results), pulp.value(prob.objective)


if __name__ == "__main__":
    yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    price_file = f"../data/market_index_{yesterday}.csv"

    if not os.path.exists(price_file):
        print(f"Price file not found: {price_file}")
        print("Run fetch_da_prices.py first")
    else:
        df_prices = pd.read_csv(price_file)
        da_prices = df_prices.set_index("settlementPeriod")["price"]
        id_prices = simulate_intraday_prices(da_prices)

        print(f"Running intraday optimiser on {yesterday}")
        print(f"DA price range:  £{da_prices.min():.2f} to £{da_prices.max():.2f}/MWh")
        print(f"ID price range:  £{id_prices.min():.2f} to £{id_prices.max():.2f}/MWh")
        print(f"Mean spread:     £{(id_prices - da_prices).mean():.2f}/MWh")
        print(f"Spread std:      £{(id_prices - da_prices).std():.2f}/MWh")
        print("=" * 60)

        all_results = []
        total_id_revenue = 0

        for battery in assets:
            reserved = ID_RESERVATION[battery.name]
            results, obj_value = optimise_battery_id(battery, id_prices, reserved)

            results["da_price"] = da_prices.values
            results["spread"] = (id_prices - da_prices).values.round(2)

            all_results.append(results)
            total_id_revenue += obj_value

            charges = len(results[results["action"] == "charge"])
            discharges = len(results[results["action"] == "discharge"])
            holds = len(results[results["action"] == "hold"])

            print(f"\n{battery.name} (ID reserved: {reserved*100:.0f}% = {battery.mw * reserved:.0f} MW):")
            print(f"  ID net revenue:    £{obj_value:,.2f}")
            print(f"  Charge periods:    {charges}")
            print(f"  Discharge periods: {discharges}")
            print(f"  Hold periods:      {holds}")
            print(f"  Final SOC:         {results['soc'].iloc[-1]}%")

        print(f"\n{'=' * 60}")
        print(f"  PORTFOLIO ID NET REVENUE: £{total_id_revenue:,.2f}")
        print(f"{'=' * 60}")

        df_all = pd.concat(all_results, ignore_index=True)
        df_all.to_csv(f"../data/id_schedule_{yesterday}.csv", index=False)
        print(f"\nSaved to data/id_schedule_{yesterday}.csv")
