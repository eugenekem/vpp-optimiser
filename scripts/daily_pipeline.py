import glob
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# --- Daily unattended pipeline ---
#
# One linear run, no loops, no polling, no watcher process left behind.
# (This project has a history of self-referential `pgrep` wait loops hanging
# for hours because they matched their own command line — this script is
# deliberately the opposite: it runs once, reports, and exits.)
#
# What it does, in order:
#   1. Confirms the right GitHub identity is active (eugenekem, not any other
#      authenticated account) — a wrong-identity push fails silently useful
#      only to a human watching; this catches it up front instead.
#   2. Syncs the repo (fetch + fast-forward pull). Refuses to guess if that's
#      not possible — a merge conflict is a human decision, not this script's.
#   3. Backfills whatever gap exists in the four core feeds, reusing
#      backfill.py's own resumable skip-if-exists logic directly.
#   4. Runs shadow.py for any date that now has both required files but
#      isn't yet shadow-logged.
#   5. Commits and pushes only data/, with a greppable [daily-pipeline] tag.
#      Safe no-op if there's nothing new (e.g. fired twice in a day).
#
# Never touches BRIEFING.md or any .py file. Never force-pushes or retries
# beyond backfill.py's own per-date retry. A push conflict is reported, not
# resolved automatically.
#
# Usage:
#   python daily_pipeline.py

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
MODELS_DIR = REPO_ROOT / "models"
DATA_DIR = REPO_ROOT / "data"

CORE_FEEDS = ["market_index", "system_prices", "wind_solar", "demand"]
MAX_BACKFILL_DAYS = 90  # safety cap per run; a larger real gap just takes a few runs to close
GIT_IDENTITY = "eugenekem"  # the only account allowed to push this repo — see BRIEFING.md known issues
MAIN_BRANCH = "main"


def run(cmd, cwd=None, check=True):
    """subprocess.run with sane defaults for this script's needs."""
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n"
            f"stdout: {result.stdout.strip()}\nstderr: {result.stderr.strip()}"
        )
    return result


def check_git_identity():
    """
    Abort rather than push as the wrong account. This repo has had two
    authenticated GitHub identities in the same environment before, and only
    one (eugenekem) has write access — the other fails with a 403 that's easy
    to miss in an unattended run.

    Only meaningful where `gh` CLI multi-account login is how auth works (the
    maintainer's local Mac). A cloud sandbox has no `gh` binary at all and
    authenticates via an injected token/proxy instead (GIT_ASKPASS +
    GITHUB_TOKEN) — there's no multi-account ambiguity to catch there, since
    that auth is scoped to this environment's own connected GitHub account by
    construction. Verified via a real one-off cloud test run (2026-09-13):
    `gh` absent, but `git ls-remote origin` succeeded and push auth was
    correctly configured through the proxy. Confirmed by running the actual
    test, not assumed.
    """
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print("ℹ️  Running in GitHub Actions — skipping the multi-account "
              "identity check (not applicable here; push auth is scoped to "
              "this repo via GITHUB_TOKEN, so there's no ambiguity to catch).")
        return

    try:
        result = run(["gh", "auth", "status"], check=False)
    except FileNotFoundError:
        print("ℹ️  'gh' not installed in this environment — skipping the "
              "multi-account identity check (not applicable here; auth is "
              "handled by this environment's own git credentials instead).")
        return
    output = result.stdout + result.stderr

    active_line = None
    current_account = None
    for line in output.splitlines():
        m = re.search(r"account (\S+)", line)
        if m:
            current_account = m.group(1)
        if "Active account: true" in line:
            active_line = current_account

    if active_line != GIT_IDENTITY:
        raise RuntimeError(
            f"Wrong GitHub identity active: '{active_line}', expected "
            f"'{GIT_IDENTITY}'. Refusing to proceed rather than fail silently "
            f"on push. Run: gh auth switch --user {GIT_IDENTITY}"
        )
    print(f"✅ GitHub identity confirmed: {GIT_IDENTITY}")


def git_sync_or_abort():
    print("Syncing repo...")
    run(["git", "fetch"], cwd=REPO_ROOT)

    # A fresh cloud checkout starts in detached HEAD (no current branch) -
    # different from a local machine, which is always on a branch. From
    # detached HEAD, `git pull --ff-only` fails immediately with "You are
    # not currently on a branch", which this function used to misreport as
    # "repo has diverged" even when origin hadn't diverged at all. Found via
    # a real cloud test run, not assumed. Checking out the branch explicitly
    # first (safe: it's the branch this whole pipeline works on) makes both
    # environments behave identically from here on.
    branch_check = run(["git", "symbolic-ref", "-q", "--short", "HEAD"],
                       cwd=REPO_ROOT, check=False)
    if branch_check.returncode != 0:
        print(f"  Detached HEAD detected — checking out {MAIN_BRANCH}...")
        checkout = run(["git", "checkout", MAIN_BRANCH], cwd=REPO_ROOT, check=False)
        if checkout.returncode != 0:
            raise RuntimeError(
                f"Could not check out '{MAIN_BRANCH}' from detached HEAD.\n"
                f"{checkout.stderr.strip()}"
            )

    result = run(["git", "pull", "--ff-only"], cwd=REPO_ROOT, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"git pull --ff-only failed — repo has diverged from origin. "
            f"Not auto-merging; a human needs to resolve this.\n{result.stderr.strip()}"
        )
    print(f"  {result.stdout.strip() or 'Already up to date.'}")


def latest_date_for(prefix):
    """Most recent date on disk for a feed, or None if there's no data at all."""
    dates = []
    for path in glob.glob(str(DATA_DIR / f"{prefix}_*.csv")):
        m = re.search(rf"{prefix}_(\d{{4}}-\d{{2}}-\d{{2}})\.csv$", path)
        if m:
            dates.append(m.group(1))
    return max(dates) if dates else None


def compute_gap():
    """
    The window to backfill: the day after the OLDEST "latest date" across the
    four core feeds (a lagging feed should drive the window, not the newest),
    through yesterday, capped at MAX_BACKFILL_DAYS.

    Returns (start, end) as "YYYY-MM-DD" strings, or (None, None) if every
    feed is already current through yesterday.
    """
    yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    latest_per_feed = {feed: latest_date_for(feed) for feed in CORE_FEEDS}
    print("Latest date on disk per feed:")
    for feed, date in latest_per_feed.items():
        print(f"  {feed:<14} {date or '(none)'}")

    missing_entirely = [f for f, d in latest_per_feed.items() if d is None]
    if missing_entirely:
        raise RuntimeError(
            f"No data at all for: {', '.join(missing_entirely)}. "
            f"That's not a normal daily gap — needs a human to check the repo "
            f"state (e.g. was data/ actually pulled?) rather than blindly "
            f"backfilling {MAX_BACKFILL_DAYS} days as if this were day one."
        )

    oldest_latest = min(latest_per_feed.values())
    if oldest_latest >= yesterday:
        return None, None  # everything's current

    start = (datetime.strptime(oldest_latest, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    end = yesterday

    span_days = (datetime.strptime(end, "%Y-%m-%d") - datetime.strptime(start, "%Y-%m-%d")).days
    if span_days > MAX_BACKFILL_DAYS:
        capped_end = (datetime.strptime(start, "%Y-%m-%d") + timedelta(days=MAX_BACKFILL_DAYS)).strftime("%Y-%m-%d")
        print(f"  Gap is {span_days} days — capping this run to {MAX_BACKFILL_DAYS} "
              f"days ({start} to {capped_end}); the rest closes over subsequent runs.")
        end = capped_end

    return start, end


def run_backfill(start, end):
    """Import and call backfill.py's own function directly — reuses its
    resumable skip-if-exists logic rather than duplicating it."""
    sys.path.insert(0, str(SCRIPT_DIR))
    original_cwd = os.getcwd()
    os.chdir(SCRIPT_DIR)  # backfill.py's DATA_DIR="../data" is relative to here
    try:
        import backfill as backfill_module
        return backfill_module.backfill(start, end)
    finally:
        os.chdir(original_cwd)


def candidate_shadow_dates(days_back=MAX_BACKFILL_DAYS):
    """
    Every date in the last `days_back` days that has BOTH files dispatcher.py
    needs (market_index, system_prices) — independent of compute_gap(), so a
    date whose fetch succeeded on a prior run but whose shadow-log step didn't
    self-heals here.
    """
    yesterday = datetime.today() - timedelta(days=1)
    candidates = []
    for i in range(days_back):
        date = (yesterday - timedelta(days=i)).strftime("%Y-%m-%d")
        if (DATA_DIR / f"market_index_{date}.csv").exists() and \
           (DATA_DIR / f"system_prices_{date}.csv").exists():
            candidates.append(date)
    return sorted(candidates)


def already_shadow_logged_dates():
    log_path = DATA_DIR / "shadow_pnl.csv"
    if not log_path.exists():
        return set()
    import pandas as pd
    return set(pd.read_csv(log_path)["date"].astype(str))


def run_shadow_for(date):
    result = run(["python", "shadow.py", date], cwd=MODELS_DIR, check=False)
    print(result.stdout.strip())
    if result.returncode != 0:
        print(f"  ⚠️  shadow.py {date} exited nonzero:\n{result.stderr.strip()}")
        return False
    return True


def commit_and_push(summary):
    run(["git", "add", "data/"], cwd=REPO_ROOT)
    diff_check = run(["git", "diff", "--cached", "--quiet"], cwd=REPO_ROOT, check=False)
    if diff_check.returncode == 0:
        print("Nothing new to commit.")
        return
    run(["git", "commit", "-m", f"[daily-pipeline] {summary}"], cwd=REPO_ROOT)
    push_result = run(["git", "push"], cwd=REPO_ROOT, check=False)
    if push_result.returncode != 0:
        print(f"⚠️  Push failed — local commit is preserved, NOT retrying or "
              f"force-pushing. A human needs to resolve this:\n{push_result.stderr.strip()}")
        sys.exit(1)
    print("Pushed.")


def main():
    print("=" * 68)
    print(f"Daily pipeline — {datetime.today().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 68)

    check_git_identity()
    git_sync_or_abort()

    start, end = compute_gap()
    fetch_summary = "no gap — feeds already current"
    if start:
        print(f"\nBackfilling {start} to {end}...")
        counts = run_backfill(start, end)
        fetch_summary = f"backfilled {start}..{end} ({counts['ok']} fetched, {counts['fail']} failed)"
    else:
        print("\nAll core feeds already current through yesterday.")

    print("\nChecking for un-shadow-logged days...")
    before = already_shadow_logged_dates()
    for date in candidate_shadow_dates():
        if date not in before:
            run_shadow_for(date)
    after = already_shadow_logged_dates()
    newly_logged = len(after) - len(before)
    print(f"Shadow-logged {newly_logged} new day(s).")

    summary = f"{fetch_summary}; shadow-logged {newly_logged} day(s)"
    print(f"\n{summary}")

    commit_and_push(summary)
    print("\nDone.")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"\n❌ {e}")
        sys.exit(1)
