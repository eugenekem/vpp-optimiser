import pandas as pd
from datetime import datetime, timedelta
import os
import sys

sys.path.append(".")
from battery import assets
from config import DA_RESERVATION, ID_RESERVATION, BM_RESERVATION, SOC_INIT
from optimiser_lp import optimise_battery_lp
from optimiser_id import optimise_battery_id, simulate_intraday_prices
from optimiser_bm import optimise_battery_bm

# --- Dispatcher ---
#
# Orchestrates the sequential SOC handoff chain:
#
#   DA optimiser  (start: 50% SOC)        -> final_soc_da
#   ID optimiser  (start: final_soc_da)   -> final_soc_id
#   BM optimiser  (start: final_soc_id)   -> final_soc_bm
#
# Each layer optimises its own MW capacity slice (config.py reservations)
# but they now share ONE continuous SOC trajectory across the trading day,
# reflecting the physical reality of a single battery.
#
# Output: combined per-asset, per-period schedule + portfolio P&L summary.


def run_dispatcher(date):
    price_file = f"../data/market_index_{date}.csv"
    bmrs_file = f"../data/system_prices_{date}.csv"

    if not os.path.exists(price_file):
        print(f"Price file not found: {price_file}")
        print("Run fetch_da_prices.py first")
        return None

    if not os.path.exists(bmrs_file):
        print(f"BMRS file not found: {bmrs_file}")
        print("Run fetch_bmrs.py first")
        return None

    df_prices = pd.read_csv(price_file)
    da_prices = df_prices.set_index("settlementPeriod")["price"]
    id_prices = simulate_intraday_prices(da_prices)

    df_bmrs = pd.read_csv(bmrs_file)
    df_bmrs = df_bmrs[df_bmrs["settlementPeriod"] <= 48].copy()
    ssp_series = df_bmrs.set_index("settlementPeriod")["systemSellPrice"]
    sbp_series = df_bmrs.set_index("settlementPeriod")["systemBuyPrice"]

    print(f"Running dispatcher for {date}")
    print(f"DA price range: £{da_prices.min():.2f} to £{da_prices.max():.2f}/MWh")
    print(f"ID price range: £{id_prices.min():.2f} to £{id_prices.max():.2f}/MWh")
    print(f"SSP range:      £{ssp_series.min():.2f} to £{ssp_series.max():.2f}/MWh")
    print(f"SBP range:      £{sbp_series.min():.2f} to £{sbp_series.max():.2f}/MWh")
    print("=" * 60)

    all_lp, all_id, all_bm = [], [], []
    total_revenue, total_cost = 0.0, 0.0

    for battery in assets:
        initial_soc = SOC_INIT * battery.capacity_mwh

        # --- DA layer ---
        da_committed = 1 - (ID_RESERVATION[battery.name] + BM_RESERVATION[battery.name])
        df_lp, lp_rev, soc_after_da = optimise_battery_lp(
            battery, da_prices, committed_capacity=da_committed,
            initial_soc_mwh=initial_soc
        )

        # --- ID layer (starts where DA left off) ---
        id_reserved = ID_RESERVATION[battery.name]
        df_id, id_rev, soc_after_id = optimise_battery_id(
            battery, id_prices, reserved_fraction=id_reserved,
            initial_soc_mwh=soc_after_da
        )

        # --- BM layer (starts where ID left off) ---
        bm_reserved = BM_RESERVATION[battery.name]
        df_bm, bm_rev, soc_after_bm = optimise_battery_bm(
            battery, ssp_series, sbp_series, reserved_fraction=bm_reserved,
            initial_soc_mwh=soc_after_id
        )

        # Attach extra columns for traceability
        df_id["da_price"] = da_prices.values
        df_id["spread"] = (id_prices - da_prices).values.round(2)

        all_lp.append(df_lp)
        all_id.append(df_id)
        all_bm.append(df_bm)

        # --- Compute gross revenue and cost directly from each schedule ---
        # DA/ID: revenue = discharge x price x 0.5h, cost = charge x price x 0.5h
        def gross_rev_cost(df, price_col):
            disc = df[df["action"] == "discharge"]
            chg = df[df["action"] == "charge"]
            rev = (disc["power_mw"] * disc[price_col] * 0.5).sum()
            cost = (chg["power_mw"] * chg[price_col] * 0.5).sum()
            return rev, cost

        lp_gross_rev, lp_gross_cost = gross_rev_cost(df_lp, "price")
        id_gross_rev, id_gross_cost = gross_rev_cost(df_id, "id_price")

        # BM: revenue uses SSP on discharge, cost uses SBP on charge
        bm_disc = df_bm[df_bm["action"] == "discharge"]
        bm_chg = df_bm[df_bm["action"] == "charge"]
        bm_gross_rev = (bm_disc["power_mw"] * bm_disc["ssp"] * 0.5).sum()
        bm_gross_cost = (bm_chg["power_mw"] * bm_chg["sbp"] * 0.5).sum()

        asset_revenue = lp_gross_rev + id_gross_rev + bm_gross_rev
        asset_cost = lp_gross_cost + id_gross_cost + bm_gross_cost
        asset_net = asset_revenue - asset_cost

        total_revenue += asset_revenue
        total_cost += asset_cost

        # SOC bound check across full chain
        min_soc_pct = min(
            df_lp["soc"].min(), df_id["soc"].min(), df_bm["soc"].min()
        )
        max_soc_pct = max(
            df_lp["soc"].max(), df_id["soc"].max(), df_bm["soc"].max()
        )

        print(f"\n{battery.name}:")
        print(f"  DA committed: {da_committed*100:.0f}% | revenue £{lp_rev:,.2f} | SOC start 50.0% -> end {soc_after_da/battery.capacity_mwh*100:.1f}%")
        print(f"  ID reserved:  {id_reserved*100:.0f}% | revenue £{id_rev:,.2f} | SOC start {soc_after_da/battery.capacity_mwh*100:.1f}% -> end {soc_after_id/battery.capacity_mwh*100:.1f}%")
        print(f"  BM reserved:  {bm_reserved*100:.0f}% | revenue £{bm_rev:,.2f} | SOC start {soc_after_id/battery.capacity_mwh*100:.1f}% -> end {soc_after_bm/battery.capacity_mwh*100:.1f}%")
        print(f"  Gross revenue: £{asset_revenue:,.2f} | Gross cost: £{asset_cost:,.2f}")
        print(f"  Combined net P&L: £{asset_net:,.2f}")
        print(f"  SOC range across day: {min_soc_pct:.1f}% to {max_soc_pct:.1f}%")

        if min_soc_pct < 9.99 or max_soc_pct > 90.01:
            print(f"  ⚠️  SOC BREACH detected")

    total_net = total_revenue - total_cost

    print(f"\n{'=' * 60}")
    print(f"  PORTFOLIO TOTAL REVENUE: £{total_revenue:,.2f}")
    print(f"  PORTFOLIO TOTAL COST:    £{total_cost:,.2f}")
    print(f"  PORTFOLIO NET P&L:       £{total_net:,.2f}")
    print(f"{'=' * 60}")

    # --- Save combined schedules ---
    df_lp_all = pd.concat(all_lp, ignore_index=True)
    df_id_all = pd.concat(all_id, ignore_index=True)
    df_bm_all = pd.concat(all_bm, ignore_index=True)

    df_lp_all.to_csv(f"../data/lp_schedule_{date}.csv", index=False)
    df_id_all.to_csv(f"../data/id_schedule_{date}.csv", index=False)
    df_bm_all.to_csv(f"../data/bm_schedule_{date}.csv", index=False)

    print(f"\nSaved updated schedules with SOC handoff to data/*_schedule_{date}.csv")

    return df_lp_all, df_id_all, df_bm_all


if __name__ == "__main__":
    yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    run_dispatcher(yesterday)
