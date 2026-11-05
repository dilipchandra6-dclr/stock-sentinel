import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time, io, wave, math, struct, base64
import urllib.request

st.set_page_config(page_title="Portfolio Sentinel Pro", layout="wide")
st.title("🛡️ Portfolio Sentinel: Technical Signals & Phone Alerts")

# --- SIDEBAR CONTROLS ---
st.sidebar.header("Portfolio Watchlist")
ticker_string = st.sidebar.text_input("Tickers (comma-separated)", value="AAPL, NVDA, MSFT, TSLA")
tickers = [t.strip().upper() for t in ticker_string.split(",") if t.strip()]

st.sidebar.markdown("---")
st.sidebar.subheader("📱 Phone Push Notifications")
enable_phone = st.sidebar.checkbox("Enable Phone Push Alerts", value=False)
ntfy_topic = st.sidebar.text_input("ntfy Topic Name", value="mystock-alerts-demo")

if st.sidebar.button("Test Phone Notification"):
    if ntfy_topic:
        try:
            req = urllib.request.Request(
                f"https://ntfy.sh/{ntfy_topic}",
                data="🚀 Test Alert: Your phone notification pipeline is connected!".encode("utf-8"),
                headers={"Title": "Stock Sentinel Test", "Priority": "high"}
            )
            urllib.request.urlopen(req, timeout=5)
            st.sidebar.success("Test notification sent to phone!")
        except Exception as e:
            st.sidebar.error(f"Failed to send: {e}")

st.sidebar.markdown("---")
st.sidebar.subheader("Audio & Automation")
enable_sound = st.sidebar.checkbox("Play Sound on Alerts", value=True)
enable_loop = st.sidebar.checkbox("Enable Auto-Refresh Loop", value=False)
refresh_interval = st.sidebar.slider("Scan Interval (seconds)", min_value=15, max_value=300, value=60)

# --- HELPER FUNCTIONS ---
def send_phone_push(topic, message, title="Stock Alert"):
    try:
        req = urllib.request.Request(
            f"https://ntfy.sh/{topic}",
            data=message.encode("utf-8"),
            headers={"Title": title, "Priority": "high"}
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass

def play_chime():
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        for i in range(2205):
            val = int(32767.0 * 0.25 * math.sin(2.0 * math.pi * 587.33 * i / 44100))
            wav.writeframes(struct.pack('<h', val))
        for i in range(4410):
            val = int(32767.0 * 0.25 * math.sin(2.0 * math.pi * 880.00 * i / 44100))
            wav.writeframes(struct.pack('<h', val))
    b64_sound = base64.b64encode(buf.getvalue()).decode()
    st.markdown(f'<audio autoplay style="display:none;"><source src="data:audio/wav;base64,{b64_sound}" type="audio/wav"></audio>', unsafe_allow_html=True)

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

# --- BATCH WATCHLIST ANALYSIS ---
watchlist_data = []
active_alerts = []

for symbol in tickers:
    stock = yf.Ticker(symbol)
    # Pull 1 year of daily data to compute 200-day moving averages
    history = stock.history(period="1y")
    
    if len(history) >= 200:
        current_price = history['Close'].iloc[-1]
        
        # Calculate moving averages
        history['SMA_50'] = history['Close'].rolling(window=50).mean()
        history['SMA_200'] = history['Close'].rolling(window=200).mean()
        history['RSI'] = compute_rsi(history['Close'])
        
        sma_50 = history['SMA_50'].iloc[-1]
        sma_200 = history['SMA_200'].iloc[-1]
        rsi_val = history['RSI'].iloc[-1]
        
        # Signal evaluation
        trend = "Bullish (Golden Cross)" if sma_50 > sma_200 else "Bearish (Death Cross)"
        
        if rsi_val <= 35 and sma_50 > sma_200:
            signal = "🟢 STRONG BUY (Oversold Dip in Uptrend)"
            active_alerts.append(f"🟢 STRONG BUY: {symbol} is oversold (RSI: {rsi_val:.1f}) in a Golden Cross.")
        elif rsi_val >= 70 or (sma_50 < sma_200 and current_price < sma_50):
            signal = "🔴 STRONG SELL / CAUTION (Overbought or Downtrend)"
            active_alerts.append(f"🔴 SELL ALERT: {symbol} triggered overbought/downtrend risk (RSI: {rsi_val:.1f}).")
        elif current_price > sma_50:
            signal = "🟢 MODERATE BUY (Above 50-SMA)"
        else:
            signal = "⚪ NEUTRAL / HOLD"
            
        news_items = stock.news
        headline_summary = "No recent headlines"
        if news_items:
            headline_summary = news_items[0].get('title') or news_items[0].get('content', {}).get('title', 'N/A')
            headline_summary = headline_summary[:45] + "..."

        watchlist_data.append({
            "Ticker": symbol,
            "Price": f"${current_price:.2f}",
            "RSI (14)": f"{rsi_val:.1f}",
            "50-Day SMA": f"${sma_50:.2f}",
            "200-Day SMA": f"${sma_200:.2f}",
            "Macro Trend": trend,
            "Signal": signal,
            "Latest News": headline_summary,
            "raw_history": history,
            "raw_news": news_items
        })

# --- DISPLAY DASHBOARD ---
if watchlist_data:
    df_display = pd.DataFrame(watchlist_data).drop(columns=["raw_history", "raw_news"])
    st.subheader("📋 Advanced Technical Watchlist")
    st.dataframe(df_display, use_container_width=True)

    # Trigger notifications if alerts exist
    if active_alerts:
        if enable_sound:
            play_chime()
        st.toast(f"🔔 {len(active_alerts)} active alerts detected!")
        if enable_phone and enable_loop and ntfy_topic:
            alert_body = "\n".join(active_alerts[:3])
            send_phone_push(ntfy_topic, alert_body, title=f"Stock Sentinel: {len(active_alerts)} Alerts")

    # --- STOCK DEEP DIVE ---
    st.markdown("---")
    st.subheader("🔍 Stock Analysis Drilldown")
    selected_ticker = st.selectbox("Inspect individual stock details:", tickers)
    
    selected = next((item for item in watchlist_data if item["Ticker"] == selected_ticker), None)
    if selected:
        col_chart, col_details = st.columns([3, 2])
        
        with col_chart:
            st.write(f"**Price, 50-Day SMA & 200-Day SMA for {selected_ticker}**")
            chart_df = selected["raw_history"][['Close', 'SMA_50', 'SMA_200']].tail(120)
            st.line_chart(chart_df)
            
            st.write(f"**14-Day RSI Gauge: {selected['RSI (14)']}** (Overbought > 70 | Oversold < 35)")
            st.line_chart(selected["raw_history"][['RSI']].tail(60))

        with col_details:
            st.write(f"**Market Context for {selected_ticker}**")
            st.info(f"**Current Signal:** {selected['Signal']}")
            st.write(f"**Macro Trend:** {selected['Macro Trend']}")
            st.markdown("---")
            st.write("**Recent Headlines:**")
            if selected["raw_news"]:
                for item in selected["raw_news"][:4]:
                    title = item.get('title') or item.get('content', {}).get('title', 'N/A')
                    link = item.get('link') or item.get('content', {}).get('canonicalUrl', {}).get('url', '#')
                    st.markdown(f"• [{title}]({link})")

    # --- AUTO-REFRESH TIMER ---
    if enable_loop:
        st.caption(f"🔄 Auto-refreshing watchlist every {refresh_interval}s...")
        time.sleep(refresh_interval)
        st.rerun()