import pandas as pd
from battery import assets

# --- DA Capacity Reservation Rules ---
# How much capacity each asset reserves for intraday/BM (not committed in DA)
RESERVATION = {
    "Battery_1": 0.50,  # Reserve 50% — nimble, better for intraday/BM
    "Battery_2": 0.30,  # Reserve 30% — balanced
    "Battery_3": 0.30,  # Reserve 30% — large, commits more in DA
    "Battery_4": 0.30,  # Reserve 30% — co-located
    "Battery_5": 0.30,  # Reserve 30% — co-located
}

# Number of periods to target for charge and discharge
# Based on typical price curve shape — morning charge, evening discharge
TOP_DISCHARGE_PERIODS = 10  # Top 10 most expensive periods
TOP_CHARGE_PERIODS = 10     # Bottom 10 cheapest periods


def get_da_schedule(price_series, assets):
    """
    Forward-looking DA optimiser.
    Looks at the full day price curve and schedules charge/discharge
    across the best periods while respecting capacity reservations.
    """

    # Rank periods by price
    sorted_by_price = price_series.sort_values()
    charge_periods = set(sorted_by_price.head(TOP_CHARGE_PERIODS).index)
    discharge_periods = set(sorted_by_price.tail(TOP_DISCHARGE_PERIODS).index)

    print(f"Charge periods (cheapest {TOP_CHARGE_PERIODS}): {sorted(charge_periods)}")
    print(f"Discharge periods (most expensive {TOP_DISCHARGE_PERIODS}): {sorted(discharge_periods)}")

    results = []

    for period, price in price_series.items():
        for battery in assets:
            reservation = RESERVATION[battery.name]
            committed_capacity = 1 - reservation  # e.g. 0.70 for most assets

            if period in charge_periods:
                available = battery.available_charge_mw() * committed_capacity
                if available > 0:
                    battery.charge(available)
                    action = 'charge'
                    power_mw = available
                else:
                    action = 'hold'
                    power_mw = 0

            elif period in discharge_periods:
                available = battery.available_discharge_mw() * committed_capacity
                if available > 0:
                    battery.discharge(available)
                    action = 'discharge'
                    power_mw = available
                else:
                    action = 'hold'
                    power_mw = 0

            else:
                action = 'hold'
                power_mw = 0

            results.append({
                'settlement_period': period,
                'price': price,
                'asset': battery.name,
                'action': action,
                'power_mw': round(power_mw, 2),
                'soc': round(battery.soc * 100, 1),
                'reserved_capacity_pct': reservation * 100
            })

    return pd.DataFrame(results)


# --- Run against yesterday's real market index prices ---

if __name__ == "__main__":
    from datetime import datetime, timedelta
    import os

    yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    price_file = f"../data/market_index_{yesterday}.csv"

    if not os.path.exists(price_file):
        print(f"Price file not found: {price_file}")
        print("Run fetch_da_prices.py first")
    else:
        df_prices = pd.read_csv(price_file)
        price_series = df_prices.set_index("settlementPeriod")["price"]

        print(f"Running DA optimiser on {yesterday}")
        print(f"Price range: £{price_series.min():.2f} to £{price_series.max():.2f}/MWh")
        print("="*60)

        results = get_da_schedule(price_series, assets)

        # Summary per asset
        print("\n--- Summary per asset ---")
        for asset_name in results['asset'].unique():
            df_asset = results[results['asset'] == asset_name]
            charges = df_asset[df_asset['action'] == 'charge']
            discharges = df_asset[df_asset['action'] == 'discharge']
            holds = df_asset[df_asset['action'] == 'hold']
            print(f"\n{asset_name} (DA reservation: {RESERVATION[asset_name]*100:.0f}%):")
            print(f"  Charge periods:    {len(charges)}")
            print(f"  Discharge periods: {len(discharges)}")
            print(f"  Hold periods:      {len(holds)}")
            print(f"  Final SOC:         {df_asset['soc'].iloc[-1]}%")

        # Save results
        results.to_csv(f"../data/da_schedule_{yesterday}.csv", index=False)
        print(f"\nSaved to data/da_schedule_{yesterday}.csv")