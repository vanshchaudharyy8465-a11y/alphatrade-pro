import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from model_engine import AlphaModelEngine
from streamlit_autorefresh import st_autorefresh

# Page Layout Setup
st.set_page_config(page_title="AlphaTrader Pro | Live Terminal", layout="wide")

# Auto-refresh every 60 seconds (1 minute) for live real-time market simulation
st_autorefresh(interval=60000, key="datarefresh")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #c9d1d9; font-family: sans-serif; }
    div[data-testid="metric-container"] { background-color: #161b22; padding: 10px; border-radius: 8px; border: 1px solid #30363d; }
</style>
""", unsafe_allow_html=True)

if 'balance' not in st.session_state:
    st.session_state.balance = 500000.0
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {}

st.title("⚡ AlphaTrader Pro | Live AI Trading Terminal")

st.sidebar.header("📊 Market Watchlist")
ticker = st.sidebar.selectbox("Choose Asset", ["RELIANCE.NS", "TCS.NS", "INFY.NS", "AAPL", "TSLA", "BTC-USD"])

time_frame_label = st.sidebar.selectbox("Select Timeframe", ["1 Day (1d)", "5 Days (5d)", "1 Month (1mo)", "1 Year (1y)"])
tf_map = {
    "1 Day (1d)": ("1d", "5m"),
    "5 Days (5d)": ("5d", "15m"),
    "1 Month (1mo)": ("1mo", "1d"),
    "1 Year (1y)": ("1y", "1d")
}
selected_period, selected_interval = tf_map[time_frame_label]

@st.cache_data(ttl=60)
def fetch_data(symbol, period, interval):
    try:
        df = yf.download(symbol, period=period, interval=interval, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception:
        return pd.DataFrame()

data = fetch_data(ticker, selected_period, selected_interval)

if data.empty or len(data) < 2:
    st.error("Data load hone mein error aayi. Kripya doosra timeframe ya asset chunein.")
else:
    latest_price = float(data['Close'].iloc[-1])
    prev_price = float(data['Close'].iloc[-2])
    change_pct = ((latest_price - prev_price) / prev_price) * 100

    open_price = float(data['Open'].iloc[-1])
    high_price = float(data['High'].max())
    low_price = float(data['Low'].min())
    vol_val = float(data['Volume'].iloc[-1]) if 'Volume' in data else 0

    engine = AlphaModelEngine(data)
    ai_target, confidence, rsi_val, signal = engine.generate_signals()

    # Metrics Layout
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Price", f"₹{latest_price:,.2f}", f"{change_pct:+.2f}%")
    c2.metric("AI Target", f"₹{ai_target:,.2f}", f"{((ai_target-latest_price)/latest_price)*100:+.2f}%")
    c3.metric("AI Conf / RSI", f"{confidence} / {rsi_val}")
    c4.metric("AI Signal", f"{signal}")

    st.markdown("---")

    chart_col, trade_col = st.columns([2.6, 1])

    with chart_col:
        st.subheader(f"📈 Live Price Chart ({ticker}) - {time_frame_label} (Auto-refreshed)")
        fig = go.Figure(data=[go.Candlestick(
            x=data.index,
            open=data['Open'],
            high=data['High'],
            low=data['Low'],
            close=data['Close'],
            name='Price',
            increasing_line_color='#238636',
            decreasing_line_color='#da3633'
        )])
        # Fixed layout with automargin to ensure numbers never get cut off
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0e1117",
            plot_bgcolor="#0e1117",
            height=430,
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis=dict(automargin=True),
            yaxis=dict(automargin=True)
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📋 Market Statistics")
        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("Open", f"₹{open_price:,.2f}")
        sc2.metric("High", f"₹{high_price:,.2f}")
        sc3.metric("Low", f"₹{low_price:,.2f}")
        sc4.metric("Volume", f"{vol_val:,.0f}")

    with trade_col:
        st.subheader("⚡ Quick Order Panel")
        st.info(f"Virtual Funds: **₹ {st.session_state.balance:,.2f}**")

        qty = st.number_input("Quantity", min_value=1, max_value=1000, value=10)
        total_cost = latest_price * qty

        b1, b2 = st.columns(2)
        if b1.button("🟢 Buy", use_container_width=True):
            if st.session_state.balance >= total_cost:
                st.session_state.balance -= total_cost
                if ticker in st.session_state.portfolio:
                    curr_qty = st.session_state.portfolio[ticker]["qty"]
                    curr_buy = st.session_state.portfolio[ticker]["buy_price"]
                    new_qty = curr_qty + qty
                    avg_buy = ((curr_qty * curr_buy) + (qty * latest_price)) / new_qty
                    st.session_state.portfolio[ticker] = {"qty": new_qty, "buy_price": avg_buy}
                else:
                    st.session_state.portfolio[ticker] = {"qty": qty, "buy_price": latest_price}
                st.success(f"Bought {qty} units!")
            else:
                st.error("Insufficient balance!")

        if b2.button("🔴 Sell", use_container_width=True):
            if ticker in st.session_state.portfolio and st.session_state.portfolio[ticker]["qty"] >= qty:
                st.session_state.balance += total_cost
                st.session_state.portfolio[ticker]["qty"] -= qty
                if st.session_state.portfolio[ticker]["qty"] == 0:
                    del st.session_state.portfolio[ticker]
                st.success(f"Sold {qty} units!")
            else:
                st.error("Not enough shares to sell!")

        st.markdown("### 💼 Portfolio & Live P&L")
        if st.session_state.portfolio:
            for s, info in st.session_state.portfolio.items():
                q = info["qty"]
                b_price = info["buy_price"]
                curr_val = latest_price if s == ticker else b_price
                pnl = (curr_val - b_price) * q
                pnl_pct = ((curr_val - b_price) / b_price) * 100 if b_price > 0 else 0
                color = "#3fb950" if pnl >= 0 else "#f85149"
                
                st.markdown(f"""
                <div style="background-color: #161b22; padding: 10px; border-radius: 6px; margin-bottom: 8px; border: 1px solid #30363d;">
                    <b>{s}</b> | {q} units<br>
                    Avg: ₹{b_price:,.2f} | Live: ₹{curr_val:,.2f}<br>
                    P&L: <span style="color:{color}; font-weight:bold;">₹{pnl:,.2f} ({pnl_pct:.2f}%)</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.write("No active positions.")
