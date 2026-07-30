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
# Usage:
#   python shadow.py               # logs yesterday (today's target date)
#   python shadow.py 2026-07-29    # backfill a specific past date

LOG_PATH = "../data/shadow_pnl.csv"


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

    result = run_dispatcher(date)
    if result is None:
        print(f"  ⏭️  Skipping {date} — dispatcher returned no result")
        return

    df_lp, df_id, df_bm = result

    da_rev, da_cost = gross(df_lp, "price", "price")
    id_rev, id_cost = gross(df_id, "id_price", "id_price")
    bm_rev, bm_cost = gross(df_bm, "ssp", "sbp")

    total_rev = da_rev + id_rev + bm_rev
    total_cost = da_cost + id_cost + bm_cost
    net_pnl = total_rev - total_cost
    day_type = classify_day(da_file)

    row = {
        "date":          date,
        "day_type":      day_type,
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

    print(f"  ✅ DA: £{da_rev-da_cost:,.0f} | ID: £{id_rev-id_cost:,.0f} | BM: £{bm_rev-bm_cost:,.0f} | Net: £{net_pnl:,.0f} | {day_type}")
    print(f"  Logged to {log_path}")


def run_shadow(date=None):
    date = date or get_target_date()
    print(f"Phase 2 Shadow Trading — {date}")
    print("=" * 60)
    run_shadow_day(date)


if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run_shadow(date_arg)
