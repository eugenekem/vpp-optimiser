# VPP Optimiser — Project Briefing
**Version:** 8.0
**Status:** In Progress — LP optimiser validated, dashboard integration next

---

## 1. Project Overview

A Virtual Power Plant optimisation platform for the GB energy market. Models battery dispatch across day-ahead, intraday, balancing mechanism, and ancillary service markets using real published market data from Elexon, NESO, Open-Meteo, and Sheffield Solar.

The project develops in phases — historical replay first, then shadow trading, then live operation. Each phase validates the previous layer before scaling.

---

## 2. Asset Portfolio

| Asset | Type | Duration | Battery (MW) | Solar (MW) | Region | DNO |
|---|---|---|---|---|---|---|
| Battery 1 | Standalone | 2-hour | 10 | — | North Scotland | SSEN Transmission |
| Battery 2 | Standalone | 4-hour | 25 | — | North England | Northern Powergrid |
| Battery 3 | Standalone | 4-hour | 50 | — | South England | National Grid (NGET) |
| Battery 4 | Co-located | 4-hour | 20 | 15 | South Scotland | SP Transmission |
| Battery 5 | Co-located | 4-hour | 40 | 30 | South England | National Grid (NGET) |

**Total capacity:** ~145 MW battery, 45 MW solar

**DA capacity reservation rules:**
- Battery 1: 50% reserved for intraday and BM
- Battery 2-5: 30% reserved for intraday and BM

**Battery operating parameters:** 90% round-trip efficiency, 10% SOC floor, 90% SOC ceiling, 50% initial SOC.

---

## 3. Target Markets

| Market | Venue | Notes |
|---|---|---|
| Day Ahead (DA) | EPEX / N2EX | Gate closure 12:00 noon day before |
| Intraday (ID) | Continuous | Approximated via DA + BM spread in early phases |
| Balancing Mechanism (BM) | Elexon / NESO | Core market for all assets |
| Ancillary Services | NESO | DC High and DC Low — primary focus |

**EFA blocks:** EFA1=23-03, EFA2=03-07, EFA3=07-11, EFA4=11-15, EFA5=15-19, EFA6=19-23

---

## 4. Data Sources

All pipelines operational, data saved to `/data`, pushed to GitHub.

| Data | Source | Script |
|---|---|---|
| System prices (SSP/SBP) | Elexon BMRS | `fetch_bmrs.py` |
| Market index prices (MID) | Elexon BMRS | `fetch_da_prices.py` |
| DC forecast (4-day) | NESO Data Portal | `fetch_dc_tenders.py` |
| Weather | Open-Meteo | `fetch_weather.py` |
| Solar generation | Sheffield Solar PV_Live | `fetch_solar.py` |

**Known gap:** Real-time intraday continuous prices not freely available. Workaround: approximate intraday using DA + BM spread.

**Design principle:** No paid data subscriptions in the short to medium term.

---

## 5. Tech Stack

| Component | Tool |
|---|---|
| Core language | Python 3.12.4 |
| Data storage | CSV → SQLite planned |
| Dashboard | Streamlit |
| Optimisation | PuLP with CBC solver |
| Version control | GitHub |

---

## 6. Optimiser Architecture

| File | Layer | Status |
|---|---|---|
| `battery.py` | Asset model | ✅ Built |
| `optimiser.py` | Rules-based optimiser | ✅ Built |
| `optimiser_da.py` | Forward-looking DA optimiser | ✅ Built |
| `optimiser_lp.py` | LP optimiser | ✅ Built |
| `compare_optimisers.py` | Benchmark harness | ✅ Built |
| `pnl.py` | P&L calculator | ✅ Built |
| `risk.py` | Risk layer | ✅ Built |
| `dashboard.py` | Operations dashboard | ✅ Built |
| `optimiser_id.py` | Intraday layer | ⬜ To do |
| `optimiser_bm.py` | BM layer | ⬜ To do |
| `dispatcher.py` | Coordinates all layers | ⬜ To do |

**Optimisation roadmap:**
1. ✅ Rules-based
2. ✅ Forward-looking DA
3. ✅ LP optimisation
4. ⬜ Stochastic optimisation under price uncertainty
5. ⬜ AI agent layer

---

## 7. LP Formulation

**Decision variables**
- c(t) = charge power in period t (MW)
- d(t) = discharge power in period t (MW)
- s(t) = state of charge in period t (MWh)

**Objective function**
```
Maximise: Σ [d(t) × p(t) × 0.5 - c(t) × p(t) × 0.5] for t in T (48 periods)
```

**Constraints**
1. Energy balance: s(t) = s(t-1) + c(t) × 0.5 × η - d(t) × 0.5 / η
2. SOC limits: s_min × E_max ≤ s(t) ≤ s_max × E_max
3. Charge power: 0 ≤ c(t) ≤ P_max × (1 - DA_reservation)
4. Discharge power: 0 ≤ d(t) ≤ P_max × (1 - DA_reservation)
5. Initial SOC: s(0) = 0.50 × E_max

**Validation:** LP outperformed rules-based by 12.2% and forward-looking DA by 24.1% on the same day's prices under identical capacity constraints. Benchmark documented in `compare_optimisers.py`.

---

## 8. Dashboard

| Section | Status |
|---|---|
| Morning briefing (market signal) | ✅ Built |
| Strategy recommendations | ✅ Built |
| Portfolio P&L | ✅ Built |
| Price curve | ✅ Built |
| Asset status | ✅ Built |
| Risk summary | ✅ Built |
| DC tender forecast | ✅ Built |
| Dispatch schedule | ✅ Built |
| Monthly P&L view | ⬜ To do |
| Telegram alerts | ⬜ To do |

---

## 9. Operating Model

- One day behind real time using published data
- DA gate closure anchor: 12:00 noon day before delivery
- Market sequence: DA → Intraday → BM → DC delivery
- Settlement reconciliation step after each trading day

---

## 10. Development Phases

- **Phase 1** — Historical replay on real published data
- **Phase 2** — Shadow trading (real-time decisions, no real trades)
- **Phase 3** — Live single asset operation
- **Phase 4** — Scale to full portfolio
- **Phase 5** — Residential solar aggregation (future scope, parked)

---

## 11. Progress

| Task | Status |
|---|---|
| Project structure and GitHub repo | ✅ Done |
| All 5 data pipelines | ✅ Done |
| Battery asset model | ✅ Done |
| Rules-based optimiser | ✅ Done |
| Forward-looking DA optimiser | ✅ Done |
| LP optimiser (with validated uplift) | ✅ Done |
| P&L calculator | ✅ Done |
| Risk layer | ✅ Done |
| Operations dashboard | ✅ Done |
| Dashboard LP integration | ⬜ Next |
| Intraday optimiser layer | ⬜ To do |
| BM optimiser layer | ⬜ To do |
| Stochastic optimisation | ⬜ To do |
| AI agent layer | ⬜ To do |
| Settlement reconciliation | ⬜ To do |
| Phase 1 historical replay | ⬜ To do |
| Phase 2 shadow trading | ⬜ To do |

---

## 12. Engineering Principles

- Modular architecture — each layer plugs in independently
- No double-commitment of asset capacity across markets
- Risk-adjusted return is the target metric, not just maximum revenue
- Free-tier data only in the short to medium term
- Validate each layer against baselines before moving on
- Pause for academic reading before major new optimisation techniques

---

## 13. Code Quality Roadmap

Scheduled after LP optimiser, intraday layer, and BM layer are functionally complete:

1. Type hints on all public functions
2. Google-style docstrings on all classes and functions
3. Unit tests (pytest) covering battery logic, P&L, risk metrics, optimiser outputs
4. Proper package structure with `__init__.py`
5. Input validation with clear error messages
6. Python `logging` module replacing `print` statements

---

## 14. Open Research Questions

- Stochastic optimisation — price uncertainty modelling approaches
- Battery degradation cost integration into LP objective
- Intraday continuous price approximation methodology
- BM bid/offer strategy under imbalance exposure
- Export/import limits per asset connection point

---

*Update to the next version when major decisions or scope changes are agreed.*
