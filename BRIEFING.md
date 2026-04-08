# Virtual Power Plant (VPP) Project — Master Briefing Document
**Version:** 6.0
**Date:** April 2026
**Status:** In Progress — P&L Calculator Next

---

## 1. Project Goal & Ambition

Build a realistic Virtual Power Plant (VPP) simulation model that mirrors real-world asset optimisation operations in the GB energy market. The ultimate goal is to develop the skills, processes, and team workflows needed to operate as a professional VPP optimisation and trading desk.

This is not a quick-build project. It is being developed carefully and deliberately to create genuine operational experience — with ambition to use this platform as a portfolio piece for roles at companies like Statkraft and EDF Renewables, or as the foundation for a startup.

---

## 2. Business Vision

Position as a team of asset optimisers, traders, and risk analysts operating across multiple GB wholesale and balancing markets. The model should replicate the daily experience of a real optimisation desk — with each team function clearly defined and working together.

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

**DA Capacity Reservation Rules:**
- Battery 1: 50% reserved — nimble, prioritise intraday and BM
- Battery 2: 30% reserved — balanced across markets
- Battery 3: 30% reserved — large, commits more in DA
- Battery 4: 30% reserved — co-located with solar
- Battery 5: 30% reserved — co-located with solar

**Asset constraints to define before Phase 1:**
- Export/import limits per asset
- Battery degradation modelling approach

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
- DC High and DC Low
- Daily ESO tenders across 6 EFA blocks (4-hour windows)
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
| Dashboard | Streamlit | To be built — daily, monthly P&L reporting |
| Optimisation engine | PuLP / Google OR-Tools | For LP optimisation layer (after rules-based) |
| Version control | GitHub | Repo: github.com/eugenekem/vpp-optimiser |

---

## 7. Optimiser Architecture

Built in modular layers so each market layer plugs in independently:

| File | Layer | Status |
|---|---|---|
| `battery.py` | Asset model | ✅ Built |
| `optimiser.py` | Rules-based optimiser | ✅ Built |
| `optimiser_da.py` | Forward-looking DA optimiser | ✅ Built |
| `optimiser_id.py` | Intraday layer | ⬜ To do |
| `optimiser_bm.py` | BM layer | ⬜ To do |
| `dispatcher.py` | Coordinates all layers | ⬜ To do |

**DA optimiser logic:**
- Looks at full day price curve upfront
- Identifies top 10 most expensive periods for discharge
- Identifies bottom 10 cheapest periods for charge
- Respects per-asset capacity reservation rules
- Leaves reserved capacity available for intraday and BM layers

---

## 8. Team Structure (Target)

| Role | Responsibility |
|---|---|
| Optimisers | Asset dispatch, charge/discharge scheduling, market stacking |
| Traders | DA and intraday position management, DC tender management |
| Short-term Planners | Intraday and BM real-time decisions |
| **Risk** | **Exposure monitoring, VaR, scenario analysis, price risk** |

**Risk layer rationale:**
- Real VPP operations optimise for risk-adjusted revenue, not just maximum revenue
- Risk team monitors exposure, worst-case P&L, and Value at Risk (VaR)
- Owner has strong statistics and ML background (Imperial College Data Analytics certificate) — directly applicable to VaR modelling, Monte Carlo simulation, and price volatility analysis
- Risk layer will be built after P&L calculator is in place

---

## 9. Operating Model

### Time Approach
The model will operate **one day behind real time** — using published data from the previous day to make decisions as if operating live.

### Key Decision Deadline
**Day Ahead gate closure: 12:00 noon, day before delivery.**

### Market Sequence
DA gate closure (12:00) → Intraday windows → BM flagging & dispatch → DC tender delivery

### Settlement Reconciliation
A reconciliation step after each trading day — comparing planned positions against actual settlement.

---

## 10. Development Phases

### Phase 1 — Historical Replay
- Run model one day behind on real published data
- Measure quality of positions against actuals

### Phase 2 — Shadow Trading (Priority Phase)
- Model runs in real time, no real trades
- Full team workflow simulation

### Phase 3 — Live Single Asset
- Battery 1 — 10MW 2-hour standalone in BM first

### Phase 4 — Scale Up
- Add assets and markets gradually

### Phase 5 — Residential Solar Aggregation (Future Scope)
- ~100 rooftop residential solar systems
- **Parked until Phase 4 is stable**

### Phase 6+ — To Be Defined
- International markets, AI-driven optimisation, full commercial operation

---

## 11. Progress To Date

| Task | Status |
|---|---|
| Project folder and GitHub repo set up | ✅ Done |
| Python environment confirmed (3.12.4) | ✅ Done |
| All 5 data pipelines | ✅ Done |
| Battery asset model | ✅ Done |
| Rules-based optimiser | ✅ Done |
| Forward-looking DA optimiser | ✅ Done |
| P&L calculator | ⬜ Next |
| Risk layer (VaR, scenario analysis) | ⬜ To do |
| Intraday optimiser layer | ⬜ To do |
| BM optimiser layer | ⬜ To do |
| Streamlit dashboard | ⬜ To do |
| Settlement reconciliation logic | ⬜ To do |
| Phase 1 historical replay | ⬜ To do |
| Phase 2 shadow trading | ⬜ To do |

---

## 12. Key Principles

- Plan carefully before executing
- Build market and asset logic correctly before adding financial layers
- Do not double-commit asset capacity across markets
- No paid data subscriptions in the short to medium term
- Academic research will inform optimisation algorithm design — pause and read when Claude flags it
- Risk-adjusted revenue is the target, not just maximum revenue
- Paste this document at the start of every new Claude session to maintain context

---

## 13. Open Questions / To Decide Later

- Export and import limits per asset
- Battery degradation modelling approach
- Gantt chart / project timeline — to be built once phases are fully scoped
- Cost of investment analysis — Phase 4 onwards
- LP optimisation upgrade — after rules-based layer is validated

---

*This document is a living reference. Update to Version 7 when new decisions or scope changes are agreed.*
