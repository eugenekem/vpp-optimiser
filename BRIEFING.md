# Virtual Power Plant (VPP) Project — Master Briefing Document
**Version:** 5.0
**Date:** April 2026
**Status:** In Progress — Data Pipeline Complete, Asset Model Next

---

## 1. Project Goal & Ambition

Build a realistic Virtual Power Plant (VPP) simulation model that mirrors real-world asset optimisation operations in the GB energy market. The ultimate goal is to develop the skills, processes, and team workflows needed to operate as a professional VPP optimisation and trading desk.

This is not a quick-build project. It is being developed carefully and deliberately to create genuine operational experience — with ambition to use this platform as a portfolio piece for roles at companies like Statkraft and EDF Renewables, or as the foundation for a startup.

---

## 2. Business Vision

Position as a team of asset optimisers and energy traders operating across multiple GB wholesale and balancing markets. The model should replicate the daily experience of a real optimisation desk — with traders and optimisers working together across short-term and day-ahead timeframes.

**This project is not initially focused on profit.** The primary objective is to master daily net arbitrage across markets before layering in cost of investment and financial performance analysis.

The platform will be smart, polished, and credible — grounded in real GB market data, real asset constraints, and real market structure.

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
- Solar yield in South England will be materially higher than Scotland

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
- Daily ESO tenders across 6 EFA blocks (4-hour windows)
- All 5 assets are credible DC participants given MW sizes
- EFA blocks: EFA1=23-03, EFA2=03-07, EFA3=07-11, EFA4=11-15, EFA5=15-19, EFA6=19-23

---

## 5. Data Sources & Pipelines

All pipelines built and working. Data saved to `/data` folder and pushed to GitHub.

| Data | Source | Script | Status |
|---|---|---|---|
| System prices (SSP/SBP) | Elexon BMRS | `fetch_bmrs.py` | ✅ Live |
| Market index prices (MID) | Elexon BMRS | `fetch_da_prices.py` | ✅ Live |
| DC forecast (4-day) | NESO Data Portal | `fetch_dc_tenders.py` | ✅ Live |
| Weather (temp, wind, solar radiation) | Open-Meteo | `fetch_weather.py` | ✅ Live |
| Solar generation (GB national) | Sheffield Solar PV_Live | `fetch_solar.py` | ✅ Live |

**Known Gap (Managed):**
- Real-time intraday continuous prices not freely available
- Workaround: Approximate intraday using DA prices plus BM system price spread

**Principle: No paid data subscriptions in the short to medium term.**

---

## 6. Tech Stack

| Component | Tool | Notes |
|---|---|---|
| Core language | Python 3.12.4 | Confirmed version |
| Data storage | CSV → SQLite | Currently CSV, upgrade to SQLite when needed |
| Dashboard | Streamlit | To be built in later phase |
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
- **This is where the team starts making live decisions without financial risk**

### Phase 3 — Live Single Asset
- Trade one asset live in one market (Battery 1 — 10MW 2-hour standalone in BM)
- Remaining assets remain in shadow mode

### Phase 4 — Scale Up
- Add assets and markets gradually
- Only expand when previous layer is stable

### Phase 5 — Residential Solar Aggregation (Future Scope)
- ~100 rooftop residential solar systems as aggregator
- **Parked until Phase 4 is stable**

### Phase 6+ — To Be Defined
- Project ambition extends well beyond Phase 5
- Future phases may include international markets, AI-driven optimisation, and full commercial operation

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
| Elexon system prices pipeline | ✅ Done |
| Market index prices pipeline | ✅ Done |
| DC forecast pipeline | ✅ Done |
| Weather data pipeline | ✅ Done |
| Solar generation pipeline | ✅ Done |
| Asset model build | ⬜ Next |
| Optimisation logic | ⬜ To do |
| Streamlit dashboard | ⬜ To do |
| Settlement reconciliation logic | ⬜ To do |
| Phase 1 historical replay | ⬜ To do |
| Phase 2 shadow trading | ⬜ To do |

---

## 11. Key Principles

- Plan carefully before executing
- Build market and asset logic correctly before adding financial layers
- Do not double-commit asset capacity across markets
- No paid data subscriptions in the short to medium term
- Academic research will inform optimisation algorithm design — pause and read when Claude flags it
- Paste this document at the start of every new Claude session to maintain context

---

## 12. Open Questions / To Decide Later

- Export and import limits per asset
- Battery degradation modelling approach
- Gantt chart / project timeline — to be built once phases are fully scoped
- Cost of investment analysis — Phase 4 onwards

---

*This document is a living reference. Update to Version 6 when new decisions or scope changes are agreed.*
