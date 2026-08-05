import subprocess
import sys
import os
import re
import pandas as pd
from datetime import datetime

# --- How fragile is the P&L result to the cost assumptions? ---
#
# forecast_pnl.py reports one number resting on one set of costs. That invites
# the obvious question: what if those costs are wrong? This runs the same test
# under several cost stacks and reports the range.
#
# Each stack runs in a SUBPROCESS with costs injected via environment
# variables, so config.py is never edited on disk — a crash or interruption
# cannot leave the repo holding someone else's assumptions.
#
# Usage:
#   python cost_sensitivity.py

STACKS = {
    # name:        (degradation, fee, impact)  £/MWh
    "light":        (2.00, 0.10, 0.25),
    "central":      (4.00, 0.15, 0.75),
    "conservative": (8.00, 0.20, 1.50),
}

OUT_PATH = "../data/cost_sensitivity.csv"


def run_stack(name, deg, fee, imp):
    env = dict(os.environ,
               VPP_COST_DEGRADATION=str(deg),
               VPP_COST_FEE=str(fee),
               VPP_COST_IMPACT=str(imp))
    print(f"\n{'='*72}\n{name.upper()}: degradation £{deg}, fee £{fee}, impact £{imp}\n{'='*72}")
    r = subprocess.run([sys.executable, "forecast_pnl.py"],
                       capture_output=True, text=True, env=env)
    out = r.stdout
    if r.returncode != 0:
        print(f"  FAILED: {r.stderr[-400:]}")
        return None

    # Pull the cost-aware totals straight from the report table.
    rows = {}
    for line in out.splitlines():
        m = re.match(r"^(perfect|naive|mean_7|regression|reg_demand)\s*\*?\s+"
                     r"£\s*([\d,\-]+)\s+£\s*([\d,\-]+)\s+£\s*([\d,\-]+)\s+([\d.\-]+)%", line)
        if m:
            arm, free, blind, aware, cap = m.groups()
            rows[arm] = {
                "free": int(free.replace(",", "")),
                "blind": int(blind.replace(",", "")),
                "aware": int(aware.replace(",", "")),
                "capture": float(cap),
            }
    if not rows:
        print("  Could not parse results — raw tail:")
        print("\n".join(out.splitlines()[-15:]))
        return None

    ndays = 0
    m = re.search(r"RESULTS — (\d+) days scored", out)
    if m:
        ndays = int(m.group(1))

    for arm, v in rows.items():
        print(f"  {arm:<12} aware £{v['aware']:>12,}  capture {v['capture']:>5.1f}%")

    return [{"stack": name, "degradation": deg, "fee": fee, "impact": imp,
             "arm": arm, "days": ndays, **v} for arm, v in rows.items()]


def main():
    t0 = datetime.now()
    all_rows = []
    for name, (deg, fee, imp) in STACKS.items():
        res = run_stack(name, deg, fee, imp)
        if res:
            all_rows.extend(res)

    if not all_rows:
        print("\n⚠️  No stack produced results.")
        return

    df = pd.DataFrame(all_rows)
    df.to_csv(OUT_PATH, index=False)

    best = "reg_demand"
    sub = df[df.arm == best].set_index("stack")
    days = int(sub["days"].iloc[0]) or 1

    print(f"\n{'='*72}")
    print(f"SENSITIVITY — {best}, {days} days")
    print(f"{'='*72}")
    print(f"{'stack':<14} {'degr.':>7} {'total P&L':>15} {'per day':>11} {'capture':>9}")
    print("-" * 72)
    for stack in ["light", "central", "conservative"]:
        if stack not in sub.index:
            continue
        r = sub.loc[stack]
        print(f"{stack:<14} £{r['degradation']:>6.2f} £{r['aware']:>14,.0f} "
              f"£{r['aware']/days:>10,.0f} {r['capture']:>8.1f}%")
    print("-" * 72)

    if {"light", "conservative"} <= set(sub.index):
        hi, lo = sub.loc["light", "aware"], sub.loc["conservative", "aware"]
        print(f"\nRange: £{lo/days:,.0f} to £{hi/days:,.0f} per day "
              f"({(hi-lo)/lo*100:.0f}% spread between the extreme assumptions)")
        print("Quote the CONSERVATIVE figure externally — if the case holds there,")
        print("it holds under scrutiny. Never quote capture without £/day.")

    print(f"\nSaved to {OUT_PATH}")
    print(f"Total runtime {(datetime.now()-t0).total_seconds()/60:.1f} min")


if __name__ == "__main__":
    main()
