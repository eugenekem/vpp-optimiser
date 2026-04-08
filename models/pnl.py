import pandas as pd
from datetime import datetime, timedelta
import os

def calculate_pnl(schedule_file, price_file):
    """
    Calculate P&L from a DA schedule against real market prices.
    
    For each discharge action: revenue = power_mw * 0.5 * price
    For each charge action: cost = power_mw * 0.5 * price
    Net P&L = total revenue - total cost
    """

    df = pd.read_csv(schedule_file)
    df_prices = pd.read_csv(price_file)

    # Map prices to settlement periods
    price_map = df_prices.set_index("settlementPeriod")["price"].to_dict()
    df["market_price"] = df["settlement_period"].map(price_map)

    # Calculate revenue and cost per row
    # Revenue: when discharging — selling power to market
    # Cost: when charging — buying power from market
    df["revenue"] = df.apply(
        lambda row: row["power_mw"] * 0.5 * row["market_price"]
        if row["action"] == "discharge" else 0, axis=1
    )

    df["cost"] = df.apply(
        lambda row: row["power_mw"] * 0.5 * row["market_price"]
        if row["action"] == "charge" else 0, axis=1
    )

    df["net_pnl"] = df["revenue"] - df["cost"]

    return df


def print_pnl_report(df, date):
    """Print a clean P&L report by asset and portfolio total."""

    print(f"\n{'='*60}")
    print(f"  P&L REPORT — {date}")
    print(f"{'='*60}")

    portfolio_revenue = 0
    portfolio_cost = 0

    for asset_name in df["asset"].unique():
        df_asset = df[df["asset"] == asset_name]
        revenue = df_asset["revenue"].sum()
        cost = df_asset["cost"].sum()
        net = revenue - cost

        portfolio_revenue += revenue
        portfolio_cost += cost

        print(f"\n{asset_name}:")
        print(f"  Revenue (discharge):  £{revenue:>10.2f}")
        print(f"  Cost    (charge):     £{cost:>10.2f}")
        print(f"  Net P&L:              £{net:>10.2f}")

    portfolio_net = portfolio_revenue - portfolio_cost
    print(f"\n{'='*60}")
    print(f"  PORTFOLIO TOTAL:")
    print(f"  Revenue:  £{portfolio_revenue:>10.2f}")
    print(f"  Cost:     £{portfolio_cost:>10.2f}")
    print(f"  Net P&L:  £{portfolio_net:>10.2f}")
    print(f"{'='*60}\n")

    return portfolio_net


# --- Run against yesterday's DA schedule and prices ---

if __name__ == "__main__":
    yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    schedule_file = f"../data/da_schedule_{yesterday}.csv"
    price_file = f"../data/market_index_{yesterday}.csv"

    if not os.path.exists(schedule_file):
        print(f"Schedule file not found: {schedule_file}")
        print("Run optimiser_da.py first")
    elif not os.path.exists(price_file):
        print(f"Price file not found: {price_file}")
        print("Run fetch_da_prices.py first")
    else:
        df = calculate_pnl(schedule_file, price_file)
        net = print_pnl_report(df, yesterday)

        # Save detailed P&L to CSV
        df.to_csv(f"../data/pnl_{yesterday}.csv", index=False)
        print(f"Detailed P&L saved to data/pnl_{yesterday}.csv")