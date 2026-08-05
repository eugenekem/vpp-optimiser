import subprocess
import sys
import os
import time
from datetime import datetime, timedelta

# --- Historical price backfill ---
#
# Downloads DA market index prices and BM system prices for a long date range,
# so the forecaster has more than the ~30 days it started with.
#
# Safe to stop (Ctrl+C) and re-run — it skips any date already on disk, so it
# resumes where it left off and never re-downloads or overwrites existing data.
#
# Run from the scripts/ folder (the fetch scripts write to ../data/).
#
# Usage:
#   python backfill.py           # last 730 days (24 months)
#   python backfill.py 365       # last 365 days
#   python backfill.py 2024-08-01 2025-08-01   # explicit range

DATA_DIR = "../data"
DELAY = 0.4          # seconds between requests — be polite to Elexon
PROGRESS_EVERY = 25  # print a progress line this often

FEEDS = [
    ("fetch_da_prices.py",  "market_index"),
    ("fetch_bmrs.py",       "system_prices"),
    ("fetch_wind_solar.py", "wind_solar"),
    ("fetch_demand.py",     "demand"),
]


def fetch_one(script, prefix, date):
    """
    Fetch one feed for one date. Returns "skip", "ok", or "fail".
    Never overwrites an existing file.
    """
    path = f"{DATA_DIR}/{prefix}_{date}.csv"
    if os.path.exists(path):
        return "skip"

    result = subprocess.run(
        ["python", script, date],
        capture_output=True, text=True
    )
    time.sleep(DELAY)

    if result.returncode != 0 or not os.path.exists(path):
        return "fail"
    return "ok"


def backfill(start_date, end_date):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    dates = [(start + timedelta(days=i)).strftime("%Y-%m-%d")
             for i in range((end - start).days + 1)]

    print(f"Backfilling {len(dates)} days: {dates[0]} to {dates[-1]}")
    print(f"Two feeds per day. Existing files are skipped, so this is resumable.")
    print("=" * 68)

    counts = {"ok": 0, "skip": 0, "fail": 0}
    failed_dates = set()
    t0 = time.time()

    for i, date in enumerate(dates, 1):
        for script, prefix in FEEDS:
            outcome = fetch_one(script, prefix, date)
            counts[outcome] += 1
            if outcome == "fail":
                failed_dates.add(date)

        if i % PROGRESS_EVERY == 0 or i == len(dates):
            elapsed = time.time() - t0
            rate = elapsed / i
            remaining = rate * (len(dates) - i)
            print(f"  [{i:>4}/{len(dates)}] {date} | "
                  f"downloaded {counts['ok']}, skipped {counts['skip']}, "
                  f"failed {counts['fail']} | "
                  f"~{remaining/60:.0f} min left")

    print("=" * 68)
    print(f"Done in {(time.time()-t0)/60:.1f} min")
    print(f"  Downloaded: {counts['ok']} files")
    print(f"  Skipped (already had): {counts['skip']} files")
    print(f"  Failed: {counts['fail']} files")

    if failed_dates:
        srt = sorted(failed_dates)
        print(f"\n  {len(srt)} date(s) had at least one feed fail.")
        print(f"  First few: {', '.join(srt[:8])}")
        print(f"  Re-run this script to retry them — successful files are kept.")

    return counts


if __name__ == "__main__":
    args = sys.argv[1:]
    today = datetime.today()

    if len(args) == 2:
        start_date, end_date = args
    else:
        days = int(args[0]) if args else 730
        start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
        end_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")

    backfill(start_date, end_date)
