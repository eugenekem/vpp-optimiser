# VPP Optimiser — orientation for Claude Code

This file is loaded automatically at the start of every session, including unattended scheduled ones. It's deliberately short — **`BRIEFING.md` is the single source of truth** for project status, results, and known issues. Read it before doing anything nontrivial. Don't duplicate its content here; update it there, not here.

## What this is

A battery dispatch optimiser for the GB energy market (5 batteries, ~145 MW), built toward a real startup — see `BRIEFING.md`'s "startup ambition" framing. Fetches real Elexon market data, forecasts day-ahead prices, and optimises charge/discharge schedules. Currently backtesting and shadow-logging only — **no real trades have ever been placed**, and no backtest number should be presented externally without the caveats in `BRIEFING.md` section 10/10d (perfect-foresight vs. cost-aware, capture ratio vs. £/day).

## GitHub identity — check this before pushing, every session

This environment has more than one authenticated GitHub account. **Only `eugenekem` has write access to this repo.** Run `gh auth status` and confirm `eugenekem` shows `Active account: true` before any push. If a different account is active, switch first: `gh auth switch --user eugenekem`. A push as the wrong account fails with a 403 — in an unattended run, that failure has no one to notice it.

## If you are the unattended daily pipeline

You are running `scripts/daily_pipeline.py`, followed by a sense-check exploration pass using `scripts/exploration_helpers.py` (as of v23, this is a standard second stage, not optional — see the routine's own prompt for the exact two-stage instructions). Your boundaries, non-negotiable:

- **Do not edit `BRIEFING.md` or any `.py` file.** Fetch and log only.
- **Do not invoke `backfill.py` or `shadow.py` directly with custom arguments** — let `daily_pipeline.py` orchestrate them.
- **Do not retry beyond what the scripts already do**, and never force-push.
- **Do not start any background or watcher process.** Run once, report, exit. (This project has a real history of a `pgrep`-based wait loop matching its own command line and hanging for 9 hours — see `BRIEFING.md` known issues. Don't repeat that pattern in any form.)
- If something fails, report the error and stop. Don't attempt to fix code.
- Exploration output goes only in `data/explorations/{date}/` — charts + a short note, nothing elsewhere.

## Commit convention

Automated daily-pipeline commits are prefixed `[daily-pipeline]` — greppable via `git log --grep '\[daily-pipeline\]'` — so they're always distinguishable from manual work at a glance.

## Data

`data/*.csv` is tracked in git (since v22) — this is deliberate, not an oversight, so the daily pipeline has history to check against on a fresh checkout. `data/raw/` remains gitignored.

## Key entry points

| Task | Script |
|---|---|
| Fetch one day of one feed | `scripts/fetch_*.py <date>` |
| Backfill a date range | `scripts/backfill.py [days \| start end]` |
| Full unattended daily run | `scripts/daily_pipeline.py` |
| Log one day's shadow P&L | `models/shadow.py [date]` |
| Forecast tomorrow's prices | `models/forecast.py` |
| Score forecast accuracy | `models/forecast.py backtest` |
| Score forecast against real P&L | `models/forecast_pnl.py` |
| Cost sensitivity sweep | `models/cost_sensitivity.py` |
