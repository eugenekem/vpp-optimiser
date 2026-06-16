import subprocess
import sys
from datetime import datetime

# -----------------------------------------------------------
# update_briefing.py
#
# This script does NOT overwrite BRIEFING.md content.
# BRIEFING.md is edited directly (by you and Claude) before running this.
#
# This script only:
#   1. Appends a session entry template to SESSIONS.md
#   2. Commits whatever is currently on disk (BRIEFING.md, code, etc.)
#   3. Pushes to GitHub
#
# Usage: python update_briefing.py
# -----------------------------------------------------------


def get_briefing_version():
    """Read the version number directly from BRIEFING.md's first lines."""
    try:
        with open("BRIEFING.md", "r") as f:
            for line in f:
                if line.strip().startswith("**Version:**"):
                    return line.split("**Version:**")[1].strip()
    except FileNotFoundError:
        pass
    return "unknown"


def update_session_log():
    version = get_briefing_version()
    entry = f"""
---
## Session — {datetime.today().strftime("%Y-%m-%d %H:%M")} (BRIEFING v{version})

### Built this session:
-

### Decisions made:
-

### Next session:
-

"""
    with open("SESSIONS.md", "a") as f:
        f.write(entry)
    print(f"✅ SESSIONS.md updated — fill in what you built and decided (detected BRIEFING v{version})")
    return version


def git_push(version):
    commands = [
        ["git", "add", "."],
        ["git", "commit", "-m", f"Update briefing to v{version} and session log"],
        ["git", "push"]
    ]
    for cmd in commands:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            # "nothing to commit" is not a real error — handle gracefully
            if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
                print("ℹ️  Nothing new to commit (BRIEFING.md/code unchanged since last push)")
                continue
            print(f"Git error: {result.stderr}")
            sys.exit(1)
    print("✅ Pushed to GitHub")


if __name__ == "__main__":
    print("ℹ️  This script does NOT write BRIEFING.md content.")
    print("   Make sure you've already saved your updated BRIEFING.md before running this.\n")

    version = update_session_log()
    git_push(version)
    print(f"\n✅ Done — BRIEFING.md v{version} committed and pushed to GitHub")
    print("📝 Open SESSIONS.md and fill in what you built and decided this session")
