import requests
import pandas as pd
from datetime import datetime, timedelta

# Fetch yesterday's system sell price (SSP) from Elexon BMRS
yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")

url = f"https://data.elexon.co.uk/bmrs/api/v1/balancing/settlement/system-prices/{yesterday}?format=json"

response = requests.get(url)
data = response.json()

# Parse into dataframe
df = pd.DataFrame(data["data"])
print(f"Fetched {len(df)} settlement periods for {yesterday}")
print(df[["settlementDate", "settlementPeriod", "systemSellPrice", "systemBuyPrice"]].head(10))

# Save to data folder
df.to_csv(f"../data/system_prices_{yesterday}.csv", index=False)
print(f"Saved to data/system_prices_{yesterday}.csv")