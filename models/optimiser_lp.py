import pulp
import pandas as pd
from datetime import datetime, timedelta
import os
import sys

sys.path.append(".")
from battery import assets

# --- LP Optimiser for single battery ---

def optimise_battery_lp(battery, price_series, committed_capacity=1.0):
    """
    Solve the LP dispatch problem for a single battery across all 48 periods.
    
    Returns a DataFrame with the optimal schedule.
    """
    
    T = list(price_series.index)  # list of settlement periods
    
    # --- Create LP problem ---
    prob = pulp.LpProblem(f"battery_dispatch_{battery.name}", pulp.LpMaximize)
    
    # --- Decision variables ---
    # Charge power per period (MW)
    charge = pulp.LpVariable.dicts(
        "charge",
        T,
        lowBound=0,
        upBound=battery.mw * committed_capacity
    )
    
    # Discharge power per period (MW)
    discharge = pulp.LpVariable.dicts(
        "discharge",
        T,
        lowBound=0,
        upBound=battery.mw * committed_capacity
    )
    
    # State of charge per period (MWh)
    soc = pulp.LpVariable.dicts(
        "soc",
        T,
        lowBound=battery.soc_min * battery.capacity_mwh,
        upBound=battery.soc_max * battery.capacity_mwh
    )
    
    # --- Objective function ---
    # Maximise: Σ [discharge × price × 0.5 - charge × price × 0.5]
    prob += pulp.lpSum([
        discharge[t] * price_series[t] * 0.5 - charge[t] * price_series[t] * 0.5
        for t in T
    ]), "total_net_revenue"
    
    # --- Constraints ---
    # 1. Energy balance
    initial_soc = 0.50 * battery.capacity_mwh
    for i, t in enumerate(T):
        if i == 0:
            # First period: SOC = initial + charge - discharge
            prob += soc[t] == initial_soc + charge[t] * battery.efficiency - discharge[t] / battery.efficiency
        else:
            # Subsequent periods: SOC = previous SOC + charge - discharge
            prev_t = T[i-1]
            prob += soc[t] == soc[prev_t] + charge[t] * battery.efficiency - discharge[t] / battery.efficiency
    
    # --- Solve ---
    solver = pulp.PULP_CBC_CMD(msg=False)
    prob.solve(solver)
    
    # --- Extract results ---
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
            "price": price_series[t],
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
        price_series = df_prices.set_index("settlementPeriod")["price"]
        
        print(f"Running LP optimiser on {yesterday}")
        print(f"Price range: £{price_series.min():.2f} to £{price_series.max():.2f}/MWh")
        print("="*60)
        
        # DA Capacity Reservation Rules
        reservation = {
            "Battery_1": 0.50,
            "Battery_2": 0.30,
            "Battery_3": 0.30,
            "Battery_4": 0.30,
            "Battery_5": 0.30,
        }
        
        all_results = []
        total_revenue = 0
        
        for battery in assets:
            committed = 1 - reservation[battery.name]
            results, obj_value = optimise_battery_lp(battery, price_series, committed)
            all_results.append(results)
            total_revenue += obj_value
            
            charges = len(results[results["action"] == "charge"])
            discharges = len(results[results["action"] == "discharge"])
            holds = len(results[results["action"] == "hold"])
            
            print(f"\n{battery.name} (committed: {committed*100:.0f}%):")
            print(f"  Net revenue:       £{obj_value:,.2f}")
            print(f"  Charge periods:    {charges}")
            print(f"  Discharge periods: {discharges}")
            print(f"  Hold periods:      {holds}")
            print(f"  Final SOC:         {results['soc'].iloc[-1]}%")
        
        print(f"\n{'='*60}")
        print(f"  PORTFOLIO NET REVENUE: £{total_revenue:,.2f}")
        print(f"{'='*60}")
        
        # Save combined results
        df_all = pd.concat(all_results, ignore_index=True)
        df_all.to_csv(f"../data/lp_schedule_{yesterday}.csv", index=False)
        print(f"\nSaved to data/lp_schedule_{yesterday}.csv")