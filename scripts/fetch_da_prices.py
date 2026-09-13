import requests
import pandas as pd
import sys
from datetime import datetime, timedelta

# Accept optional date argument for historical replay
# Usage: python fetch_da_prices.py            # fetches yesterday
#        python fetch_da_prices.py 2026-06-15 # fetches specific date

if len(sys.argv) > 1:
    target_date = sys.argv[1]
else:
    target_date = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")

# Fixed (v24): a GB settlement day can start as early as 23:00 UTC the day
# before (BST), so a window of exactly [D 00:00, D 23:59:59] UTC missed
# target_date's own first periods (they live in the day-before's window) while
# picking up the NEXT day's first periods instead. We now widen the window on
# both sides and then filter to rows Elexon itself dates as target_date -
# using Elexon's own authoritative settlementDate rather than computing
# BST/GMT boundaries ourselves, so this is correct in both seasons and on the
# two annual clock-change days without special-casing them here.
window_start = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
window_end = (datetime.strptime(target_date, "%Y-%m-%d") + timedelta(days=1, hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

url = (
    f"https://data.elexon.co.uk/bmrs/api/v1/balancing/pricing/market-index"
    f"?from={window_start}&to={window_end}&format=json"
)

response = requests.get(url)
data = response.json()

df = pd.DataFrame(data["data"])
df = df[df["dataProvider"] == "APXMIDP"].copy()
df = df[df["settlementDate"] == target_date].copy()
df = df.sort_values("settlementPeriod").reset_index(drop=True)

print(f"Fetched {len(df)} settlement periods for {target_date}")
print(df[["settlementDate", "settlementPeriod", "price", "volume"]].head(10))

df.to_csv(f"../data/market_index_{target_date}.csv", index=False)
print(f"Saved to data/market_index_{target_date}.csv")
