import pulp
import pandas as pd
import sys

sys.path.append(".")
from config import DURATION, SOC_INIT

# --- CVaR-hedged LP optimiser for a single battery (DA leg only) ---
#
# optimise_battery_lp() (optimiser_lp.py) is NOT touched or imported here -
# this is a deliberately separate function so nothing depending on the
# original can regress.
#
# Plain-language version: instead of planning against ONE guessed price,
# this plans against MANY realistic guesses (scenarios) at once, using a
# single shared schedule (you commit to one plan before knowing which
# scenario becomes real - no do-overs). A naive "do well on average across
# scenarios" version of this is mathematically identical to just planning
# against the average guess - proven below, and checked by this file's own
# __main__ smoke test - so it adds nothing on its own. What actually makes
# this a genuine hedge is CVaR: an extra term in the objective that
# specifically rewards schedules that don't fall apart in the WORST
# scenarios, not just ones that look good on average.
#
# CVaR (Conditional Value at Risk), Rockafellar-Uryasev linear formulation:
#   zeta       = the revenue threshold marking the worst (1-alpha) share of
#                scenarios (e.g. alpha=0.90 -> the worst 10%)
#   eta[s]     = how far scenario s falls short of zeta, if at all (>=0)
#   CVaR       = zeta - 1/(N*(1-alpha)) * sum(eta[s])
#              = the average revenue of just the worst (1-alpha) scenarios
#   objective  = expected_revenue + cvar_lambda * CVaR
# lambda=0 recovers plain expected-value optimisation (which is why it must
# equal optimise_battery_lp() on the scenario mean - see __main__ below).
# Higher lambda trades away some average return for a better worst case.
#
# Mean-equivalence proof (why lambda=0 must equal solving on the mean price):
#   charge[t]/discharge[t] are IDENTICAL across every scenario (no recourse -
#   this is a single shared schedule, decided before any scenario resolves).
#   The objective and every constraint are linear in price, with no
#   scenario-dependent constraint. So:
#     E_s[ sum_t discharge[t]*(price_s[t]-c_d)*DUR - charge[t]*(price_s[t]+c_c)*DUR ]
#   = sum_t discharge[t]*(E_s[price_s[t]]-c_d)*DUR - charge[t]*(E_s[price_s[t]]+c_c)*DUR
#   by linearity of expectation - exactly optimise_battery_lp()'s objective
#   evaluated at price_series = mean(scenarios). Same feasible region (SOC
#   constraints don't involve price at all), so the optimal schedule and
#   objective value are identical, not just similar.


def optimise_battery_lp_cvar(battery, scenario_prices, committed_capacity=1.0,
                              initial_soc_mwh=None, cost_discharge=0.0, cost_charge=0.0,
                              cvar_alpha=0.90, cvar_lambda=0.5):
    """
    Solve the DA dispatch problem for a single battery, hedged across
    multiple price scenarios instead of trusting one price series.

    Parameters
    ----------
    scenario_prices : list[pd.Series]
        Each indexed by settlement period, all sharing the same index -
        one guessed price path per scenario.
    cvar_alpha : float
        Confidence level (e.g. 0.90 = protect against the worst 10% of
        scenarios). Must be in [0, 1).
    cvar_lambda : float
        Risk-aversion weight. 0 = pure expected value (mathematically
        identical to optimise_battery_lp on the scenario mean - see the
        module docstring's proof). Higher = more weight on the worst case.

    Returns
    -------
    tuple[pd.DataFrame, float, float, dict]
        Schedule DataFrame, objective value (£), final SOC in MWh,
        diagnostics = {"expected_revenue", "cvar", "zeta", "n_scenarios"}.
    """
    if not scenario_prices:
        raise ValueError("scenario_prices must be a non-empty list")

    T = list(scenario_prices[0].index)
    for i, s in enumerate(scenario_prices):
        if list(s.index) != T:
            raise ValueError(f"scenario {i} has a different index than scenario 0 - "
                              f"align all scenarios (e.g. via reindex) before calling this")

    N = len(scenario_prices)
    if not (0 <= cvar_alpha < 1):
        raise ValueError(f"cvar_alpha must be in [0, 1), got {cvar_alpha}")

    if initial_soc_mwh is None:
        initial_soc_mwh = SOC_INIT * battery.capacity_mwh

    prob = pulp.LpProblem(f"battery_dispatch_cvar_{battery.name}", pulp.LpMaximize)

    # --- Decision variables: SHARED across all scenarios (no recourse) ---
    charge = pulp.LpVariable.dicts(
        "charge", T, lowBound=0, upBound=battery.mw * committed_capacity
    )
    discharge = pulp.LpVariable.dicts(
        "discharge", T, lowBound=0, upBound=battery.mw * committed_capacity
    )
    soc = pulp.LpVariable.dicts(
        "soc", T,
        lowBound=battery.soc_min * battery.capacity_mwh,
        upBound=battery.soc_max * battery.capacity_mwh
    )

    # --- CVaR auxiliary variables ---
    zeta = pulp.LpVariable("zeta")  # free (unbounded) - the VaR threshold
    eta = pulp.LpVariable.dicts("eta", range(N), lowBound=0)

    # --- Per-scenario revenue expressions (linear in charge/discharge - not solved yet) ---
    scenario_revenue = []
    for s, prices in enumerate(scenario_prices):
        rev = pulp.lpSum([
            discharge[t] * (prices[t] - cost_discharge) * DURATION
            - charge[t] * (prices[t] + cost_charge) * DURATION
            for t in T
        ])
        scenario_revenue.append(rev)

    expected_revenue = (1.0 / N) * pulp.lpSum(scenario_revenue)
    cvar = zeta - (1.0 / (N * (1 - cvar_alpha))) * pulp.lpSum(eta[s] for s in range(N))

    # --- Objective: expected value + risk-aversion term ---
    prob += expected_revenue + cvar_lambda * cvar, "mean_cvar_objective"

    # --- CVaR shortfall constraints ---
    for s in range(N):
        prob += eta[s] >= zeta - scenario_revenue[s]

    # --- Energy balance constraints (identical to optimise_battery_lp - no price term) ---
    for i, t in enumerate(T):
        if i == 0:
            prob += soc[t] == initial_soc_mwh + charge[t] * DURATION * battery.efficiency - discharge[t] * DURATION / battery.efficiency
        else:
            prev_t = T[i - 1]
            prob += soc[t] == soc[prev_t] + charge[t] * DURATION * battery.efficiency - discharge[t] * DURATION / battery.efficiency

    # --- Solve ---
    solver = pulp.PULP_CBC_CMD(msg=False)
    prob.solve(solver)

    # --- Extract results (same shape as optimise_battery_lp) ---
    mean_price = pd.concat(scenario_prices, axis=1).mean(axis=1)

    results = []
    for t in T:
        c = charge[t].varValue if charge[t].varValue else 0
        d = discharge[t].varValue if discharge[t].varValue else 0
        soc_val = soc[t].varValue if soc[t].varValue else 0

        if c > 0.01:
            action, power = "charge", c
        elif d > 0.01:
            action, power = "discharge", d
        else:
            action, power = "hold", 0

        results.append({
            "settlement_period": t,
            "price": mean_price[t],  # diagnostic only - the objective used the full scenario set, not just this
            "asset": battery.name,
            "action": action,
            "power_mw": round(power, 2),
            "soc": round(soc_val / battery.capacity_mwh * 100, 1),
            "energy_mwh": round(soc_val, 2)
        })

    df_results = pd.DataFrame(results)
    final_soc_mwh = df_results["energy_mwh"].iloc[-1] if len(df_results) > 0 else initial_soc_mwh

    diagnostics = {
        "expected_revenue": pulp.value(expected_revenue),
        "cvar": pulp.value(cvar),
        "zeta": zeta.varValue,
        "n_scenarios": N,
    }

    return df_results, pulp.value(prob.objective), final_soc_mwh, diagnostics


if __name__ == "__main__":
    # Smoke test - must pass before this function is trusted anywhere else.
    # Uses real scenario data (not synthetic), same as the actual dispatch path will.
    import numpy as np
    from battery import assets
    from optimiser_lp import optimise_battery_lp
    from forecast_residuals import sample_scenarios, load_residual_history

    battery = assets[0]
    rh = load_residual_history("reg_demand")
    scenarios = sample_scenarios("2025-06-15", "reg_demand", n_scenarios=20,
                                  residual_history=rh, rng=np.random.default_rng(0))
    if scenarios is None:
        print("⚠️  No scenarios available for the smoke-test date - pick a later date with more residual history")
        sys.exit(1)

    print(f"Smoke test: {len(scenarios)} real scenarios for 2025-06-15, battery={battery.name}")

    # Check 1: lambda=0 must equal optimise_battery_lp on the scenario mean
    mean_price = pd.concat(scenarios, axis=1).mean(axis=1)
    _, det_obj, _ = optimise_battery_lp(battery, mean_price, committed_capacity=0.5)
    _, cvar_obj_l0, _, diag_l0 = optimise_battery_lp_cvar(
        battery, scenarios, committed_capacity=0.5, cvar_lambda=0.0
    )
    diff = abs(det_obj - cvar_obj_l0)
    status = "✅ PASS" if diff < 0.01 else "❌ FAIL"
    print(f"\nCheck 1 (mean-equivalence at lambda=0): deterministic £{det_obj:,.2f} vs "
          f"CVaR(λ=0) £{cvar_obj_l0:,.2f} — diff £{diff:.4f} — {status}")

    # Check 2: N=1 collapses CVaR to that single scenario's own revenue
    _, obj_n1, _, diag_n1 = optimise_battery_lp_cvar(
        battery, scenarios[:1], committed_capacity=0.5, cvar_lambda=1.0, cvar_alpha=0.90
    )
    diff2 = abs(diag_n1["cvar"] - diag_n1["expected_revenue"])
    status2 = "✅ PASS" if diff2 < 0.01 else "❌ FAIL"
    print(f"Check 2 (N=1 collapse): CVaR £{diag_n1['cvar']:,.2f} vs expected_revenue "
          f"£{diag_n1['expected_revenue']:,.2f} — diff £{diff2:.4f} — {status2}")

    # Check 3: a genuine hedge (lambda>0) should not do BETTER on average than lambda=0 -
    # trading some expected value for a better worst case is the whole point, and pulp
    # solved lambda=0's problem to find the actual expected-value maximum, so lambda>0
    # can only match or give up some of it.
    _, _, _, diag_l1 = optimise_battery_lp_cvar(
        battery, scenarios, committed_capacity=0.5, cvar_lambda=1.0
    )
    ok3 = diag_l1["expected_revenue"] <= diag_l0["expected_revenue"] + 0.01
    status3 = "✅ PASS" if ok3 else "❌ FAIL"
    print(f"Check 3 (hedging cannot improve the mean): λ=0 expected £{diag_l0['expected_revenue']:,.2f} "
          f"vs λ=1 expected £{diag_l1['expected_revenue']:,.2f} — {status3}")
    print(f"  λ=1 CVaR (worst-tail average): £{diag_l1['cvar']:,.2f} vs λ=0's £{diag_l0['cvar']:,.2f} "
          f"— hedging should IMPROVE this")
