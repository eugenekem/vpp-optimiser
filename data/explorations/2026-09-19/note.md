## Weakest green day on record: 2026-09-18

**What stood out:** 2026-09-18 is classified a "green" day (`day_type`, the highest-volatility bucket used for days with a wide price range and a negative dip — today's range was £-0.50 to £167.78) but earned only £71,199 net P&L, the lowest of all 14 green days in the full shadow-log history (mean £147,697, previous low £93,896 on 2026-09-04).

**Why:** it isn't a simple story of "prices were calmer than usual" — price std on 09-18 (£53.8) is close to 09-17's (£57.8, which earned £140,480, almost double). What stands out instead is that every leg is weak simultaneously: da_net £43,808 (lowest of any green day), id_net £9,931, and bm_net £17,460 are all well below their typical green-day levels. 09-18 is also the third consecutive day of falling mean price (£154 → £99 → £79 for 09-16/17/18) and the second straight day with a negative price dip, so the market itself has been trending toward thinner, cheaper conditions — which can compress arbitrage margin even on a day the classifier still calls "green" because of the range/negative-price rule.

**Is it a data quality issue?** No — both days have complete 48/48 settlement periods, and demand/price feeds look normal in shape. This also isn't the cost-aware effect on its own: 09-18's cost_ratio (total_cost / total_revenue = 0.28) sits in the middle of the three cost_aware=True days so far (0.19–0.58), not at the high end.

**Urgency:** not urgent, not code-breaking. Flagging because the day_type label (green/amber/red) is being used elsewhere as a quick filter for "how good a trading day was" (see the 2026-09-13 finding on the same classifier), and this is now the second instance of that label mapping to a P&L outcome outside its usual range — worth a look once a few more cost_aware days accumulate, to see whether this is a one-off quiet green day or the start of the classifier's range/negative-price rule becoming a weaker predictor of P&L now that dispatch is forecast-driven and cost-aware rather than perfect-foresight.

![Weakest green day on record: 2026-09-18](weakest_green_day_on_record__2026_09_18.png)

---

## Wind glut drives 2026-09-19 to lowest price of the run

**What stood out:** 2026-09-19's mean market-index price was £25.70/MWh — by far the lowest of the last 21 days (previous low £57.61 on 2026-09-05, next-lowest in this run £78.70 on 2026-09-18). Prices sat between -£3.26 and +£14.49 for the first 16 hours of the day (settlement periods 1-32), then spiked to £137.30 around 8pm before fading. This is the fourth straight day of falling mean price (£154 -> £99 -> £79 -> £26 for 09-16 through 09-19), continuing the trend the 09-18 finding flagged as worth watching.

**Why:** wind output ran 22.6-26.8 GW (peaking near 34 GW with solar) for nearly the entire day, comfortably exceeding the ~19-23 GW national demand seen overnight and into the afternoon. Supply from wind alone covered demand for most of the day, which is the standard mechanism for GB's near-zero/negative merit-order prices - this is a real, explainable market event (a wind glut), not a data quality issue. Both feeds have complete 48/48 settlement periods.

**Effect on shadow P&L:** total_cost (the cost-aware charging cost) collapsed to £638.86 - versus a 97-day history median of £79,350 and a previous cost-aware-era low of £28,279 (09-18). That's because the model charged into a day of near-zero buying prices. Revenue fell in step (£71,500, also a recent low), so net_pnl (£70,862) landed almost exactly where 09-18 did (£71,199) despite a much more extreme price environment underneath - cheap charging offsetting weak selling.

**Is it urgent?** No - it's a real, explainable market event, and the cost-aware model responded sensibly (cost collapsed together with revenue rather than one moving independently of the other). Flagging alongside the 09-18 finding because it's now four consecutive falling-price days and the second consecutive day where the green/amber day_type label describes a day whose P&L composition looks nothing like a typical green day - worth revisiting once this stretch of thin, cheap-and-volatile conditions ends, to see whether the classifier still tracks realised P&L well.

![Wind glut drives 2026-09-19 to lowest price of the run](wind_glut_drives_2026_09_19_to_lowest_price_of_the_run.png)

---

