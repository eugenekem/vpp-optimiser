# ⚡ VPP Optimiser

A production-grade **Virtual Power Plant (VPP) optimisation platform** for GB energy markets. Built on real market data from Elexon BMRS and National Grid ESO, the platform simulates the full operational workflow of a battery asset optimisation desk — from day-ahead scheduling through to risk management and P&L reporting.

---

## Overview

The platform manages a proxy portfolio of 5 BESS assets (145 MW total capacity) across multiple GB wholesale and ancillary markets. It is designed to replicate the daily decision-making of a real VPP optimisation team — with a war room dashboard, per-asset strategy recommendations, and a modular optimisation architecture.

**Target markets:**
- Day Ahead (DA) — EPEX / N2EX auction
- Intraday (ID) — Continuous intraday trading
- Balancing Mechanism (BM) — Elexon / National Grid ESO
- Ancillary Services — Dynamic Containment (DC High and DC Low)

---

## Asset Portfolio

| Asset | Type | Duration | Capacity | Region |
|---|---|---|---|---|
| Battery 1 | Standalone | 2-hour | 10 MW | North Scotland |
| Battery 2 | Standalone | 4-hour | 25 MW | North England |
| Battery 3 | Standalone | 4-hour | 50 MW | South England |
| Battery 4 | Co-located + Solar | 4-hour | 20 MW / 15 MW solar | South Scotland |
| Battery 5 | Co-located + Solar | 4-hour | 40 MW / 30 MW solar | South England |

---

## Architecture

```
vpp-optimiser/
├── scripts/                  # Data pipeline scripts
│   ├── fetch_bmrs.py         # Elexon system prices (SSP/SBP)
│   ├── fetch_da_prices.py    # Market index prices (MID)
│   ├── fetch_dc_tenders.py   # NESO DC tender forecast
│   ├── fetch_weather.py      # Open-Meteo weather data
│   └── fetch_solar.py        # Sheffield Solar PV_Live
│
├── models/                   # Core optimisation models
│   ├── battery.py            # Battery asset model (SOC, charge/discharge logic)
│   ├── optimiser.py          # Rules-based optimiser
│   ├── optimiser_da.py       # Forward-looking DA optimiser
│   ├── pnl.py                # P&L calculator
│   └── risk.py               # Risk layer (VaR, Sharpe, scenario analysis)
│
├── dashboard.py              # War room Streamlit dashboard
├── update_briefing.py        # Briefing and session log automation
├── BRIEFING.md               # Master project briefing document
└── data/                     # Output data (CSV)
```

---

## Data Sources

All data is sourced from free, publicly available APIs:

| Data | Source | API |
|---|---|---|
| System prices (SSP/SBP) | Elexon BMRS | `data.elexon.co.uk` |
| Market index prices | Elexon BMRS | `data.elexon.co.uk` |
| DC tender forecast | National Grid ESO | `api.neso.energy` |
| Weather data | Open-Meteo | `archive-api.open-meteo.com` |
| Solar generation | Sheffield Solar PV_Live | `api.solar.sheffield.ac.uk` |

---

## War Room Dashboard

The Streamlit dashboard provides a full operational view for the head of optimisation:

- **Morning briefing** — Green/amber/red market signal based on price spread and negative price detection
- **Strategy recommendations** — Per-asset actionable guidance based on market conditions and risk metrics
- **Portfolio P&L** — Revenue, cost, and net P&L per asset and portfolio total
- **Price curve** — 48-period settlement price chart
- **Asset status** — Live SOC, available capacity, and solar output per asset
- **Risk summary** — Sharpe ratio, VaR (95%), P&L volatility, concentration risk
- **DC tender forecast** — 4-day forward NESO Dynamic Containment requirements
- **Dispatch schedule** — Period-by-period charge/discharge decisions per asset

---

## Optimiser Architecture

The platform is built in modular layers — each market layer plugs in independently:

```
Rules-based optimiser (built)
    ↓
Forward-looking DA optimiser (built)
    ↓
LP optimisation — PuLP / Google OR-Tools (in progress)
    ↓
Intraday layer (planned)
    ↓
BM layer (planned)
    ↓
Stochastic optimisation under price uncertainty (planned)
    ↓
AI agent layer — Claude API (planned)
```

---

## Risk Layer

The risk module calculates:
- **Value at Risk (VaR)** at 95% and 99% confidence levels
- **Sharpe ratio** — return per unit of risk across settlement periods
- **P&L volatility** — standard deviation of period-level net P&L
- **Scenario analysis** — stress tests across ±20% and ±50% price scenarios
- **Concentration risk** — P&L contribution per asset with breach alerts

---

## Getting Started

### Prerequisites
```bash
Python 3.12+
pip install requests pandas numpy streamlit pulp
```

### Run data pipelines
```bash
cd scripts
python fetch_da_prices.py
python fetch_bmrs.py
python fetch_dc_tenders.py
python fetch_weather.py
python fetch_solar.py
```

### Run optimiser and P&L
```bash
cd models
python optimiser_da.py
python pnl.py
python risk.py
```

### Launch war room dashboard
```bash
streamlit run dashboard.py
```

---

## Tech Stack

| Component | Tool |
|---|---|
| Core language | Python 3.12 |
| Data storage | CSV → SQLite (planned) |
| Dashboard | Streamlit |
| Optimisation | PuLP / Google OR-Tools |
| Version control | GitHub |

---

## Roadmap

- [x] Data pipelines (Elexon, NESO, weather, solar)
- [x] Battery asset model with SOC constraints
- [x] Rules-based optimiser
- [x] Forward-looking DA optimiser with capacity reservation
- [x] P&L calculator
- [x] Risk layer (VaR, Sharpe, scenarios)
- [x] War room dashboard
- [ ] LP optimisation upgrade
- [ ] Intraday optimiser layer
- [ ] BM optimiser layer
- [ ] Stochastic optimisation
- [ ] AI agent integration
- [ ] Monthly P&L reporting
- [ ] Telegram alerts
- [ ] Phase 2 shadow trading

---

## Author

**Eugene Sovathana Kem**
GB Electricity Market Analyst | Energy Economics MSc (Paul Stevens Prize, University of Dundee) | Data Analytics Certificate, Imperial College Business School

[LinkedIn](https://www.linkedin.com/in/eugenekem) | Glasgow, UK
