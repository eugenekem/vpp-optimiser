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
