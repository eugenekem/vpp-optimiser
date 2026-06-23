import requests
import pandas as pd
import sys
from datetime import datetime, timedelta

# Accept optional date argument for historical replay
# Usage: python fetch_bmrs.py            # fetches yesterday
#        python fetch_bmrs.py 2026-06-15 # fetches specific date

if len(sys.argv) > 1:
    target_date = sys.argv[1]
else:
    target_date = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")

url = f"https://data.elexon.co.uk/bmrs/api/v1/balancing/settlement/system-prices/{target_date}?format=json"

response = requests.get(url)
data = response.json()

df = pd.DataFrame(data["data"])
print(f"Fetched {len(df)} settlement periods for {target_date}")
print(df[["settlementDate", "settlementPeriod", "systemSellPrice", "systemBuyPrice"]].head(10))

df.to_csv(f"../data/system_prices_{target_date}.csv", index=False)
print(f"Saved to data/system_prices_{target_date}.csv")
