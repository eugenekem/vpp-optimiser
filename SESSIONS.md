
---
## Session — 2026-04-08 18:34

### Built this session: battery model, rules-based optimiser, DA optimiser, P&L calculator, briefing automation
- 

### Decisions made: capacity reservation rules, risk team added, war room dashboard
- 

### Next session: risk layer (VaR, scenario analysis)
- 


---
## Session — 2026-04-08 18:39

### Built this session:
- 

### Decisions made:
- 

### Next session:
- 


---
## Session — 2026-04-10 22:58

### Built this session:
- 

### Decisions made:
- 

### Next session:
- 


---
## Session — 2026-04-12 18:26

### Built this session:
- dispatch schedule view, fixed signal logic, dashboard v2 complete

### Decisions made:
- green day triggered by negative prices not just spread size

### Next session:
- intraday optimiser layer OR LP optimisation upgrade


---
## Session — 2026-04-12 18:28

### Built this session:
- 

### Decisions made:
- 

### Next session:
- 


---
## Session — 2026-04-14 22:18

### Built this session:
- 

### Decisions made:
- 

### Next session:
- 


---
## Session — 2026-04-14 22:23

### Built this session:
- 

### Decisions made:
- 

### Next session:
- 


---
## Session — 2026-04-14 22:24

### Built this session:
- 

### Decisions made:
- 

### Next session:
- 

---
## Session — 2026-04-23

### Built this session:
- LP optimiser with PuLP (optimiser_lp.py)
- Comparison harness (compare_optimisers.py)
- NOTES.md for technical decisions log

### Decisions made:
- Fixed energy balance bug (missing 0.5h time factor)
- Validated LP: +12.2% vs rules-based, +24.1% vs forward-DA
- Cleaned README and BRIEFING for professional framing
- Personal career positioning moved out of repo

### Next session:
- Integrate LP optimiser into dashboard OR build intraday layer
---
## Session — 2026-04-29 22:57

### Built this session:
- Dashboard LP integration — LP schedule now drives P&L, risk, and dispatch sections
- compute_lp_pnl() derives P&L directly from LP schedule without re-running pnl.py
- LP preferred throughout, DA optimiser as fallback
- New charts per asset: SOC curve across 48 periods, dispatch vs price overlay
- LP vs DA comparison bar chart with uplift % caption
- Decimal formatting fix on dispatch table
- 

### Decisions made:
- DA fallback to be removed once LP is permanent daily default
- Charts confirmed LP is behaving correctly — charges at price troughs, discharges at peaks
- 

### Next session:
- 


---
## Session — 2026-04-30 21:53

### Built this session:
- config.py — single source of truth for DA/ID/BM capacity splits
- Updated optimiser_lp.py and optimiser_id.py to import from config
- optimiser_bm.py — BM layer using real SSP/SBP prices from Elexon BMRS
- Three-way capacity split: Battery 1 DA=40% ID=30% BM=30%, others DA=50% ID=20% BM=30%

### Decisions made:
- BM needs its own capacity slice — can't share with ID
- Config centralises all splits so one change updates all three layers
- SSP=SBP today indicates balanced system — BM spread behaviour to observe on volatile days



### Next session:
- 


---
## Session — 2026-04-30 21:55

### Built this session:
- 

### Decisions made:
- 

### Next session:
- 

