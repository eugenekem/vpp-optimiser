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

# Fixed (v24): previously queried an exact UTC calendar-day window and then
# force-labelled every row with the query date, discarding Elexon's own
# settlementDate — this was the actual bug (not an API limitation), matching
# the same UTC-window issue in fetch_da_prices.py. Now widened the same way
# and filtered to Elexon's own settlementDate == target_date, so this file's
# settlement period N is genuinely target_date's period N, and it still lines
# up row-for-row with the now-also-fixed market_index_{date}.csv.
window_start = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
window_end = (datetime.strptime(target_date, "%Y-%m-%d") + timedelta(days=1, hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

url = (
    "https://data.elexon.co.uk/bmrs/api/v1/forecast/generation/wind-and-solar/day-ahead"
    f"?from={window_start}&to={window_end}"
    "&processType=day%20ahead&format=json"
)

response = requests.get(url, timeout=60)
response.raise_for_status()
rows = response.json()["data"]

if not rows:
    print(f"No wind/solar forecast returned for {target_date}")
    sys.exit(1)

df = pd.DataFrame(rows)
df = df[df["settlementDate"] == target_date].copy()

if df.empty:
    print(f"No rows with settlementDate == {target_date} in the response")
    sys.exit(1)

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
