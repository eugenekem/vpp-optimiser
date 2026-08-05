# config.py — VPP Optimiser shared configuration
#
# Single source of truth for capacity reservation splits across DA, ID, and BM.
# All optimiser layers import from here — change splits in one place only.
#
# Splits must sum to 1.0 per asset:
#   Battery_1:     DA=0.40  ID=0.30  BM=0.30  → 1.00
#   Batteries 2-5: DA=0.50  ID=0.20  BM=0.30  → 1.00

# --- Capacity reservation splits ---

DA_RESERVATION = {
    "Battery_1": 0.40,
    "Battery_2": 0.50,
    "Battery_3": 0.50,
    "Battery_4": 0.50,
    "Battery_5": 0.50,
}

ID_RESERVATION = {
    "Battery_1": 0.30,
    "Battery_2": 0.20,
    "Battery_3": 0.20,
    "Battery_4": 0.20,
    "Battery_5": 0.20,
}

BM_RESERVATION = {
    "Battery_1": 0.30,
    "Battery_2": 0.30,
    "Battery_3": 0.30,
    "Battery_4": 0.30,
    "Battery_5": 0.30,
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
import os as _os

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

# --- Validation: splits must sum to 1.0 ---
for asset in DA_RESERVATION:
    total = DA_RESERVATION[asset] + ID_RESERVATION[asset] + BM_RESERVATION[asset]
    assert abs(total - 1.0) < 1e-6, (
        f"Reservation splits for {asset} sum to {total:.2f}, expected 1.0"
    )
