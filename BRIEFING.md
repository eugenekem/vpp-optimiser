# VPP Optimiser — Project Briefing
**Version:** 13.0
**Status:** Phase 1 historical replay complete — 30 days validated, Phase 2 shadow trading next

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

**Battery operating parameters:** 90% round-trip efficiency, 10% SOC floor, 90% SOC ceiling, 50% initial SOC.

---

## 3. Capacity Reservation Splits (config.py)

Three-way split across DA, ID, and BM. Defined centrally in `models/config.py` — single source of truth, all optimisers import from here.

| Asset | DA | ID | BM |
|---|---|---|---|
| Battery 1 | 40% | 30% | 30% |
| Battery 2-5 | 50% | 20% | 30% |

---

## 4. Target Markets

| Market | Venue | Notes |
|---|---|---|
| Day Ahead (DA) | EPEX / N2EX | Gate closure 12:00 noon day before |
| Intraday (ID) | Simulated | DA price + Normal(0, £5) spread — real continuous prices not freely available |
| Balancing Mechanism (BM) | Elexon / NESO | Real SSP/SBP prices from BMRS |
| Ancillary Services | NESO | DC High and DC Low — primary focus, not yet integrated into dispatch |

**EFA blocks:** EFA1=23-03, EFA2=03-07, EFA3=07-11, EFA4=11-15, EFA5=15-19, EFA6=19-23

---

## 5. Data Sources

All pipelines operational, data saved to `/data`, pushed to GitHub.

| Data | Source | Script | Notes |
|---|---|---|---|
| System prices (SSP/SBP) | Elexon BMRS | `fetch_bmrs.py` | Accepts optional date arg |
| Market index prices (MID) | Elexon BMRS | `fetch_da_prices.py` | Accepts optional date arg |
| DC forecast (4-day) | NESO Data Portal | `fetch_dc_tenders.py` | |
| Weather | Open-Meteo | `fetch_weather.py` | |
| Solar generation | Sheffield Solar PV_Live | `fetch_solar.py` | |

**Known gap:** Real-time intraday continuous prices not freely available. Workaround: simulate ID price as DA price + Normal(0, £5) spread.

**Design principle:** No paid data subscriptions in the short to medium term.

---

## 6. Tech Stack

| Component | Tool |
|---|---|
| Core language | Python 3.12.4 |
| Data storage | CSV → SQLite planned |
| Dashboard | Streamlit |
| Optimisation | PuLP with CBC solver |
| Version control | GitHub |

---

## 7. Optimiser Architecture

| File | Layer | Status |
|---|---|---|
| `battery.py` | Asset model | ✅ Built |
| `optimiser.py` | Rules-based optimiser | ✅ Built |
| `optimiser_da.py` | Forward-looking DA optimiser | ✅ Built |
| `optimiser_lp.py` | LP optimiser (DA layer) | ✅ Built |
| `optimiser_id.py` | Intraday layer | ✅ Built |
| `optimiser_bm.py` | BM layer | ✅ Built |
| `config.py` | Shared capacity split config | ✅ Built |
| `dispatcher.py` | Sequential DA→ID→BM orchestrator with SOC handoff | ✅ Built |
| `compare_optimisers.py` | Benchmark harness | ✅ Built |
| `pnl.py` | P&L calculator | ✅ Built |
| `risk.py` | Risk layer | ✅ Built |
| `dashboard.py` | Operations dashboard — full DA+ID+BM | ✅ Built |
| `replay.py` | Phase 1 historical replay | ✅ Built |
| `shadow.py` | Phase 2 shadow trading | ⬜ Next |

**Optimisation roadmap:**
1. ✅ Rules-based
2. ✅ Forward-looking DA
3. ✅ LP optimisation
4. ✅ Intraday layer (simulated prices)
5. ✅ BM layer (real SSP/SBP)
6. ✅ Sequential SOC handoff across DA→ID→BM
7. ⬜ Stochastic optimisation under price uncertainty
8. ⬜ AI agent layer

---

## 8. LP Formulation

**Decision variables** (per layer — DA, ID, BM each solve their own LP using the same structure)
- c(t) = charge power in period t (MW)
- d(t) = discharge power in period t (MW)
- s(t) = state of charge in period t (MWh)

**Objective function**
```
Maximise: Σ [d(t) × p(t) × 0.5 - c(t) × p(t) × 0.5] for t in T (48 periods)
```
DA/ID use market price; BM uses SSP for discharge revenue and SBP for charge cost.

**Constraints**
1. Energy balance: s(t) = s(t-1) + c(t) × 0.5 × η - d(t) × 0.5 / η
2. SOC limits: s_min × E_max ≤ s(t) ≤ s_max × E_max
3. Charge/discharge power: 0 ≤ c(t), d(t) ≤ P_max × layer_capacity_fraction
4. Initial SOC: handed off sequentially — DA starts at 50%, ID starts where DA ended, BM starts where ID ended

**Critical fix (v11):** Sequential SOC handoff fixed independent-layer over-commitment bug. Mirrors real market timing.

**Validation (2026-06-15):** Portfolio revenue £129,120, cost £82,852, net P&L £46,268. All assets within 10-90% SOC bounds.

---

## 9. Dashboard

| Section | Status |
|---|---|
| Morning briefing (market signal) | ✅ Built |
| Strategy recommendations | ✅ Built |
| Portfolio P&L — DA+ID+BM combined | ✅ Built |
| P&L by asset | ✅ Built |
| P&L by market (DA / ID / BM breakdown) | ✅ Built |
| Net P&L contribution by market bar chart | ✅ Built |
| Price curve | ✅ Built |
| Asset status | ✅ Built |
| Risk summary (Sharpe, VaR, volatility, concentration) | ✅ Built |
| DC tender forecast | ✅ Built |
| Dispatch schedule — nested tabs (asset → DA/ID/BM) | ✅ Built |
| SOC curve per layer | ✅ Built |
| Price curve per layer (separate axis) | ✅ Built |
| Charge/discharge MW bar chart per layer (separate axis) | ✅ Built |
| Monthly P&L view | ⬜ To do |
| Telegram alerts | ⬜ To do |

---

## 10. Phase 1 Historical Replay Results

**Script:** `models/replay.py`
**Output:** `data/replay_pnl.csv`

| Metric | Value |
|---|---|
| Period | 30 days (2026-05-24 to 2026-06-22) |
| Days completed | 30 / 30 |
| Days skipped | 0 |
| Total net P&L | £1,895,106 |
| Daily average | £63,170 |
| Best day | £133,604 (2026-06-07) |
| Worst day | £33,105 (2026-05-30) |
| Positive days | 30 / 30 |
| DA contribution | £1,117,359 (59%) |
| ID contribution | £212,360 (11%) |
| BM contribution | £565,386 (30%) |

**Key finding:** All 30 days profitable. DA dominates contribution as expected given largest committed slice. BM meaningful at 30%. ID smallest due to simulated prices close to DA limiting additional uplift.

---

## 11. Operating Model

- One day behind real time using published data
- DA gate closure anchor: 12:00 noon day before delivery
- Market sequence: DA → Intraday → BM → DC delivery
- SOC handoff sequence matches market sequence — DA→ID→BM
- Settlement reconciliation step after each trading day (not yet built)

---

## 12. Development Phases

- **Phase 1** — Historical replay on real published data ✅ Complete
- **Phase 2** — Shadow trading (real-time decisions, no real trades) ⬜ Next
- **Phase 3** — Live single asset operation
- **Phase 4** — Scale to full portfolio
- **Phase 5** — Residential solar aggregation (future scope, parked)

---

## 13. Progress

| Task | Status |
|---|---|
| Project structure and GitHub repo | ✅ Done |
| All 5 data pipelines | ✅ Done |
| Battery asset model | ✅ Done |
| Rules-based optimiser | ✅ Done |
| Forward-looking DA optimiser | ✅ Done |
| LP optimiser (DA layer) | ✅ Done |
| Intraday optimiser layer | ✅ Done |
| BM optimiser layer | ✅ Done |
| config.py — shared capacity splits | ✅ Done |
| Sequential SOC handoff (dispatcher.py) | ✅ Done |
| P&L calculator | ✅ Done |
| Risk layer | ✅ Done |
| Operations dashboard — full DA+ID+BM | ✅ Done |
| update_briefing.py — fixed overwrite bug | ✅ Done |
| Phase 1 historical replay (replay.py) | ✅ Done |
| Phase 2 shadow trading (shadow.py) | ⬜ Next |
| Stochastic optimisation | ⬜ To do |
| AI agent layer | ⬜ To do |
| Settlement reconciliation | ⬜ To do |
| Monthly P&L dashboard view | ⬜ To do |

---

## 14. Engineering Principles

- Modular architecture — each layer plugs in independently
- No double-commitment of asset capacity across markets
- Risk-adjusted return is the target metric, not just maximum revenue
- Free-tier data only in the short to medium term
- Validate each layer against baselines before moving on
- Pause for academic reading before major new optimisation techniques
- Shared physical constraints (like SOC) must be modelled jointly or sequentially
- Keep BRIEFING.md accurate after every session — it is the single source of truth

---

## 15. Code Quality Roadmap

Scheduled after stochastic optimisation and AI agent layer are functionally complete:

1. Type hints on all public functions
2. Google-style docstrings on all classes and functions
3. Unit tests (pytest) covering battery logic, P&L, risk metrics, optimiser outputs, and SOC handoff correctness
4. Proper package structure with `__init__.py`
5. Input validation with clear error messages
6. Python `logging` module replacing `print` statements

---

## 16. Open Research Questions

- Stochastic optimisation — price uncertainty modelling approaches
- Battery degradation cost integration into LP objective
- Intraday continuous price approximation — currently simulated, real data unavailable free
- BM bid/offer strategy under imbalance exposure
- Export/import limits per asset connection point
- Whether DA/ID/BM should eventually be jointly optimised in one LP rather than sequentially

---

## 17. Known Issues / Lessons Learned

- **v6 → v11 documentation gap:** `update_briefing.py` previously hardcoded stale v6.0 content and silently overwrote BRIEFING.md. Fixed in v11 — script now only logs sessions and pushes whatever is on disk.
- **Dispatch chart scale mismatch:** MW and price on same axis made MW lines invisible. Fixed in v12 by splitting into separate charts.
- **SOC over-commitment bug:** Independent optimisation of DA/ID/BM against shared SOC caused impossible SOC values. Fixed in v11 by sequential SOC handoff.
- **Fetch scripts date-locked:** `fetch_da_prices.py` and `fetch_bmrs.py` originally hardcoded "yesterday". Fixed in v13 to accept optional date argument, enabling historical replay to fetch any date.

---

*Update to the next version when major decisions or scope changes are agreed.*
