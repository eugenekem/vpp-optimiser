import subprocess
import sys
from datetime import datetime

# -----------------------------------------------------------
# update_briefing.py
#
# This script does NOT overwrite BRIEFING.md content.
# BRIEFING.md is edited directly (by you and Claude) before running this.
#
# This script:
#   1. Reads today's git commits and uses them to auto-fill the session log
#   2. Prompts for decisions and next session (optional — press Enter to skip)
#   3. Appends the completed session entry to SESSIONS.md
#   4. Commits everything and pushes to GitHub
#
# Usage: python update_briefing.py
# -----------------------------------------------------------


def get_briefing_version():
    """Read the version number directly from BRIEFING.md."""
    try:
        with open("BRIEFING.md", "r") as f:
            for line in f:
                if line.strip().startswith("**Version:**"):
                    return line.split("**Version:**")[1].strip()
    except FileNotFoundError:
        pass
    return "unknown"


def get_todays_commits():
    """
    Pull git log commits from today only.
    Returns a list of commit message strings.
    """
    today = datetime.today().strftime("%Y-%m-%d")
    result = subprocess.run(
        ["git", "log", "--oneline", f"--after={today} 00:00", "--no-merges"],
        capture_output=True, text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    lines = result.stdout.strip().split("\n")
    # Strip the short hash prefix from each line
    messages = [" ".join(line.split()[1:]) for line in lines if line.strip()]
    return messages


def prompt_optional(label):
    """Prompt user for optional input. Returns empty string if skipped."""
    print(f"\n{label}")
    print("(Press Enter to skip)")
    lines = []
    while True:
        line = input("> ").strip()
        if line == "":
            break
        lines.append(f"- {line}")
    return "\n".join(lines) if lines else "- (not recorded)"


def update_session_log(version):
    commits = get_todays_commits()

    if commits:
        built_section = "\n".join(f"- {c}" for c in commits)
        print(f"\n✅ Auto-filled from today's git commits:\n{built_section}")
    else:
        print("\n⚠️  No commits found for today — enter what you built manually:")
        built_section = prompt_optional("What did you build this session?")

    print("\nWhat decisions were made? (one per line, Enter blank line to finish)")
    decisions = prompt_optional("Decisions:")

    print("\nWhat's next session's focus? (one per line, Enter blank line to finish)")
    next_session = prompt_optional("Next session:")

    entry = f"""
---
## Session — {datetime.today().strftime("%Y-%m-%d %H:%M")} (BRIEFING v{version})

### Built this session:
{built_section}

### Decisions made:
{decisions}

### Next session:
{next_session}

"""
    with open("SESSIONS.md", "a") as f:
        f.write(entry)
    print(f"\n✅ SESSIONS.md updated (BRIEFING v{version})")


def git_push(version):
    commands = [
        ["git", "add", "."],
        ["git", "commit", "-m", f"Update briefing to v{version} and session log"],
        ["git", "push"]
    ]
    for cmd in commands:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
                print("ℹ️  Nothing new to commit")
                continue
            print(f"Git error: {result.stderr}")
            sys.exit(1)
    print("✅ Pushed to GitHub")


if __name__ == "__main__":
    print("ℹ️  This script does NOT write BRIEFING.md content.")
    print("   Make sure you've already saved your updated BRIEFING.md before running.\n")

    version = get_briefing_version()
    update_session_log(version)
    git_push(version)
    print(f"\n✅ Done — session logged and pushed (BRIEFING v{version})")
