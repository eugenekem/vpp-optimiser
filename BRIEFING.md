# VPP Optimiser — Project Briefing
**Version:** 18.0
**Status:** Phase 1 replay and Phase 2 shadow trading built. DA price forecasting uses Elexon's **day-ahead wind/solar forecast**: +18.0% accuracy skill vs naive, and — the number that matters — **85.9% capture of perfect-foresight P&L vs 81.5% for the best history-only method**, over 696 days, robustness-checked and not outlier-driven (section 10c). Demand forecast feed built and backfilling; not yet in the model. Forecasts still NOT wired into dispatch.
**Reading this for anything external:** use section 10c, quoted as a *capture ratio*, with its caveats. **Section 10's £1.9M / £63k-per-day figures are perfect-foresight and must never be presented as trading results.**

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

> **⚠️ PERFECT-FORESIGHT NUMBERS — NOT A TRADING RESULT. DO NOT USE EXTERNALLY.**
> Every figure below was produced by optimising against prices that were **already published and known**. It is the profit a crystal ball would earn, not what this system can make. It validates that the dispatch logic and constraints work — that was its purpose — and nothing more.
> The comparable perfect-foresight DA figure in section 10c is £33,503/day; the best *forecast-driven* result is £28,764/day (85.9% capture), and even that excludes spreads, transaction costs, market impact and degradation.
> Any external or investor-facing claim must come from section 10c, stated as a capture ratio, with its caveats attached. A technical reviewer will ask whether a backtest used realised prices; presenting these numbers without this warning would be indefensible.

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

Walk-forward validated — each day predicted using only prior days. Leakage guard verified for every method, including `regression` (confirmed it never reads the target day's actuals or any later date).

| Method | Description |
|---|---|
| `naive` | Copy the most recent available day — the benchmark to beat |
| `mean_7` | Per-settlement-period mean of last 7 available days |
| `mean_90` | Same, over 90 days — **a control**, matching the regression's training window |
| `weekday` | Per-period mean, weekdays predicting weekdays and weekends weekends |
| `regression` | Per-period least-squares fit of price against Elexon's **day-ahead wind and solar forecast** (90-day window) |

**Definitive results — walk-forward over 696 days scored by all five methods (3 Aug 2024 – 3 Aug 2026):**

| Method | Days | MAE | RMSE | Cheap-4 hits | Peak-4 hits | Skill vs naive |
|---|---|---|---|---|---|---|
| naive | 696 | £22.76 | £28.92 | 0.9 / 4 | 1.7 / 4 | — |
| mean_7 | 696 | £21.28 | £26.07 | 1.1 / 4 | 2.2 / 4 | +6.5% |
| mean_90 *(control)* | 696 | £22.74 | £27.25 | 1.1 / 4 | 1.8 / 4 | +0.1% |
| weekday | 696 | £21.46 | £26.18 | 1.1 / 4 | 2.2 / 4 | +5.7% |
| **regression** | 696 | **£18.67** | **£22.78** | **1.3 / 4** | **2.2 / 4** | **+18.0%** |

All methods are compared on **identical days** — `regression` covers fewer days (no wind/solar published for 4 dates, plus its 90-day warm-up), and averaging each method over whatever days it happened to cover would not be like-for-like.

**Result 1 — predictive inputs work, and the v16 hypothesis was correct.** Adding the day-ahead wind/solar forecast nearly triples skill over the best history-only method (+18.0% vs +6.5%). This confirms the v16 conclusion that the bottleneck was *inputs*, not more history.

**Result 2 — the `mean_90` control rules out the obvious confound.** The regression trains on 90 days while `mean_7` uses 7, so the gain could have come from the longer window rather than from wind/solar. It did not: `mean_90` scores **+0.1%**, i.e. a 90-day average is no better than copying yesterday. The improvement is genuinely attributable to the renewable-generation signal.

**Result 3 — but period *selection* barely improved.** Cheap-4 hits moved only 1.1 → 1.3 / 4, and Peak-4 did not move at all (2.2 / 4). The model got substantially better at predicting the *level* of prices without getting much better at identifying *which* periods are cheapest. For a battery, period selection is the entire source of profit, so **this is not yet demonstrated to be tradeable**, despite the strong MAE result.

**Conclusion:** a real, verified improvement, and the first method with a credible claim to signal. The open question — does accuracy convert into money — is now answered in section 10c.

---

## 10c. Forecast → P&L: does accuracy actually earn money?

**Script:** `models/forecast_pnl.py` **Output:** `data/forecast_pnl.csv`

MAE cannot answer whether a forecast is worth trading on. This test does, in pounds. For each day, a dispatch schedule is built using **forecast** prices (what you could actually commit to day-ahead), then settled at **actual** prices (what you really get paid). The `perfect` arm optimises on actual prices — the crystal-ball ceiling — so each method can be scored as a *capture ratio*: the share of theoretically available money it actually won.

**Results — 696 days (35 skipped), DA layer only:**

| Arm | Total P&L | Per day | Capture |
|---|---|---|---|
| `perfect` *(not tradeable)* | £23,317,960 | £33,503 | 100.0% |
| naive | £16,838,330 | £24,193 | 72.2% |
| mean_7 | £19,001,647 | £27,301 | 81.5% |
| **regression** | **£20,019,765** | **£28,764** | **85.9%** |

**Headline: the wind/solar forecast captures 85.9% of perfect-foresight profit**, versus 81.5% for the best history-only method and 72.2% for copying yesterday — worth **£1.02M more than `mean_7`** across 696 days.

**Accuracy converts to money, but at a discount.** The +18.0% MAE improvement produced +5.4% more P&L — roughly a third of the accuracy gain reached the bottom line. This is consistent with the section 10b finding that period *selection* barely improved: the optimiser only needs the price *ranking* to be right, so better level accuracy is partly wasted on it. Anyone reasoning from MAE alone would have overstated the commercial value by ~3×.

**Robustness — checked, and it holds:**
- Beats `mean_7` on **406 of 696 days (58.3%)** — a real but not overwhelming edge.
- **Top 5 days account for only 15.0% of the total advantage**, so this is broad-based, not a few lucky outliers.
- Median daily capture **88.7%**; 25th percentile 81.3%; 10th percentile 71.1%. Only 1 day of negative P&L, 12 days below 50% capture.
- Mean daily advantage (£1,463) far exceeds the median (£516) — the edge is right-skewed. It comes mainly from days when renewables swing unusually and price history is blind while the wind forecast is not (e.g. 2025-05-27: `mean_7` £3,922 vs `regression` £40,287). That is a coherent mechanism, not a statistical artefact.

**⚠️ What this number is NOT.** It remains a backtest, and must not be presented as a trading track record. It assumes execution of the full volume at the published market-index price, with **no bid/offer spread, no transaction costs, no market impact** (a ~145 MW portfolio bidding into GB DA would move the price against itself), **no battery degradation cost**, and perfect availability. The realistic figure is lower. The defensible claim is the *relative* one — 85.9% vs 81.5% capture, measured like-for-like on identical days — not the absolute pound total.

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
| Add wind/solar day-ahead forecast feed (fetch_wind_solar.py, 726 days) | ✅ Done |
| Regression price model on wind/solar (+18.0% skill, control-verified) | ✅ Done |
| Test whether forecast accuracy converts into P&L (forecast_pnl.py) | ✅ Done — 85.9% capture |
| Add demand forecast as a feature (fetch_demand.py built, backfilling) | 🔄 In progress |

| Fix clock-change crash in dispatcher.py (replay/shadow break on 2 dates) | ⬜ To do |
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
  - **✅ RESOLVED (v17) — predictive features work.** Elexon publishes a day-ahead wind/solar generation forecast (`/forecast/generation/wind-and-solar/day-ahead`, ~16:45 the evening before delivery, history back past 2023). Now fetched by `scripts/fetch_wind_solar.py` and used by the `regression` method: +18.0% skill vs +6.5% for the best history-only method, with a `mean_90` control confirming the gain is from the renewable signal and not the longer training window. Open-Meteo was **not** needed — Elexon's own feed is better (it is a generation forecast, not weather requiring conversion) and uses infrastructure already in place.
  - **The open question is now tradeability, not accuracy.** MAE improved sharply but Cheap-4 period selection barely moved (1.1 → 1.3 / 4) and Peak-4 not at all. Since a battery earns from *picking periods*, better MAE may not mean better P&L. **Proposed test:** run `dispatcher.py` twice over the same historical days — once on forecast prices, once on actual prices (perfect foresight) — and compare realised P&L. That measures what actually matters, in £, and directly answers whether to wire forecasts into dispatch. The forecast file format is already dispatcher-compatible, so this is a small piece of work.
  - **Demand forecast still unused.** `/forecast/demand/day-ahead` returns only the current forecast (no date range); the `/history` variant is keyed by `publishTime`, so backfilling it is fiddlier than wind/solar was. Worth adding after the P&L test.
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
- **v17 — wind/solar day-ahead forecast added; predictive inputs confirmed to work.** `scripts/fetch_wind_solar.py` backfilled 726 of 730 days (4 dates return HTTP 200 with zero rows — genuine Elexon publication gaps, not a script fault). New `regression` method in `forecast.py`: per-settlement-period least squares of price against forecast wind and solar, 90-day rolling window, extrapolation clamped to the observed training range. **+18.0% skill vs naive.** Two methodology safeguards worth keeping: (1) a `mean_90` control was added specifically to rule out the longer training window as the cause — it scored +0.1%, isolating the gain to the renewable signal; (2) `backtest()` now scores all methods on identical days only, since `regression` covers fewer days and comparing different samples would flatter it. Both guards exist because v16's `weekday` result was a small-sample illusion — assume any new improvement is a confound until a control says otherwise.
- **⚠️ Feature/price alignment is deliberate — do not "fix" `fetch_wind_solar.py` in isolation.** It mirrors `fetch_da_prices.py`'s UTC-calendar-day window on `startTime` rather than filtering to its own settlement date. This is intentional: it makes `wind_solar_{D}.csv` line up row-for-row with `market_index_{D}.csv`, so the same `settlementPeriod` means the same real half-hour in both. Filtering wind/solar to settlement date D while prices remain on the UTC-window convention would put features and target 24 hours apart for SP1–2. If the settlement-date misalignment is ever fixed, **both feeds must be fixed together**.
- **v18 — forecast accuracy converts to money, but at roughly a third of the rate MAE implies.** `forecast_pnl.py` settles forecast-built dispatch at actual prices. The regression's +18.0% MAE advantage produced only **+5.4% P&L** over `mean_7`. Consistent with section 10b: the LP only needs the price *ranking*, so improvements in level accuracy are largely wasted on it. **Lesson: never quote a forecast-accuracy improvement as if it were a commercial one** — reasoning from MAE alone would have overstated the value ~3×. Robustness checked before believing the result: wins 58.3% of days, top-5 days only 15.0% of the advantage, and the edge is right-skewed (mean £1,463 vs median £516) because it comes from days when renewables swing and price history is blind. That is a mechanism, not an artefact.
- **`fetch_demand.py` uses a different alignment convention on purpose.** Prices and wind/solar use a UTC-calendar-day window on `startTime`; demand rows are stored with their own `settlementDate`. Joining demand to prices must therefore key on **(settlementDate, settlementPeriod)**, not settlementPeriod alone, or the two will sit two periods apart during BST and be correct during GMT — a seasonal bug that would pass a spot check in winter. Integration deliberately deferred rather than rushed unattended.
