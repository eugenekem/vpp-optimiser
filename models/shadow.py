import pandas as pd
import os
import sys
from datetime import datetime, timedelta

sys.path.append(".")
from replay import fetch_if_missing, classify_day
from dispatcher import run_dispatcher

# --- Phase 2 Shadow Trading ---
#
# Runs the same DA->ID->BM dispatcher used in Phase 1, one day at a time,
# and appends the result to a running log (data/shadow_pnl.csv) instead of
# overwriting a fixed historical window like replay.py does.
#
# v25: the DA leg's schedule is now built on a genuine price FORECAST
# (reg_demand, the best-validated method - see BRIEFING.md section 10),
# not the real published price. This closes the gap the project has been
# explicit about since Phase 1: a real trader must commit to a DA schedule
# before the real price is known. Settlement is still at the real price
# (dispatcher.py's settle_price), so this is a genuinely realistic daily
# log for the first time - not just Phase 1's replay logic re-run daily.
# The 91 days logged before this change used the real price for both
# decision and settlement; they're kept as-is (not deleted or recomputed)
# and distinguished via the da_basis column, added at the same time.
#
# v27: the DA leg is now genuinely cost-aware - both the schedule DECISION
# (dispatcher.py passes real execution costs into the optimiser, so it
# skips spreads too thin to cover them, matching v20's proven approach)
# and the SETTLEMENT (net_pnl now reflects real costs, not raw price x
# power). Until this fix, dispatcher.py's live DA calls never passed
# costs at all, so every prior row - including all "reg_demand" rows -
# was computed cost-BLIND despite v20 proving cost-awareness helps.
# Distinguished via the new cost_aware column, same backfill-then-mark
# precedent as da_basis. ID/BM remain cost-blind - a distinct, still-open
# gap (no cost-aware LP variant exists for them at all yet).
#
# v29: ID and BM now carry the same cost-awareness as DA - same
# cost_discharge/cost_charge mechanism, same reused cost constants (see
# dispatcher.py), applied to both the ID/BM schedule DECISIONS and their
# SETTLEMENT. cost_aware=True now means all three legs are cost-aware, not
# just DA - the live path has no remaining cost-blind gap. No relabeling
# needed: no row in this file has ever been logged with cost_aware=True
# before this change, so the column's meaning shifts cleanly with no
# historical ambiguity.
#
# v31: the BM leg no longer decides with perfect foresight. Until now
# dispatcher.py handed optimiser_bm.py the whole day's REAL imbalance price
# (SSP == SBP) as its decision input, so ~29% of every logged net_pnl rested
# on knowing the future. BM now decides on the real DA price (known once DA
# clears - the same reason ID may know it) and still settles at the real
# imbalance price (bm_decision_method="real_da"). Over 60 days that lowers
# BM P&L ~30% and the total ~9%; DA and ID are untouched. Distinguished via
# the new bm_basis column ("foresight" = all rows before this change,
# backfilled; "real_da" = from here on), same label-don't-rewrite precedent
# as da_basis and cost_aware. Still NOT modelled: BM fill/acceptance
# (NESO chooses what is taken; pay-as-bid), so BM stays an imbalance-
# exposure figure rather than a defensible standalone revenue claim.
#
# Usage:
#   python shadow.py               # logs yesterday (today's target date)
#   python shadow.py 2026-07-29    # backfill a specific past date

LOG_PATH = "../data/shadow_pnl.csv"
DA_FORECAST_METHOD = "reg_demand"
BM_DECISION_METHOD = "real_da"


def get_target_date():
    return (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")


def already_shadowed(date, log_path=LOG_PATH):
    if not os.path.exists(log_path):
        return False
    df = pd.read_csv(log_path)
    return str(date) in df["date"].astype(str).values


def gross(df, price_col_d, price_col_c):
    rev = (df[df["action"] == "discharge"]["power_mw"] *
           df[df["action"] == "discharge"][price_col_d] * 0.5).sum()
    cost = (df[df["action"] == "charge"]["power_mw"] *
            df[df["action"] == "charge"][price_col_c] * 0.5).sum()
    return rev, cost


def run_shadow_day(date, log_path=LOG_PATH):
    if already_shadowed(date, log_path):
        print(f"  ⏭️  {date} already shadow-logged — skipping")
        return

    da_file = f"../data/market_index_{date}.csv"
    bm_file = f"../data/system_prices_{date}.csv"

    da_ok = fetch_if_missing("fetch_da_prices.py", da_file, date)
    bm_ok = fetch_if_missing("fetch_bmrs.py", bm_file, date)

    if not da_ok or not bm_ok:
        print(f"  ⏭️  Skipping {date} — data unavailable")
        return

    result = run_dispatcher(date, da_forecast_method=DA_FORECAST_METHOD,
                            bm_decision_method=BM_DECISION_METHOD)
    if result is None:
        print(f"  ⏭️  Skipping {date} — dispatcher returned no result")
        return

    df_lp, df_id, df_bm = result
    da_basis = df_lp.attrs.get("da_basis", "real")
    bm_basis = df_lp.attrs.get("bm_basis", "foresight")

    # settle_price_discharge/charge are the real price, cost-adjusted (see
    # dispatcher.py) - "price" would hold the forecast whenever da_basis !=
    # "real", and settling against your own forecast would silently overstate
    # performance; the raw "settle_price" (real but cost-blind) would
    # understate real costs, the bug this v27 fix closes. ID/BM now settle
    # cost-aware too (v29) via the same pattern - id_price/ssp/sbp adjusted
    # by the same cost_discharge/cost_charge as DA.
    da_rev, da_cost = gross(df_lp, "settle_price_discharge", "settle_price_charge")
    id_rev, id_cost = gross(df_id, "id_price_discharge", "id_price_charge")
    bm_rev, bm_cost = gross(df_bm, "ssp_settle", "sbp_settle")

    total_rev = da_rev + id_rev + bm_rev
    total_cost = da_cost + id_cost + bm_cost
    net_pnl = total_rev - total_cost
    day_type = classify_day(da_file)

    row = {
        "date":          date,
        "day_type":      day_type,
        "da_basis":      da_basis,
        "cost_aware":    True,
        "bm_basis":      bm_basis,
        "da_net":        round(da_rev - da_cost, 2),
        "id_net":        round(id_rev - id_cost, 2),
        "bm_net":        round(bm_rev - bm_cost, 2),
        "total_revenue": round(total_rev, 2),
        "total_cost":    round(total_cost, 2),
        "net_pnl":       round(net_pnl, 2),
    }

    row_df = pd.DataFrame([row])
    write_header = not os.path.exists(log_path)
    row_df.to_csv(log_path, mode="a", header=write_header, index=False)

    print(f"  ✅ DA ({da_basis}): £{da_rev-da_cost:,.0f} | ID: £{id_rev-id_cost:,.0f} | BM: £{bm_rev-bm_cost:,.0f} | Net: £{net_pnl:,.0f} | {day_type}")
    print(f"  Logged to {log_path}")


def run_shadow(date=None):
    date = date or get_target_date()
    print(f"Phase 2 Shadow Trading — {date}")
    print("=" * 60)
    run_shadow_day(date)


if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run_shadow(date_arg)
