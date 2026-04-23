# VPP Optimiser

A Virtual Power Plant optimisation platform for the GB energy market. Models battery dispatch across day-ahead, intraday, balancing mechanism, and ancillary service markets using real published market data.

---

## Portfolio

Five battery assets across Scotland and England:

| Asset | Type | Duration | Battery | Solar | Region |
|---|---|---|---|---|---|
| Battery 1 | Standalone | 2-hour | 10 MW | — | North Scotland |
| Battery 2 | Standalone | 4-hour | 25 MW | — | North England |
| Battery 3 | Standalone | 4-hour | 50 MW | — | South England |
| Battery 4 | Co-located | 4-hour | 20 MW | 15 MW | South Scotland |
| Battery 5 | Co-located | 4-hour | 40 MW | 30 MW | South England |

**Total:** ~145 MW battery, 45 MW solar.

---

## Markets

- Day Ahead (EPEX / N2EX)
- Intraday (continuous)
- Balancing Mechanism (Elexon / NESO)
- Dynamic Containment High and Low (NESO)

---

## Data Sources

All free-tier, operational data within 24 hours of settlement:

- Elexon BMRS — system prices, market index prices
- NESO Data Portal — DC tender forecasts, ancillary service data
- Open-Meteo — weather data per asset location
- Sheffield Solar PV_Live — GB solar generation

---

## Architecture

Modular Python implementation with separate layers for asset modelling, market optimisation, P&L calculation, and risk analysis. Each layer is standalone and can be developed independently.

| Component | File |
|---|---|
| Asset model | `models/battery.py` |
| Rules-based optimiser | `models/optimiser.py` |
| Forward-looking DA optimiser | `models/optimiser_da.py` |
| LP optimiser (PuLP) | `models/optimiser_lp.py` |
| P&L calculator | `models/pnl.py` |
| Risk layer | `models/risk.py` |
| Operations dashboard | `dashboard.py` |

---

## Stack

Python 3.12 · PuLP (CBC solver) · Streamlit · pandas · numpy

---

## Running

```bash
# Pull latest market data
cd scripts
python fetch_da_prices.py
python fetch_dc_tenders.py
python fetch_weather.py
python fetch_solar.py
python fetch_bmrs.py

# Run optimisers
cd ../models
python optimiser_lp.py
python pnl.py
python risk.py

# Launch dashboard
cd ..
streamlit run dashboard.py
```

---

## Status

Active development. See `BRIEFING.md` for architecture and roadmap.
