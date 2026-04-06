import requests
import pandas as pd
from datetime import datetime, timedelta

yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
from_time = f"{yesterday}T00:00:00Z"
to_time = f"{yesterday}T23:59:59Z"

url = f"https://data.elexon.co.uk/bmrs/api/v1/balancing/pricing/market-index?from={from_time}&to={to_time}&format=json"

response = requests.get(url)
data = response.json()

df = pd.DataFrame(data["data"])

# Filter to APXMIDP only — the main price provider
df = df[df["dataProvider"] == "APXMIDP"].copy()
df = df.sort_values("settlementPeriod").reset_index(drop=True)

print(f"Fetched {len(df)} settlement periods for {yesterday}")
print(df[["settlementDate", "settlementPeriod", "price", "volume"]].head(10))

df.to_csv(f"../data/market_index_{yesterday}.csv", index=False)
print(f"Saved to data/market_index_{yesterday}.csv")