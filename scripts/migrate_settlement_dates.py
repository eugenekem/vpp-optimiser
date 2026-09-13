import glob
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

# --- One-off migration: fix settlement-date misalignment in historical data ---
#
# market_index_*.csv and wind_solar_*.csv were fetched by a UTC calendar-day
# window rather than true GB settlement date. During BST, SP1-2 of file D
# actually belong to real settlement date D+1. This regroups every row by its
# TRUE settlement date, using data already on disk — no live re-fetching,
# except two small, explicit boundary gaps.
#
# market_index rows already carry their own correct settlementDate — pure
# relabel. wind_solar rows do NOT (fetch_wind_solar.py used to overwrite it
# with the query date) — so the true date is recovered by joining on
# (query_date, settlementPeriod) against the ORIGINAL market_index files,
# which mirror wind_solar row-for-row by deliberate design.
#
# Writes to data/market_index_fixed/ and data/wind_solar_fixed/ first.
# Nothing in data/ is touched until move_into_place() is called explicitly.
#
# Usage:
#   python migrate_settlement_dates.py            # stage only
#   python migrate_settlement_dates.py --apply    # stage, verify, then move into place

DATA_DIR = Path("../data")
MI_FIXED = DATA_DIR / "market_index_fixed"
WS_FIXED = DATA_DIR / "wind_solar_fixed"
MI_BACKUP = DATA_DIR / "pre_migration_backup" / "market_index"
WS_BACKUP = DATA_DIR / "pre_migration_backup" / "wind_solar"


def load_all(prefix):
    """All existing files for a feed as one long dataframe, tagged with the
    query date each row came from (the original filename's date)."""
    frames = []
    for path in sorted(glob.glob(str(DATA_DIR / f"{prefix}_*.csv"))):
        m = re.search(rf"{prefix}_(\d{{4}}-\d{{2}}-\d{{2}})\.csv$", path)
        if not m:
            continue
        df = pd.read_csv(path)
        df["_query_date"] = m.group(1)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def migrate_market_index():
    print("=== market_index: pure relabel by each row's own settlementDate ===")
    all_rows = load_all("market_index")
    total_before = len(all_rows)

    MI_FIXED.mkdir(parents=True, exist_ok=True)
    written, dropped_partial = 0, 0
    for true_date, group in all_rows.groupby("settlementDate"):
        group = group.drop(columns=["_query_date"]).drop_duplicates(subset="settlementPeriod")
        group = group.sort_values("settlementPeriod")
        # Real days have 46/48/50 periods. Fewer than that means an
        # incomplete trailing/leading date (its other source file doesn't
        # exist on disk yet) - don't write a partial file into the live
        # dataset; daily_pipeline.py's gap detection would see it as "done"
        # by filename and never fetch the rest. Dropping lets the FIXED
        # fetcher naturally produce a complete file for it on its own turn.
        if len(group) < 44:
            dropped_partial += len(group)
            continue
        group.to_csv(MI_FIXED / f"market_index_{true_date}.csv", index=False)
        written += len(group)
    if dropped_partial:
        print(f"  Dropped {dropped_partial} rows from incomplete boundary date(s) "
              f"(<44 periods) - left for the fixed fetcher to complete naturally.")

    print(f"  {total_before} rows in -> {written} rows out across "
          f"{len(list(MI_FIXED.glob('*.csv')))} files")
    if written != total_before:
        print(f"  ⚠️  Row count changed ({total_before} -> {written}) — "
              f"expected if duplicates existed, investigate if unexpected.")
    return all_rows  # reused to build the wind_solar lookup


def migrate_wind_solar(market_index_rows):
    print("\n=== wind_solar: recover true date via market_index row-position mirror ===")
    # (query_date, settlementPeriod) -> true settlementDate, from the
    # ORIGINAL market_index files (before this script relabels them).
    lookup = market_index_rows.set_index(
        ["_query_date", "settlementPeriod"]
    )["settlementDate"].to_dict()

    all_rows = load_all("wind_solar")
    total_before = len(all_rows)

    all_rows["true_date"] = all_rows.apply(
        lambda r: lookup.get((r["_query_date"], r["settlementPeriod"])), axis=1
    )
    unmatched = all_rows["true_date"].isna().sum()
    if unmatched:
        print(f"  ⚠️  {unmatched} wind_solar rows have no matching market_index "
              f"row for the same (query_date, period) — dropped, not guessed.")
    all_rows = all_rows.dropna(subset=["true_date"])

    WS_FIXED.mkdir(parents=True, exist_ok=True)
    written, dropped_partial = 0, 0
    for true_date, group in all_rows.groupby("true_date"):
        group = group.drop(columns=["_query_date", "true_date", "settlementDate"])
        group.insert(0, "settlementDate", true_date)
        group = group.drop_duplicates(subset="settlementPeriod").sort_values("settlementPeriod")
        if len(group) < 44:
            dropped_partial += len(group)
            continue
        group.to_csv(WS_FIXED / f"wind_solar_{true_date}.csv", index=False)
        written += len(group)
    if dropped_partial:
        print(f"  Dropped {dropped_partial} rows from incomplete boundary date(s) "
              f"(<44 periods).")

    print(f"  {total_before} rows in -> {written} rows out across "
          f"{len(list(WS_FIXED.glob('*.csv')))} files "
          f"({unmatched} unmatched/dropped)")


def backfill_boundary_gap():
    """The very first historical date is missing its true SP1-2, which live
    in the day before (never fetched). Re-fetch that one earlier date live,
    using the now-fixed fetchers, then re-run the migration so it's included."""
    fixed_files = sorted(MI_FIXED.glob("market_index_*.csv"))
    if not fixed_files:
        return
    first_date = fixed_files[0].stem.replace("market_index_", "")
    df = pd.read_csv(fixed_files[0])
    if len(df) >= 46:  # already complete (or a legitimate 46-period clock-change day)
        print(f"\n=== boundary check: {first_date} already has {len(df)} periods, no gap ===")
        return

    from datetime import datetime, timedelta
    day_before = (datetime.strptime(first_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"\n=== boundary gap: {first_date} has only {len(df)} periods — "
          f"live-fetching {day_before} to recover its SP1-2 ===")
    for script in ["fetch_da_prices.py", "fetch_wind_solar.py"]:
        subprocess.run(["python", script, day_before], check=False)


def verify():
    print("\n=== verification ===")
    for name, folder in [("market_index", MI_FIXED), ("wind_solar", WS_FIXED)]:
        counts = {}
        for path in sorted(folder.glob("*.csv")):
            n = len(pd.read_csv(path))
            counts[n] = counts.get(n, 0) + 1
        print(f"  {name}: row-count distribution across files: {counts}")


def move_into_place():
    print("\n=== moving fixed files into data/, archiving originals ===")
    MI_BACKUP.mkdir(parents=True, exist_ok=True)
    WS_BACKUP.mkdir(parents=True, exist_ok=True)

    for orig in DATA_DIR.glob("market_index_*.csv"):
        shutil.move(str(orig), str(MI_BACKUP / orig.name))
    for orig in DATA_DIR.glob("wind_solar_*.csv"):
        shutil.move(str(orig), str(WS_BACKUP / orig.name))

    for fixed in MI_FIXED.glob("*.csv"):
        shutil.move(str(fixed), str(DATA_DIR / fixed.name))
    for fixed in WS_FIXED.glob("*.csv"):
        shutil.move(str(fixed), str(DATA_DIR / fixed.name))

    MI_FIXED.rmdir()
    WS_FIXED.rmdir()
    print(f"  Originals archived to {MI_BACKUP} and {WS_BACKUP}")
    print(f"  Fixed files now live in {DATA_DIR}")


if __name__ == "__main__":
    market_index_rows = migrate_market_index()
    migrate_wind_solar(market_index_rows)
    backfill_boundary_gap()
    verify()

    if "--apply" in sys.argv:
        move_into_place()
    else:
        print(f"\nStaged only — review {MI_FIXED} and {WS_FIXED}, "
              f"then re-run with --apply to move into place.")
