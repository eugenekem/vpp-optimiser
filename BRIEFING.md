# Virtual Power Plant (VPP) Project — Master Briefing Document
**Version:** 4.0
**Date:** April 2026
**Status:** In Progress — Data Pipeline Build

---

## 1. Project Goal & Ambition

Build a realistic Virtual Power Plant (VPP) simulation model that mirrors real-world asset optimisation operations in the GB energy market. The ultimate goal is to develop the skills, processes, and team workflows needed to operate as a professional VPP optimisation and trading desk.

This is not a quick-build project. It is being developed carefully and deliberately to create genuine operational experience.

---

## 2. Business Vision

Position as a team of asset optimisers and energy traders operating across multiple GB wholesale and balancing markets. The model should replicate the daily experience of a real optimisation desk — with traders and optimisers working together across short-term and day-ahead timeframes.

**This project is not initially focused on profit.** The primary objective is to master daily net arbitrage across markets before layering in cost of investment and financial performance analysis.

---

## 3. Asset Portfolio

A proxy portfolio of 5 power units with variable sizing for portfolio diversity:

| Asset | Type | Duration | MW (Battery) | MW (Solar) | Region | DNO |
|---|---|---|---|---|---|---|
| Battery 1 | Standalone | 2-hour | 10 MW | — | North Scotland | SSEN Transmission |
| Battery 2 | Standalone | 4-hour | 25 MW | — | North England | Northern Powergrid |
| Battery 3 | Standalone | 4-hour | 50 MW | — | South England | National Grid (NGET) |
| Battery 4 | Co-located + Solar | 4-hour | 20 MW | 15 MW | South Scotland | SP Transmission |
| Battery 5 | Co-located + Solar | 4-hour | 40 MW | 30 MW | South England | National Grid (NGET) |

**Total battery capacity:** ~145 MW
**Total solar capacity:** 45 MW

**Geographical notes:**
- Scottish assets sit within constraint zones — Anglo-Scottish interconnector congestion will affect BM behaviour
- North Scotland has high wind penetration — creates interesting system price dynamics
- South Scotland is a major renewable export zone
- South England assets experience highest demand zone exposure and better solar yield
- Solar yield in South England will be materially higher than Scotland — affects co-located optimisation decisions

**Asset constraints to define before Phase 1:**
- Export/import limits per asset
- Battery degradation modelling approach — affects cycling aggressiveness

---

## 4. Target Markets

All markets are GB-based:

| Market | Venue | Notes |
|---|---|---|
| Day Ahead (DA) | EPEX / N2EX auction | Gate closure 12:00 noon day before |
| Intraday (ID) | Continuous intraday | Approximated via DA + BM spread in early phases |
| Balancing Mechanism (BM) | Elexon / National Grid ESO | Core market for all assets |
| Ancillary Services | National Grid ESO | DC High and DC Low — primary focus |

**Ancillary service focus: Dynamic Containment (DC)**
- DC High (over-frequency response) and DC Low (under-frequency response)
- Daily ESO tenders — clean, well-documented, free data available
- All 5 assets are credible DC participants given MW sizes
- Batteries are naturally well-suited to frequency response

---

## 5. Data Sources

### Free & Accessible
- **Elexon BMRS** — BM data, settlement prices, system prices, imbalance volumes
- **National Grid ESO** — DC tender results, ancillary service data, system forecasts
- **EPEX / N2EX** — Day ahead auction results (with short lag)
- **Open-Meteo / Met Office DataHub (free tier)** — Weather data for solar and demand forecasting
- **Sheffield Solar / Solcast (free tier)** — Solar generation estimates

### Known Gap (Managed)
- Real-time intraday continuous prices not freely available
- **Workaround:** Approximate intraday using DA prices plus BM system price spread — sufficient for Phase 1 and Phase 2

### Not Required Yet (Paid)
- High-quality solar irradiance forecasts at scale
- Real-time intraday order book data

**Principle: No paid data subscriptions in the short to medium term.**

---

## 6. Tech Stack

| Component | Tool | Notes |
|---|---|---|
| Core language | Python 3.12.4 | Confirmed version |
| Data storage | CSV → SQLite | Start with CSV, upgrade to SQLite when needed |
| Dashboard | Streamlit | Simple, Python-based, fast to build |
| Optimisation engine | PuLP / Google OR-Tools | For charge/discharge scheduling |
| Version control | GitHub | Repo: github.com/eugenekem/vpp-optimiser |

---

## 7. Operating Model

### Time Approach
The model will operate **one day behind real time** — using published data from the previous day to make decisions as if operating live.

### Key Decision Deadline
**Day Ahead gate closure: 12:00 noon, day before delivery.** This is the anchor point for the entire team's daily workflow.

### Market Sequence
DA gate closure (12:00) → Intraday windows → BM flagging & dispatch → DC tender delivery

### Settlement Reconciliation
A reconciliation step is required after each trading day — comparing planned positions against actual settlement to measure performance and identify gaps.

---

## 8. Development Phases

### Phase 1 — Historical Replay
- Run model one day behind on real published data
- Make decisions as if operating in real time
- Measure quality of positions against actuals
- No risk; full learning environment

### Phase 2 — Shadow Trading (Priority Phase)
- Model runs in real time but makes no real trades
- Decisions compared against actual market outcomes same day
- Tests optimisation logic, team workflows, and decision timing
- Exposes data feed issues, timing problems, and model gaps
- **This is where the team starts making live decisions without financial risk**

### Phase 3 — Live Single Asset
- Trade one asset live in one market (Battery 1 — 10MW 2-hour standalone in BM)
- Remaining assets remain in shadow mode
- Learn what breaks in real operation

### Phase 4 — Scale Up
- Add assets and markets gradually
- Only expand when previous layer is stable

### Phase 5 — Residential Solar Aggregation (Future Scope)
- Operate as an aggregator across ~100 rooftop residential solar systems
- **Parked until Phase 4 is stable. Not in scope for current build.**

---

## 9. Team Structure (Target)

- **Optimisers** — Asset dispatch, charge/discharge scheduling, market stacking
- **Traders** — DA and intraday position management, DC tender management
- **Short-term Planners** — Intraday and BM real-time decisions

---

## 10. Progress To Date

| Task | Status |
|---|---|
| Project folder and GitHub repo set up | ✅ Done |
| Python environment confirmed (3.12.4) | ✅ Done |
| Elexon system prices pipeline (`fetch_bmrs.py`) | ✅ Done |
| Market index prices pipeline (`fetch_da_prices.py`) | ✅ Done |
| National Grid ESO / DC tender data pipeline | ⬜ Next |
| Weather data pipeline | ⬜ To do |
| Solar generation data pipeline | ⬜ To do |
| Asset model build | ⬜ To do |
| Optimisation logic | ⬜ To do |
| Streamlit dashboard | ⬜ To do |

---

## 11. Key Principles

- Plan carefully before executing
- Build market and asset logic correctly before adding financial layers
- Do not double-commit asset capacity across markets
- No paid data subscriptions in the short to medium term
- Paste this document at the start of every new Claude session to maintain context

---

## 12. Open Questions / To Decide Later

- Export and import limits per asset
- Battery degradation modelling approach
- Gantt chart / project timeline — to be built once phases are fully scoped
- Cost of investment analysis — Phase 4 onwards

---

*This document is a living reference. Update to Version 5 when new decisions or scope changes are agreed.*
