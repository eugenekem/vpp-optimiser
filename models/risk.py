import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

def calculate_var(pnl_series, confidence=0.95):
    """
    Calculate Value at Risk (VaR) at a given confidence level.
    Uses historical simulation method.
    VaR answers: what is the worst loss at X% confidence?
    """
    sorted_pnl = np.sort(pnl_series)
    index = int((1 - confidence) * len(sorted_pnl))
    var = sorted_pnl[index]
    return var


def calculate_volatility(pnl_series):
    """
    Calculate daily P&L volatility (standard deviation).
    Higher volatility = more uncertain returns.
    """
    return np.std(pnl_series)


def calculate_sharpe(pnl_series, risk_free=0):
    """
    Sharpe ratio — return per unit of risk.
    Higher is better. Above 1.0 is good, above 2.0 is excellent.
    """
    mean = np.mean(pnl_series)
    std = np.std(pnl_series)
    if std == 0:
        return 0
    return (mean - risk_free) / std


def scenario_analysis(df_pnl, scenarios):
    """
    Stress test P&L under different price scenarios.
    scenarios: dict of {scenario_name: price_multiplier}
    """
    results = {}
    for scenario_name, multiplier in scenarios.items():
        df_scenario = df_pnl.copy()
        df_scenario["scenario_price"] = df_scenario["market_price"] * multiplier
        df_scenario["scenario_revenue"] = df_scenario.apply(
            lambda row: row["power_mw"] * 0.5 * row["scenario_price"]
            if row["action"] == "discharge" else 0, axis=1
        )
        df_scenario["scenario_cost"] = df_scenario.apply(
            lambda row: row["power_mw"] * 0.5 * row["scenario_price"]
            if row["action"] == "charge" else 0, axis=1
        )
        scenario_net = df_scenario["scenario_revenue"].sum() - df_scenario["scenario_cost"].sum()
        results[scenario_name] = round(scenario_net, 2)
    return results


def concentration_risk(df_pnl):
    """
    Measure how concentrated P&L is across assets.
    High concentration = over-reliance on one asset.
    """
    asset_pnl = {}
    for asset in df_pnl["asset"].unique():
        df_asset = df_pnl[df_pnl["asset"] == asset]
        net = df_asset["revenue"].sum() - df_asset["cost"].sum()
        asset_pnl[asset] = round(net, 2)

    total = sum(asset_pnl.values())
    concentration = {
        asset: round(pnl / total * 100, 1) if total != 0 else 0
        for asset, pnl in asset_pnl.items()
    }
    return asset_pnl, concentration


def print_risk_report(df_pnl, date):
    """Print a clean risk report."""

    print(f"\n{'='*60}")
    print(f"  RISK REPORT — {date}")
    print(f"{'='*60}")

    # --- P&L distribution for VaR ---
    # Simulate daily P&L distribution using settlement period net P&L
    period_pnl = df_pnl.groupby("settlement_period")["net_pnl"].sum().values

    var_95 = calculate_var(period_pnl, confidence=0.95)
    var_99 = calculate_var(period_pnl, confidence=0.99)
    volatility = calculate_volatility(period_pnl)
    sharpe = calculate_sharpe(period_pnl)

    print(f"\n--- Price risk ---")
    print(f"  Period P&L volatility:  £{volatility:>8.2f}/period")
    print(f"  VaR (95% confidence):   £{var_95:>8.2f} worst period")
    print(f"  VaR (99% confidence):   £{var_99:>8.2f} worst period")
    print(f"  Sharpe ratio:           {sharpe:>8.2f}")

    # --- Scenario analysis ---
    scenarios = {
        "Base case (actual)":     1.00,
        "Price -20%":             0.80,
        "Price -50% (crash)":     0.50,
        "Price +20%":             1.20,
        "Price +50% (spike)":     1.50,
    }

    scenario_results = scenario_analysis(df_pnl, scenarios)

    print(f"\n--- Scenario analysis ---")
    base = scenario_results["Base case (actual)"]
    for name, value in scenario_results.items():
        diff = value - base
        diff_str = f"({'+' if diff >= 0 else ''}{diff:,.0f})" if name != "Base case (actual)" else ""
        print(f"  {name:<30} £{value:>10,.2f}  {diff_str}")

    # --- Concentration risk ---
    asset_pnl, concentration = concentration_risk(df_pnl)

    print(f"\n--- Concentration risk ---")
    for asset, pct in concentration.items():
        bar = "█" * int(pct / 5)
        print(f"  {asset:<12} {pct:>5.1f}%  {bar}")

    # --- Risk flags ---
    print(f"\n--- Risk flags ---")
    flags = []

    max_concentration = max(concentration.values())
    if max_concentration > 50:
        flags.append(f"  ⚠ High concentration — one asset driving >{max_concentration:.0f}% of P&L")

    if sharpe < 0.5:
        flags.append(f"  ⚠ Low Sharpe ratio ({sharpe:.2f}) — returns not justifying risk taken")

    if var_95 < -500:
        flags.append(f"  ⚠ High period VaR — worst periods losing £{abs(var_95):.0f}+")

    if not flags:
        flags.append("  ✓ No major risk flags for this session")

    for flag in flags:
        print(flag)

    print(f"\n{'='*60}\n")


# --- Run against yesterday's P&L file ---

if __name__ == "__main__":
    yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    pnl_file = f"../data/pnl_{yesterday}.csv"

    if not os.path.exists(pnl_file):
        print(f"P&L file not found: {pnl_file}")
        print("Run pnl.py first")
    else:
        df_pnl = pd.read_csv(pnl_file)
        print_risk_report(df_pnl, yesterday)