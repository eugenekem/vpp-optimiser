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

from_time = f"{target_date}T00:00:00Z"
to_time   = f"{target_date}T23:59:59Z"

url = (
    f"https://data.elexon.co.uk/bmrs/api/v1/balancing/pricing/market-index"
    f"?from={from_time}&to={to_time}&format=json"
)

response = requests.get(url)
data = response.json()

df = pd.DataFrame(data["data"])
df = df[df["dataProvider"] == "APXMIDP"].copy()
df = df.sort_values("settlementPeriod").reset_index(drop=True)

print(f"Fetched {len(df)} settlement periods for {target_date}")
print(df[["settlementDate", "settlementPeriod", "price", "volume"]].head(10))

df.to_csv(f"../data/market_index_{target_date}.csv", index=False)
print(f"Saved to data/market_index_{target_date}.csv")
