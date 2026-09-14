# VPP Optimiser — Project Briefing
**Version:** 25.0
**Status:** Phase 1 replay and Phase 2 shadow trading built. Daily pipeline split across GitHub Actions (fetch, 05:00 UTC) and a cloud routine (check-in, alert, exploration sense-check, 06:00 UTC). **v24: the long-standing settlement-date misalignment bug (open since v15) is fixed** — `fetch_da_prices.py`/`fetch_wind_solar.py` corrected, all ~730 days of historical data migrated and verified lossless. **v25: all headline numbers re-validated against the corrected data — confirmed negligible impact** — see section 17.
**Headline numbers in sections 10b/10c/10d were re-run against the corrected date data (v25) and confirmed stable**: accuracy skill +24.5% → +24.1%, cost-aware capture 86.2% → 86.6%, conservative £/day £24,702 → £25,558. The small £/day increases come from 40 extra days of data now included (721 vs 681), not from the date fix — capture ratios moved by only ~0.4 points across every method and cost stack. See section 17, v25 entry for the full re-validation.
**Reading this for anything external:** use **section 10d** (cost-aware) — it supersedes 10c's costless figures. Always quote **£/day alongside the capture ratio**, never the ratio alone. **Section 10's £1.9M / £63k-per-day figures are perfect-foresight and must never be presented as trading results.**

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
| Bulk historical backfill | Elexon BMRS | `scripts/backfill.py` | Loops all 4 date-capable fetch scripts (prices, system prices, wind/solar, demand) over a date range; skips existing files so it is resumable; retry-with-backoff since v22 |
| Unattended daily run | Elexon BMRS | `scripts/daily_pipeline.py` | Detects the real gap, backfills it, shadow-logs new days, commits/pushes `data/` only — see section 17, v22 |
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

**Definitive results — walk-forward over 721 days scored by all six methods (3 Aug 2024 – 13 Sep 2026), re-validated v25 against settlement-date-corrected data:**

| Method | Days | MAE | RMSE | Cheap-4 hits | Peak-4 hits | Skill vs naive |
|---|---|---|---|---|---|---|
| naive | 721 | £23.33 | £29.67 | 0.9 / 4 | 1.7 / 4 | — |
| mean_7 | 721 | £21.80 | £26.74 | 1.1 / 4 | 2.2 / 4 | +6.6% |
| mean_90 *(control)* | 721 | £23.67 | £28.22 | 1.1 / 4 | 1.8 / 4 | −1.5% |
| weekday | 721 | £21.90 | £26.71 | 1.1 / 4 | 2.2 / 4 | +6.2% |
| regression *(wind+solar)* | 721 | £19.33 | £23.50 | 1.3 / 4 | 2.1 / 4 | +17.1% |
| **reg_demand** *(+demand)* | 721 | **£17.72** | **£21.65** | **1.4 / 4** | **2.1 / 4** | **+24.1%** |

*(Superseded numbers from the pre-fix, 681-day run: naive £22.82 MAE, reg_demand £17.23 MAE / +24.5% skill — kept here only to show the fix moved skill by −0.4 points, i.e. essentially nothing.)*

All methods are compared on **identical days** — `regression` covers fewer days (no wind/solar published for some dates, plus its 90-day warm-up), and averaging each method over whatever days it happened to cover would not be like-for-like.

**Result 1 — predictive inputs work, and the v16 hypothesis was correct.** Adding the day-ahead wind/solar forecast nearly triples skill over the best history-only method (+18.0% vs +6.5%). This confirms the v16 conclusion that the bottleneck was *inputs*, not more history.

**Result 2 — the `mean_90` control rules out the obvious confound.** The regression trains on 90 days while `mean_7` uses 7, so the gain could have come from the longer window rather than from wind/solar. It did not: `mean_90` scores **+0.1%**, i.e. a 90-day average is no better than copying yesterday. The improvement is genuinely attributable to the renewable-generation signal.

**Result 3 — but period *selection* barely improved.** Cheap-4 hits moved only 1.1 → 1.3 / 4, and Peak-4 did not move at all (2.2 / 4). The model got substantially better at predicting the *level* of prices without getting much better at identifying *which* periods are cheapest. For a battery, period selection is the entire source of profit, so **this is not yet demonstrated to be tradeable**, despite the strong MAE result.

**Conclusion:** a real, verified improvement, and the first method with a credible claim to signal. The open question — does accuracy convert into money — is now answered in section 10c.

---

## 10c. Forecast → P&L: does accuracy actually earn money?

**Script:** `models/forecast_pnl.py` **Output:** `data/forecast_pnl.csv`

MAE cannot answer whether a forecast is worth trading on. This test does, in pounds. For each day, a dispatch schedule is built using **forecast** prices (what you could actually commit to day-ahead), then settled at **actual** prices (what you really get paid). The `perfect` arm optimises on actual prices — the crystal-ball ceiling — so each method can be scored as a *capture ratio*: the share of theoretically available money it actually won.

**Results — 721 days, DA layer only, re-validated v25 against settlement-date-corrected data:**

| Arm | Total P&L | Per day | Capture |
|---|---|---|---|
| `perfect` *(not tradeable)* | £24,781,062 | £34,370 | 100.0% |
| naive | £18,179,966 | £25,215 | 73.4% |
| mean_7 | £20,344,602 | £28,217 | 82.1% |
| regression *(wind+solar)* | £21,338,452 | £29,596 | 86.1% |
| **reg_demand** *(+demand)* | **£21,658,359** | **£30,039** | **87.4%** |

*(Pre-fix, 681-day figures: 87.1% capture, £29,229/day for `reg_demand` — the fix moved capture by +0.3 points, i.e. no material change.)*

**Headline: the best forecast captures 87.4% of perfect-foresight profit**, versus 82.1% for the best history-only method and 73.4% for copying yesterday — worth **£994k more than `mean_7`** across 721 days.

**⚠️ Accuracy converts to money at a sharply diminishing rate — the most important strategic finding so far.**

| Step | Accuracy gain (skill) | P&L gain (capture) | Conversion |
|---|---|---|---|
| `mean_7` → `regression` (add wind/solar) | +10.5 pts (6.6 → 17.1%) | +4.0 pts (82.1 → 86.1%) | ~38% |
| `regression` → `reg_demand` (add demand) | +7.0 pts (17.1 → 24.1%) | +1.3 pts (86.1 → 87.4%) | ~19% |

Each increment of forecast accuracy buys **less** profit than the one before — unchanged conclusion after re-validation. Demand remains a real but small improvement for a whole new data pipeline.

**Implication: chasing further forecast accuracy is close to exhausted as a strategy.** The remaining ~13 points to perfect foresight are unlikely to be recovered by better price prediction — much of it is probably irreducible uncertainty. Future effort is better spent on (a) the markets not yet optimised against forecasts (BM, ancillary/DC), (b) stochastic optimisation that hedges across a *distribution* of prices rather than trusting one path, or (c) execution realism (spreads, costs, market impact), which currently sits outside the model entirely and will lower every number here.

**Historical note on the earlier framing.** The MAE improvement produces a smaller P&L improvement — roughly a third to two-fifths of the accuracy gain reaches the bottom line (see conversion table above). This is consistent with the section 10b finding that period *selection* barely improved: the optimiser only needs the price *ranking* to be right, so better level accuracy is partly wasted on it. Anyone reasoning from MAE alone would overstate the commercial value.

**Robustness — checked, and it holds (re-validated v25 against corrected data):**
- Beats `mean_7` on **446 of 721 days (61.9%)** — a real but not overwhelming edge.
- **Top 5 days account for only 13.3% of the total advantage**, so this is broad-based, not a few lucky outliers.
- Median daily capture **90.2%**; 25th percentile 83.2%; 10th percentile 73.1%. Only 1 day of negative P&L, 10 days below 50% capture.
- Mean daily advantage (£1,822) exceeds the median (£605) — the edge is right-skewed, coming mainly from days when renewables swing unusually and price history is blind while the wind forecast is not. That is a coherent mechanism, not a statistical artefact.
- *(Pre-fix, 696-day figures: 58.3% win rate, 15.0% top-5 share, £1,463/£516 mean/median advantage — all directionally the same after re-validation.)*

**⚠️ What this number is NOT.** It remains a backtest, and must not be presented as a trading track record. It assumes execution of the full volume at the published market-index price, with **no bid/offer spread, no transaction costs, no market impact** (a ~145 MW portfolio bidding into GB DA would move the price against itself), **no battery degradation cost**, and perfect availability. The realistic figure is lower. The defensible claim is the *relative* one — 85.9% vs 81.5% capture, measured like-for-like on identical days — not the absolute pound total.

## 10d. Execution costs — closing the backtest-to-reality gap

**Added v20.** Every figure before this assumed costless trading of unlimited volume at the published index price. Costs are now modelled in `config.py` and applied in two distinct ways, which are reported separately because they answer different questions.

**Central GB assumptions:** degradation **£4.00/MWh discharged**, exchange + clearing fees **£0.15/MWh**, own-bid market impact **£0.75/MWh**, the last two charged in both directions. All configurable.

**Results — 721 days, DA layer, re-validated v25 against settlement-date-corrected data:**

| Arm | No costs | Costs, blind | Costs, aware | Capture |
|---|---|---|---|---|
| `perfect` *(not tradeable)* | £24,781,062 | £22,899,624 | £23,013,987 | 100.0% |
| naive | £18,179,966 | £16,302,388 | £16,636,897 | 72.3% |
| mean_7 | £20,344,602 | £18,465,133 | £18,501,238 | 80.4% |
| regression | £21,338,452 | £19,418,859 | £19,619,646 | 85.3% |
| **reg_demand** | £21,658,359 | £19,698,180 | **£19,941,516** | **86.6%** |

*(Pre-fix, 681-day figures: `reg_demand` £18,255,788 aware / 86.2% capture — the fix moved capture by +0.4 points.)*

*blind* = the optimiser ignores costs (as before) but they are charged at settlement. *aware* = costs are inside the LP objective, so spreads too thin to cover them are not traded.

**Result 1 — costs cost ~8%, not ~50%.** `reg_demand` falls from £21.66M to £19.94M (**−7.9%**), i.e. £30,039 → **£27,658 per day**. Less damaging than feared because this strategy earns from wide daily spreads (£30–60/MWh), which comfortably absorb a ~£5/MWh round trip. A thin-margin strategy would have been destroyed by the same assumptions.

**Result 2 — cost-awareness is worth having but is not transformative: +1.2% (£243,336).** Most trades the optimiser makes are already well above the cost threshold, so declining the marginal ones recovers only a slice. Cheap to implement, so worth keeping.

**Result 3 — costs make good forecasting MORE valuable, not less.** `reg_demand`'s advantage over `mean_7` remains **+7.8%** once costs are charged (aware vs aware), consistent with the pre-fix finding that costs penalise wrong trades harder than right ones, so forecast quality matters more in a realistic setting than a costless backtest implies.

**⚠️ Capture fell slightly, 87.4% → 86.6% (−0.8 pts), and the reason matters — unchanged after re-validation.** Perfect foresight retained 92.9% of its costless P&L while `reg_demand` retained 92.1% — the crystal ball is hurt *less* by costs, because it only ever makes wide-margin trades, while a forecast makes marginal and occasionally wrong ones that costs punish hardest.

**Never quote capture without the pounds.** Capture is a share of a moving ceiling: if costs or market conditions drag the ceiling down faster than your P&L, capture can *rise* while you earn *less*. Quote £/day alongside the ratio.

### Cost sensitivity — how much does the assumption matter?

**Script:** `models/cost_sensitivity.py` **Output:** `data/cost_sensitivity.csv`

The central stack was a judgement call, so the whole test was re-run across a plausible range. `reg_demand`, 721 days, re-validated v25:

| Stack | Degradation | Total P&L | Per day | Capture |
|---|---|---|---|---|
| light | £2.00/MWh | £20,814,920 | £28,870 | 87.0% |
| **central** | £4.00/MWh | £19,941,516 | **£27,658** | 86.6% |
| **conservative** | £8.00/MWh | £18,427,409 | **£25,558** | 85.7% |

*(Pre-fix, 681-day figures: light £28,054/day, central £26,807/day, conservative £24,702/day — the fix moved every figure up by 3-4%, fully explained by 40 extra days of data now included, and moved capture by only ~0.4 points at every stack.)*

**Result 1 — the conclusion is robust to the cost assumption.** Quadrupling degradation from £2 to £8/MWh moves daily P&L by only **13%** (£28,870 → £25,558), and capture by 1.3 points. The strategy does not depend on a favourable cost assumption, because it earns from wide daily spreads rather than thin margins. **Quote the conservative figure — ~£25,558/day — externally.** If the case holds at £8/MWh degradation it will survive challenge.

**Result 2 — the forecast edge *grows monotonically* as costs rise, confirmed after re-validation.** Advantage of `reg_demand` over `mean_7`: **+7.00%** (light) → **+7.78%** (central) → **+9.14%** (conservative) — versus +7.28% / +7.86% / +8.91% pre-fix. Same shape, same conclusion: costs punish wrong trades harder than right ones, so **forecast quality matters most precisely when trading is most expensive**. Commercially this remains the strongest argument in the project.

**Still excluded:** imbalance exposure if delivery deviates from contract, availability/outages, non-linear market impact at larger volumes, and any ID/BM execution cost (this is the DA layer only). The realistic number remains below the figures above.

---

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
| Add demand forecast as a feature (reg_demand) | ✅ Done — +1.2 pts capture |
| Execution costs modelled (config.py + cost-aware LP) | ✅ Done — 86.6% capture, £27.7k/day |
| Cost sensitivity sweep (light / central / conservative) | ✅ Done — £25.6k–£28.9k/day |
| Unattended daily pipeline — GitHub Actions (fetch) + cloud routine (alert, exploration) | ✅ Done — see §18 |
| Cloud scheduling of the daily pipeline | ✅ Done (v25) — Actions 05:00 UTC, cloud routine 06:00 UTC |
| Sense-check exploration stage (exploration_helpers.py) — tested, real finding | ✅ Done (v23) — chained into daily schedule as standard Stage 2 |
| Fix clock-change crash in dispatcher.py (replay/shadow break on 2 dates) | ✅ Done (v22) |
| Fix settlement-date misalignment (market_index/wind_solar, open since v15) | ✅ Done (v24) — see section 17 |
| Re-validate headline numbers against corrected data (shadow.py, forecast.py, forecast_pnl.py, cost_sensitivity.py) | ✅ Done (v25) — confirmed negligible impact, see section 17 |
| Wire forecast into dispatch (blocked on accuracy) | ⬜ To do |
| Stochastic optimisation — hedge across a price distribution | ⬜ To do |
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
- **✅ FIXED (v24) — Settlement-date misalignment in `market_index_*.csv` (found v15).** Each file used to mix two settlement dates: `fetch_da_prices.py` filtered on `startTime` within a UTC calendar day, but during BST a GB settlement day starts at 23:00 UTC the evening before, so SP1–2 in `market_index_{D}.csv` actually belonged to settlement date D+1. `fetch_wind_solar.py` deliberately mirrored the same convention (and additionally overwrote each row's real `settlementDate` with the query date — a separate, compounding bug in that script specifically).
  **Fix:** both fetchers now widen their query window and filter to Elexon's own `settlementDate == target_date`, correct in both BST/GMT and on clock-change days by construction (no BST logic hand-rolled). All ~730 days of historical `market_index_*`/`wind_solar_*` files migrated via `scripts/migrate_settlement_dates.py` — pure local relabeling for market_index (every row already carried its true date), true dates recovered for wind_solar by joining against the original market_index files' row-position mirroring. Zero data loss (37008→37006 / 36716→36710 rows; the handful dropped were incomplete boundary-date artifacts, not real data). Originals archived to `data/pre_migration_backup/`, not deleted. Verified before applying: row-count distribution checked (only 46/48/50-period files, no partials), `dispatcher.py` run against migrated 2026-06-22 and the clock-change date 2026-03-29 — both clean.
  **One data point from that spot-check:** 2026-06-22's net P&L moved £75,719 → £76,151 (+0.6%) once correctly dated — small, as expected, since the same real prices are used either way, just 1-2 periods reshuffled between adjacent days.
  **✅ Follow-up done (v25) — re-validated at scale, not just spot-checked.** `shadow.py`, `forecast.py`'s backtest, `forecast_pnl.py`, and `cost_sensitivity.py` were all re-run against the corrected data and compared line-for-line against the pre-fix figures. Result: the "near-zero aggregate impact" prediction held. See the v25 entry below for the full comparison.
  **Also unaffected, confirmed independently:** `system_prices_*.csv` and `demand_*.csv` (both query Elexon by true settlement date directly, never had this bug).
  **Minor cleanup opportunity, not done:** `dispatcher.py`'s and `forecast.py`'s clock-change deduplication workarounds, and `forecast.py::load_demand`'s date-based join, existed specifically to cope with this bug and are now unnecessary (harmless to leave, safe to simplify later).
- **v15 — forecast.py added.** DA price forecasting baselines (`naive`, `mean_7`, `weekday`) plus walk-forward accuracy scoring. Writes only to `data/forecast_{date}.csv` — deliberately NEVER `market_index_{date}.csv`, since that filename is what `fetch_if_missing()` checks; writing there would make replay/shadow silently consume predictions as if they were real published prices. Leakage guard verified: forecasts for a date are identical whether or not that date's actuals are present. No existing files modified. Result recorded honestly in section 10b — beats naive, still not tradeable.
- **v14 — shadow.py added.** Reuses `fetch_if_missing`/`classify_day` (from `replay.py`) and `run_dispatcher` (from `dispatcher.py`) unmodified — no changes to existing pipeline files. Appends one row per day to `data/shadow_pnl.csv` (idempotent — checks the `date` column before processing, safe to re-run). Supports `python shadow.py [YYYY-MM-DD]` for manual backfill of a missed day. Confirmed the pipeline does not consume solar/weather/DC-tender data, so those 3 date-locked fetch scripts (see section 5) are not a blocker for this.

- **v16 — 730-day backfill + a corrected conclusion.** `scripts/backfill.py` extended price history from ~30 to 730 complete days (3 Aug 2024 – 3 Aug 2026, both feeds, zero gaps). Two lessons: (1) the v15 finding that `weekday` beat naive by +15.8% was **small-sample noise** — on 730 days it drops to +5.5% and is beaten by simpler `mean_7`. Small samples produce confident wrong answers; validate on the largest sample available before believing a result. (2) More history did **not** improve accuracy meaningfully, which redirects effort from "more/better statistics on price history" to "get predictive inputs" — a cheap experiment that killed an expensive wrong path.
- **Clock-change days crash naive per-period indexing (found and fixed in v16).** On the spring clock-change Sunday (30 Mar 2025, 29 Mar 2026) the GB settlement day has only **46** periods, so the UTC-window fetch also captures SP1–2 of the next settlement date — producing duplicate `settlementPeriod` values with different prices, which raised `ValueError: cannot reindex on an axis with duplicate labels`. Fixed in `forecast.py::load_actual` by keeping the row whose `settlementDate` matches the file's own date (affects 2 of 731 files; normal days unchanged). **Note:** this is a symptom of the settlement-date misalignment logged above, not a full fix — autumn clock-change days (50 periods) are still silently truncated to 48 rows by the fetch window and have not been addressed. **✅ FIXED (v22).** `dispatcher.py` had the same bug — `set_index("settlementPeriod")["price"]` with no de-duplication returned a 2-row Series instead of a float, and the LP failed with `TypeError: cannot convert the series to <class 'float'>`. Fixed with the same de-duplication pattern as `forecast.py::load_actual`. Verified rather than assumed: both 30 Mar 2025 and 29 Mar 2026 now run successfully producing exactly 46 periods, and a normal day (2026-06-15) re-run produced byte-identical output. Also checked `system_prices_*.csv` for the same issue (this note previously said it needed checking) — confirmed clean, because `fetch_bmrs.py` queries by settlement date directly rather than a UTC time window, so no fix was needed there.

---

- **v17 — wind/solar day-ahead forecast added; predictive inputs confirmed to work.** `scripts/fetch_wind_solar.py` backfilled 726 of 730 days (4 dates return HTTP 200 with zero rows — genuine Elexon publication gaps, not a script fault). New `regression` method in `forecast.py`: per-settlement-period least squares of price against forecast wind and solar, 90-day rolling window, extrapolation clamped to the observed training range. **+18.0% skill vs naive.** Two methodology safeguards worth keeping: (1) a `mean_90` control was added specifically to rule out the longer training window as the cause — it scored +0.1%, isolating the gain to the renewable signal; (2) `backtest()` now scores all methods on identical days only, since `regression` covers fewer days and comparing different samples would flatter it. Both guards exist because v16's `weekday` result was a small-sample illusion — assume any new improvement is a confound until a control says otherwise.
- **⚠️ Feature/price alignment is deliberate — do not "fix" `fetch_wind_solar.py` in isolation.** It mirrors `fetch_da_prices.py`'s UTC-calendar-day window on `startTime` rather than filtering to its own settlement date. This is intentional: it makes `wind_solar_{D}.csv` line up row-for-row with `market_index_{D}.csv`, so the same `settlementPeriod` means the same real half-hour in both. Filtering wind/solar to settlement date D while prices remain on the UTC-window convention would put features and target 24 hours apart for SP1–2. If the settlement-date misalignment is ever fixed, **both feeds must be fixed together**.
- **v18 — forecast accuracy converts to money, but at roughly a third of the rate MAE implies.** `forecast_pnl.py` settles forecast-built dispatch at actual prices. The regression's +18.0% MAE advantage produced only **+5.4% P&L** over `mean_7`. Consistent with section 10b: the LP only needs the price *ranking*, so improvements in level accuracy are largely wasted on it. **Lesson: never quote a forecast-accuracy improvement as if it were a commercial one** — reasoning from MAE alone would have overstated the value ~3×. Robustness checked before believing the result: wins 58.3% of days, top-5 days only 15.0% of the advantage, and the edge is right-skewed (mean £1,463 vs median £516) because it comes from days when renewables swing and price history is blind. That is a mechanism, not an artefact.
- **`fetch_demand.py` uses a different alignment convention on purpose.** Prices and wind/solar use a UTC-calendar-day window on `startTime`; demand rows are stored with their own `settlementDate`. Joining demand to prices must therefore key on **(settlementDate, settlementPeriod)**, not settlementPeriod alone, or the two will sit two periods apart during BST and be correct during GMT — a seasonal bug that would pass a spot check in winter. Integration deliberately deferred rather than rushed unattended.
- **v19 — demand forecast added; diminishing returns now the headline.** `reg_demand` (wind + solar + day-ahead national demand) reaches +24.5% accuracy skill and **87.1% P&L capture**. The gain over wind/solar alone is real and statistically solid (+1.37% P&L, £268,552 over 681 days, paired t = 3.57, top-5 days only 8.3% of the gain) but small. Conversion of accuracy into money fell from ~40% to ~18% between the two feature additions. **Treat further forecast-accuracy work as low-yield**; the remaining gap to perfect foresight is probably mostly irreducible. Note also that every P&L figure here still excludes spreads, transaction costs, market impact and degradation — closing that gap would change the numbers more than another feature would.
- **Process failure worth remembering: a `pgrep -f "<pattern>"` wait loop matched its own command line.** A backgrounded `until ! pgrep -f "backfill.py"; do sleep 30; done` never exited, because the shell running it had `backfill.py` in its own command string. The backfill had finished normally; only the watcher hung, and it burned ~9 hours before anyone noticed. Use the bracket trick (`pgrep -f "[b]ackfill.py"`) or match on the interpreter, and **verify a watcher actually exits** rather than assuming it will.
- **v20 — execution costs modelled; ~8% of P&L, and good forecasting matters MORE once costs are real.** Degradation/fees/impact are now in `config.py`, applied both at settlement and (optionally) inside the LP objective. `optimise_battery_lp` gained `cost_discharge`/`cost_charge`, **defaulting to 0.0 so replay.py and shadow.py results are unchanged** unless costs are passed explicitly. Headline: `reg_demand` £29,229 → **£26,807/day (−8.3%)**; cost-awareness worth +1.2%; and the forecast's edge over `mean_7` *widens* from +6.87% to +7.86%, because costs punish wrong trades harder than right ones. **Capture is a ratio to a moving ceiling — always quote £/day beside it**; an earlier claim that capture rose under costs was wrong, caused by comparing a 19-day sample with a 681-day one.
- **v21 — cost sensitivity: the result does not rest on a favourable assumption.** Quadrupling degradation (£2 → £8/MWh) moves daily P&L only 14% (£28,054 → £24,702) and capture 1.4 points. **Use ~£24,700/day (conservative) for anything external.** The forecast's edge over `mean_7` rises monotonically with cost — +7.28% / +7.86% / +8.91% across light / central / conservative — confirming that forecast quality matters *most* when trading is most expensive. That the edge widens under pessimistic assumptions is the strongest commercial argument the project has so far.
- **Operational lesson: do not put job logs or sentinels in `/tmp`.** The overnight sweep completed correctly and wrote `data/cost_sensitivity.csv`, but macOS had purged `/tmp/sensitivity.log` and `/tmp/sens_done` by morning, so the first check suggested the job had died. Results survived only because the real output went to `data/`. Write logs and completion markers inside the repo (gitignored) so a run can always be diagnosed after the fact.
- **v22 — unattended daily pipeline built, tested, and run for real.** After a month away, every core feed was found stale by 38–40 days (last data 2026-08-03) — the concrete proof that "run it when you remember to" doesn't work. Built `scripts/daily_pipeline.py`: detects the real gap (driven by whichever feed lags most, not just the newest), backfills via `backfill.py`'s own resumable function (imported, not reimplemented), shadow-logs any date with both required files that isn't yet logged, and commits/pushes only `data/` with a greppable `[daily-pipeline]` prefix. Single linear script — explicitly no loops, no watcher process (see the `pgrep` self-match entry above; this is the pattern being avoided). `backfill.py` gained retry-with-backoff (3 attempts, 5/20/60s) for transient failures — previously zero retries. `scripts/exploration_helpers.py` added as loaders + a save helper for an optional sense-check plotting stage (chained after the daily fetch, not built into `dashboard.py`) — deliberately does not decide *what* to plot, since that is a judgment call each run, not something to hard-code. `CLAUDE.md` added at repo root: auto-loaded every session including unattended ones, states the GitHub identity check and the daily pipeline's autonomy boundaries (fetch/log only — never edits `BRIEFING.md` or any `.py` file) so a scheduled agent doesn't need this conversation's context to behave correctly.
  **First real run, verified, not just tested:** closed the 40-day gap (159 files fetched, 1 genuine Elexon gap on 2026-08-23), and cleared an 88-day shadow-logging backlog that had built up since `shadow.py` was last run manually. Re-run immediately after confirmed a clean no-op (idempotency holds). Committed as `c26a4d3`.
  **Three real infrastructure problems surfaced and fixed getting the `data/` commit (~3,000 files) to actually push** — worth recording since any of the three alone looked like "the" cause before the others were found: (1) disk was 96% full (9.3GB free) — `mmap` itself timed out inside `git gc`, not just the network; freed by clearing ~22GB of unrelated media from `~/Downloads` (Trash does not free space until emptied — moving files there did nothing until the user emptied it, since Trash lives on the same volume). (2) The repo lived inside `~/Documents`, which has iCloud Desktop & Documents sync enabled — `brctl status` showed iCloud's file-provider daemon actively intercepting individual `.git/objects` files in real time, which independently explains slow `git add`, the `mmap` timeout, and repeated push failures. **Fixed by relocating the repo to `~/repos/vpp-optimiser_ClaudeCode`**, with a symlink left at the old `~/Documents/vpp-optimiser_ClaudeCode` path so nothing else that expects it there breaks. **Any git repo under `~/Documents` or `~/Desktop` on this Mac will hit this same problem — keep dev repos outside both.** (3) 3,312 objects were sitting as loose files, never packed, forcing git to negotiate each individually over HTTPS; consolidated into 2 packfiles via `git gc`. Lesson: three independent, stacked causes can each look sufficient on their own — verify a fix against the actual outcome (a real completed push) rather than stopping at the first plausible explanation.
  **Not yet done:** the cloud schedule itself (next step — via the `schedule` skill, confirmed to run independent of this machine, unlike the local-only `mcp__scheduled-tasks__*` surface which only fires while the desktop app is open). The exploration/sense-check stage is built but not yet exercised or wired into the schedule.

- **v23 — the daily pipeline is now live in the cloud, scheduled daily at 05:00 UTC (6am London).** Routine name "VPP Daily Pipeline" (`trig_016Yr8xD6M4NqEmdfoxtKcrh`), created via the `schedule` skill / `RemoteTrigger` API. Getting here took **4 one-off test runs**, each of which found a real, distinct bug — worth recording all of them, since together they're the actual list of "things that differ between a local Mac and this cloud sandbox" for any future automation on this project:
  1. **No `gh` CLI at all in the cloud sandbox** (not just unauthenticated — the binary doesn't exist). `check_git_identity()` called `subprocess.run(["gh", ...])` unconditionally, which raised `FileNotFoundError` before the function's own exit-code handling ever ran. Fixed by catching `FileNotFoundError` specifically and skipping the check — there's no multi-account ambiguity to guard against when `gh` isn't the auth mechanism at all; the cloud environment authenticates via an injected `GIT_ASKPASS`/`GITHUB_TOKEN` proxy instead, scoped to the connected GitHub account by construction. Verified all three cases (gh present+correct, gh present+wrong account, gh absent) before trusting it, including deliberately faking a wrong-account response to confirm the original safety property survived the fix.
  2. **Cloud checkouts start in detached HEAD**, never on a branch — normal for a fresh cloud clone, never true on a local machine. `git_sync_or_abort()` ran `git pull --ff-only` unconditionally, which fails immediately from detached HEAD with "You are not currently on a branch" — misreported by the function as "repo has diverged from origin" even when it hadn't. Fixed by detecting detached HEAD (`git symbolic-ref -q --short HEAD`, nonzero = detached) and checking out `main` first. Verified against a real reproduction (a scratch clone put into detached HEAD exactly as the cloud does it) — and caught a testing mistake along the way: the first attempt "failed" identically, which turned out to be testing the stale GitHub version of the file, not the local fix. A reminder that testing against a fresh clone needs the code under test copied in, not just cloned.
  3. **Dependencies were never installed** — `pandas` etc. genuinely absent from the sandbox's Python. Not a real gap (`requirements.txt` exists specifically for this) — just missing from the test prompt itself. Fixed by adding `pip install -r requirements.txt` as an explicit step in the routine's prompt.
  4. **Test run 4 passed completely** — sync, dependency install, gap detection all correct. One honest caveat: because all feeds were already current (from same-day manual work), this run's gap-detection correctly no-op'd rather than exercising a real fetch→shadow-log→commit→push cycle end-to-end in the cloud. That exact path was proven for real earlier the same day on the local Mac (the 40-day backfill that produced commit `c26a4d3`), using identical code — so the first genuinely new day the cloud schedule fires (2026-09-14) is the true first full-path proof, not a fresh unknown.
  **Lesson worth generalising**: don't assume "the identity check was the problem" fixes everything just because it was the first error — three of these were each independently sufficient to block the pipeline, and each was found only by actually re-running the real thing after the previous fix, not by reasoning about what "should" now work.

- **Exploration agent test-drive: `classify_day()` mislabels the single best day in 90 days of shadow history.** Ran `exploration_helpers.py` for real against `shadow_pnl.csv` (chart + note in `data/explorations/2026-09-13/`). Found: 23 Jun 2026 (£305,190 net P&L, the best day of all 90) is labeled "amber," not "green," because `classify_day()` requires a negative minimum price for "green" regardless of range — that day had a £475/MWh range (£85–£561) but never went negative. Not a P&L bug (money is computed correctly regardless of label) but a real labeling gap: if `day_type` is ever used as a filter or model feature, this day would be invisible despite being the most profitable on record. Low priority, logged for later. Proves the exploration toolkit works as designed on a first real run — not yet chained into the daily schedule.

- **v25 — daily pipeline split across two platforms; the cloud routine cannot reach Elexon at all.** The first real morning run (2026-09-14) of the v23 cloud routine failed every one of its four feed fetches with a proxy-level 403 to `data.elexon.co.uk`. Root cause, confirmed via the sandbox's own proxy diagnostics: Claude Code cloud sandboxes restrict outbound network access to Anthropic's own APIs and package registries (pypi/npm/jsr) only — arbitrary external hosts are blocked by design, not a bug or a missing flag. **Fix: split the pipeline.** Stage 1 (fetch/backfill/shadow-log/commit) now runs as a **GitHub Actions workflow** (`.github/workflows/daily-pipeline.yml`, 05:00 UTC) — GitHub-hosted runners have no such restriction. Stage 2 (the cloud routine, rescheduled to 06:00 UTC for headroom) now: (1) confirms Stage 1 succeeded via the GitHub Actions API, falling back to a `git log` check for today's `github-actions[bot]` commit if that call is itself blocked; (2) sends exactly one `PushNotification` either way — this is the "alert me if it worked or not" behaviour requested and verified working for both outcomes; (3) only if Stage 1 succeeded, runs the same exploration sense-check as before. `daily_pipeline.py`'s `check_git_identity()` gained a third recognized environment (`GITHUB_ACTIONS == "true"`) alongside the existing local-Mac and cloud-sandbox cases, since Actions authenticates via `GITHUB_TOKEN` with no multi-account ambiguity to guard against.
  **A second, unrelated problem surfaced by the same day's testing:** the cloud routine's own `git push` (for Stage 2's exploration commits) failed with a 403 — "Claude doesn't have GitHub access to eugenekem/vpp-optimiser for your organization" — a GitHub App repository-access issue, not a network block, and not something fixable from inside a routine. Traced to the Claude GitHub App's installation needing its repository access re-confirmed on GitHub's side (Settings → Installations), separate from the claude.ai connector page showing "Connected" (that page only confirms the OAuth link, not per-repo installation scope). User reconnected it; a second end-to-end test run the same day pushed cleanly. Documented here as the fix, not a workaround, since it may recur if the installation is ever modified.
  Both fixes verified with real triggered runs (not assumed): a manual `workflow_dispatch` and a genuine scheduled fire for Actions; two manual `RemoteTrigger` runs for the cloud routine, the second confirming the push fix.

- **v25 — headline-number re-validation: the near-zero-impact prediction confirmed at scale, not just spot-checked.** Re-ran all four scripts flagged after the v24 settlement-date fix (`shadow.py`, `forecast.py backtest`, `forecast_pnl.py`, `cost_sensitivity.py`) against the corrected data and compared line-for-line against the pre-fix figures, rather than trusting the single-date spot-check to generalise.
  - **`forecast.py backtest`** (721 vs 681 days): `reg_demand` skill +24.5% → **+24.1%** (−0.4 pts). Every method's ranking and rough magnitude unchanged.
  - **`forecast_pnl.py`** (721 vs 681 days, cost-aware): `reg_demand` capture 87.1% → **87.4%** (costless) / 86.2% → **86.6%** (cost-aware, +0.4 pts). £/day rose £29,229 → £30,039 (costless) / £26,807 → £27,658 (cost-aware) — a ~3% increase fully explained by 40 extra days of data now included (721 vs 681; the daily pipeline has kept running since the original figures were computed), not by the date fix itself.
  - **`cost_sensitivity.py`** (721 vs 681 days): capture moved by ~0.4 points at every stack (light 86.7%→87.0%, central 86.2%→86.6%, conservative 85.3%→85.7%); the 13-14% spread between light and conservative assumptions is unchanged; the forecast's edge over `mean_7` under cost pressure is unchanged in shape (+7.00/+7.78/+9.14% vs the old +7.28/+7.86/+8.91%). **New conservative figure to quote externally: ~£25,558/day** (was £24,702/day).
  - **`shadow.py`** (91 real shadow-trading days, 15 Jun – 13 Sep 2026, re-run against corrected data via a one-off script since `shadow.py`'s own idempotency check would otherwise skip already-logged dates): total net P&L £7,558,059 → £7,522,978 (**−0.46%**). 86 of 91 days changed by under 5%; 5 days moved more, the largest by £14,780 (2026-09-11) — expected, since the date fix reshuffles 1-2 boundary periods between adjacent days, occasionally landing on a day's cheapest/priciest period. One day's `classify_day()` label flipped (not a money bug, see the exploration-agent finding above). Old file archived to `data/pre_revalidation_backup/`, not deleted.
  **Conclusion: the v24 fix changes almost nothing about the project's actual conclusions.** Capture ratios moved by ~0.4 points everywhere — noise-level, and in the same direction each time, which is itself informative (a real but tiny structural effect, not random). The external-facing headline is now **~£25,558/day (conservative), 85.7% capture** — update anywhere the old £24,702/86.2% figures were being quoted (customer conversations, deck drafts, etc., if any exist outside this repo).

---

*Update to the next version when major decisions or scope changes are agreed.*
