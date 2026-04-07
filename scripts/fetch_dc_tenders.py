import requests
import pandas as pd
from datetime import datetime, timedelta
from io import StringIO

yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")

# NESO DC 4-day forecast - actively updated daily
url = "https://api.neso.energy/dataset/c8cd1e99-bc7e-454c-8ac1-ebd9264f4d0f/resource/1b85a3f3-80f0-49cf-9b0e-49648fa0cae6/download/dcrequirements.csv"

response = requests.get(url)
df = pd.read_csv(StringIO(response.text))

print(f"Fetched {len(df)} DC forecast records")
print(df)

df.to_csv(f"../data/dc_forecast_{yesterday}.csv", index=False)
print(f"Saved to data/dc_forecast_{yesterday}.csv")