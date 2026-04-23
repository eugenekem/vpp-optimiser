# NOTES — Project reflections and milestones

Private notes for personal reference. Tracks key decisions, technical breakthroughs, and milestone reflections across the project build.

---

## Purpose

This file captures:
- Notable technical decisions and why they were made
- Results from validation and benchmarking
- Reflections at the end of each major build chapter
- Open research questions to revisit

---

## Milestones

### Data pipeline foundation
Five data pipelines covering Elexon BMRS, NESO, Open-Meteo, Sheffield Solar. All free-tier. Delivering operational data within 24h of settlement. Established the principle of running "one day behind real time" for Phase 1.

### Battery asset model
Object-oriented design with SOC logic, efficiency modelling, and per-asset constraints. Portfolio instantiated across Scotland and England with variable sizing for geographic and operational diversity.

### Rules-based optimiser
First working optimiser. Reactive threshold-based logic. Validated that the pipeline and asset model work end-to-end. Limitations exposed: no forward-looking capability, no capacity reservation.

### Forward-looking DA optimiser
Added full-day price awareness and per-asset capacity reservation rules (Battery 1 at 50%, others at 30%). Better than rules-based but still heuristic.

### P&L and risk layers
Full per-asset and portfolio P&L with revenue/cost decomposition. Risk metrics added: VaR at 95% and 99%, Sharpe ratio, volatility, concentration risk, scenario analysis under price shocks.

### War room dashboard
Streamlit dashboard with morning briefing, per-asset strategy recommendations, P&L, price curve, asset status, risk summary, DC tender forecast, and dispatch schedule.

### LP optimisation
PuLP implementation of full LP formulation — 48 decision variables per battery (charge, discharge, SOC), energy balance constraints, SOC limits, power limits, reservation rules.

**Benchmark result:** LP outperformed rules-based by 12.2% and forward-looking DA by 24.1% on the same day's prices with identical capacity constraints. Validated on 2026-04-22 with price range -£27 to +£127.

**Bug diagnosed during validation:** Initial energy balance equation missing the 0.5h time factor, causing the LP to overestimate energy flow per period. Caught through a simple 4-period unit test comparing expected vs actual SOC values.

---

## Open research questions

- Stochastic optimisation — price uncertainty modelling approaches
- Battery degradation cost integration into objective function
- Intraday continuous price approximation methodology
- BM bid/offer strategy under imbalance exposure

---

## Technical decisions worth documenting

- Settlement period = 30 minutes (GB market standard) — all time factors use 0.5h
- Round-trip efficiency = 90% — applied symmetrically on charge and discharge
- SOC bounds = 10% to 90% — standard BESS operating envelope
- PuLP with CBC solver — open source, fast enough for 48-period single-asset problems
- Modular architecture — each optimiser is standalone; dispatcher coordinates

---

*This file is for personal reference during project development.*
