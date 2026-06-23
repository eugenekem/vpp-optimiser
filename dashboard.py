import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys

sys.path.append("models")
from battery import assets
from pnl import calculate_pnl
from risk import calculate_var, calculate_volatility, calculate_sharpe, concentration_risk, scenario_analysis

# --- Page config ---
st.set_page_config(
    page_title="VPP War Room",
    page_icon="⚡",
    layout="wide"
)

# --- Date ---
yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")

# --- Load data ---
@st.cache_data
def load_prices(date):
    path = f"data/market_index_{date}.csv"
    if os.path.exists(path):
        return pd.read_csv(path)
    return None

@st.cache_data
def load_pnl(date):
    path = f"data/pnl_{date}.csv"
    if os.path.exists(path):
        return pd.read_csv(path)
    return None

@st.cache_data
def load_lp_schedule(date):
    path = f"data/lp_schedule_{date}.csv"
    if os.path.exists(path):
        return pd.read_csv(path)
    return None

@st.cache_data
def load_id_schedule(date):
    path = f"data/id_schedule_{date}.csv"
    if os.path.exists(path):
        return pd.read_csv(path)
    return None

@st.cache_data
def load_bm_schedule(date):
    path = f"data/bm_schedule_{date}.csv"
    if os.path.exists(path):
        return pd.read_csv(path)
    return None

df_prices   = load_prices(yesterday)
df_pnl      = load_pnl(yesterday)
df_lp       = load_lp_schedule(yesterday)
df_id       = load_id_schedule(yesterday)
df_bm       = load_bm_schedule(yesterday)

# --- Determine data availability ---
has_all_markets = df_lp is not None and df_id is not None and df_bm is not None
has_lp_only     = df_lp is not None and not has_all_markets

# --- Compute P&L from schedules ---
def compute_combined_pnl(df_lp, df_id, df_bm):
    rows = []
    for df, layer, price_col_d, price_col_c in [
        (df_lp, "DA", "price", "price"),
        (df_id, "ID", "id_price", "id_price"),
        (df_bm, "BM", "ssp", "sbp"),
    ]:
        for _, row in df.iterrows():
            if row["action"] == "discharge":
                rev  = row["power_mw"] * row[price_col_d] * 0.5
                cost = 0.0
            elif row["action"] == "charge":
                rev  = 0.0
                cost = row["power_mw"] * row[price_col_c] * 0.5
            else:
                rev = cost = 0.0
            rows.append({
                "asset": row["asset"],
                "settlement_period": row["settlement_period"],
                "layer": layer,
                "revenue": round(rev, 2),
                "cost": round(cost, 2),
                "net_pnl": round(rev - cost, 2),
            })
    return pd.DataFrame(rows)

def compute_lp_pnl(df_lp):
    rows = []
    for _, row in df_lp.iterrows():
        rev  = row["power_mw"] * row["price"] * 0.5 if row["action"] == "discharge" else 0
        cost = row["power_mw"] * row["price"] * 0.5 if row["action"] == "charge" else 0
        rows.append({
            "asset": row["asset"],
            "settlement_period": row["settlement_period"],
            "revenue": rev, "cost": cost, "net_pnl": rev - cost
        })
    return pd.DataFrame(rows)

if has_all_markets:
    df_combined_pnl = compute_combined_pnl(df_lp, df_id, df_bm)
    active_pnl      = df_combined_pnl
    pnl_label       = "DA + ID + BM (all markets)"
elif has_lp_only:
    df_combined_pnl = None
    active_pnl      = compute_lp_pnl(df_lp)
    pnl_label       = "DA only (LP optimiser)"
else:
    df_combined_pnl = None
    active_pnl      = df_pnl
    pnl_label       = "DA optimiser (rules-based)"

# --- Header ---
st.markdown("## ⚡ VPP War Room")
markets_active = "DA + ID + BM" if has_all_markets else "DA only"
st.markdown(f"**Trading date:** {yesterday} &nbsp;|&nbsp; **Markets:** {markets_active}")
st.divider()

# --- Morning Signal ---
st.markdown("### Morning briefing")

if df_prices is not None:
    price_range  = df_prices["price"].max() - df_prices["price"].min()
    min_price    = df_prices["price"].min()
    max_price    = df_prices["price"].max()
    has_negative = min_price < 0

    if has_negative and price_range > 40:
        signal, signal_text, signal_color = "🟢 Good day", "Wide price spread with negative prices — strong arbitrage conditions.", "success"
    elif price_range > 50:
        signal, signal_text, signal_color = "🟡 Moderate day", "Reasonable spread but no negative prices — moderate arbitrage opportunity.", "warning"
    else:
        signal, signal_text, signal_color = "🔴 Difficult day", "Narrow spread — consider DC stacking and reduced DA commitment.", "error"

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if signal_color == "success":   st.success(f"**{signal}**")
        elif signal_color == "warning": st.warning(f"**{signal}**")
        else:                           st.error(f"**{signal}**")
    with col2: st.metric("Price range", f"£{price_range:.0f}/MWh")
    with col3: st.metric("Min price",   f"£{min_price:.2f}")
    with col4: st.metric("Max price",   f"£{max_price:.2f}")
    st.caption(signal_text)

st.divider()

# --- Strategy Recommendations ---
st.markdown("### Strategy recommendations")

if df_prices is not None:
    price_range  = df_prices["price"].max() - df_prices["price"].min()
    min_price    = df_prices["price"].min()
    has_negative = min_price < 0

    if df_pnl is not None:
        period_pnl = df_pnl.groupby("settlement_period")["net_pnl"].sum().values
        sharpe     = calculate_sharpe(period_pnl)
        _, concentration = concentration_risk(df_pnl)
        max_concentrated_asset = max(concentration, key=concentration.get)
        max_concentration_pct  = concentration[max_concentrated_asset]
    else:
        sharpe = 1.0; max_concentrated_asset = None; max_concentration_pct = 0

    day_type = "green" if (has_negative and price_range > 40) else "amber" if price_range > 50 else "red"

    if day_type == "green":
        recommendations = {
            "Battery_1": ("✅ Full DA commit",      "Strong spread — commit fully in DA. Reserve 50% for BM spikes."),
            "Battery_2": ("✅ Full DA commit",      "Charge during negative prices. Discharge top 10 periods aggressively."),
            "Battery_3": ("✅ Full DA commit",      "Maximum arbitrage day. Charge all negative price periods. Discharge evening peak."),
            "Battery_4": ("✅ Full DA commit",      "Solar will assist charging. Stack DC alongside DA for extra revenue."),
            "Battery_5": ("✅ Full DA commit",      "Solar advantage today. Discharge evening peak, let solar top up during day."),
        }
    elif day_type == "amber":
        recommendations = {
            "Battery_1": ("⚠️ Prioritise DC over DA", "Narrow spread limits DA value. Stack DC High and DC Low for reliable ancillary revenue."),
            "Battery_2": ("⚠️ Reduce DA commitment",  "Limit discharge to top 8 periods only. Hold remaining capacity for intraday opportunities."),
            "Battery_3": ("⚠️ Reduce DA commitment",  "Reduce discharge threshold. Narrow spread means lower margin — be selective on periods."),
            "Battery_4": ("⚠️ Treat as standalone",   "Co-located advantage limited without negative prices. Focus on top discharge periods only."),
            "Battery_5": ("⚠️ Treat as standalone",   "Same as Battery 4 — solar charging benefit reduced. Prioritise DC stacking."),
        }
    else:
        recommendations = {
            "Battery_1": ("🔴 Hold for BM only",    "Poor spread — do not commit in DA. Reserve entirely for BM short-duration spikes."),
            "Battery_2": ("🔴 Minimal DA, stack DC", "Charge only if price below £30. Discharge only top 5 periods. Stack DC for base revenue."),
            "Battery_3": ("🔴 Reduce exposure",      "Commit only 50% capacity in DA. Wide reservation for intraday. Avoid locking in poor margin."),
            "Battery_4": ("🔴 DC priority",          "Skip DA energy arbitrage. Full capacity available for DC High and DC Low today."),
            "Battery_5": ("🔴 DC priority",          "Same as Battery 4. Poor energy spread means DC stacking is the better revenue source today."),
        }

    if max_concentration_pct > 40 and max_concentrated_asset:
        st.warning(f"⚠️ Concentration alert — {max_concentrated_asset} driving {max_concentration_pct:.0f}% of P&L.")
    if sharpe < 0.5:
        st.warning(f"⚠️ Low Sharpe ratio ({sharpe:.2f}) — returns are not justifying risk.")

    col1, col2 = st.columns(2)
    for i, (asset_name, (headline, detail)) in enumerate(recommendations.items()):
        col = col1 if i % 2 == 0 else col2
        with col:
            with st.container(border=True):
                st.markdown(f"**{asset_name}** — {headline}")
                st.markdown(f"<span style='font-size:13px;color:gray;'>{detail}</span>", unsafe_allow_html=True)

st.divider()

# --- Portfolio P&L ---
st.markdown("### Portfolio P&L")

if active_pnl is not None:
    total_revenue = active_pnl["revenue"].sum()
    total_cost    = active_pnl["cost"].sum()
    total_net     = total_revenue - total_cost

    st.caption(f"Source: {pnl_label}")
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Total revenue", f"£{total_revenue:,.0f}")
    with col2: st.metric("Total cost",    f"£{total_cost:,.0f}")
    with col3: st.metric("Net P&L",       f"£{total_net:,.0f}", delta=f"£{total_net:,.0f}", delta_color="normal")

    st.markdown("**P&L by asset**")
    asset_data = []
    for asset_name in sorted(active_pnl["asset"].unique()):
        df_a  = active_pnl[active_pnl["asset"] == asset_name]
        rev   = df_a["revenue"].sum()
        cost  = df_a["cost"].sum()
        net   = rev - cost
        asset_data.append({"Asset": asset_name, "Revenue (£)": f"£{rev:,.0f}", "Cost (£)": f"£{cost:,.0f}", "Net P&L (£)": f"£{net:,.0f}"})
    st.dataframe(pd.DataFrame(asset_data), use_container_width=True, hide_index=True)

    if has_all_markets:
        st.markdown("**P&L by market**")
        market_data = []
        for layer in ["DA", "ID", "BM"]:
            df_l = df_combined_pnl[df_combined_pnl["layer"] == layer]
            rev  = df_l["revenue"].sum()
            cost = df_l["cost"].sum()
            net  = rev - cost
            market_data.append({"Market": layer, "Revenue (£)": f"£{rev:,.0f}", "Cost (£)": f"£{cost:,.0f}", "Net P&L (£)": f"£{net:,.0f}"})
        st.dataframe(pd.DataFrame(market_data), use_container_width=True, hide_index=True)

        st.markdown("**Net P&L contribution by market**")
        market_net = df_combined_pnl.groupby("layer")["net_pnl"].sum()
        st.bar_chart(market_net, use_container_width=True)

st.divider()

# --- Price curve ---
st.markdown("### Price curve")
if df_prices is not None:
    st.line_chart(df_prices.set_index("settlementPeriod")["price"], use_container_width=True)

st.divider()

# --- Asset status ---
st.markdown("### Asset status")
asset_cols = st.columns(5)
for i, asset in enumerate(assets):
    with asset_cols[i]:
        st.markdown(f"**{asset.name}**")
        st.markdown(f"{asset.region}")
        st.progress(asset.soc, text=f"SOC {asset.soc*100:.0f}%")
        st.markdown(f"⚡ {asset.mw} MW / {asset.capacity_mwh} MWh")
        if asset.solar_mw > 0:
            st.markdown(f"☀️ {asset.solar_mw} MW solar")

st.divider()

# --- Risk summary ---
st.markdown("### Risk summary")
risk_pnl = active_pnl
if risk_pnl is not None:
    period_pnl = risk_pnl.groupby("settlement_period")["net_pnl"].sum().values
    var_95     = calculate_var(period_pnl, 0.95)
    volatility = calculate_volatility(period_pnl)
    sharpe     = calculate_sharpe(period_pnl)
    _, concentration = concentration_risk(risk_pnl)

    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Sharpe ratio",   f"{sharpe:.2f}", delta="good" if sharpe > 1 else "low" if sharpe < 0.5 else "ok")
    with col2: st.metric("VaR 95%",        f"£{var_95:,.0f}")
    with col3: st.metric("P&L volatility", f"£{volatility:,.0f}/period")

    st.markdown("**Concentration risk**")
    conc_df = pd.DataFrame({"Asset": list(concentration.keys()), "P&L contribution (%)": list(concentration.values())})
    st.bar_chart(conc_df.set_index("Asset"), use_container_width=True)

st.divider()

# --- DC Forecast ---
st.markdown("### DC tender forecast")
dc_files = [f for f in os.listdir("data") if f.startswith("dc_forecast_")]
if dc_files:
    latest_dc = sorted(dc_files)[-1]
    df_dc = pd.read_csv(f"data/{latest_dc}")
    st.caption(f"Latest available: {latest_dc.replace('dc_forecast_','').replace('.csv','')}")
    st.dataframe(df_dc, use_container_width=True, hide_index=True)
else:
    st.info("No DC forecast data available.")

st.divider()

# --- Dispatch Schedule ---
st.markdown("### Dispatch schedule")

def highlight_action(row):
    if row["Action"] == "charge":      return ["background-color: #d4edda"] * len(row)
    elif row["Action"] == "discharge": return ["background-color: #f8d7da"] * len(row)
    else:                              return [""] * len(row)

def render_schedule_tab(df_raw, price_col, label):
    """Render table + SOC curve + price chart + MW bar chart for one layer."""
    df = df_raw.copy()
    df = df[["settlement_period", price_col, "action", "power_mw", "soc"]].copy()
    df.columns = ["Period", "Price (£/MWh)", "Action", "Power (MW)", "SOC (%)"]

    styled = (
        df.style
        .apply(highlight_action, axis=1)
        .format({"Price (£/MWh)": "{:.2f}", "Power (MW)": "{:.2f}", "SOC (%)": "{:.1f}"})
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)

    charges    = len(df[df["Action"] == "charge"])
    discharges = len(df[df["Action"] == "discharge"])
    holds      = len(df[df["Action"] == "hold"])
    st.caption(f"Charge: {charges} | Discharge: {discharges} | Hold: {holds}")

    # SOC curve
    st.markdown(f"**SOC curve ({label})**")
    st.line_chart(df[["Period", "SOC (%)"]].set_index("Period"), use_container_width=True)

    # Price curve — separate chart so MW scale stays readable
    st.markdown(f"**Price curve ({label})**")
    price_data = df_raw.set_index("settlement_period")[[price_col]].rename(
        columns={price_col: "Price (£/MWh)"}
    )
    st.line_chart(price_data, use_container_width=True)

    # Charge / discharge MW — bar chart on its own axis
    st.markdown(f"**Charge / discharge MW ({label})**")
    mw_data = pd.DataFrame({
        "Charge (MW)":    df_raw[df_raw["action"] == "charge"].set_index("settlement_period")["power_mw"],
        "Discharge (MW)": df_raw[df_raw["action"] == "discharge"].set_index("settlement_period")["power_mw"],
    }).fillna(0)
    st.bar_chart(mw_data, use_container_width=True)
    st.caption("Charge bars should cluster at price troughs, discharge bars at price peaks.")


if has_all_markets:
    st.caption("Source: DA + ID + BM (dispatcher — sequential SOC handoff)")
    asset_tabs = st.tabs(["Battery_1", "Battery_2", "Battery_3", "Battery_4", "Battery_5"])

    for i, tab in enumerate(asset_tabs):
        asset_name = f"Battery_{i+1}"
        with tab:
            market_tabs = st.tabs(["DA", "ID", "BM"])

            with market_tabs[0]:
                df_asset_lp = df_lp[df_lp["asset"] == asset_name].copy()
                render_schedule_tab(df_asset_lp, "price", "DA layer")

            with market_tabs[1]:
                df_asset_id = df_id[df_id["asset"] == asset_name].copy()
                render_schedule_tab(df_asset_id, "id_price", "ID layer")

            with market_tabs[2]:
                df_asset_bm = df_bm[df_bm["asset"] == asset_name].copy()
                render_schedule_tab(df_asset_bm, "ssp", "BM layer")

elif df_lp is not None:
    st.caption("Source: LP optimiser (DA only)")
    asset_tabs = st.tabs(["Battery_1", "Battery_2", "Battery_3", "Battery_4", "Battery_5"])
    for i, tab in enumerate(asset_tabs):
        asset_name = f"Battery_{i+1}"
        with tab:
            df_asset_lp = df_lp[df_lp["asset"] == asset_name].copy()
            render_schedule_tab(df_asset_lp, "price", "DA layer")
else:
    st.info("No dispatch schedule available. Run dispatcher.py first.")

st.divider()
markets_str = "DA + ID + BM" if has_all_markets else "DA only"
st.caption(f"VPP War Room | Data as of {yesterday} | {markets_str} | github.com/eugenekem/vpp-optimiser")
