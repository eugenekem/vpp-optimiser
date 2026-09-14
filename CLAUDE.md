# VPP Optimiser — orientation for Claude Code

This file is loaded automatically at the start of every session, including unattended scheduled ones. It's deliberately short — **`BRIEFING.md` is the single source of truth** for project status, results, and known issues. Read it before doing anything nontrivial. Don't duplicate its content here; update it there, not here.

## What this is

A battery dispatch optimiser for the GB energy market (5 batteries, ~145 MW), built toward a real startup — see `BRIEFING.md`'s "startup ambition" framing. Fetches real Elexon market data, forecasts day-ahead prices, and optimises charge/discharge schedules. Currently backtesting and shadow-logging only — **no real trades have ever been placed**, and no backtest number should be presented externally without the caveats in `BRIEFING.md` section 10/10d (perfect-foresight vs. cost-aware, capture ratio vs. £/day).

## GitHub identity — check this before pushing, every session

This environment has more than one authenticated GitHub account. **Only `eugenekem` has write access to this repo.** Run `gh auth status` and confirm `eugenekem` shows `Active account: true` before any push. If a different account is active, switch first: `gh auth switch --user eugenekem`. A push as the wrong account fails with a 403 — in an unattended run, that failure has no one to notice it.

In GitHub Actions specifically, this check doesn't apply — push auth there is scoped to the repo via `GITHUB_TOKEN`, not `gh auth login`, so there's no multi-account ambiguity (`daily_pipeline.py`'s `check_git_identity()` skips itself automatically when `GITHUB_ACTIONS=true`).

## Two-part daily pipeline (as of v25)

**Stage 1 (fetch/backfill/shadow-log/commit)** runs in **GitHub Actions** (`.github/workflows/daily-pipeline.yml`, 05:00 UTC), not the cloud routine — Claude Code cloud sandboxes restrict outbound network access to Anthropic APIs and package registries only, so they can never reach `data.elexon.co.uk` (confirmed via a real failed run, 2026-09-14). GitHub-hosted runners have no such restriction.

**Stage 2 (check-in + exploration sense-check)** runs in the **cloud routine** ("VPP Daily Pipeline", 06:00 UTC — an hour after Actions, for headroom). If you are that routine:

1. `git pull`, then confirm Stage 1 succeeded — try the GitHub Actions API first, fall back to checking for today's `github-actions[bot]` commit in `git log` if that network call is blocked (expected in this sandbox, not a bug).
2. Send exactly one `PushNotification` either way (success or failure) — this is the user's requested "did it work today" alert.
3. Only if Stage 1 succeeded: run the exploration sense-check using `scripts/exploration_helpers.py`, same as before.

Boundaries, non-negotiable (both stages, wherever they run):

- **Do not edit `BRIEFING.md`, `CLAUDE.md`, or any `.py` file.**
- **Do not invoke `backfill.py`, `shadow.py`, or `daily_pipeline.py` directly with custom arguments.**
- **Do not retry beyond what's already specified**, and never force-push.
- **Do not start any background or watcher process.** Run once, report, exit. (This project has a real history of a `pgrep`-based wait loop matching its own command line and hanging for 9 hours — see `BRIEFING.md` known issues. Don't repeat that pattern in any form.)
- If something fails, report the error and stop. Don't attempt to fix code.
- Exploration output goes only in `data/explorations/{date}/` — charts + a short note, nothing elsewhere.

**Known issue (open, 2026-09-14):** the cloud routine's own `git push` (Stage 2's exploration commits) is currently failing with a 403 — "Claude doesn't have GitHub access to eugenekem/vpp-optimiser for your organization." This is separate from the Elexon network block above and needs the user to reconnect the Claude GitHub App (https://github.com/apps/claude/installations/select_target or https://claude.ai/customize/connectors). Until fixed, exploration findings are computed correctly but may fail to push — the routine will report this in its PushNotification each morning rather than fail silently.

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
