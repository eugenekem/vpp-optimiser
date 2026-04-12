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
today = datetime.today().strftime("%Y-%m-%d")

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
def load_dc(date):
    path = f"data/dc_forecast_{date}.csv"
    if os.path.exists(path):
        return pd.read_csv(path)
    return None

@st.cache_data
def load_schedule(date):
    path = f"data/da_schedule_{date}.csv"
    if os.path.exists(path):
        return pd.read_csv(path)
    return None

df_prices = load_prices(yesterday)
df_pnl = load_pnl(yesterday)
df_dc = load_dc(yesterday)
df_schedule = load_schedule(yesterday)

# --- Header ---
st.markdown("## ⚡ VPP War Room")
st.markdown(f"**Trading date:** {yesterday} &nbsp;|&nbsp; **Session:** Day Ahead")
st.divider()

# --- Morning Signal ---
st.markdown("### Morning briefing")

if df_prices is not None:
    price_range = df_prices["price"].max() - df_prices["price"].min()
    min_price = df_prices["price"].min()
    max_price = df_prices["price"].max()
    has_negative = min_price < 0

    if has_negative and price_range > 40:
        signal = "🟢 Good day"
        signal_text = "Wide price spread with negative prices — strong arbitrage conditions."
        signal_color = "success"
    elif price_range > 50:
        signal = "🟡 Moderate day"
        signal_text = "Reasonable spread but no negative prices — moderate arbitrage opportunity."
        signal_color = "warning"
    else:
        signal = "🔴 Difficult day"
        signal_text = "Narrow spread — consider DC stacking and reduced DA commitment."
        signal_color = "error"

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if signal_color == "success":
            st.success(f"**{signal}**")
        elif signal_color == "warning":
            st.warning(f"**{signal}**")
        else:
            st.error(f"**{signal}**")
    with col2:
        st.metric("Price range", f"£{price_range:.0f}/MWh")
    with col3:
        st.metric("Min price", f"£{min_price:.2f}")
    with col4:
        st.metric("Max price", f"£{max_price:.2f}")

    st.caption(signal_text)

st.divider()

# --- Strategy Recommendations ---
st.markdown("### Strategy recommendations")

if df_prices is not None:
    price_range = df_prices["price"].max() - df_prices["price"].min()
    min_price = df_prices["price"].min()
    has_negative = min_price < 0

    if df_pnl is not None:
        period_pnl = df_pnl.groupby("settlement_period")["net_pnl"].sum().values
        sharpe = calculate_sharpe(period_pnl)
        asset_pnl, concentration = concentration_risk(df_pnl)
        max_concentrated_asset = max(concentration, key=concentration.get)
        max_concentration_pct = concentration[max_concentrated_asset]
    else:
        sharpe = 1.0
        max_concentrated_asset = None
        max_concentration_pct = 0

    if has_negative and price_range > 40:
        day_type = "green"
    elif price_range > 50:
        day_type = "amber"
    else:
        day_type = "red"

    recommendations = {}

    if day_type == "green":
        recommendations = {
            "Battery_1": ("✅ Full DA commit", "Strong spread — commit fully in DA. Reserve 50% for BM spikes."),
            "Battery_2": ("✅ Full DA commit", "Charge during negative prices. Discharge top 10 periods aggressively."),
            "Battery_3": ("✅ Full DA commit", "Maximum arbitrage day. Charge all negative price periods. Discharge evening peak."),
            "Battery_4": ("✅ Full DA commit", "Solar will assist charging. Stack DC alongside DA for extra revenue."),
            "Battery_5": ("✅ Full DA commit", "Solar advantage today. Discharge evening peak, let solar top up during day."),
        }
    elif day_type == "amber":
        recommendations = {
            "Battery_1": ("⚠️ Prioritise DC over DA", "Narrow spread limits DA value. Stack DC High and DC Low for reliable ancillary revenue."),
            "Battery_2": ("⚠️ Reduce DA commitment", "Limit discharge to top 8 periods only. Hold remaining capacity for intraday opportunities."),
            "Battery_3": ("⚠️ Reduce DA commitment", "Reduce discharge threshold. Narrow spread means lower margin — be selective on periods."),
            "Battery_4": ("⚠️ Treat as standalone today", "Co-located advantage limited without negative prices. Focus on top discharge periods only."),
            "Battery_5": ("⚠️ Treat as standalone today", "Same as Battery 4 — solar charging benefit reduced. Prioritise DC stacking."),
        }
    else:
        recommendations = {
            "Battery_1": ("🔴 Hold for BM only", "Poor spread — do not commit in DA. Reserve entirely for BM short-duration spikes."),
            "Battery_2": ("🔴 Minimal DA, stack DC", "Charge only if price below £30. Discharge only top 5 periods. Stack DC for base revenue."),
            "Battery_3": ("🔴 Reduce exposure", "Commit only 50% capacity in DA. Wide reservation for intraday. Avoid locking in poor margin."),
            "Battery_4": ("🔴 DC priority", "Skip DA energy arbitrage. Full capacity available for DC High and DC Low today."),
            "Battery_5": ("🔴 DC priority", "Same as Battery 4. Poor energy spread means DC stacking is the better revenue source today."),
        }

    if max_concentration_pct > 40 and max_concentrated_asset:
        st.warning(
            f"⚠️ Concentration alert — {max_concentrated_asset} driving "
            f"{max_concentration_pct:.0f}% of P&L. Consider rebalancing exposure."
        )

    if sharpe < 0.5:
        st.warning(
            f"⚠️ Low Sharpe ratio ({sharpe:.2f}) — returns are not justifying risk. "
            f"Consider tightening thresholds or reducing committed capacity today."
        )

    col1, col2 = st.columns(2)
    asset_list = list(recommendations.items())

    for i, (asset_name, (headline, detail)) in enumerate(asset_list):
        col = col1 if i % 2 == 0 else col2
        with col:
            with st.container(border=True):
                st.markdown(f"**{asset_name}** — {headline}")
                st.markdown(f"<span style='font-size:13px;color:gray;'>{detail}</span>",
                            unsafe_allow_html=True)

st.divider()

# --- P&L Summary ---
st.markdown("### Portfolio P&L")

if df_pnl is not None:
    total_revenue = df_pnl["revenue"].sum()
    total_cost = df_pnl["cost"].sum()
    total_net = total_revenue - total_cost

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total revenue", f"£{total_revenue:,.0f}")
    with col2:
        st.metric("Total cost", f"£{total_cost:,.0f}")
    with col3:
        st.metric("Net P&L", f"£{total_net:,.0f}", delta=f"£{total_net:,.0f}")

    st.markdown("**P&L by asset**")
    asset_data = []
    for asset_name in df_pnl["asset"].unique():
        df_asset = df_pnl[df_pnl["asset"] == asset_name]
        revenue = df_asset["revenue"].sum()
        cost = df_asset["cost"].sum()
        net = revenue - cost
        asset_data.append({
            "Asset": asset_name,
            "Revenue (£)": f"£{revenue:,.0f}",
            "Cost (£)": f"£{cost:,.0f}",
            "Net P&L (£)": f"£{net:,.0f}"
        })
    st.dataframe(pd.DataFrame(asset_data), use_container_width=True, hide_index=True)

st.divider()

# --- Price curve ---
st.markdown("### Price curve")

if df_prices is not None:
    st.line_chart(
        df_prices.set_index("settlementPeriod")["price"],
        use_container_width=True
    )

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

if df_pnl is not None:
    period_pnl = df_pnl.groupby("settlement_period")["net_pnl"].sum().values
    var_95 = calculate_var(period_pnl, 0.95)
    volatility = calculate_volatility(period_pnl)
    sharpe = calculate_sharpe(period_pnl)
    asset_pnl, concentration = concentration_risk(df_pnl)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Sharpe ratio", f"{sharpe:.2f}",
                  delta="good" if sharpe > 1 else "low" if sharpe < 0.5 else "ok")
    with col2:
        st.metric("VaR 95%", f"£{var_95:,.0f}")
    with col3:
        st.metric("P&L volatility", f"£{volatility:,.0f}/period")

    st.markdown("**Concentration risk**")
    conc_df = pd.DataFrame({
        "Asset": list(concentration.keys()),
        "P&L contribution (%)": list(concentration.values())
    })
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
# --- Dispatch Schedule ---
st.markdown("### Dispatch schedule")

if df_schedule is not None:
    st.caption("DA optimiser decisions — period by period")

    asset_tabs = st.tabs(["Battery_1", "Battery_2", "Battery_3", "Battery_4", "Battery_5"])

    for i, tab in enumerate(asset_tabs):
        asset_name = f"Battery_{i+1}"
        with tab:
            df_asset = df_schedule[df_schedule["asset"] == asset_name].copy()
            df_asset = df_asset[["settlement_period", "price", "action", "power_mw", "soc"]].copy()
            df_asset.columns = ["Period", "Price (£/MWh)", "Action", "Power (MW)", "SOC (%)"]

            def highlight_action(row):
                if row["Action"] == "charge":
                    return ["background-color: #d4edda"] * len(row)
                elif row["Action"] == "discharge":
                    return ["background-color: #f8d7da"] * len(row)
                else:
                    return [""] * len(row)

            styled = df_asset.style.apply(highlight_action, axis=1)
            st.dataframe(styled, use_container_width=True, hide_index=True)

            charges = len(df_asset[df_asset["Action"] == "charge"])
            discharges = len(df_asset[df_asset["Action"] == "discharge"])
            holds = len(df_asset[df_asset["Action"] == "hold"])
            st.caption(f"Charge: {charges} periods | Discharge: {discharges} periods | Hold: {holds} periods")
else:
    st.info("No dispatch schedule available. Run optimiser_da.py first.")



st.divider()
st.caption(f"VPP War Room | Data as of {yesterday} | github.com/eugenekem/vpp-optimiser")
