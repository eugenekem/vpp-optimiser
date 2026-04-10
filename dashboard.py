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

    if price_range > 80 and has_negative:
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
        st.metric("Market signal", signal)
    with col2:
        st.metric("Price range", f"£{price_range:.0f}/MWh")
    with col3:
        st.metric("Min price", f"£{min_price:.2f}")
    with col4:
        st.metric("Max price", f"£{max_price:.2f}")

    if signal_color == "success":
        st.success(signal_text)
    elif signal_color == "warning":
        st.warning(signal_text)
    else:
        st.error(signal_text)

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
        st.metric("Net P&L", f"£{total_net:,.0f}",
                  delta=f"£{total_net:,.0f}")

    # P&L by asset
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

    # Concentration
    st.markdown("**Concentration risk**")
    conc_df = pd.DataFrame({
        "Asset": list(concentration.keys()),
        "P&L contribution (%)": list(concentration.values())
    })
    st.bar_chart(conc_df.set_index("Asset"), use_container_width=True)

st.divider()

# --- DC Forecast ---
st.markdown("### DC tender forecast")

if df_dc is not None:
    st.dataframe(df_dc, use_container_width=True, hide_index=True)
else:
    st.info("No DC forecast data available for this date.")

st.divider()
st.caption(f"VPP War Room | Data as of {yesterday} | github.com/eugenekem/vpp-optimiser")