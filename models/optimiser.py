import pandas as pd
from battery import assets

# --- Rules-based optimiser ---

CHARGE_THRESHOLD = 20    # £/MWh - charge if price below this
DISCHARGE_THRESHOLD = 70 # £/MWh - discharge if price above this

def decide(battery, price):
    """
    Given a battery and a price, decide what action to take.
    Returns: action ('charge', 'discharge', 'hold'), power_mw
    """
    if price < CHARGE_THRESHOLD:
        available = battery.available_charge_mw()
        if available > 0:
            return 'charge', available
        else:
            return 'hold', 0

    elif price > DISCHARGE_THRESHOLD:
        available = battery.available_discharge_mw()
        if available > 0:
            return 'discharge', available
        else:
            return 'hold', 0

    else:
        return 'hold', 0


def run_optimiser(price_series, assets):
    """
    Run the rules-based optimiser across a full day of prices.
    price_series: pandas Series with settlement periods as index and prices as values
    """
    results = []

    for period, price in price_series.items():
        for battery in assets:
            action, power_mw = decide(battery, price)

            if action == 'charge':
                battery.charge(power_mw)
            elif action == 'discharge':
                battery.discharge(power_mw)

            results.append({
                'settlement_period': period,
                'price': price,
                'asset': battery.name,
                'action': action,
                'power_mw': power_mw,
                'soc': round(battery.soc * 100, 1)
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

        print(f"Running optimiser on {yesterday}")
        print(f"Price range: £{price_series.min():.2f} to £{price_series.max():.2f}/MWh")
        print(f"Charge threshold: £{CHARGE_THRESHOLD}/MWh")
        print(f"Discharge threshold: £{DISCHARGE_THRESHOLD}/MWh")
        print("="*60)

        results = run_optimiser(price_series, assets)

        # Summary per asset
        print("\n--- Summary per asset ---")
        for asset_name in results['asset'].unique():
            df_asset = results[results['asset'] == asset_name]
            charges = df_asset[df_asset['action'] == 'charge']
            discharges = df_asset[df_asset['action'] == 'discharge']
            holds = df_asset[df_asset['action'] == 'hold']
            print(f"\n{asset_name}:")
            print(f"  Charge periods:    {len(charges)}")
            print(f"  Discharge periods: {len(discharges)}")
            print(f"  Hold periods:      {len(holds)}")
            print(f"  Final SOC:         {df_asset['soc'].iloc[-1]}%")

        # Save results
        results.to_csv(f"../data/optimiser_results_{yesterday}.csv", index=False)
        print(f"\nSaved to data/optimiser_results_{yesterday}.csv")