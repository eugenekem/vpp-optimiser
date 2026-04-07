import requests
import pandas as pd
from datetime import datetime, timedelta

yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")

# Sheffield Solar PV_Live - national GB solar generation
url = f"https://api.solar.sheffield.ac.uk/pvlive/api/v4/gsp/0?start={yesterday}T00:00:00&end={yesterday}T23:30:00&extra_fields=capacity_mwp"

response = requests.get(url)
data = response.json()

df = pd.DataFrame(data["data"], columns=data["meta"])
df = df.sort_values("datetime_gmt").reset_index(drop=True)

# Calculate capacity factor - useful for scaling to your assets
df["capacity_factor"] = df["generation_mw"] / df["capacity_mwp"]

print(f"Fetched {len(df)} records for {yesterday}")
print(df[["datetime_gmt", "generation_mw", "capacity_mwp", "capacity_factor"]].head(10))

df.to_csv(f"../data/solar_{yesterday}.csv", index=False)
print(f"Saved to data/solar_{yesterday}.csv")