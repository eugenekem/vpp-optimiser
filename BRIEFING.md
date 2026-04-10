# Virtual Power Plant (VPP) Project — Master Briefing Document
**Version:** 7.0
**Date:** April 2026
**Status:** In Progress — Dashboard Built, Dispatch Schedule Next

---

## 1. Project Goal & Ambition

Build a production-grade Virtual Power Plant (VPP) optimisation platform grounded in real GB market data, real asset constraints, and real market structure. The platform will demonstrate professional-level capability in battery asset optimisation, multi-market stacking, risk management, and operational decision-making.

This is not a learning exercise. It is a commercial platform build — with ambition to underpin a consultancy, startup, or to position for senior roles at companies like Statkraft, Habitat Energy, Limejump, or EDF Renewables.

---

## 2. Owner Profile

**Eugene Sovathana Kem** — Glasgow, UK

**Current role:** GB Electricity Market Analyst, SSE Plc (Oct 2022 - Present)
- Leads end-to-end development of Plexos power market model for day-ahead forecasting
- Drives SSE's Net Zero investment strategy through long-term revenue forecasts
- Reduced capacity market simulation run times by 95% migrating Excel/VBA to Python
- Facilitates multi-billion pound investment decisions through quantitative analysis
- Performs annual DCF analysis including NPV and LCOE across technology types
- Presents complex model outputs to senior stakeholders across business units

**Previous experience:**
- Lead Analyst, The Lantau Group (Hong Kong) — supply/demand modelling across Southeast Asia
- Analyst, The Lantau Group — renewable project due diligence and long-term price forecasting
- Electrical Engineer, Kamworks Solar (Cambodia) — solar project design and delivery

**Education:**
- MSc International Energy Studies & Energy Economics, University of Dundee — **Paul Stevens Prize winner, highest distinction**
- Data Analytics Professional Certificate, Imperial College Business School
- Engineer's Degree, Electrical & Electronic, Institute of Technology of Cambodia

**Key skills directly applicable to this project:**
- Long-term fundamental modelling (Plexos), capacity market bidding, grid-scale storage economics
- Statistical modelling, Monte Carlo simulation, machine learning (Python, SQL, R, GAMS)
- Regulatory economics, market design, asset bankability assessment
- DCF analysis, NPV, LCOE, real option valuation

**What this project adds to the profile:**
- Real-time battery dispatch optimisation (rules-based → LP → stochastic)
- Multi-market stacking (DA, intraday, BM, ancillary services)
- Production-grade platform development (Python, Streamlit, SQLite, GitHub)
- AI agent integration for autonomous optimisation

---

## 3. Business Vision

A full trading operations platform — a war room where the operator sits as head of optimisation, sees all assets live, manages positions across markets, reviews P&L and risk, and makes decisions alongside an AI optimiser.

**Longer term:** This platform could underpin:
- An independent VPP optimisation consultancy
- A startup offering optimisation-as-a-service to battery asset owners
- A demonstrable portfolio piece for senior roles at Statkraft, EDF, Habitat Energy, Limejump

**The platform will be:**
- Production-grade — not a demo, a real operational system
- Commercially credible — real GB market data, real asset economics, real risk management
- Intellectually rigorous — grounded in academic research and professional market knowledge
- AI-augmented — agents that observe, decide, and act alongside the human operator

---

## 4. Asset Portfolio

| Asset | Type | Duration | MW (Battery) | MW (Solar) | Region | DNO |
|---|---|---|---|---|---|---|
| Battery 1 | Standalone | 2-hour | 10 MW | — | North Scotland | SSEN Transmission |
| Battery 2 | Standalone | 4-hour | 25 MW | — | North England | Northern Powergrid |
| Battery 3 | Standalone | 4-hour | 50 MW | — | South England | National Grid (NGET) |
| Battery 4 | Co-located + Solar | 4-hour | 20 MW | 15 MW | South Scotland | SP Transmission |
| Battery 5 | Co-located + Solar | 4-hour | 40 MW | 30 MW | South England | National Grid (NGET) |

**Total battery capacity:** ~145 MW | **Total solar capacity:** 45 MW

**DA Capacity Reservation Rules:**
- Battery 1: 50% reserved — nimble, prioritise intraday and BM
- Battery 2-5: 30% reserved — balanced across markets

---

## 5. Target Markets

| Market | Venue | Notes |
|---|---|---|
| Day Ahead (DA) | EPEX / N2EX | Gate closure 12:00 noon day before |
| Intraday (ID) | Continuous | Approximated via DA + BM spread in early phases |
| Balancing Mechanism (BM) | Elexon / NESO | Core market for all assets |
| Ancillary Services | NESO | DC High and DC Low — primary focus |

**EFA blocks:** EFA1=23-03, EFA2=03-07, EFA3=07-11, EFA4=11-15, EFA5=15-19, EFA6=19-23

---

## 6. Data Sources & Pipelines

| Data | Source | Script | Status |
|---|---|---|---|
| System prices (SSP/SBP) | Elexon BMRS | `fetch_bmrs.py` | ✅ Live |
| Market index prices (MID) | Elexon BMRS | `fetch_da_prices.py` | ✅ Live |
| DC forecast (4-day) | NESO Data Portal | `fetch_dc_tenders.py` | ✅ Live |
| Weather | Open-Meteo | `fetch_weather.py` | ✅ Live |
| Solar generation | Sheffield Solar PV_Live | `fetch_solar.py` | ✅ Live |

**Known Gap (Managed):**
- Real-time intraday continuous prices not freely available
- Workaround: Approximate intraday using DA prices plus BM system price spread

**Principle: No paid data subscriptions in the short to medium term.**

---

## 7. Tech Stack

| Component | Tool | Notes |
|---|---|---|
| Core language | Python 3.12.4 | Confirmed |
| Data storage | CSV → SQLite | Currently CSV, upgrade to SQLite when needed |
| Dashboard | Streamlit | War room operations platform — live |
| Optimisation engine | PuLP / Google OR-Tools | LP layer planned after rules-based validated |
| Stochastic optimisation | To be researched | Monte Carlo + price uncertainty modelling |
| AI agents | Claude API | Autonomous optimisation and decision support |
| Version control | GitHub | github.com/eugenekem/vpp-optimiser |

---

## 8. Optimiser Architecture

| File | Layer | Status |
|---|---|---|
| `battery.py` | Asset model | ✅ Built |
| `optimiser.py` | Rules-based optimiser | ✅ Built |
| `optimiser_da.py` | Forward-looking DA optimiser | ✅ Built |
| `pnl.py` | P&L calculator | ✅ Built |
| `risk.py` | Risk layer (VaR, scenarios, concentration) | ✅ Built |
| `dashboard.py` | War room Streamlit dashboard | ✅ Built |
| `optimiser_id.py` | Intraday layer | ⬜ To do |
| `optimiser_bm.py` | BM layer | ⬜ To do |
| `dispatcher.py` | Coordinates all layers | ⬜ To do |

**Optimisation roadmap:**
1. Rules-based (done) → 2. Forward-looking DA (done) → 3. LP optimisation → 4. Stochastic optimisation under price uncertainty → 5. AI agent layer

---

## 9. Dashboard Sections

| Section | Status | Notes |
|---|---|---|
| Morning briefing (market signal) | ✅ Built | Green/amber/red signal with price metrics |
| Strategy recommendations | ✅ Built | Per-asset actionable guidance |
| Portfolio P&L | ✅ Built | Revenue, cost, net per asset |
| Price curve | ✅ Built | 48-period settlement price chart |
| Asset status | ✅ Built | SOC, MW, solar per asset |
| Risk summary | ✅ Built | Sharpe, VaR, volatility, concentration |
| DC tender forecast | ✅ Built | 4-day forward NESO data |
| Dispatch schedule | ⬜ Next | Period-by-period per asset view |
| Monthly P&L view | ⬜ To do | Aggregate performance over time |
| Telegram alerts | ⬜ To do | Real-time notifications to team |

---

## 10. Team Structure (Target)

| Role | Responsibility |
|---|---|
| Optimisers | Asset dispatch, charge/discharge scheduling, market stacking |
| Traders | DA and intraday position management, DC tender management |
| Short-term Planners | Intraday and BM real-time decisions |
| Risk | Exposure monitoring, VaR, scenario analysis, price risk |
| AI Agents | Autonomous monitoring, decision support, alert generation |

---

## 11. Operating Model

- One day behind real time using published data
- DA gate closure anchor: 12:00 noon day before delivery
- Market sequence: DA → Intraday → BM → DC delivery
- Settlement reconciliation step after each trading day

---

## 12. Development Phases

- **Phase 1** — Historical Replay
- **Phase 2** — Shadow Trading (Priority Phase)
- **Phase 3** — Live Single Asset (Battery 1, BM first)
- **Phase 4** — Scale Up
- **Phase 5** — Residential Solar Aggregation (parked)
- **Phase 6+** — International markets, AI optimisation, full commercial operation, consultancy/startup

---

## 13. Progress To Date

| Task | Status |
|---|---|
| Project folder and GitHub repo | ✅ Done |
| Python environment (3.12.4) | ✅ Done |
| All 5 data pipelines | ✅ Done |
| Battery asset model | ✅ Done |
| Rules-based optimiser | ✅ Done |
| Forward-looking DA optimiser | ✅ Done |
| P&L calculator | ✅ Done |
| Risk layer | ✅ Done |
| War room dashboard (v1) | ✅ Done |
| Dispatch schedule view | ⬜ Next |
| Intraday optimiser layer | ⬜ To do |
| BM optimiser layer | ⬜ To do |
| LP optimisation upgrade | ⬜ To do |
| Stochastic optimisation | ⬜ To do |
| AI agent layer | ⬜ To do |
| Monthly P&L reporting | ⬜ To do |
| Telegram alerts | ⬜ To do |
| Settlement reconciliation | ⬜ To do |
| Phase 1 historical replay | ⬜ To do |
| Phase 2 shadow trading | ⬜ To do |

---

## 14. Key Principles

- This is a production-grade build, not a learning exercise
- Build modularly — each layer plugs in independently
- Do not double-commit asset capacity across markets
- Risk-adjusted revenue is the target, not just maximum revenue
- Optimisation roadmap: rules-based → LP → stochastic → AI agents
- Academic research will inform optimisation design — pause and read when Claude flags it
- No paid data subscriptions in the short to medium term
- Paste this document at the start of every new Claude session

---

## 15. Open Questions / To Decide Later

- Export and import limits per asset
- Battery degradation modelling approach
- Stochastic optimisation research — flag when ready to pause and study
- Cost of investment analysis — Phase 4 onwards
- Consultancy/startup structure — Phase 6+

---

*Update to Version 8 when new decisions or scope changes are agreed.*
