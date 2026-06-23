import pandas as pd
import subprocess
import os
import sys
from datetime import datetime, timedelta

sys.path.append("models")
from dispatcher import run_dispatcher

# --- Phase 1 Historical Replay ---
#
# Runs the full DA→ID→BM dispatcher across a range of historical dates.
# For each date:
#   1. Checks if market data files already exist — skips fetch if so
#   2. Fetches missing data passing the specific date to each fetch script
#   3. Runs the dispatcher and captures daily P&L
#   4. Appends results to data/replay_pnl.csv
#
# Usage:
#   python replay.py        # runs last 30 days
#   python replay.py 60     # runs last 60 days


def fetch_if_missing(script_name, expected_file, date):
    """Run a fetch script with a specific date only if the output file doesn't exist."""
    if os.path.exists(expected_file):
        return True
    print(f"  Fetching {script_name} for {date}...")
    result = subprocess.run(
        ["python", f"../scripts/{script_name}", date],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  ⚠️  {script_name} failed: {result.stderr.strip()}")
        return False
    if not os.path.exists(expected_file):
        print(f"  ⚠️  {script_name} ran but file not created — data may not exist for {date}")
        return False
    return True


def classify_day(da_price_file):
    """Return day type based on DA price spread."""
    try:
        df = pd.read_csv(da_price_file)
        price_range = df["price"].max() - df["price"].min()
        min_price = df["price"].min()
        if min_price < 0 and price_range > 40:
            return "🟢 green"
        elif price_range > 50:
            return "🟡 amber"
        else:
            return "🔴 red"
    except Exception:
        return "unknown"


def run_replay(days=30):
    today = datetime.today()
    dates = [(today - timedelta(days=i+1)).strftime("%Y-%m-%d") for i in range(days)]
    dates = sorted(dates)  # chronological order

    print(f"Phase 1 Historical Replay — {days} days")
    print(f"Date range: {dates[0]} to {dates[-1]}")
    print("=" * 60)

    results = []
    skipped = []

    for date in dates:
        print(f"\n📅 {date}")

        da_file = f"../data/market_index_{date}.csv"
        bm_file = f"../data/system_prices_{date}.csv"

        da_ok = fetch_if_missing("fetch_da_prices.py", da_file, date)
        bm_ok = fetch_if_missing("fetch_bmrs.py", bm_file, date)

        if not da_ok or not bm_ok:
            print(f"  ⏭️  Skipping {date} — data unavailable")
            skipped.append(date)
            continue

        try:
            result = run_dispatcher(date)
            if result is None:
                print(f"  ⏭️  Skipping {date} — dispatcher returned no result")
                skipped.append(date)
                continue

            df_lp, df_id, df_bm = result

            def gross(df, price_col_d, price_col_c):
                rev  = (df[df["action"] == "discharge"]["power_mw"] *
                        df[df["action"] == "discharge"][price_col_d] * 0.5).sum()
                cost = (df[df["action"] == "charge"]["power_mw"] *
                        df[df["action"] == "charge"][price_col_c] * 0.5).sum()
                return rev, cost

            da_rev,  da_cost  = gross(df_lp, "price",    "price")
            id_rev,  id_cost  = gross(df_id, "id_price", "id_price")
            bm_rev,  bm_cost  = gross(df_bm, "ssp",      "sbp")

            total_rev  = da_rev  + id_rev  + bm_rev
            total_cost = da_cost + id_cost + bm_cost
            net_pnl    = total_rev - total_cost
            day_type   = classify_day(da_file)

            results.append({
                "date":          date,
                "day_type":      day_type,
                "da_net":        round(da_rev - da_cost, 2),
                "id_net":        round(id_rev - id_cost, 2),
                "bm_net":        round(bm_rev - bm_cost, 2),
                "total_revenue": round(total_rev, 2),
                "total_cost":    round(total_cost, 2),
                "net_pnl":       round(net_pnl, 2),
            })

            print(f"  ✅ DA: £{da_rev-da_cost:,.0f} | ID: £{id_rev-id_cost:,.0f} | BM: £{bm_rev-bm_cost:,.0f} | Net: £{net_pnl:,.0f} | {day_type}")

        except Exception as e:
            print(f"  ❌ Error on {date}: {e}")
            skipped.append(date)
            continue

    if results:
        df_results = pd.DataFrame(results)
        output_path = "../data/replay_pnl.csv"
        df_results.to_csv(output_path, index=False)

        print(f"\n{'=' * 60}")
        print(f"REPLAY SUMMARY — {len(results)} days completed, {len(skipped)} skipped")
        print(f"{'=' * 60}")
        print(f"  Total net P&L:     £{df_results['net_pnl'].sum():>12,.0f}")
        print(f"  Daily average:     £{df_results['net_pnl'].mean():>12,.0f}")
        print(f"  Best day:          £{df_results['net_pnl'].max():>12,.0f}  ({df_results.loc[df_results['net_pnl'].idxmax(), 'date']})")
        print(f"  Worst day:         £{df_results['net_pnl'].min():>12,.0f}  ({df_results.loc[df_results['net_pnl'].idxmin(), 'date']})")
        print(f"  Positive days:     {(df_results['net_pnl'] > 0).sum()} / {len(results)}")
        print(f"  DA contribution:   £{df_results['da_net'].sum():>12,.0f}")
        print(f"  ID contribution:   £{df_results['id_net'].sum():>12,.0f}")
        print(f"  BM contribution:   £{df_results['bm_net'].sum():>12,.0f}")

        if skipped:
            print(f"\n  Skipped dates: {', '.join(skipped)}")

        print(f"\nSaved to {output_path}")
    else:
        print("\n⚠️  No results — all dates skipped or failed.")


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    run_replay(days)
