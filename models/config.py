# config.py — VPP Optimiser shared configuration
#
# Single source of truth for capacity reservation splits across DA, ID, and BM.
# All optimiser layers import from here — change splits in one place only.
#
# Splits must sum to 1.0 per asset. Defaults (never backtested until v30's
# reservation_sensitivity.py sweep) split batteries into two duration classes:
#   Battery_1 (2-hour):     DA=0.40  ID=0.30  BM=0.30  → 1.00
#   Batteries 2-5 (4-hour): DA=0.50  ID=0.20  BM=0.30  → 1.00
#
# ID/BM are overridable per-run via environment variables (same mechanism as
# the execution costs below) so reservation_sensitivity.py can sweep candidate
# splits in subprocesses without editing this file. DA is always the implied
# complement (1 - ID - BM) per class — dispatcher.py has only ever read DA's
# committed capacity this way (see BRIEFING.md v30), so deriving it here keeps
# config.py honest about what's actually live rather than hardcoding a DA
# value that could silently drift out of sync with an overridden ID/BM.
import os as _os

_ID_4H = float(_os.environ.get("VPP_RES_ID_4H", 0.20))
_BM_4H = float(_os.environ.get("VPP_RES_BM_4H", 0.30))
_ID_2H = float(_os.environ.get("VPP_RES_ID_2H", 0.30))
_BM_2H = float(_os.environ.get("VPP_RES_BM_2H", 0.30))

assert _ID_4H + _BM_4H <= 1.0, f"4-hour class ID+BM ({_ID_4H + _BM_4H:.2f}) exceeds 1.0 — DA would go negative"
assert _ID_2H + _BM_2H <= 1.0, f"2-hour class ID+BM ({_ID_2H + _BM_2H:.2f}) exceeds 1.0 — DA would go negative"

# --- Capacity reservation splits ---

ID_RESERVATION = {
    "Battery_1": _ID_2H,
    "Battery_2": _ID_4H,
    "Battery_3": _ID_4H,
    "Battery_4": _ID_4H,
    "Battery_5": _ID_4H,
}

BM_RESERVATION = {
    "Battery_1": _BM_2H,
    "Battery_2": _BM_4H,
    "Battery_3": _BM_4H,
    "Battery_4": _BM_4H,
    "Battery_5": _BM_4H,
}

DA_RESERVATION = {
    name: 1.0 - ID_RESERVATION[name] - BM_RESERVATION[name] for name in ID_RESERVATION
}

# --- Battery operating parameters ---
EFFICIENCY = 0.90       # Round-trip efficiency
SOC_FLOOR  = 0.10       # Minimum SOC (10%)
SOC_CEIL   = 0.90       # Maximum SOC (90%)
SOC_INIT   = 0.50       # Initial SOC (50%)
DURATION   = 0.50       # Settlement period duration (hours)

# --- Execution costs (£/MWh) ---
#
# Everything before v20 assumed costless trading of unlimited volume at the
# published market-index price. These are the costs that gap sits on. They are
# the single biggest difference between a backtest number and a real one.
#
# "Central" GB BESS assumptions — deliberately middle-of-the-road, and the
# figures a technical reviewer is most likely to probe. Override per run.
#
# Overridable per-run via environment variables so a sensitivity sweep can vary
# them in subprocesses without editing this file — an interrupted run can never
# leave the repo holding another scenario's assumptions.

COST_DEGRADATION = float(_os.environ.get("VPP_COST_DEGRADATION", 4.00))
                          # per MWh DISCHARGED — battery life consumed by cycling
COST_FEE         = float(_os.environ.get("VPP_COST_FEE", 0.15))
                          # per MWh traded, both directions — exchange + clearing
COST_IMPACT      = float(_os.environ.get("VPP_COST_IMPACT", 0.75))
                          # per MWh traded, both directions — own-bid price impact
                          # (a ~145 MW book is a non-trivial share of a GB DA
                          #  half-hour, so it moves the price against itself)

# Applied as: discharge earns (price - IMPACT - FEE - DEGRADATION)
#             charge   pays  (price + IMPACT + FEE)
# Degradation is charged on discharge only, i.e. per MWh delivered.

# --- Intraday price simulation ---
ID_SPREAD_MEAN = 0.0    # £/MWh — intraday prices centred on DA
ID_SPREAD_STD  = 5.0    # £/MWh — typical intraday volatility around DA
ID_RANDOM_SEED = 42     # Fixed seed for Phase 1 historical replay

# --- CVaR-hedged stochastic DA optimisation (v26, optimiser_lp_stochastic.py) ---
CVAR_N_SCENARIOS_DEFAULT = int(_os.environ.get("VPP_CVAR_N_SCENARIOS", 20))
CVAR_ALPHA_DEFAULT       = float(_os.environ.get("VPP_CVAR_ALPHA", 0.90))
CVAR_LAMBDA_DEFAULT      = float(_os.environ.get("VPP_CVAR_LAMBDA", 0.5))

# --- Validation: splits must sum to 1.0 ---
for asset in DA_RESERVATION:
    total = DA_RESERVATION[asset] + ID_RESERVATION[asset] + BM_RESERVATION[asset]
    assert abs(total - 1.0) < 1e-6, (
        f"Reservation splits for {asset} sum to {total:.2f}, expected 1.0"
    )
