import pulp
import pandas as pd
from datetime import datetime, timedelta
import os
import sys

sys.path.append(".")
from battery import assets
from config import BM_RESERVATION, DURATION, SOC_INIT

# --- Balancing Mechanism Optimiser ---
#
# Optimises the BM capacity slice using real SSP/SBP prices from Elexon BMRS.
# Discharge earns SSP, charge costs SBP.
#
# initial_soc_mwh: starting SOC handed off from the ID layer (sequential chain).


def optimise_battery_bm(battery, ssp_series, sbp_series, reserved_fraction, initial_soc_mwh=None,
                        cost_discharge=0.0, cost_charge=0.0, decision_prices=None):
    """
    Solve the LP dispatch problem for the BM capacity slice.

    Parameters
    ----------
    battery : Battery
    ssp_series : pd.Series
        System Sell Price series indexed by settlement period.
    sbp_series : pd.Series
        System Buy Price series indexed by settlement period.
    reserved_fraction : float
        Fraction of battery MW reserved for BM (BM_RESERVATION).
    initial_soc_mwh : float or None
        Starting SOC in MWh, handed off from ID layer. Defaults to SOC_INIT if None.
    cost_discharge, cost_charge : float
        Execution costs in £/MWh, same convention as optimiser_lp.py — subtracted
        from SSP on discharge and added to SBP on charge inside the objective, so
        the optimiser stops cycling for spreads too thin to cover real costs.
        Default 0.0 preserves the original costless behaviour.
    decision_prices : pd.Series or None
        If given, the LP decides charge/discharge against THESE prices (both
        directions) instead of the real SSP/SBP. The returned ssp/sbp/
        price_used columns still hold the real prices, so settlement is
        unaffected. None (default) decides on the real SSP/SBP, i.e. with
        perfect foresight of the imbalance price - the Phase 1 ceiling.

    Returns
    -------
    tuple[pd.DataFrame, float, float]
        Schedule DataFrame, objective value (£), final SOC in MWh.
    """
    T = list(ssp_series.index)
    bm_capacity_mw = battery.mw * reserved_fraction

    if initial_soc_mwh is None:
        initial_soc_mwh = SOC_INIT * battery.capacity_mwh

    prob = pulp.LpProblem(f"bm_dispatch_{battery.name}", pulp.LpMaximize)

    charge = pulp.LpVariable.dicts("charge", T, lowBound=0, upBound=bm_capacity_mw)
    discharge = pulp.LpVariable.dicts("discharge", T, lowBound=0, upBound=bm_capacity_mw)
    soc = pulp.LpVariable.dicts(
        "soc", T,
        lowBound=battery.soc_min * battery.capacity_mwh,
        upBound=battery.soc_max * battery.capacity_mwh
    )

    dec_ssp = ssp_series if decision_prices is None else decision_prices
    dec_sbp = sbp_series if decision_prices is None else decision_prices

    prob += pulp.lpSum([
        discharge[t] * (dec_ssp[t] - cost_discharge) * DURATION
        - charge[t] * (dec_sbp[t] + cost_charge) * DURATION
        for t in T
    ]), "bm_net_revenue"

    for i, t in enumerate(T):
        if i == 0:
            prob += soc[t] == initial_soc_mwh + charge[t] * DURATION * battery.efficiency - discharge[t] * DURATION / battery.efficiency
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
            price_used = sbp_series[t]
        elif d > 0.01:
            action = "discharge"
            power = d
            price_used = ssp_series[t]
        else:
            action = "hold"
            power = 0
            price_used = 0

        results.append({
            "settlement_period": t,
            "ssp": round(ssp_series[t], 2),
            "sbp": round(sbp_series[t], 2),
            "price_used": round(price_used, 2),
            "asset": battery.name,
            "action": action,
            "power_mw": round(power, 2),
            "soc": round(s / battery.capacity_mwh * 100, 1),
            "energy_mwh": round(s, 2)
        })

    df_results = pd.DataFrame(results)
    final_soc_mwh = df_results["energy_mwh"].iloc[-1] if len(df_results) > 0 else initial_soc_mwh

    return df_results, pulp.value(prob.objective), final_soc_mwh


# --- Run for all 5 assets (standalone test — uses default 50% start) ---

if __name__ == "__main__":
    yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    bmrs_file = f"../data/system_prices_{yesterday}.csv"

    if not os.path.exists(bmrs_file):
        print(f"BMRS file not found: {bmrs_file}")
        print("Run fetch_bmrs.py first")
    else:
        df_bmrs = pd.read_csv(bmrs_file)
        df_bmrs = df_bmrs[df_bmrs["settlementPeriod"] <= 48].copy()
        ssp_series = df_bmrs.set_index("settlementPeriod")["systemSellPrice"]
        sbp_series = df_bmrs.set_index("settlementPeriod")["systemBuyPrice"]

        print(f"Running BM optimiser on {yesterday}")
        print(f"SSP range: £{ssp_series.min():.2f} to £{ssp_series.max():.2f}/MWh")
        print(f"SBP range: £{sbp_series.min():.2f} to £{sbp_series.max():.2f}/MWh")
        print(f"Mean SSP:  £{ssp_series.mean():.2f}/MWh")
        print(f"Mean SBP:  £{sbp_series.mean():.2f}/MWh")
        print("=" * 60)

        all_results = []
        total_bm_revenue = 0

        for battery in assets:
            reserved = BM_RESERVATION[battery.name]
            results, obj_value, final_soc = optimise_battery_bm(battery, ssp_series, sbp_series, reserved)
            all_results.append(results)
            total_bm_revenue += obj_value

            charges = len(results[results["action"] == "charge"])
            discharges = len(results[results["action"] == "discharge"])
            holds = len(results[results["action"] == "hold"])

            print(f"\n{battery.name} (BM reserved: {reserved*100:.0f}% = {battery.mw * reserved:.0f} MW):")
            print(f"  BM net revenue:    £{obj_value:,.2f}")
            print(f"  Charge periods:    {charges}")
            print(f"  Discharge periods: {discharges}")
            print(f"  Hold periods:      {holds}")
            print(f"  Final SOC:         {results['soc'].iloc[-1]}%")

        print(f"\n{'=' * 60}")
        print(f"  PORTFOLIO BM NET REVENUE: £{total_bm_revenue:,.2f}")
        print(f"{'=' * 60}")

        df_all = pd.concat(all_results, ignore_index=True)
        df_all.to_csv(f"../data/bm_schedule_{yesterday}.csv", index=False)
        print(f"\nSaved to data/bm_schedule_{yesterday}.csv")
