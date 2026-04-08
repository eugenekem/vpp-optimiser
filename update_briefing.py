import subprocess
import sys
from datetime import datetime

# -----------------------------------------------------------
# update_briefing.py
# Run this script to update BRIEFING.md and push to GitHub
# Usage: python update_briefing.py
# -----------------------------------------------------------

BRIEFING_CONTENT = '''# Virtual Power Plant (VPP) Project — Master Briefing Document
**Version:** 6.0
**Date:** April 2026
**Status:** In Progress — P&L Calculator Complete, Risk Layer Next

---

## 1. Project Goal & Ambition

Build a realistic Virtual Power Plant (VPP) simulation model that mirrors real-world asset optimisation operations in the GB energy market. The ultimate goal is to develop the skills, processes, and team workflows needed to operate as a professional VPP optimisation and trading desk.

This is not a quick-build project. It is being developed carefully and deliberately to create genuine operational experience — with ambition to use this platform as a portfolio piece for roles at companies like Statkraft and EDF Renewables, or as the foundation for a startup.

---

## 2. Business Vision

Position as a team of asset optimisers, traders, short-term planners and risk analysts operating across multiple GB wholesale and balancing markets.

The platform will be smart, polished, and credible — grounded in real GB market data, real asset constraints, and real market structure.

Vision: A full trading operations platform — a war room dashboard where the user sits as head of optimisation, sees all assets live, manages positions, reviews P&L, monitors risk, and makes decisions alongside the optimiser.

**This project is not initially focused on profit.** The primary objective is to master daily net arbitrage across markets before layering in cost of investment and financial performance analysis.

---

## 3. Asset Portfolio

| Asset | Type | Duration | MW (Battery) | MW (Solar) | Region | DNO |
|---|---|---|---|---|---|---|
| Battery 1 | Standalone | 2-hour | 10 MW | — | North Scotland | SSEN Transmission |
| Battery 2 | Standalone | 4-hour | 25 MW | — | North England | Northern Powergrid |
| Battery 3 | Standalone | 4-hour | 50 MW | — | South England | National Grid (NGET) |
| Battery 4 | Co-located + Solar | 4-hour | 20 MW | 15 MW | South Scotland | SP Transmission |
| Battery 5 | Co-located + Solar | 4-hour | 40 MW | 30 MW | South England | National Grid (NGET) |

**Total battery capacity:** ~145 MW | **Total solar capacity:** 45 MW

**DA Capacity Reservation Rules:**
- Battery 1: 50% reserved — nimble, prioritise intraday and BM
- Battery 2-5: 30% reserved — balanced across markets

---

## 4. Target Markets

| Market | Venue | Notes |
|---|---|---|
| Day Ahead (DA) | EPEX / N2EX | Gate closure 12:00 noon day before |
| Intraday (ID) | Continuous | Approximated via DA + BM spread in early phases |
| Balancing Mechanism (BM) | Elexon / NESO | Core market for all assets |
| Ancillary Services | NESO | DC High and DC Low — primary focus |

**EFA blocks:** EFA1=23-03, EFA2=03-07, EFA3=07-11, EFA4=11-15, EFA5=15-19, EFA6=19-23

---

## 5. Data Sources & Pipelines

| Data | Source | Script | Status |
|---|---|---|---|
| System prices (SSP/SBP) | Elexon BMRS | `fetch_bmrs.py` | ✅ Live |
| Market index prices (MID) | Elexon BMRS | `fetch_da_prices.py` | ✅ Live |
| DC forecast (4-day) | NESO Data Portal | `fetch_dc_tenders.py` | ✅ Live |
| Weather | Open-Meteo | `fetch_weather.py` | ✅ Live |
| Solar generation | Sheffield Solar PV_Live | `fetch_solar.py` | ✅ Live |

---

## 6. Tech Stack

| Component | Tool | Notes |
|---|---|---|
| Core language | Python 3.12.4 | Confirmed |
| Data storage | CSV → SQLite | Currently CSV |
| Dashboard | Streamlit | War room operations platform |
| Optimisation engine | PuLP / Google OR-Tools | LP layer after rules-based |
| Version control | GitHub | github.com/eugenekem/vpp-optimiser |

---

## 7. Optimiser Architecture

| File | Layer | Status |
|---|---|---|
| `battery.py` | Asset model | ✅ Built |
| `optimiser.py` | Rules-based optimiser | ✅ Built |
| `optimiser_da.py` | Forward-looking DA optimiser | ✅ Built |
| `pnl.py` | P&L calculator | ✅ Built |
| `optimiser_id.py` | Intraday layer | ⬜ To do |
| `optimiser_bm.py` | BM layer | ⬜ To do |
| `risk.py` | Risk layer (VaR, scenarios) | ⬜ To do |
| `dispatcher.py` | Coordinates all layers | ⬜ To do |

---

## 8. Team Structure

| Role | Responsibility |
|---|---|
| Optimisers | Asset dispatch, charge/discharge scheduling, market stacking |
| Traders | DA and intraday position management, DC tender management |
| Short-term Planners | Intraday and BM real-time decisions |
| Risk | Exposure monitoring, VaR, scenario analysis, price risk |

---

## 9. Operating Model

- One day behind real time using published data
- DA gate closure anchor: 12:00 noon day before delivery
- Market sequence: DA → Intraday → BM → DC delivery
- Settlement reconciliation step after each trading day

---

## 10. Development Phases

- **Phase 1** — Historical Replay
- **Phase 2** — Shadow Trading (Priority Phase)
- **Phase 3** — Live Single Asset (Battery 1, BM first)
- **Phase 4** — Scale Up
- **Phase 5** — Residential Solar Aggregation (parked)
- **Phase 6+** — International markets, AI optimisation, full commercial operation

---

## 11. Progress To Date

| Task | Status |
|---|---|
| Project folder and GitHub repo | ✅ Done |
| Python environment (3.12.4) | ✅ Done |
| All 5 data pipelines | ✅ Done |
| Battery asset model | ✅ Done |
| Rules-based optimiser | ✅ Done |
| Forward-looking DA optimiser | ✅ Done |
| P&L calculator | ✅ Done |
| Risk layer (VaR, scenario analysis) | ⬜ Next |
| Intraday optimiser layer | ⬜ To do |
| BM optimiser layer | ⬜ To do |
| War room Streamlit dashboard | ⬜ To do |
| Settlement reconciliation | ⬜ To do |
| Phase 1 historical replay | ⬜ To do |
| Phase 2 shadow trading | ⬜ To do |

---

## 12. Key Principles

- Plan carefully before executing
- Build modularly — each layer plugs in independently
- Do not double-commit asset capacity across markets
- Risk-adjusted revenue is the target, not just maximum revenue
- No paid data subscriptions in the short to medium term
- Academic research will inform optimisation — pause and read when Claude flags it
- Paste this document at the start of every new Claude session

---

## 13. Open Questions / To Decide Later

- Export and import limits per asset
- Battery degradation modelling approach
- Gantt chart / project timeline
- Cost of investment analysis — Phase 4 onwards
- LP optimisation upgrade — after rules-based layer is validated

---

*Update to Version 7 when new decisions or scope changes are agreed.*
'''

SESSION_ENTRY = f"""
---
## Session — {datetime.today().strftime("%Y-%m-%d %H:%M")}

### Built this session:
- 

### Decisions made:
- 

### Next session:
- 

"""

def write_briefing():
    with open("BRIEFING.md", "w") as f:
        f.write(BRIEFING_CONTENT)
    print("✅ BRIEFING.md updated")

def update_session_log():
    with open("SESSIONS.md", "a") as f:
        f.write(SESSION_ENTRY)
    print("✅ SESSIONS.md updated — fill in what you built and decided")

def git_push(version):
    commands = [
        ["git", "add", "."],
        ["git", "commit", "-m", f"Update briefing to v{version} and session log"],
        ["git", "push"]
    ]
    for cmd in commands:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Git error: {result.stderr}")
            sys.exit(1)
    print("✅ Pushed to GitHub")

if __name__ == "__main__":
    version = input("Enter new briefing version number (e.g. 7): ").strip()
    write_briefing()
    update_session_log()
    git_push(version)
    print(f"\n✅ Done — BRIEFING.md v{version} saved and pushed to GitHub")
    print("📝 Open SESSIONS.md and fill in what you built and decided this session")