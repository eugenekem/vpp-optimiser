# VPP Optimiser — Code Map

A one-page guide to the codebase. Paste this alongside BRIEFING.md when starting a new Claude session.

---

## Project Structure

```
vpp-optimiser/
├── BRIEFING.md              # Master project briefing (read first)
├── CODE_MAP.md              # This file
├── SESSIONS.md              # Session-by-session log
├── README.md                # GitHub landing page
├── update_briefing.py       # Automation for updating briefing + session log
├── dashboard.py             # Streamlit war room dashboard
├── scripts/                 # Data pipelines
│   ├── fetch_bmrs.py        # Elexon system prices (SSP/SBP)
│   ├── fetch_da_prices.py   # Elexon market index prices (MID)
│   ├── fetch_dc_tenders.py  # NESO DC forecast (4-day forward)
│   ├── fetch_weather.py     # Open-Meteo weather for 5 asset locations
│   └── fetch_solar.py       # Sheffield Solar PV_Live GB solar generation
├── models/                  # Core model logic
│   ├── battery.py           # Battery asset class — SOC, charge/discharge, constraints
│   ├── optimiser.py         # Rules-based optimiser (simple thresholds)
│   ├── optimiser_da.py      # Forward-looking DA optimiser with reservation rules
│   ├── pnl.py               # P&L calculator per asset and portfolio
│   └── risk.py              # VaR, Sharpe, scenario analysis, concentration risk
└── data/                    # Generated CSV outputs (gitignored)
```

---

## File-by-File Reference

### Data Pipelines (`scripts/`)

**`fetch_bmrs.py`**
Pulls Elexon BMRS system prices (SSP/SBP) for yesterday. Outputs `data/system_prices_YYYY-MM-DD.csv`. Settlement period, SSP, SBP, imbalance volumes.

**`fetch_da_prices.py`**
Pulls Elexon market index prices (MID). Outputs `data/market_index_YYYY-MM-DD.csv`. Filters to APXMIDP provider only. This is our proxy for DA prices.

**`fetch_dc_tenders.py`**
Pulls NESO 4-day DC forecast from api.neso.energy. Outputs `data/dc_forecast_YYYY-MM-DD.csv`. DCH and DCL volumes across 6 EFA blocks per day.

**`fetch_weather.py`**
Pulls hourly weather from Open-Meteo for all 5 asset locations. Outputs `data/weather_YYYY-MM-DD.csv`. Temperature, wind speed, solar radiation.

**`fetch_solar.py`**
Pulls Sheffield Solar PV_Live for GB national solar generation. Outputs `data/solar_YYYY-MM-DD.csv`. Generation MW, capacity MW, capacity factor.

---

### Core Models (`models/`)

**`battery.py`**
Battery asset class. Every battery has MW, duration, capacity MWh, efficiency (90%), SOC floor (10%), SOC ceiling (90%), optional solar MW. Methods: `charge()`, `discharge()`, `available_charge_mw()`, `available_discharge_mw()`, `status()`. Instantiates the 5-asset portfolio as a list called `assets`.

**`optimiser.py`**
Rules-based optimiser. Makes decisions one period at a time based on simple thresholds (charge below £20, discharge above £70). Reactive, not forward-looking.

**`optimiser_da.py`**
Forward-looking DA optimiser. Looks at the full day price curve, identifies top 10 cheapest periods for charging and top 10 most expensive for discharging. Respects per-asset capacity reservation rules (Battery 1: 50%, others: 30%). Outputs `data/da_schedule_YYYY-MM-DD.csv`.

**`pnl.py`**
P&L calculator. Reads the DA schedule and market prices, calculates revenue (discharge × price × 0.5h), cost (charge × price × 0.5h), and net P&L per asset and portfolio. Outputs `data/pnl_YYYY-MM-DD.csv`.

**`risk.py`**
Risk layer. Calculates:
- VaR (95% and 99% confidence) — historical simulation method
- Volatility — standard deviation of period P&L
- Sharpe ratio — mean / std of period P&L
- Scenario analysis — P&L under price shocks (±20%, ±50%)
- Concentration risk — % of P&L by asset

---

### Dashboard (`dashboard.py`)

Streamlit war room interface with sections:
1. Morning briefing — green/amber/red signal based on price spread and negative prices
2. Strategy recommendations — per-asset actionable guidance based on day type
3. Portfolio P&L — revenue, cost, net per asset
4. Price curve — 48-period line chart
5. Asset status — SOC bars, MW, solar per asset
6. Risk summary — Sharpe, VaR, volatility, concentration chart
7. DC tender forecast — latest NESO 4-day forward
8. Dispatch schedule — period-by-period per asset (tabs), colour coded

Run with: `streamlit run dashboard.py`

---

### Automation (`update_briefing.py`)

End-of-session helper. Run with `python update_briefing.py`, enter version number. Writes current BRIEFING.md, appends new entry to SESSIONS.md, commits and pushes to GitHub.

---

## How the Pieces Connect

```
Data pipelines → CSVs in data/
            ↓
         battery.py (asset model)
            ↓
      optimiser_da.py (uses battery model + prices)
            ↓
         pnl.py (reads schedule + prices)
            ↓
         risk.py (reads P&L)
            ↓
      dashboard.py (visualises everything)
```

---

## Typical Daily Workflow

```bash
cd ~/Documents/vpp-optimiser/scripts
python fetch_da_prices.py
python fetch_dc_tenders.py
python fetch_weather.py
python fetch_solar.py
python fetch_bmrs.py

cd ../models
python optimiser_da.py
python pnl.py
python risk.py

cd ..
streamlit run dashboard.py
```

---

## What's Next (from BRIEFING.md section 8)

**`optimiser_lp.py`** — Linear programming optimiser using PuLP. Will replace the forward-looking DA optimiser. Looks at all 48 periods simultaneously and finds the globally optimal dispatch schedule.

See BRIEFING.md section 8 for the full LP formulation.

---

*Update this document when new files are added or significantly restructured.*
