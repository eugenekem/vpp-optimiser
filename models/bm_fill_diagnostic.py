import sys
import glob
import re
import pandas as pd

# --- How big is BM's fill/acceptance gap, really? ---
#
# optimiser_bm.py lets the battery trade its full reserved MW every period
# with no cap reflecting whether NESO would actually accept that volume in
# the real Balancing Mechanism - flagged since v30/v31 as a separate,
# unfixed realism gap (BM ~29% of logged P&L).
#
# system_prices_{date}.csv (already fetched from Elexon's settlement
# endpoint) has always carried totalAcceptedOfferVolume/totalAcceptedBidVolume
# per period - the real GB-wide volume NESO actually accepted, the same
# figures Elexon uses to derive SSP/SBP. Nothing in this codebase reads them.
# This script does not invent a capture-rate assumption - it just measures
# what share of the whole GB market our modelled BM trades would represent,
# so the gap is quantified before anyone guesses at a fix.
#
# Usage:
#   python bm_fill_diagnostic.py [N]   # last N days with both files (default: all)

DATA_DIR = "../data"
DURATION = 0.5


def available_days():
    bm_dates = {re.search(r"bm_schedule_(\d{4}-\d{2}-\d{2})\.csv$", p).group(1)
                for p in glob.glob(f"{DATA_DIR}/bm_schedule_*.csv")}
    sp_dates = {re.search(r"system_prices_(\d{4}-\d{2}-\d{2})\.csv$", p).group(1)
                for p in glob.glob(f"{DATA_DIR}/system_prices_*.csv")}
    return sorted(bm_dates & sp_dates)


def day_ratios(date):
    bm = pd.read_csv(f"{DATA_DIR}/bm_schedule_{date}.csv")
    sp = pd.read_csv(f"{DATA_DIR}/system_prices_{date}.csv")
    sp = sp[sp["settlementPeriod"] <= 48].drop_duplicates("settlementPeriod", keep="first")
    accepted_offer = sp.set_index("settlementPeriod")["totalAcceptedOfferVolume"]
    accepted_bid = sp.set_index("settlementPeriod")["totalAcceptedBidVolume"].abs()

    # Portfolio's traded BM volume per period, summed across all 5 assets, MWh
    active = bm[bm["action"].isin(["discharge", "charge"])].copy()
    if active.empty:
        return pd.DataFrame()
    active["volume_mwh"] = active["power_mw"] * DURATION
    per_period = active.groupby(["settlement_period", "action"])["volume_mwh"].sum().unstack(fill_value=0)

    rows = []
    for sp_num, row in per_period.iterrows():
        disc = row.get("discharge", 0.0)
        chg = row.get("charge", 0.0)
        if disc > 0:
            rows.append({"date": date, "settlement_period": sp_num, "side": "discharge",
                         "portfolio_mwh": disc, "system_accepted_mwh": accepted_offer.get(sp_num, float("nan"))})
        if chg > 0:
            rows.append({"date": date, "settlement_period": sp_num, "side": "charge",
                         "portfolio_mwh": chg, "system_accepted_mwh": accepted_bid.get(sp_num, float("nan"))})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # A handful of periods have system_accepted_mwh at or near zero (down to
    # 1e-8 MWh - Elexon rounding noise, not a real market) - the whole GB
    # market accepted essentially nothing on that side, yet the model still
    # traded. That's not "a large %", it's undefined/meaningless as a ratio
    # and the starkest possible implausibility - flagged separately via
    # zero_accepted (threshold 1 MWh, i.e. 2 MW for a half-hour period -
    # comfortably below any real battery dispatch), never folded into
    # ratio_pct (which would otherwise blow up and poison every summary stat).
    df["zero_accepted"] = df["system_accepted_mwh"].abs() < 1.0
    df["ratio_pct"] = (df["portfolio_mwh"] / df["system_accepted_mwh"] * 100).where(~df["zero_accepted"])
    return df


def net_pnl_at_risk(date, df_ratios, threshold_pct):
    """What fraction of this day's logged BM net P&L comes from periods over threshold."""
    bm = pd.read_csv(f"{DATA_DIR}/bm_schedule_{date}.csv")
    price_col = "sbp_settle" if "sbp_settle" in bm.columns else "sbp"
    disc_col = "ssp_settle" if "ssp_settle" in bm.columns else "ssp"
    bm["pnl"] = 0.0
    disc = bm["action"] == "discharge"
    chg = bm["action"] == "charge"
    bm.loc[disc, "pnl"] = bm.loc[disc, "power_mw"] * bm.loc[disc, disc_col] * DURATION
    bm.loc[chg, "pnl"] = -bm.loc[chg, "power_mw"] * bm.loc[chg, price_col] * DURATION
    total_pnl = bm["pnl"].sum()
    if total_pnl == 0 or df_ratios.empty:
        return 0.0, total_pnl
    flagged = (df_ratios["ratio_pct"] > threshold_pct) | df_ratios["zero_accepted"]
    flagged_periods = set(df_ratios.loc[flagged, "settlement_period"])
    at_risk = bm.loc[bm["settlement_period"].isin(flagged_periods), "pnl"].sum()
    return (at_risk / total_pnl * 100) if total_pnl else 0.0, total_pnl


def main(n_days=None):
    days = available_days()
    if n_days:
        days = days[-n_days:]
    print(f"BM fill/acceptance diagnostic — {len(days)} days ({days[0]} to {days[-1]})" if days else "No days available")
    print("=" * 72)

    all_ratios = []
    total_pnl_all = 0.0
    at_risk_pnl_all = 0.0
    THRESHOLD = 10.0  # illustrative: >10% of GB-wide accepted volume in one period, from a single 145MW portfolio

    for date in days:
        try:
            r = day_ratios(date)
        except Exception as e:
            print(f"  ⚠️  {date}: {e}")
            continue
        if r.empty:
            continue
        all_ratios.append(r)
        pct_at_risk, day_pnl = net_pnl_at_risk(date, r, THRESHOLD)
        total_pnl_all += day_pnl
        at_risk_pnl_all += day_pnl * pct_at_risk / 100

    if not all_ratios:
        print("No BM-active days with both schedule and system-price data found.")
        return

    df = pd.concat(all_ratios, ignore_index=True)
    df.to_csv(f"{DATA_DIR}/bm_fill_diagnostic.csv", index=False)

    n_zero = df["zero_accepted"].sum()
    print(f"\nPeriods with BM activity: {len(df)} (across {df['date'].nunique()} days)")
    print(f"\n⚠️  Periods where GB-WIDE accepted volume was ZERO on that side, yet the model still "
          f"traded: {n_zero} / {len(df)} ({n_zero/len(df)*100:.2f}%) — the starkest case: these trades "
          f"could not have been filled at all, at any capture rate.")
    if n_zero:
        print(df.loc[df["zero_accepted"], ["date", "settlement_period", "side", "portfolio_mwh"]]
              .to_string(index=False))

    finite = df.loc[~df["zero_accepted"], "ratio_pct"]
    print(f"\nRatio distribution (excludes the {n_zero} zero-accepted periods above): "
          f"portfolio's traded BM volume as % of GB-wide accepted volume that period")
    print(finite.describe(percentiles=[.5, .9, .99]).to_string())

    over_threshold = (finite > THRESHOLD).sum()
    print(f"\nPeriods where portfolio volume > {THRESHOLD:.0f}% of GB-wide accepted volume: "
          f"{over_threshold} / {len(finite)} ({over_threshold/len(finite)*100:.1f}%, "
          f"plus the {n_zero} zero-accepted periods above)")

    print(f"\nShare of logged BM net P&L from periods over {THRESHOLD:.0f}%: "
          f"£{at_risk_pnl_all:,.0f} of £{total_pnl_all:,.0f} total "
          f"({at_risk_pnl_all/total_pnl_all*100:.1f}%)" if total_pnl_all else "  (no BM P&L to attribute)")

    print(f"\nSaved per-period ratios to {DATA_DIR}/bm_fill_diagnostic.csv")
    print("\nReminder: totalAcceptedOfferVolume/BidVolume are GB-WIDE totals, not this portfolio's")
    print("addressable share - a high ratio doesn't prove our volume would be rejected, only that")
    print(f"it would represent an implausibly large slice ({THRESHOLD:.0f}%+) of everything NESO accepted")
    print("that period. This is a red-flag signal, not a validated fill-rate constraint.")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(n)
