# VPP Optimiser — Project Briefing
**Version:** 11.0
**Status:** In Progress — DA/ID/BM layers integrated with sequential SOC handoff, dashboard next

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

| Data | Source | Script |
|---|---|---|
| System prices (SSP/SBP) | Elexon BMRS | `fetch_bmrs.py` |
| Market index prices (MID) | Elexon BMRS | `fetch_da_prices.py` |
| DC forecast (4-day) | NESO Data Portal | `fetch_dc_tenders.py` |
| Weather | Open-Meteo | `fetch_weather.py` |
| Solar generation | Sheffield Solar PV_Live | `fetch_solar.py` |

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
| `dashboard.py` | Operations dashboard | ✅ Built (LP-integrated, ID/BM not yet wired in) |

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

**Critical fix (v11):** Each layer previously assumed an independent 50% starting SOC and its own private capacity slice. When combined, this caused SOC to go negative and above 100% — a physically impossible result. Fixed by chaining the three optimisers sequentially, each handing its final SOC to the next layer as its starting point. This mirrors real market timing (DA commits first, ID adjusts, BM responds last).

**Validation (2026-06-15):** Portfolio revenue £129,120, cost £82,852, net P&L £46,268. All assets stayed within 10-90% SOC bounds across the full combined dispatch — no breaches.

---

## 9. Dashboard

| Section | Status |
|---|---|
| Morning briefing (market signal) | ✅ Built |
| Strategy recommendations | ✅ Built |
| Portfolio P&L | ✅ Built (LP only — ID/BM not yet wired in) |
| Price curve | ✅ Built |
| Asset status | ✅ Built |
| Risk summary | ✅ Built |
| DC tender forecast | ✅ Built |
| Dispatch schedule | ✅ Built (LP only) |
| SOC curve chart | ✅ Built |
| Dispatch vs price overlay chart | ✅ Built |
| LP vs DA comparison chart | ✅ Built |
| Combined DA+ID+BM dashboard view | ⬜ Next |
| Monthly P&L view | ⬜ To do |
| Telegram alerts | ⬜ To do |

---

## 10. Operating Model

- One day behind real time using published data
- DA gate closure anchor: 12:00 noon day before delivery
- Market sequence: DA → Intraday → BM → DC delivery
- SOC handoff sequence matches market sequence — DA→ID→BM
- Settlement reconciliation step after each trading day (not yet built)

---

## 11. Development Phases

- **Phase 1** — Historical replay on real published data
- **Phase 2** — Shadow trading (real-time decisions, no real trades)
- **Phase 3** — Live single asset operation
- **Phase 4** — Scale to full portfolio
- **Phase 5** — Residential solar aggregation (future scope, parked)

---

## 12. Progress

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
| Operations dashboard (LP-integrated) | ✅ Done |
| Dashboard ID/BM integration | ⬜ Next |
| Stochastic optimisation | ⬜ To do |
| AI agent layer | ⬜ To do |
| Settlement reconciliation | ⬜ To do |
| Phase 1 historical replay | ⬜ To do |
| Phase 2 shadow trading | ⬜ To do |

---

## 13. Engineering Principles

- Modular architecture — each layer plugs in independently
- No double-commitment of asset capacity across markets
- Risk-adjusted return is the target metric, not just maximum revenue
- Free-tier data only in the short to medium term
- Validate each layer against baselines before moving on
- Pause for academic reading before major new optimisation techniques
- Shared physical constraints (like SOC) must be modelled jointly or sequentially — never assume independent layers can be safely summed post-hoc

---

## 14. Code Quality Roadmap

Scheduled after stochastic optimisation and AI agent layer are functionally complete:

1. Type hints on all public functions
2. Google-style docstrings on all classes and functions
3. Unit tests (pytest) covering battery logic, P&L, risk metrics, optimiser outputs, and SOC handoff correctness
4. Proper package structure with `__init__.py`
5. Input validation with clear error messages
6. Python `logging` module replacing `print` statements

---

## 15. Open Research Questions

- Stochastic optimisation — price uncertainty modelling approaches
- Battery degradation cost integration into LP objective
- Intraday continuous price approximation methodology — currently simulated, real data still unavailable free
- BM bid/offer strategy under imbalance exposure
- Export/import limits per asset connection point
- Whether DA/ID/BM should eventually be jointly optimised in one LP rather than sequentially — sequential is simpler and matches real market timing, but may leave value on the table compared to a fully joint solve

---

## 16. Known Issues / Lessons Learned

- **v6 → v11 documentation gap:** `update_briefing.py` previously hardcoded stale v6.0 content and silently overwrote BRIEFING.md on every run, while still committing successfully. Git history showed clean v7-v11 commits, but the actual file content never advanced past v6 until this manual restoration. Script has been fixed (v11) to never write BRIEFING.md content — it now only logs sessions and pushes whatever is on disk. BRIEFING.md must be edited directly going forward.

---

*Update to the next version when major decisions or scope changes are agreed.*
