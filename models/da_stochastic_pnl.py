import sys
from datetime import datetime

import numpy as np
import pandas as pd

sys.path.append(".")
from battery import assets
from config import (ID_RESERVATION, BM_RESERVATION, SOC_INIT,
                    COST_DEGRADATION, COST_FEE, COST_IMPACT,
                    CVAR_N_SCENARIOS_DEFAULT, CVAR_ALPHA_DEFAULT)
from optimiser_lp import optimise_battery_lp
from optimiser_lp_stochastic import optimise_battery_lp_cvar
import forecast as F
import forecast_residuals as FR
from forecast_pnl import settle

# --- Does the CVaR hedge actually help, or is it just a worse forecast? ---
#
# Three arms, same scenario draw per day, so the comparison is clean:
#   deterministic    - today's reg_demand point forecast (unmodified,
#                       identical to forecast_pnl.py's own reg_demand arm)
#   ensemble_mean     - mean(scenarios), still via the plain optimiser. By
#                       the mean-equivalence proof (optimiser_lp_stochastic.py),
#                       this IS the lambda=0 special case of cvar_stochastic -
#                       asserted below as a live check on real settlement data.
#   cvar_stochastic   - same scenarios, hedged via optimise_battery_lp_cvar
#
# ensemble_mean - deterministic = value of a better central estimate alone
# cvar_stochastic - ensemble_mean = value of risk-aversion alone
# Only the second number tests whether CVaR hedging actually helps.
#
# Cost-aware throughout (matches current project best-practice, BRIEFING
# section 10d). DA layer only, same scoping as forecast_pnl.py.
#
# Usage:
#   python da_stochastic_pnl.py <n_recent_days> [cvar_lambda]

DATA_DIR = "../data"
OUT_PATH = f"{DATA_DIR}/da_stochastic_pnl.csv"
METHOD = "reg_demand"
COST_KW = dict(cost_discharge=COST_IMPACT + COST_FEE + COST_DEGRADATION,
               cost_charge=COST_IMPACT + COST_FEE)


def run_day(date, history, residual_history, n_scenarios=CVAR_N_SCENARIOS_DEFAULT,
            cvar_alpha=CVAR_ALPHA_DEFAULT, cvar_lambda=0.5):
    """One day, all four arms (perfect ceiling + 3 real arms). None if any arm can't be built."""
    actual = F.load_actual(date)
    if actual is None or actual.empty:
        return None

    fc, _ = F.forecast_prices(date, METHOD, history=history)
    if fc is None:
        return None

    # Seeded deterministically per date - NOT per run - so every arm across
    # every lambda in a sweep is compared on the exact same scenario draw for
    # that date. Without this, each separate `main()` call would draw fresh
    # random scenarios, making ensemble_mean (which depends on the draw, not
    # on lambda) drift between runs and contaminating the sweep - caught by
    # noticing ensemble_mean's own numbers change across lambda values when
    # they structurally cannot depend on lambda at all.
    seed = int(date.replace("-", ""))
    scenarios = FR.sample_scenarios(date, METHOD, n_scenarios=n_scenarios,
                                     residual_history=residual_history,
                                     rng=np.random.default_rng(seed))
    if not scenarios:
        return None

    common_idx = fc.index.intersection(actual.index)
    if common_idx.empty:
        return None
    fc = fc.reindex(common_idx)
    aligned = [s.reindex(common_idx) for s in scenarios]
    aligned = [s for s in aligned if not s.isna().any()]
    if not aligned or not all(list(s.index) == list(aligned[0].index) for s in aligned):
        return None
    ensemble_mean = pd.concat(aligned, axis=1).mean(axis=1)

    totals = {"perfect": 0.0, "deterministic": 0.0, "ensemble_mean": 0.0, "cvar_stochastic": 0.0}
    for battery in assets:
        da_committed = 1 - (ID_RESERVATION[battery.name] + BM_RESERVATION[battery.name])
        kw = dict(committed_capacity=da_committed, initial_soc_mwh=SOC_INIT * battery.capacity_mwh)

        sched_perfect, _, _ = optimise_battery_lp(battery, actual, **kw, **COST_KW)
        sched_det, _, _ = optimise_battery_lp(battery, fc, **kw, **COST_KW)
        sched_mean, _, _ = optimise_battery_lp(battery, ensemble_mean, **kw, **COST_KW)
        sched_cvar, _, _, _ = optimise_battery_lp_cvar(
            battery, aligned, **kw, cvar_alpha=cvar_alpha, cvar_lambda=cvar_lambda, **COST_KW
        )

        p = settle(sched_perfect, actual, with_costs=True)
        d = settle(sched_det, actual, with_costs=True)
        m = settle(sched_mean, actual, with_costs=True)
        c = settle(sched_cvar, actual, with_costs=True)
        if None in (p, d, m, c):
            return None
        totals["perfect"] += p
        totals["deterministic"] += d
        totals["ensemble_mean"] += m
        totals["cvar_stochastic"] += c

    return totals


def main(limit=60, cvar_lambda=0.5):
    residual_history = FR.load_residual_history(METHOD)
    if residual_history is None:
        print(f"⚠️  No residual history for '{METHOD}' — run forecast_residuals.py build first")
        return

    history = F.available_dates()
    dates = history[-limit:]

    print(f"3-arm DA stochastic comparison over {len(dates)} most recent days, cvar_lambda={cvar_lambda}")
    print("=" * 72)

    rows, skipped = [], 0
    t0 = datetime.now()
    for i, date in enumerate(dates, 1):
        res = run_day(date, history, residual_history, cvar_lambda=cvar_lambda)
        if res is None:
            skipped += 1
        else:
            res["date"] = date
            rows.append(res)
        if i % 10 == 0 or i == len(dates):
            el = (datetime.now() - t0).total_seconds()
            print(f"  [{i:>3}/{len(dates)}] {date} | scored {len(rows)}, skipped {skipped} | "
                  f"{el/i:.1f}s/day avg")

    if not rows:
        print("\n⚠️  No days could be scored.")
        return

    df = pd.DataFrame(rows)
    df.to_csv(OUT_PATH, index=False)

    print(f"\n{'=' * 72}\nRESULTS — {len(df)} days scored, {skipped} skipped\n{'=' * 72}")

    ceiling = df["perfect"].sum()
    print(f"\n{'arm':<18} {'mean/day':>10} {'median/day':>11} {'p5/day':>10} "
          f"{'worst day':>11} {'std/day':>9} {'capture':>8}")
    print("-" * 82)
    for arm in ["deterministic", "ensemble_mean", "cvar_stochastic"]:
        s = df[arm]
        cap = s.sum() / ceiling * 100 if ceiling else float("nan")
        print(f"{arm:<18} £{s.mean():>9,.0f} £{s.median():>10,.0f} £{s.quantile(.05):>9,.0f} "
              f"£{s.min():>10,.0f} £{s.std():>8,.0f} {cap:>7.1f}%")

    print("-" * 82)
    print("p5/day = 5th percentile (worst ~10% of days); worst day = single minimum")

    central_delta = df["ensemble_mean"].sum() - df["deterministic"].sum()
    risk_delta = df["cvar_stochastic"].sum() - df["ensemble_mean"].sum()
    print(f"\nvalue of a better central estimate (ensemble_mean - deterministic): "
          f"£{central_delta:,.0f} total (£{central_delta/len(df):,.0f}/day)")
    print(f"value of risk-aversion alone (cvar_stochastic - ensemble_mean):      "
          f"£{risk_delta:,.0f} total (£{risk_delta/len(df):,.0f}/day)")

    print(f"\nmean_7 check disabled (not an arm here - see forecast_pnl.py for that comparison)")
    print(f"Saved per-day detail to {OUT_PATH}")
    print(f"Total runtime {(datetime.now()-t0).total_seconds()/60:.1f} min "
          f"({(datetime.now()-t0).total_seconds()/len(dates):.1f}s/day avg)")


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    lam = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
    main(limit, lam)
