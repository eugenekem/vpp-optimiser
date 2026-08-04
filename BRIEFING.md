# VPP Optimiser — Project Briefing
**Version:** 16.0
**Status:** Phase 1 historical replay complete. Phase 2 shadow trading (shadow.py) built. DA price forecasting baselines measured against 730 days of backfilled history (v16) — **conclusion: price history alone is not enough; the bottleneck is predictive inputs, not more data.** Forecasts NOT wired into dispatch. Still not a live-trading system: all trading logic decides on published (already-known) prices — see sections 10b, 16 and 18.

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
| Bulk historical backfill | Elexon BMRS | `scripts/backfill.py` | Loops the two fetch scripts over a date range; skips existing files so it is resumable |
| DC forecast (4-day) | NESO Data Portal | `fetch_dc_tenders.py` | |
| Weather | Open-Meteo | `fetch_weather.py` | |
| Solar generation | Sheffield Solar PV_Live | `fetch_solar.py` | |

**Known gap:** Real-time intraday continuous prices not freely available. Workaround: simulate ID price as DA price + Normal(0, £5) spread.

**Note:** `fetch_dc_tenders.py`, `fetch_weather.py`, and `fetch_solar.py` are still hardcoded to "yesterday" (no date arg support), and `fetch_weather.py` uses Open-Meteo's backward-looking archive endpoint. Confirmed non-blocking for the DA/ID/BM dispatch pipeline (`dispatcher.py` only consumes `market_index`/`system_prices` data) — relevant only if these feeds are later wired into dashboard display or the optimiser itself.

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
| `shadow.py` | Phase 2 shadow trading | ✅ Built |
| `forecast.py` | DA price forecast + accuracy scoring | ✅ Built (baselines only, not wired to dispatch) |

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

## 10b. DA Price Forecast — Baseline Results

**Script:** `models/forecast.py`
**Outputs:** `data/forecast_{date}.csv` (predictions), `data/forecast_accuracy.csv` (scores)

Three deliberately simple methods, walk-forward validated (each day predicted using only prior days — leakage-guarded and verified):

| Method | Description |
|---|---|
| `naive` | Copy the most recent available day — the benchmark to beat |
| `mean_7` | Per-settlement-period mean of last 7 available days |
| `weekday` | As above, but weekday days predict weekdays, weekend days predict weekends |

**Definitive results — walk-forward over 730 days (3 Aug 2024 – 3 Aug 2026), full backfilled history:**

| Method | Days | MAE | RMSE | Cheap-4 hits | Peak-4 hits | Skill vs naive |
|---|---|---|---|---|---|---|
| naive | 730 | £23.00 | £29.16 | 0.8 / 4 | 1.7 / 4 | — |
| **mean_7** | 730 | **£21.51** | **£26.26** | **1.1 / 4** | **2.2 / 4** | **+6.5%** |
| weekday | 730 | £21.72 | £26.42 | 1.1 / 4 | 2.1 / 4 | +5.5% |

**⚠️ This supersedes the earlier 30-day result, which was misleading.** On the 30-day sample, `weekday` appeared to beat naive by **+15.8%** and was recorded here as "real signal, not noise." With 24× more data that claim does not hold: skill collapses to **+5.5%**, and `weekday` is now *slightly worse* than plain `mean_7`. The weekday/weekend split was fitting small-sample noise. This is exactly the failure mode the backfill was meant to expose, and it is the single most valuable result of v16.

**Key finding — more history did not fix accuracy.** Going from 30 → 730 days moved skill from an illusory +15.8% to a real +6.5%. Beating "copy yesterday" by 6.5% is not a trading edge. Most telling is the **Cheap-4 hit rate of 1.1/4** — the forecast correctly identifies only ~28% of the genuinely cheapest periods (barely above the ~8% you would get at random, but nowhere near usable). For a battery, *picking the right periods* is the entire source of profit.

**Conclusion:** the bottleneck is **inputs, not history**. Price history alone cannot predict GB price shape, because shape is driven by fundamentals the model cannot see — wind and solar output, demand, and gas prices. Adding more years, or more elaborate statistics over the same single variable, is very unlikely to help. Next real step is predictive features (see section 16), not a bigger model. Wiring `forecast.py` into `dispatcher.py` remains premature.

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
- **Phase 2** — Shadow trading (daily batch, logs decisions on published data, no real trades) ✅ Built — accumulating days
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
| Phase 2 shadow trading (shadow.py) | ✅ Done |
| DA price forecast baselines + accuracy scoring (forecast.py) | ✅ Done |
| Backfill 730 days of price history (backfill.py) | ✅ Done |
| Add predictive features (wind/solar/demand forecasts) — the real blocker | ⬜ Next |
| Improve forecast accuracy to a tradeable level | ⬜ Blocked on features above |
| Wire forecast into dispatch (blocked on accuracy) | ⬜ To do |
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

- **Price forecasting remains the blocker for real trading — now started, not solved.** Phase 1 (replay.py) and Phase 2 (shadow.py) both decide using published/already-known prices. `forecast.py` (v15) established measured baselines, but accuracy is not yet tradeable (see section 10b). Open questions from here:
  - **More history is the likely bottleneck.** Only ~30 clean consecutive days exist. Backfilling `market_index_*.csv` across many months would enable both better methods and honest validation. Cheapest, highest-value next step.
  - **Predictive features not yet usable.** Wind/solar generation forecasts and demand forecasts drive GB price shape far more than price history alone. Requires a forward-looking weather feed — `fetch_weather.py` currently uses Open-Meteo's *archive* endpoint (past weather); a forecast endpoint would be needed.
  - Whether to forecast the *price level* at all, versus directly forecasting the *ranking* of periods (cheapest→priciest), since dispatch only needs the ordering. Possibly an easier and more directly useful target.
  - How to represent forecast uncertainty so the optimiser can hedge rather than trust a single predicted path (links to stochastic optimisation below).
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
- **⚠️ Settlement-date misalignment in `market_index_*.csv` (found v15, NOT yet fixed).** Each file mixes two settlement dates. `fetch_da_prices.py` filters on `startTime` within a UTC calendar day, but during BST a GB settlement day starts at 23:00 UTC the evening before — so SP1–2 in `market_index_{D}.csv` actually belong to settlement date D+1, while SP3–48 belong to D. Verified in `market_index_2026-06-22.csv` (SP1 carries `settlementDate` 2026-06-23). Consistent across all files, so replay/shadow results are internally consistent and comparisons remain valid — but the mapping is off by two periods against true settlement days. **Must be resolved before live trading**, and it also mildly contaminates forecast training data. Affects `system_prices_*.csv` alignment too — needs checking.
- **v15 — forecast.py added.** DA price forecasting baselines (`naive`, `mean_7`, `weekday`) plus walk-forward accuracy scoring. Writes only to `data/forecast_{date}.csv` — deliberately NEVER `market_index_{date}.csv`, since that filename is what `fetch_if_missing()` checks; writing there would make replay/shadow silently consume predictions as if they were real published prices. Leakage guard verified: forecasts for a date are identical whether or not that date's actuals are present. No existing files modified. Result recorded honestly in section 10b — beats naive, still not tradeable.
- **v14 — shadow.py added.** Reuses `fetch_if_missing`/`classify_day` (from `replay.py`) and `run_dispatcher` (from `dispatcher.py`) unmodified — no changes to existing pipeline files. Appends one row per day to `data/shadow_pnl.csv` (idempotent — checks the `date` column before processing, safe to re-run). Supports `python shadow.py [YYYY-MM-DD]` for manual backfill of a missed day. Confirmed the pipeline does not consume solar/weather/DC-tender data, so those 3 date-locked fetch scripts (see section 5) are not a blocker for this.

- **v16 — 730-day backfill + a corrected conclusion.** `scripts/backfill.py` extended price history from ~30 to 730 complete days (3 Aug 2024 – 3 Aug 2026, both feeds, zero gaps). Two lessons: (1) the v15 finding that `weekday` beat naive by +15.8% was **small-sample noise** — on 730 days it drops to +5.5% and is beaten by simpler `mean_7`. Small samples produce confident wrong answers; validate on the largest sample available before believing a result. (2) More history did **not** improve accuracy meaningfully, which redirects effort from "more/better statistics on price history" to "get predictive inputs" — a cheap experiment that killed an expensive wrong path.
- **Clock-change days crash naive per-period indexing (found and fixed in v16).** On the spring clock-change Sunday (30 Mar 2025, 29 Mar 2026) the GB settlement day has only **46** periods, so the UTC-window fetch also captures SP1–2 of the next settlement date — producing duplicate `settlementPeriod` values with different prices, which raised `ValueError: cannot reindex on an axis with duplicate labels`. Fixed in `forecast.py::load_actual` by keeping the row whose `settlementDate` matches the file's own date (affects 2 of 731 files; normal days unchanged). **Note:** this is a symptom of the settlement-date misalignment logged above, not a full fix — autumn clock-change days (50 periods) are still silently truncated to 48 rows by the fetch window and have not been addressed. **`dispatcher.py` is also broken on these two dates — verified, not yet fixed.** It does `set_index("settlementPeriod")["price"]` with no de-duplication, so `price_series[t]` returns a 2-row Series instead of a float and the LP fails with `TypeError: cannot convert the series to <class 'float'>`. This means `replay.py` and `shadow.py` will crash (and skip the day) if they ever process 30 Mar 2025 or 29 Mar 2026. Not hit so far because neither has run over those dates. Fix by applying the same de-duplication used in `forecast.py::load_actual`.

---

*Update to the next version when major decisions or scope changes are agreed.*
