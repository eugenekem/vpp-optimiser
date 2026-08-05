import requests
import pandas as pd
import sys
from datetime import datetime, timedelta

# Fetches Elexon's DAY-AHEAD national demand forecast for a target date.
#
# The /history endpoint is keyed by publishTime and returns the forecast as it
# stood at that moment, covering a rolling horizon. We ask for the publication
# at noon the day BEFORE delivery, which:
#   - covers all 48 settlement periods of the target date, and
#   - is genuinely available before day-ahead gate closure (12:00), so using
#     it as a predictive feature is not look-ahead cheating.
#
# ALIGNMENT NOTE: rows are stored faithfully with their own settlementDate and
# settlementPeriod — deliberately NOT forced onto the UTC-window convention
# used by fetch_da_prices.py / fetch_wind_solar.py. Joining to prices must key
# on (settlementDate, settlementPeriod) so the two stay in step across BST/GMT.
#
# Usage:
#   python fetch_demand.py             # yesterday
#   python fetch_demand.py 2026-06-15  # specific date

if len(sys.argv) > 1:
    target_date = sys.argv[1]
else:
    target_date = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")

target = datetime.strptime(target_date, "%Y-%m-%d")
publish_at = (target - timedelta(days=1)).strftime("%Y-%m-%dT12:00Z")
next_date = (target + timedelta(days=1)).strftime("%Y-%m-%d")

url = ("https://data.elexon.co.uk/bmrs/api/v1/forecast/demand/day-ahead/history"
       f"?publishTime={publish_at}&format=json")

response = requests.get(url, timeout=60)
response.raise_for_status()
rows = response.json().get("data", [])

if not rows:
    print(f"No demand forecast published at {publish_at} for {target_date}")
    sys.exit(1)

df = pd.DataFrame(rows)

# Keep the target date plus the following day: the next day's early periods are
# what the price files fold in during BST, so retaining them lets the join line
# up without another network call.
df = df[df["settlementDate"].isin([target_date, next_date])].copy()

if df.empty or target_date not in set(df["settlementDate"]):
    print(f"Publication at {publish_at} did not cover {target_date}")
    sys.exit(1)

keep = ["settlementDate", "settlementPeriod", "startTime", "publishTime",
        "nationalDemand", "transmissionSystemDemand"]
df = df[[c for c in keep if c in df.columns]]
df = df.sort_values(["settlementDate", "settlementPeriod"]).reset_index(drop=True)

n_target = (df["settlementDate"] == target_date).sum()
print(f"Fetched {len(df)} rows ({n_target} for {target_date}) "
      f"published {df['publishTime'].iloc[0]}")
print(df.head(3).to_string(index=False))

df.to_csv(f"../data/demand_{target_date}.csv", index=False)
print(f"Saved to data/demand_{target_date}.csv")
