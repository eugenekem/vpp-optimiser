import requests
import pandas as pd
import sys
from datetime import datetime, timedelta

# Fetches Elexon's DAY-AHEAD wind and solar generation forecast.
#
# This is the forecast published the day BEFORE delivery (~16:45), so it is
# legitimately available before day-ahead gate closure — usable as a predictive
# input without look-ahead cheating.
#
# Returns three series per settlement period: Solar, Wind Offshore, Wind Onshore.
#
# Usage:
#   python fetch_wind_solar.py             # yesterday
#   python fetch_wind_solar.py 2026-06-15  # specific date

if len(sys.argv) > 1:
    target_date = sys.argv[1]
else:
    target_date = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")

url = (
    "https://data.elexon.co.uk/bmrs/api/v1/forecast/generation/wind-and-solar/day-ahead"
    f"?from={target_date}T00:00Z&to={target_date}T23:30Z"
    "&processType=day%20ahead&format=json"
)

response = requests.get(url, timeout=60)
response.raise_for_status()
rows = response.json()["data"]

if not rows:
    print(f"No wind/solar forecast returned for {target_date}")
    sys.exit(1)

df = pd.DataFrame(rows)

# NOTE ON ALIGNMENT — deliberate, do not "fix" in isolation.
# Like fetch_da_prices.py, this queries a UTC calendar-day window on startTime.
# During BST that window holds SP3-48 of `target_date` plus SP1-2 of the next
# settlement date (a GB settlement day starts 23:00 UTC the evening before).
# We keep that convention ON PURPOSE so this file lines up row-for-row with
# market_index_{date}.csv: the same settlementPeriod in both files refers to
# the same real half-hour. Filtering to settlementDate == target_date here
# would silently put features and prices 24h out of step for SP1-2.
# The underlying misalignment is a known issue affecting both feeds equally.

# One row per settlement period, one column per generation type.
wide = (
    df.pivot_table(index="settlementPeriod", columns="psrType",
                   values="quantity", aggfunc="sum")
      .rename(columns={"Solar": "solar_mw",
                       "Wind Offshore": "wind_offshore_mw",
                       "Wind Onshore": "wind_onshore_mw"})
      .sort_index()
)

for col in ["solar_mw", "wind_offshore_mw", "wind_onshore_mw"]:
    if col not in wide.columns:
        wide[col] = 0.0

wide["wind_total_mw"] = wide["wind_offshore_mw"] + wide["wind_onshore_mw"]
wide["renewable_total_mw"] = wide["wind_total_mw"] + wide["solar_mw"]
wide = wide.reset_index()
wide.insert(0, "settlementDate", target_date)

print(f"Fetched {len(wide)} settlement periods for {target_date}")
print(wide[["settlementPeriod", "solar_mw", "wind_total_mw", "renewable_total_mw"]].head())

wide.to_csv(f"../data/wind_solar_{target_date}.csv", index=False)
print(f"Saved to data/wind_solar_{target_date}.csv")
