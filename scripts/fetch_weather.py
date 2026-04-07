import requests
import pandas as pd
from datetime import datetime, timedelta

yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")

# Asset locations
assets = [
    {"name": "Battery_1", "lat": 57.5, "lon": -4.0,  "region": "North Scotland"},
    {"name": "Battery_2", "lat": 54.5, "lon": -1.5,  "region": "North England"},
    {"name": "Battery_3", "lat": 51.5, "lon": -1.0,  "region": "South England"},
    {"name": "Battery_4", "lat": 55.5, "lon": -3.5,  "region": "South Scotland"},
    {"name": "Battery_5", "lat": 51.5, "lon": -1.0,  "region": "South England"},
]

all_data = []

for asset in assets:
    url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={asset['lat']}&longitude={asset['lon']}"
        f"&start_date={yesterday}&end_date={yesterday}"
        f"&hourly=temperature_2m,windspeed_10m,shortwave_radiation"
        f"&timezone=Europe/London"
    )
    
    response = requests.get(url)
    data = response.json()
    
    df = pd.DataFrame({
        "time": data["hourly"]["time"],
        "temperature_c": data["hourly"]["temperature_2m"],
        "windspeed_ms": data["hourly"]["windspeed_10m"],
        "solar_radiation_wm2": data["hourly"]["shortwave_radiation"],
        "asset": asset["name"],
        "region": asset["region"]
    })
    
    all_data.append(df)
    print(f"Fetched {len(df)} records for {asset['name']} ({asset['region']})")

# Combine all assets
df_all = pd.concat(all_data, ignore_index=True)
df_all.to_csv(f"../data/weather_{yesterday}.csv", index=False)
print(f"\nSaved to data/weather_{yesterday}.csv")
print(df_all[df_all["asset"] == "Battery_1"].head(5))