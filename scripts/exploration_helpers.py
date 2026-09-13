import os
from datetime import datetime
from pathlib import Path

import pandas as pd

# --- Sense-check exploration toolkit ---
#
# Not a script that runs on its own — a small set of loaders and a save
# helper for whatever agent is looking at "what's new today" and deciding if
# something's worth a quick chart. Deliberately doesn't decide WHAT to plot;
# that's a judgment call made fresh each day against that day's actual data,
# not something to hard-code here.
#
# This sits alongside dashboard.py, not instead of it — dashboard.py is the
# polished, always-on view; this is for ad-hoc sense-checks when something
# looks like it might be worth a second look.
#
# Output convention: data/explorations/{date}/ — one folder per day something
# actually stood out. No folder at all on a quiet day; this is not meant to
# accumulate empty noise.

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent / "data"
EXPLORATIONS_DIR = DATA_DIR / "explorations"


def load_recent_prices(days=30, feed="market_index"):
    """
    Last N days of a price-shaped feed (market_index or system_prices),
    concatenated with a date column. Returns None if nothing's on disk yet.
    """
    import glob
    import re

    paths = sorted(glob.glob(str(DATA_DIR / f"{feed}_*.csv")))
    if not paths:
        return None

    frames = []
    for path in paths[-days:]:
        m = re.search(rf"{feed}_(\d{{4}}-\d{{2}}-\d{{2}})\.csv$", path)
        if not m:
            continue
        df = pd.read_csv(path)
        df["date"] = m.group(1)
        frames.append(df)

    return pd.concat(frames, ignore_index=True) if frames else None


def load_shadow_history():
    """Full data/shadow_pnl.csv history, or None if it doesn't exist yet."""
    path = DATA_DIR / "shadow_pnl.csv"
    return pd.read_csv(path) if path.exists() else None


def load_forecast_accuracy():
    """Full data/forecast_accuracy.csv history, or None if it doesn't exist yet."""
    path = DATA_DIR / "forecast_accuracy.csv"
    return pd.read_csv(path) if path.exists() else None


def save_finding(title, fig, note_text, date=None):
    """
    Save one chart + a short plain-English note for a day something stood out.

    Writes to data/explorations/{date}/{slug}.png and note.md (appended, so
    multiple findings on the same day share one note file rather than
    overwriting each other).
    """
    date = date or datetime.today().strftime("%Y-%m-%d")
    out_dir = EXPLORATIONS_DIR / date
    out_dir.mkdir(parents=True, exist_ok=True)

    slug = "".join(c if c.isalnum() else "_" for c in title.lower())[:60].strip("_")
    chart_path = out_dir / f"{slug}.png"
    fig.savefig(chart_path, dpi=110, bbox_inches="tight")

    note_path = out_dir / "note.md"
    with open(note_path, "a") as f:
        f.write(f"## {title}\n\n{note_text}\n\n![{title}]({chart_path.name})\n\n---\n\n")

    print(f"Saved finding: {chart_path}")
    return chart_path, note_path
