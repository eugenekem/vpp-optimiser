import pandas as pd
from datetime import datetime, timedelta
import os
import sys

sys.path.append(".")
from battery import assets
from config import (DA_RESERVATION, ID_RESERVATION, BM_RESERVATION, SOC_INIT,
                    CVAR_N_SCENARIOS_DEFAULT, CVAR_ALPHA_DEFAULT, CVAR_LAMBDA_DEFAULT,
                    COST_DEGRADATION, COST_FEE, COST_IMPACT)
from optimiser_lp import optimise_battery_lp
from optimiser_lp_stochastic import optimise_battery_lp_cvar
from optimiser_id import optimise_battery_id, simulate_intraday_prices
from optimiser_bm import optimise_battery_bm
import forecast as F
import forecast_residuals as FR

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
#
# da_forecast_method (added v25): if set, the DA leg's charge/discharge
# DECISIONS are built on a price forecast instead of the real published
# price — the realistic case, since a real trader must commit before the
# real DA price is known. Settlement money still uses the REAL price
# (df_lp["settle_price"]) regardless — you're paid what actually happened,
# not what you predicted. ID/BM are completely unaffected either way: ID's
# synthetic price is still derived from the REAL da_prices (it isn't a
# forecast-quality question, see forecast_pnl.py's own DA-only scoping),
# and BM already settles on real SSP/SBP.
# Default None preserves the exact original behaviour (decide AND settle
# on the real price) so replay.py's Phase 1 results are untouched.
#
# A "_stochastic" suffix (added v26, e.g. da_forecast_method="reg_demand_stochastic")
# additionally hedges the DA decision across many price SCENARIOS (see
# optimiser_lp_stochastic.py) instead of trusting the single point forecast
# completely. Only engaged if the base method's point forecast succeeded
# with NO fallback (da_basis == base_method exactly) - residual history is
# method-specific, so perturbing a forecast that isn't the one requested
# would be inconsistent. Falls back to the plain (non-stochastic) result on
# any failure, same "never claim it happened when it didn't" discipline as
# the point-forecast fallback above.


def run_dispatcher(date, da_forecast_method=None, n_scenarios=None,
                    cvar_alpha=None, cvar_lambda=None):
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

    # market_index_{date}.csv is fetched by UTC start-time window, so during
    # BST it also picks up SP1-2 of the *next* settlement date. Normally
    # harmless, but on the spring clock-change Sunday the settlement day has
    # only 46 periods, so SP1-2 appear twice with different prices -
    # set_index then raises a duplicate-label error downstream. Same fix as
    # forecast.py::load_actual: keep the row belonging to this file's own
    # settlement date. Affects 2 of 731+ days (30 Mar 2025, 29 Mar 2026);
    # normal days are unaffected since there's nothing to deduplicate.
    if df_prices["settlementPeriod"].duplicated().any():
        own = df_prices[df_prices["settlementDate"] == date]
        other = df_prices[df_prices["settlementDate"] != date]
        df_prices = pd.concat([own, other]).drop_duplicates(
            subset="settlementPeriod", keep="first"
        )

    da_prices = df_prices.set_index("settlementPeriod")["price"].sort_index()

    is_stochastic = bool(da_forecast_method) and da_forecast_method.endswith("_stochastic")
    base_method = da_forecast_method[:-len("_stochastic")] if is_stochastic else da_forecast_method

    # decision_prices drives what the DA leg actually schedules against.
    # da_basis records which price basis was really used, for traceability -
    # only ever "real" unless a forecast method was requested AND succeeded.
    decision_prices = da_prices
    da_basis = "real"
    if base_method:
        history = F.available_dates()
        fc, info = F.forecast_prices(date, base_method, history=history)
        if fc is None and base_method != "mean_7":
            print(f"  ⚠️  '{base_method}' forecast unavailable for {date} "
                  f"(likely missing wind/solar or demand data) — falling back to mean_7")
            fc, info = F.forecast_prices(date, "mean_7", history=history)
            base_method = "mean_7"
        if fc is not None:
            fc = fc.reindex(da_prices.index).dropna()
        if fc is not None and not fc.empty:
            decision_prices = fc
            da_basis = base_method
        else:
            print(f"  ⚠️  No usable forecast for {date} (insufficient history) — "
                  f"falling back to the real price for this day only")

    # Only attempt the stochastic hedge if the point forecast above succeeded
    # with NO fallback (da_basis == base_method exactly) - see module docstring.
    scenario_prices = None
    if is_stochastic and da_basis == base_method:
        rh = FR.load_residual_history(base_method)
        scenarios = FR.sample_scenarios(
            date, base_method,
            n_scenarios=n_scenarios or CVAR_N_SCENARIOS_DEFAULT,
            residual_history=rh,
        )
        if scenarios:
            aligned = [s.reindex(da_prices.index).dropna() for s in scenarios]
            aligned = [s for s in aligned if not s.empty]
            # optimise_battery_lp_cvar requires every scenario to share the
            # exact same index - guard rather than let a rare edge-case day
            # crash the whole dispatch run.
            if aligned and all(list(s.index) == list(aligned[0].index) for s in aligned):
                scenario_prices = aligned
                da_basis = f"{base_method}_stochastic"
        if scenario_prices is None:
            print(f"  ⚠️  No usable scenarios for {date} (insufficient residual history "
                  f"or alignment issue) — using the plain '{base_method}' forecast instead")

    id_prices = simulate_intraday_prices(da_prices)  # always from the REAL price - unaffected by da_basis

    df_bmrs = pd.read_csv(bmrs_file)
    df_bmrs = df_bmrs[df_bmrs["settlementPeriod"] <= 48].copy()
    ssp_series = df_bmrs.set_index("settlementPeriod")["systemSellPrice"]
    sbp_series = df_bmrs.set_index("settlementPeriod")["systemBuyPrice"]

    print(f"Running dispatcher for {date}")
    if scenario_prices:
        all_scenario_vals = pd.concat(scenario_prices, axis=1)
        print(f"DA basis: {da_basis} ({len(scenario_prices)} scenarios, "
              f"£{all_scenario_vals.min().min():.2f}-£{all_scenario_vals.max().max():.2f} "
              f"vs real £{da_prices.min():.2f}-£{da_prices.max():.2f})")
    elif da_basis != "real":
        print(f"DA basis: {da_basis} (decision £{decision_prices.min():.2f}-£{decision_prices.max():.2f} "
              f"vs real £{da_prices.min():.2f}-£{da_prices.max():.2f})")
    else:
        print(f"DA basis: {da_basis} (£{da_prices.min():.2f} to £{da_prices.max():.2f}/MWh)")
    print(f"ID price range: £{id_prices.min():.2f} to £{id_prices.max():.2f}/MWh")
    print(f"SSP range:      £{ssp_series.min():.2f} to £{ssp_series.max():.2f}/MWh")
    print(f"SBP range:      £{sbp_series.min():.2f} to £{sbp_series.max():.2f}/MWh")
    print("=" * 60)

    all_lp, all_id, all_bm = [], [], []
    all_cvar_diagnostics = {}
    total_revenue, total_cost = 0.0, 0.0

    for battery in assets:
        initial_soc = SOC_INIT * battery.capacity_mwh

        # --- DA layer ---
        # Decisions are built on decision_prices (forecast, if requested and
        # available) or hedged across scenario_prices (if stochastic);
        # settle_price below is always the REAL price, so money is always
        # what actually happened regardless of da_basis.
        da_committed = 1 - (ID_RESERVATION[battery.name] + BM_RESERVATION[battery.name])
        cvar_diag = None
        # Real execution costs, matching optimiser_lp.py's own convention and
        # exactly the expression forecast_pnl.py/da_stochastic_pnl.py already
        # use (COST_KW) - reused, not re-derived. Was previously omitted here
        # entirely, so the live DA leg silently defaulted to cost-BLIND
        # (0.0) despite v20 proving cost-awareness helps - see BRIEFING.md.
        cost_discharge = COST_IMPACT + COST_FEE + COST_DEGRADATION
        cost_charge = COST_IMPACT + COST_FEE
        if scenario_prices:
            df_lp, lp_planned_rev, soc_after_da, cvar_diag = optimise_battery_lp_cvar(
                battery, scenario_prices, committed_capacity=da_committed,
                initial_soc_mwh=initial_soc,
                cvar_alpha=cvar_alpha or CVAR_ALPHA_DEFAULT,
                cvar_lambda=cvar_lambda if cvar_lambda is not None else CVAR_LAMBDA_DEFAULT,
                cost_discharge=cost_discharge, cost_charge=cost_charge,
            )
            all_cvar_diagnostics[battery.name] = cvar_diag
        else:
            df_lp, lp_planned_rev, soc_after_da = optimise_battery_lp(
                battery, decision_prices, committed_capacity=da_committed,
                initial_soc_mwh=initial_soc,
                cost_discharge=cost_discharge, cost_charge=cost_charge,
            )
        # settle_price: raw real price, no cost adjustment - kept for
        # traceability/diagnostics only. Actual settlement (what shadow.py
        # logs as money) uses the two cost-adjusted columns below, mirroring
        # forecast_pnl.py::settle(..., with_costs=True) exactly: discharge is
        # paid price-minus-costs, charge costs price-plus-costs - genuinely
        # asymmetric, so one shared column can't represent both.
        df_lp["settle_price"] = df_lp["settlement_period"].map(da_prices)
        df_lp["settle_price_discharge"] = df_lp["settle_price"] - cost_discharge
        df_lp["settle_price_charge"] = df_lp["settle_price"] + cost_charge

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
        # price_col_charge defaults to price_col_discharge for ID/BM, whose
        # settlement is symmetric; the DA leg passes distinct cost-adjusted
        # columns since discharge/charge get opposite cost adjustments.
        def gross_rev_cost(df, price_col_discharge, price_col_charge=None):
            price_col_charge = price_col_charge or price_col_discharge
            disc = df[df["action"] == "discharge"]
            chg = df[df["action"] == "charge"]
            rev = (disc["power_mw"] * disc[price_col_discharge] * 0.5).sum()
            cost = (chg["power_mw"] * chg[price_col_charge] * 0.5).sum()
            return rev, cost

        # LP settles on the cost-adjusted real price, not "price" (which holds
        # decision_prices - the forecast, if da_basis != "real") and not the
        # raw settle_price (real but cost-blind) - see BRIEFING.md for why
        # the live path was cost-blind until this fix.
        lp_gross_rev, lp_gross_cost = gross_rev_cost(df_lp, "settle_price_discharge", "settle_price_charge")
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

        da_label = "planned revenue" if da_basis != "real" else "revenue"
        print(f"\n{battery.name}:")
        print(f"  DA committed: {da_committed*100:.0f}% | {da_label} £{lp_planned_rev:,.2f} | settled £{lp_gross_rev - lp_gross_cost:,.2f} | SOC start 50.0% -> end {soc_after_da/battery.capacity_mwh*100:.1f}%")
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

    # Side-channel, not a return-signature change: replay.py unpacks a plain
    # 3-tuple and must keep working untouched. shadow.py reads this to know
    # which basis actually produced the schedule (could differ from the
    # requested da_forecast_method if it fell back).
    df_lp_all.attrs["da_basis"] = da_basis
    df_lp_all.attrs["cvar_diagnostics"] = all_cvar_diagnostics  # {} unless stochastic actually ran

    df_lp_all.to_csv(f"../data/lp_schedule_{date}.csv", index=False)
    df_id_all.to_csv(f"../data/id_schedule_{date}.csv", index=False)
    df_bm_all.to_csv(f"../data/bm_schedule_{date}.csv", index=False)

    print(f"\nSaved updated schedules with SOC handoff to data/*_schedule_{date}.csv")

    return df_lp_all, df_id_all, df_bm_all


if __name__ == "__main__":
    yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    run_dispatcher(yesterday)
