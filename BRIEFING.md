# Virtual Power Plant (VPP) Project — Master Briefing Document
**Version:** 7.0
**Date:** April 2026
**Status:** In Progress — Dashboard Built, LP Optimisation Next

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

**Education:**
- MSc International Energy Studies & Energy Economics, University of Dundee — Paul Stevens Prize, highest distinction
- Data Analytics Professional Certificate, Imperial College Business School
- Engineer's Degree, Electrical & Electronic, Institute of Technology of Cambodia

**Key skills directly applicable:**
- Long-term fundamental modelling (Plexos), capacity market bidding, grid-scale storage economics
- Statistical modelling, Monte Carlo simulation, machine learning (Python, SQL, R, GAMS)
- Regulatory economics, market design, asset bankability assessment

---

## 3. Asset Portfolio

| Asset | Type | Duration | MW (Battery) | MW (Solar) | Region | DNO |
|---|---|---|---|---|---|---|
| Battery 1 | Standalone | 2-hour | 10 MW | — | North Scotland | SSEN Transmission |
| Battery 2 | Standalone | 4-hour | 25 MW | — | North England | Northern Powergrid |
| Battery 3 | Standalone | 4-hour | 50 MW | — | South England | National Grid (NGET) |
| Battery 4 | Co-located + Solar | 4-hour | 20 MW | 15 MW | South Scotland | SP Transmission |
| Battery 5 | Co-located + Solar | 4-hour | 40 MW | 30 MW | South England | National Grid (NGET) |

**Total battery capacity:** ~145 MW | **Total solar capacity:** 45 MW

**DA Capacity Reservation Rules:**
- Battery 1: 50% reserved
- Battery 2-5: 30% reserved

**Battery operating parameters:** 90% efficiency, 10% SOC floor, 90% SOC ceiling, 50% initial SOC

---

## 4. Target Markets

| Market | Venue | Notes |
|---|---|---|
| Day Ahead (DA) | EPEX / N2EX | Gate closure 12:00 noon day before |
| Intraday (ID) | Continuous | Approximated via DA + BM spread in early phases |
| Balancing Mechanism (BM) | Elexon / NESO | Core market for all assets |
| Ancillary Services | NESO | DC High and DC Low — primary focus |

EFA blocks: EFA1=23-03, EFA2=03-07, EFA3=07-11, EFA4=11-15, EFA5=15-19, EFA6=19-23

---

## 5. Data Sources & Pipelines

| Data | Source | Script | Status |
|---|---|---|---|
| System prices | Elexon BMRS | `fetch_bmrs.py` | ✅ Live |
| Market index prices | Elexon BMRS | `fetch_da_prices.py` | ✅ Live |
| DC forecast | NESO Data Portal | `fetch_dc_tenders.py` | ✅ Live |
| Weather | Open-Meteo | `fetch_weather.py` | ✅ Live |
| Solar generation | Sheffield Solar PV_Live | `fetch_solar.py` | ✅ Live |

**Principle: No paid data subscriptions in the short to medium term.**

---

## 6. Tech Stack

| Component | Tool |
|---|---|
| Core language | Python 3.12.4 |
| Data storage | CSV → SQLite |
| Dashboard | Streamlit |
| Optimisation engine | PuLP |
| AI agents | Claude API |
| Version control | GitHub — github.com/eugenekem/vpp-optimiser |

---

## 7. Optimiser Architecture

| File | Layer | Status |
|---|---|---|
| `battery.py` | Asset model | ✅ Built |
| `optimiser.py` | Rules-based optimiser | ✅ Built |
| `optimiser_da.py` | Forward-looking DA optimiser | ✅ Built |
| `pnl.py` | P&L calculator | ✅ Built |
| `risk.py` | Risk layer | ✅ Built |
| `dashboard.py` | War room dashboard | ✅ Built |
| `optimiser_lp.py` | LP optimisation | ⬜ Next |
| `optimiser_id.py` | Intraday layer | ⬜ To do |
| `optimiser_bm.py` | BM layer | ⬜ To do |
| `dispatcher.py` | Coordinates all layers | ⬜ To do |

**Roadmap:** Rules-based ✅ → DA forward-looking ✅ → LP optimisation ⬜ → Stochastic optimisation ⬜ → AI agents ⬜

---

## 8. LP Formulation (Ready to Build)

**Decision Variables**
- c(t) = charge power in period t (MW)
- d(t) = discharge power in period t (MW)
- s(t) = state of charge in period t (MWh)

**Objective Function**
```
Maximise: Σ [d(t) × p(t) × 0.5 - c(t) × p(t) × 0.5]  for t in T (48 periods)
```

**Constraints**
1. Energy balance: s(t) = s(t-1) + c(t) × η - d(t) / η
2. SOC limits: s_min × E_max ≤ s(t) ≤ s_max × E_max
3. Charge power limit: 0 ≤ c(t) ≤ P_max × (1 - DA_reservation)
4. Discharge power limit: 0 ≤ d(t) ≤ P_max × (1 - DA_reservation)
5. No simultaneous charge and discharge: c(t) × d(t) = 0
6. Solar constraint (co-located): c(t) ≤ solar(t) when charging from solar only
7. Initial SOC: s(0) = 0.50 × E_max

---

## 9. Dashboard Sections

| Section | Status |
|---|---|
| Morning briefing | ✅ Built — green triggered by negative prices |
| Strategy recommendations | ✅ Built — per-asset guidance |
| Portfolio P&L | ✅ Built |
| Price curve | ✅ Built |
| Asset status | ✅ Built |
| Risk summary | ✅ Built |
| DC tender forecast | ✅ Built |
| Dispatch schedule | ✅ Built — colour coded |
| Monthly P&L view | ⬜ To do |
| Telegram alerts | ⬜ To do |

---

## 10. Operating Model

- One day behind real time using published data
- DA gate closure anchor: 12:00 noon day before delivery
- Market sequence: DA → Intraday → BM → DC delivery
- Settlement reconciliation step after each trading day

---

## 11. Development Phases

- **Phase 1** — Historical Replay
- **Phase 2** — Shadow Trading (Priority Phase)
- **Phase 3** — Live Single Asset (Battery 1, BM first)
- **Phase 4** — Scale Up
- **Phase 5** — Residential Solar Aggregation (parked)
- **Phase 6+** — International markets, AI optimisation, full commercial operation

---

## 12. Progress To Date

| Task | Status |
|---|---|
| All 5 data pipelines | ✅ Done |
| Battery asset model | ✅ Done |
| Rules-based optimiser | ✅ Done |
| Forward-looking DA optimiser | ✅ Done |
| P&L calculator | ✅ Done |
| Risk layer | ✅ Done |
| War room dashboard with dispatch schedule | ✅ Done |
| LP optimisation research | ✅ Done |
| LP optimisation build | ⬜ Next |

---

## 13. Key Principles

- Production-grade build, not a learning exercise
- Build modularly — each layer plugs in independently
- Do not double-commit asset capacity across markets
- Risk-adjusted revenue is the target
- Optimisation roadmap: rules-based → LP → stochastic → AI agents
- Pause for academic reading when Claude flags it
- No paid data subscriptions in the short to medium term
- Paste this document at the start of every new Claude session

---

## 14. Open Questions

- Export and import limits per asset
- Battery degradation modelling approach
- Stochastic optimisation research
- Cost of investment analysis — Phase 4 onwards

---

*Update to Version 8 when new decisions or scope changes are agreed.*
