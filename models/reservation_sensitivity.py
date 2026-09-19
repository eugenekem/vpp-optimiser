import subprocess
import sys
import os
import json
import pandas as pd
from datetime import datetime

# --- How good is the current fixed DA/ID/BM capacity split? ---
#
# config.py's reservation splits (Battery_1: 40/30/30, Batteries 2-5: 50/20/30)
# have never been backtested against alternatives - just hardcoded defaults,
# with no comment explaining why those specific numbers were chosen. This
# sweeps candidate ID/BM splits (DA is always the implied complement) via
# config.py's env-var overrides, one duration class at a time (2-hour:
# Battery_1 only; 4-hour: Battery_2-5, the majority of portfolio MW), in
# subprocesses so config.py is never edited on disk. Each candidate is scored
# on cost-aware, forecast-basis (reg_demand) net P&L across a historical
# window - the same realistic methodology shadow.py uses live (v28/v29),
# reusing shadow.py's own gross() settlement helper rather than
# reimplementing it. Does NOT call run_shadow_day() itself, so the live
# data/shadow_pnl.csv is never touched by this sweep.
#
# Pilot then validate, exactly like the CVaR project (v26/v27): a 58-day
# pilot's promising CVaR result reversed at full 718-day scale. This script
# never treats a pilot result as a conclusion - `validate` re-runs a specific
# candidate over a much longer window before any split is proposed for
# config.py's actual defaults.
#
# Usage (run from within models/):
#   python reservation_sensitivity.py time [N]                 # benchmark: time N days on the default split
#   python reservation_sensitivity.py pilot [N] [4h|2h]         # sweep the full grid over the last N days
#   python reservation_sensitivity.py validate ID BM N [4h|2h]  # re-run one candidate split over N days
#   python reservation_sensitivity.py --worker CLASS ID BM N    # internal: one scenario, prints JSON

OUT_PATH = "../data/reservation_sensitivity.csv"
GRID_STEP = 0.10
FLOOR = 0.10

# Current config.py defaults, per class - used as the baseline every sweep compares against.
DEFAULTS = {"4h": (0.20, 0.30), "2h": (0.30, 0.30)}
ENV_VARS = {"4h": ("VPP_RES_ID_4H", "VPP_RES_BM_4H"), "2h": ("VPP_RES_ID_2H", "VPP_RES_BM_2H")}


def grid_points():
    """All (id_pct, bm_pct) on a GRID_STEP lattice with da = 1-id-bm >= FLOOR."""
    n = round((1 - 2 * FLOOR) / GRID_STEP)
    steps = [round(FLOOR + i * GRID_STEP, 2) for i in range(n + 1)]
    points = []
    for id_pct in steps:
        for bm_pct in steps:
            da_pct = round(1.0 - id_pct - bm_pct, 2)
            if da_pct >= FLOOR - 1e-9:
                points.append((id_pct, bm_pct))
    return points


def run_worker(battery_class, id_pct, bm_pct, n_days):
    sys.path.append(".")
    import forecast as F
    from dispatcher import run_dispatcher
    from shadow import gross

    dates = F.available_dates()[-n_days:]
    total_net = 0.0
    days_counted = 0
    for date in dates:
        result = run_dispatcher(date, da_forecast_method="reg_demand", write_schedules=False)
        if result is None:
            continue
        df_lp, df_id, df_bm = result
        da_rev, da_cost = gross(df_lp, "settle_price_discharge", "settle_price_charge")
        id_rev, id_cost = gross(df_id, "id_price_discharge", "id_price_charge")
        bm_rev, bm_cost = gross(df_bm, "ssp_settle", "sbp_settle")
        total_net += (da_rev + id_rev + bm_rev) - (da_cost + id_cost + bm_cost)
        days_counted += 1
    print(json.dumps({"class": battery_class, "id_pct": id_pct, "bm_pct": bm_pct,
                       "days": days_counted, "net_pnl": total_net}))


def run_scenario(battery_class, id_pct, bm_pct, n_days):
    """Runs one grid point in a subprocess with the split injected via env vars."""
    id_var, bm_var = ENV_VARS[battery_class]
    env = dict(os.environ)
    env[id_var] = str(id_pct)
    env[bm_var] = str(bm_pct)
    r = subprocess.run(
        [sys.executable, os.path.abspath(__file__), "--worker", battery_class, str(id_pct), str(bm_pct), str(n_days)],
        capture_output=True, text=True, env=env,
    )
    if r.returncode != 0:
        print(f"  FAILED ID={id_pct:.0%} BM={bm_pct:.0%}: {r.stderr[-400:]}")
        return None
    line = r.stdout.strip().splitlines()[-1]
    return json.loads(line)


def time_benchmark(n_days, battery_class="4h"):
    """Times a single grid point to estimate full-sweep runtime before committing to it."""
    id_pct, bm_pct = DEFAULTS[battery_class]
    t0 = datetime.now()
    result = run_scenario(battery_class, id_pct, bm_pct, n_days)
    elapsed = (datetime.now() - t0).total_seconds()
    print(f"{n_days} days took {elapsed:.1f}s ({elapsed / max(n_days, 1):.2f}s/day)")
    if result:
        print(f"  -> net P&L £{result['net_pnl']:,.0f} over {result['days']} days")
    n_points = len(grid_points())
    print(f"\nGrid has {n_points} points. Estimated pilot runtime at this rate: "
          f"~{n_points * elapsed / 60:.1f} min for a {n_days}-day pilot.")


def run_pilot(n_days, battery_class="4h"):
    points = grid_points()
    print(f"Sweeping {len(points)} (ID%, BM%) splits [{battery_class} class] over the last {n_days} available days")
    print("=" * 72)
    rows = []
    t0 = datetime.now()
    for id_pct, bm_pct in points:
        result = run_scenario(battery_class, id_pct, bm_pct, n_days)
        if result:
            da_pct = round(1.0 - id_pct - bm_pct, 2)
            rows.append({"phase": "pilot", "class": battery_class, "da_pct": da_pct, **result})
            print(f"  DA={da_pct:.0%} ID={id_pct:.0%} BM={bm_pct:.0%}  "
                  f"net £{result['net_pnl']:,.0f}  (£{result['net_pnl'] / max(result['days'], 1):,.0f}/day)")

    if not rows:
        print("\n⚠️  No grid point produced results.")
        return

    df = pd.DataFrame(rows)
    write_header = not os.path.exists(OUT_PATH)
    df.to_csv(OUT_PATH, mode="a", header=write_header, index=False)

    df = df.sort_values("net_pnl", ascending=False)
    print("\nTop 5 by total net P&L:")
    print(df.head(5)[["da_pct", "id_pct", "bm_pct", "net_pnl", "days"]].to_string(index=False))

    default_id, default_bm = DEFAULTS[battery_class]
    default_row = df[(df["id_pct"] == default_id) & (df["bm_pct"] == default_bm)]
    if not default_row.empty:
        print(f"\nCurrent default (ID={default_id:.0%} BM={default_bm:.0%}): "
              f"£{default_row.iloc[0]['net_pnl']:,.0f}")

    print(f"\nSaved to {OUT_PATH}. Runtime {(datetime.now() - t0).total_seconds() / 60:.1f} min")
    print("\nNOTE: this is a pilot result only. Re-run the top candidate(s) with `validate`")
    print("at full historical scale before drawing any conclusion - the CVaR project's own")
    print("58-day pilot reversed at 718-day scale (BRIEFING.md v27) for exactly this reason.")


def run_validate(id_pct, bm_pct, n_days, battery_class="4h"):
    default_id, default_bm = DEFAULTS[battery_class]
    print(f"Full-scale validation [{battery_class} class] over {n_days} days...")
    default = run_scenario(battery_class, default_id, default_bm, n_days)
    candidate = run_scenario(battery_class, id_pct, bm_pct, n_days)
    if not default or not candidate:
        print("⚠️  One or both scenarios failed - see FAILED lines above.")
        return

    da_default = round(1.0 - default_id - default_bm, 2)
    da_candidate = round(1.0 - id_pct - bm_pct, 2)
    print(f"  Current default (DA={da_default:.0%} ID={default_id:.0%} BM={default_bm:.0%}): "
          f"£{default['net_pnl']:,.0f}  (£{default['net_pnl'] / max(default['days'], 1):,.0f}/day, {default['days']} days)")
    print(f"  Candidate       (DA={da_candidate:.0%} ID={id_pct:.0%} BM={bm_pct:.0%}): "
          f"£{candidate['net_pnl']:,.0f}  (£{candidate['net_pnl'] / max(candidate['days'], 1):,.0f}/day, {candidate['days']} days)")
    delta = candidate["net_pnl"] - default["net_pnl"]
    print(f"  Difference: £{delta:,.0f} ({delta / abs(default['net_pnl']) * 100:+.1f}%)")

    rows = [{"phase": "validate", "class": battery_class, "da_pct": da_default, **default},
            {"phase": "validate", "class": battery_class, "da_pct": da_candidate, **candidate}]
    df = pd.DataFrame(rows)
    write_header = not os.path.exists(OUT_PATH)
    df.to_csv(OUT_PATH, mode="a", header=write_header, index=False)
    print(f"\nSaved to {OUT_PATH}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python reservation_sensitivity.py [time|pilot|validate] ...")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "--worker":
        run_worker(sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), int(sys.argv[5]))
    elif cmd == "time":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        cls = sys.argv[3] if len(sys.argv) > 3 else "4h"
        time_benchmark(n, cls)
    elif cmd == "pilot":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 60
        cls = sys.argv[3] if len(sys.argv) > 3 else "4h"
        run_pilot(n, cls)
    elif cmd == "validate":
        if len(sys.argv) < 5:
            print("Usage: python reservation_sensitivity.py validate ID BM N [4h|2h]")
            sys.exit(1)
        cls = sys.argv[5] if len(sys.argv) > 5 else "4h"
        run_validate(float(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4]), cls)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
