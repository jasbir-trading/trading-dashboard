import streamlit as st
import pandas as pd
import numpy as np
import requests
import ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import time

st.set_page_config(
    page_title="🥇 Gold Trading Dashboard",
    page_icon="🥇",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── DARK THEME
st.markdown("""
<style>
body { background:#050508; color:#e0e0e0; }
.stApp { background:#050508; }
.signal-master {
    padding:16px; border-radius:10px; text-align:center;
    font-size:20px; font-weight:700; margin:10px 0;
}
.bull-signal { background:#0d2e1a; border:2px solid #00ff88; color:#00ff88; }
.bear-signal { background:#2e0d0d; border:2px solid #ff4444; color:#ff4444; }
.neutral-signal { background:#1a1a2e; border:2px solid #888; color:#888; }
</style>
""", unsafe_allow_html=True)

# ── SIDEBAR
st.sidebar.title("🥇 Gold Settings")
gold_tf = st.sidebar.selectbox("Timeframe",
    ["15m","1h","4h","1d"], index=2, key="gold_tf")
candles = st.sidebar.slider("Candles", 50, 500, 200, key="gold_candles")
auto_refresh = st.sidebar.checkbox("Auto Refresh 60s", key="gold_refresh")

st.sidebar.markdown("---")
st.sidebar.subheader("📱 Telegram Alerts")
tg_token   = st.sidebar.text_input("Bot Token", type="password",
    value="8247892871:AAEKDmYgPDFaJ0Biy6oOmBn339J-gCUjkDU", key="gold_token")
tg_chat_id = st.sidebar.text_input("Chat ID",
    value="5651074993", key="gold_chat")
alerts_on  = st.sidebar.checkbox("Enable Alerts", value=True, key="gold_alerts")

st.sidebar.markdown("---")
st.sidebar.markdown("""
**⚠️ Avoid Trading During:**
- 🇺🇸 US NFP (1st Friday)
- 🇺🇸 US CPI (monthly)
- 🏦 Fed Meetings (8x/year)
- 🇺🇸 US PPI (monthly)

📅 [Check Calendar](https://forexfactory.com/calendar)
""")

# ── FUNCTIONS
def send_tg(token, chat_id, msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
    except: pass

@st.cache_data(ttl=60)
def get_gold_data(tf, lim):
    """Fetch Gold XAUUSD data"""
    # Method 1 — Yahoo Finance
    try:
        tf_map = {"15m":"15m","1h":"1h","4h":"1h","1d":"1d"}
        yf_tf = tf_map.get(tf, "1h")
        import datetime as dt
        end = int(dt.datetime.now().timestamp())
        days = {"15m":5,"1h":30,"4h":60,"1d":365}.get(tf, 30)
        start = end - (days * 86400)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/GC%3DF?interval={yf_tf}&period1={start}&period2={end}"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=15)
        data = r.json()
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        ohlcv = result["indicators"]["quote"][0]
        rows = []
        for i, t in enumerate(timestamps):
            try:
                o = ohlcv["open"][i]
                h = ohlcv["high"][i]
                l = ohlcv["low"][i]
                c = ohlcv["close"][i]
                v = ohlcv["volume"][i]
                if all(x is not None and x > 0 for x in [o,h,l,c]):
                    rows.append({
                        "time": pd.to_datetime(t, unit="s"),
                        "open": float(o), "high": float(h),
                        "low": float(l), "close": float(c),
                        "volume": float(v or 1000)
                    })
            except: continue
        if rows:
            df = pd.DataFrame(rows).tail(lim).reset_index(drop=True)
            return df
    except: pass

    # Method 2 — Stooq
    try:
        url = "https://stooq.com/q/d/l/?s=xauusd&i=d"
        r = requests.get(url, timeout=10)
        lines = r.text.strip().split('\n')
        rows = []
        for line in lines[1:]:
            parts = line.split(',')
            if len(parts) >= 5:
                rows.append({
                    "time": pd.to_datetime(parts[0]),
                    "open": float(parts[1]), "high": float(parts[2]),
                    "low": float(parts[3]), "close": float(parts[4]),
                    "volume": 1000.0
                })
        if rows:
            df = pd.DataFrame(rows).tail(lim).reset_index(drop=True)
            return df
    except: pass

    return pd.DataFrame()

def add_indicators(df):
    df = df.copy()
    df["ema20"]  = ta.trend.EMAIndicator(df["close"], window=20).ema_indicator()
    df["ema50"]  = ta.trend.EMAIndicator(df["close"], window=50).ema_indicator()
    df["ema200"] = ta.trend.EMAIndicator(df["close"], window=200).ema_indicator()
    df["rsi"]    = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    macd = ta.trend.MACD(df["close"])
    df["macd"]        = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"]   = macd.macd_diff()
    adx = ta.trend.ADXIndicator(df["high"], df["low"], df["close"])
    df["adx"]     = adx.adx()
    df["adx_pos"] = adx.adx_pos()
    df["adx_neg"] = adx.adx_neg()
    bb = ta.volatility.BollingerBands(df["close"])
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_mid"]   = bb.bollinger_mavg()
    df["bb_pct"]   = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])
    df["atr"]      = ta.volatility.AverageTrueRange(
        df["high"], df["low"], df["close"], window=14).average_true_range()
    df["vwap"]   = (df["close"] * df["volume"]).cumsum() / df["volume"].cumsum()
    df["vol_ma"] = df["volume"].rolling(20).mean()
    df["vol_spike"] = df["volume"] > df["vol_ma"] * 1.5
    return df

def detect_smc(df):
    df = df.copy()
    df["prev_high"] = df["high"].shift(1)
    df["prev_low"]  = df["low"].shift(1)
    df["bos_bull"]  = df["high"] > df["prev_high"]
    df["bos_bear"]  = df["low"]  < df["prev_low"]
    df["buy_liq"]   = (df["low"] < df["prev_low"]) & (df["close"] > df["prev_low"])
    df["sell_liq"]  = (df["high"] > df["prev_high"]) & (df["close"] < df["prev_high"])
    df["choch_bull"] = (df["close"] > df["prev_high"]) & (df["close"].shift(1) < df["prev_high"].shift(1))
    df["choch_bear"] = (df["close"] < df["prev_low"])  & (df["close"].shift(1) > df["prev_low"].shift(1))
    lb = 50
    df["range_high"]    = df["high"].rolling(lb).max()
    df["range_low"]     = df["low"].rolling(lb).min()
    df["equilibrium"]   = (df["range_high"] + df["range_low"]) / 2
    df["discount_zone"] = df["close"] < df["equilibrium"]
    df["premium_zone"]  = df["close"] > df["equilibrium"]
    df["zone_pct"]      = (df["close"] - df["range_low"]) / (df["range_high"] - df["range_low"]) * 100
    # Trend bias
    hh_hl = (df["high"] > df["high"].shift(1)) & (df["low"] > df["low"].shift(1))
    lh_ll = (df["high"] < df["high"].shift(1)) & (df["low"] < df["low"].shift(1))
    bull_count = hh_hl.tail(10).sum()
    bear_count = lh_ll.tail(10).sum()
    bias = "BULLISH" if bull_count > bear_count else "BEARISH" if bear_count > bull_count else "RANGING"
    df["trend_bias"] = bias
    return df

def detect_sr_zones(df, n=20):
    support_zones = []
    resistance_zones = []
    for i in range(n, len(df)-n):
        if df["low"].iloc[i] == df["low"].iloc[i-n:i+n].min():
            support_zones.append({"price": df["low"].iloc[i], "touches": 1})
        if df["high"].iloc[i] == df["high"].iloc[i-n:i+n].max():
            resistance_zones.append({"price": df["high"].iloc[i], "touches": 1})
    return support_zones[-5:], resistance_zones[-5:]

# ── MAIN APP
st.title("🥇 Gold Trading Dashboard (XAUUSD)")
st.caption("Full SMC analysis on Gold — BOS, CHoCH, Liquidity, OB, S/R zones")

# Session times
now_utc = datetime.utcnow().hour + datetime.utcnow().minute / 60
london_open = 8 <= now_utc < 17
ny_open     = 13 <= now_utc < 22
overlap     = 13 <= now_utc < 17
asia_open   = now_utc < 8 or now_utc >= 22

sc1,sc2,sc3,sc4 = st.columns(4)
with sc1:
    color = "#00ff88" if london_open else "#ff4444"
    st.markdown(f"""<div style="border:2px solid {color};border-radius:8px;padding:10px;text-align:center;">
    <b style="color:#00bfff;">London</b><br>08:00-17:00 UTC<br>
    <b style="color:{color};">{"🟢 OPEN" if london_open else "🔴 Closed"}</b><br>
    <span style="color:#aaa;font-size:11px;">Most liquidity grabs</span></div>""", unsafe_allow_html=True)
with sc2:
    color = "#00ff88" if ny_open else "#ff4444"
    st.markdown(f"""<div style="border:2px solid {color};border-radius:8px;padding:10px;text-align:center;">
    <b style="color:#00bfff;">New York</b><br>13:00-22:00 UTC<br>
    <b style="color:{color};">{"🟢 OPEN" if ny_open else "🔴 Closed"}</b><br>
    <span style="color:#aaa;font-size:11px;">Biggest moves</span></div>""", unsafe_allow_html=True)
with sc3:
    color = "#FFD700" if overlap else "#888"
    st.markdown(f"""<div style="border:2px solid {color};border-radius:8px;padding:10px;text-align:center;">
    <b style="color:#FFD700;">Overlap</b><br>13:00-17:00 UTC<br>
    <b style="color:{color};">{"🔥 BEST TIME" if overlap else "⚪ Closed"}</b><br>
    <span style="color:#aaa;font-size:11px;">Most volatile!</span></div>""", unsafe_allow_html=True)
with sc4:
    color = "#888"
    st.markdown(f"""<div style="border:2px solid {color};border-radius:8px;padding:10px;text-align:center;">
    <b style="color:#aaa;">Asia</b><br>00:00-08:00 UTC<br>
    <b style="color:#888;">{"🟡 Open" if asia_open else "⚪ Closed"}</b><br>
    <span style="color:#aaa;font-size:11px;">Avoid — choppy</span></div>""", unsafe_allow_html=True)

if overlap:
    st.success("🔥 BEST TIME TO TRADE GOLD — London+NY Overlap active!")
elif london_open or ny_open:
    st.info("✅ Good time to trade — active session open")
else:
    st.warning("⚠️ Asian session — avoid trading Gold now!")

st.markdown("---")

# Load data
with st.spinner("Loading Gold data..."):
    gold_df = get_gold_data(gold_tf, candles)

if not gold_df.empty:
    gold_df = add_indicators(gold_df)
    gold_df = detect_smc(gold_df)
    gold_sup, gold_res = detect_sr_zones(gold_df)

    lat = gold_df.iloc[-1]
    prev = gold_df.iloc[-2]
    gold_price = float(lat["close"])
    gold_bias  = str(lat["trend_bias"])
    price_change = ((lat["close"] - prev["close"]) / prev["close"]) * 100

    # Metrics
    m1,m2,m3,m4,m5,m6 = st.columns(6)
    m1.metric("Gold Price", f"${gold_price:,.2f}", f"{price_change:+.2f}%")
    m2.metric("Bias", gold_bias)
    m3.metric("RSI", f"{lat['rsi']:.1f}")
    m4.metric("ADX", f"{lat['adx']:.1f}", "Strong" if lat["adx"] > 25 else "Weak")
    m5.metric("Zone", f"{lat['zone_pct']:.0f}%",
        "Discount ✅" if lat["discount_zone"] else "Premium")
    m6.metric("EMA200", f"${lat['ema200']:,.2f}",
        "Above ✅" if gold_price > lat["ema200"] else "Below ⚠️")

    # Signal
    sig_score = 0
    if gold_bias == "BULLISH": sig_score += 2
    elif gold_bias == "BEARISH": sig_score -= 2
    if lat["rsi"] < 40: sig_score += 2
    elif lat["rsi"] > 60: sig_score -= 2
    if lat["macd"] > lat["macd_signal"]: sig_score += 1
    else: sig_score -= 1
    if lat["adx"] > 25: sig_score += 1
    if lat["bos_bull"]: sig_score += 2
    if lat["bos_bear"]: sig_score -= 2
    if lat["buy_liq"]: sig_score += 1
    if lat["sell_liq"]: sig_score -= 1
    if lat["discount_zone"]: sig_score += 1
    if lat["premium_zone"]: sig_score -= 1
    if lat["close"] > lat["ema200"]: sig_score += 1
    else: sig_score -= 1

    if sig_score >= 5:   sig_label, sig_css = "🥇 GOLD BULLISH — Look for LONGS", "bull-signal"
    elif sig_score <= -5: sig_label, sig_css = "🥇 GOLD BEARISH — Look for SHORTS", "bear-signal"
    else:                 sig_label, sig_css = "🥇 GOLD NEUTRAL — Wait for signal", "neutral-signal"

    st.markdown(f'<div class="signal-master {sig_css}">{sig_label} | Score: {sig_score}</div>',
        unsafe_allow_html=True)

    st.markdown("---")

    # ── MAIN CHART
    st.markdown("### 📊 Gold Chart")
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.6,0.2,0.2], vertical_spacing=0.03)

    fig.add_trace(go.Candlestick(
        x=gold_df["time"], open=gold_df["open"],
        high=gold_df["high"], low=gold_df["low"], close=gold_df["close"],
        name="Gold", increasing_line_color="#FFD700",
        decreasing_line_color="#ff4444"), row=1,col=1)

    # EMAs
    fig.add_trace(go.Scatter(x=gold_df["time"],y=gold_df["ema20"],
        name="EMA20",line=dict(color="#00ff88",width=1.5)), row=1,col=1)
    fig.add_trace(go.Scatter(x=gold_df["time"],y=gold_df["ema50"],
        name="EMA50",line=dict(color="#FF8C00",width=1.5)), row=1,col=1)
    fig.add_trace(go.Scatter(x=gold_df["time"],y=gold_df["ema200"],
        name="EMA200",line=dict(color="#FF4500",width=2.5)), row=1,col=1)
    fig.add_trace(go.Scatter(x=gold_df["time"],y=gold_df["vwap"],
        name="VWAP",line=dict(color="#00bfff",width=1.5,dash="dot")), row=1,col=1)

    # Bollinger Bands
    fig.add_trace(go.Scatter(x=gold_df["time"],y=gold_df["bb_upper"],
        name="BB Upper",line=dict(color="rgba(255,255,255,0.3)",width=1,dash="dash")), row=1,col=1)
    fig.add_trace(go.Scatter(x=gold_df["time"],y=gold_df["bb_lower"],
        name="BB Lower",line=dict(color="rgba(255,255,255,0.3)",width=1,dash="dash"),
        fill="tonexty",fillcolor="rgba(255,255,255,0.02)"), row=1,col=1)

    # S/R zones
    for zone in gold_sup[:4]:
        fig.add_hline(y=zone["price"],line_dash="dash",
            line_color="rgba(0,255,136,0.6)",line_width=1,
            annotation_text=f"S ${zone['price']:,.0f}",
            annotation_font_color="#00ff88",annotation_position="right",
            row=1,col=1)
    for zone in gold_res[:4]:
        fig.add_hline(y=zone["price"],line_dash="dash",
            line_color="rgba(255,68,68,0.6)",line_width=1,
            annotation_text=f"R ${zone['price']:,.0f}",
            annotation_font_color="#ff4444",annotation_position="right",
            row=1,col=1)

    # BOS markers
    bos_b = gold_df[gold_df["bos_bull"]].tail(5)
    if not bos_b.empty:
        fig.add_trace(go.Scatter(x=bos_b["time"],y=bos_b["high"]*1.001,
            mode="markers+text",marker=dict(symbol="triangle-up",color="#00ff88",size=12),
            text=["BOS"]*len(bos_b),textposition="top center",
            textfont=dict(color="#00ff88",size=10),name="BOS Bull"), row=1,col=1)

    bos_br = gold_df[gold_df["bos_bear"]].tail(5)
    if not bos_br.empty:
        fig.add_trace(go.Scatter(x=bos_br["time"],y=bos_br["low"]*0.999,
            mode="markers+text",marker=dict(symbol="triangle-down",color="#ff4444",size=12),
            text=["BOS"]*len(bos_br),textposition="bottom center",
            textfont=dict(color="#ff4444",size=10),name="BOS Bear"), row=1,col=1)

    # CHoCH markers
    choch_b = gold_df[gold_df["choch_bull"]].tail(3)
    if not choch_b.empty:
        fig.add_trace(go.Scatter(x=choch_b["time"],y=choch_b["high"]*1.002,
            mode="markers+text",marker=dict(symbol="diamond",color="#00ffff",size=10),
            text=["CHoCH"]*len(choch_b),textposition="top center",
            textfont=dict(color="#00ffff",size=9),name="CHoCH Bull"), row=1,col=1)

    # Liquidity sweeps
    buy_liq = gold_df[gold_df["buy_liq"]].tail(5)
    if not buy_liq.empty:
        fig.add_trace(go.Scatter(x=buy_liq["time"],y=buy_liq["low"]*0.999,
            mode="markers",marker=dict(symbol="star",color="#00ffff",size=12),
            name="Buy Liq Sweep"), row=1,col=1)

    sell_liq = gold_df[gold_df["sell_liq"]].tail(5)
    if not sell_liq.empty:
        fig.add_trace(go.Scatter(x=sell_liq["time"],y=sell_liq["high"]*1.001,
            mode="markers",marker=dict(symbol="star",color="#ff8800",size=12),
            name="Sell Liq Sweep"), row=1,col=1)

    # MACD
    macd_colors = ["#00ff88" if v >= 0 else "#ff4444" for v in gold_df["macd_hist"]]
    fig.add_trace(go.Bar(x=gold_df["time"],y=gold_df["macd_hist"],
        name="MACD Hist",marker_color=macd_colors,opacity=0.7), row=2,col=1)
    fig.add_trace(go.Scatter(x=gold_df["time"],y=gold_df["macd"],
        name="MACD",line=dict(color="#00bfff",width=1.2)), row=2,col=1)
    fig.add_trace(go.Scatter(x=gold_df["time"],y=gold_df["macd_signal"],
        name="Signal",line=dict(color="#FFD700",width=1.2)), row=2,col=1)

    # RSI
    fig.add_trace(go.Scatter(x=gold_df["time"],y=gold_df["rsi"],
        name="RSI",line=dict(color="#bf00ff",width=1.5)), row=3,col=1)
    fig.add_hline(y=70,line_dash="dash",line_color="rgba(255,68,68,0.5)",row=3,col=1)
    fig.add_hline(y=50,line_dash="dot", line_color="rgba(255,255,255,0.2)",row=3,col=1)
    fig.add_hline(y=30,line_dash="dash",line_color="rgba(0,255,136,0.5)",row=3,col=1)

    fig.update_layout(
        height=750, template="plotly_dark",
        paper_bgcolor="#050508", plot_bgcolor="#050508",
        xaxis_rangeslider_visible=False,
        title=dict(text=f"🥇 Gold XAUUSD | {gold_tf} | EMA20+50+200 + VWAP | BOS/CHoCH/Liquidity",
            font=dict(color="#FFD700",size=14)),
        legend=dict(orientation="h",y=1.02,font=dict(size=10)),
        margin=dict(t=60,b=20,l=10,r=100)
    )
    fig.update_xaxes(gridcolor="#0d0d18")
    fig.update_yaxes(gridcolor="#0d0d18")
    fig.update_yaxes(title_text="Price $", row=1,col=1)
    fig.update_yaxes(title_text="MACD",   row=2,col=1)
    fig.update_yaxes(title_text="RSI",    row=3,col=1)
    st.plotly_chart(fig, use_container_width=True, key="gold_main")

    st.markdown("---")

    # ── SETUP CHECKER
    st.subheader("🎯 Gold Setup Checker")

    gc1, gc2 = st.columns(2)

    with gc1:
        st.markdown("### 🟢 Long Setup (16 Conditions)")
        long_checks = [
            ("Trend Bias Bullish",       gold_bias == "BULLISH"),
            ("Price above EMA200",       gold_price > float(lat["ema200"])),
            ("Price above EMA50",        gold_price > float(lat["ema50"])),
            ("Price above EMA20",        gold_price > float(lat["ema20"])),
            ("Discount Zone (<50%)",     bool(lat["discount_zone"])),
            ("RSI below 55",             float(lat["rsi"]) < 55),
            ("RSI above 30 (not oversold)", float(lat["rsi"]) > 30),
            ("MACD bullish cross",       float(lat["macd"]) > float(lat["macd_signal"])),
            ("ADX strong (>25)",         float(lat["adx"]) > 25),
            ("+DI above -DI",            float(lat["adx_pos"]) > float(lat["adx_neg"])),
            ("BOS bullish",              bool(lat["bos_bull"])),
            ("CHoCH bullish",            bool(lat["choch_bull"])),
            ("Buy liquidity sweep",      bool(lat["buy_liq"])),
            ("Above VWAP",               gold_price > float(lat["vwap"])),
            ("BB not upper (not overbought)", float(lat["bb_pct"]) < 0.8),
            ("London/NY session",        london_open or ny_open),
        ]
        long_score = sum(1 for _,v in long_checks if v)
        if long_score >= 10:   l_color, l_emoji = "#00ff88", "🔥🔥🔥 PERFECT LONG!"
        elif long_score >= 7:  l_color, l_emoji = "#00cc66", "🔥🔥 STRONG LONG"
        elif long_score >= 5:  l_color, l_emoji = "#88ff88", "🔥 MODERATE"
        else:                   l_color, l_emoji = "#444",    "⚪ WAIT"

        st.markdown(f"""
        <div style="background:#0d1f0d;border:2px solid {l_color};border-radius:10px;
        padding:12px;text-align:center;margin:8px 0;">
        <b style="color:{l_color};font-size:24px;">{long_score}/16</b><br>
        <b style="color:{l_color};">{l_emoji}</b>
        </div>""", unsafe_allow_html=True)

        for name, val in long_checks:
            color = "#00ff88" if val else "#333"
            st.markdown(f'<span style="color:{color};font-size:13px;">{"✅" if val else "❌"} {name}</span>',
                unsafe_allow_html=True)

    with gc2:
        st.markdown("### 🔴 Short Setup (16 Conditions)")
        short_checks = [
            ("Trend Bias Bearish",       gold_bias == "BEARISH"),
            ("Price below EMA200",       gold_price < float(lat["ema200"])),
            ("Price below EMA50",        gold_price < float(lat["ema50"])),
            ("Price below EMA20",        gold_price < float(lat["ema20"])),
            ("Premium Zone (>50%)",      bool(lat["premium_zone"])),
            ("RSI above 45",             float(lat["rsi"]) > 45),
            ("RSI below 70 (not overbought)", float(lat["rsi"]) < 70),
            ("MACD bearish cross",       float(lat["macd"]) < float(lat["macd_signal"])),
            ("ADX strong (>25)",         float(lat["adx"]) > 25),
            ("-DI above +DI",            float(lat["adx_neg"]) > float(lat["adx_pos"])),
            ("BOS bearish",              bool(lat["bos_bear"])),
            ("CHoCH bearish",            bool(lat["choch_bear"])),
            ("Sell liquidity sweep",     bool(lat["sell_liq"])),
            ("Below VWAP",               gold_price < float(lat["vwap"])),
            ("BB not lower (not oversold)", float(lat["bb_pct"]) > 0.2),
            ("London/NY session",        london_open or ny_open),
        ]
        short_score = sum(1 for _,v in short_checks if v)
        if short_score >= 10:   s_color, s_emoji = "#ff4444", "🔥🔥🔥 PERFECT SHORT!"
        elif short_score >= 7:  s_color, s_emoji = "#cc3333", "🔥🔥 STRONG SHORT"
        elif short_score >= 5:  s_color, s_emoji = "#ff8888", "🔥 MODERATE"
        else:                    s_color, s_emoji = "#444",    "⚪ WAIT"

        st.markdown(f"""
        <div style="background:#1f0d0d;border:2px solid {s_color};border-radius:10px;
        padding:12px;text-align:center;margin:8px 0;">
        <b style="color:{s_color};font-size:24px;">{short_score}/16</b><br>
        <b style="color:{s_color};">{s_emoji}</b>
        </div>""", unsafe_allow_html=True)

        for name, val in short_checks:
            color = "#ff4444" if val else "#333"
            st.markdown(f'<span style="color:{color};font-size:13px;">{"✅" if val else "❌"} {name}</span>',
                unsafe_allow_html=True)

    # Telegram alerts
    if alerts_on and tg_token and tg_chat_id:
        if long_score >= 10:
            send_tg(tg_token, tg_chat_id,
                f"🥇🟢🟢🟢 <b>PERFECT GOLD LONG!</b>\n"
                f"Score: {long_score}/16\n"
                f"Price: ${gold_price:,.2f}\n"
                f"RSI: {lat['rsi']:.1f}\n"
                f"Bias: {gold_bias}\n"
                f"Time: {datetime.now().strftime('%H:%M')}\n"
                f"⚡ Wait for 15m BOS then ENTER!")
        elif long_score >= 7:
            send_tg(tg_token, tg_chat_id,
                f"🥇🟢🟢 <b>STRONG GOLD LONG</b>\n"
                f"Score: {long_score}/16\n"
                f"Price: ${gold_price:,.2f}\n"
                f"Time: {datetime.now().strftime('%H:%M')}")
        if short_score >= 10:
            send_tg(tg_token, tg_chat_id,
                f"🥇🔴🔴🔴 <b>PERFECT GOLD SHORT!</b>\n"
                f"Score: {short_score}/16\n"
                f"Price: ${gold_price:,.2f}\n"
                f"RSI: {lat['rsi']:.1f}\n"
                f"Bias: {gold_bias}\n"
                f"Time: {datetime.now().strftime('%H:%M')}\n"
                f"⚡ Wait for 15m BOS down then ENTER!")
        elif short_score >= 7:
            send_tg(tg_token, tg_chat_id,
                f"🥇🔴🔴 <b>STRONG GOLD SHORT</b>\n"
                f"Score: {short_score}/16\n"
                f"Price: ${gold_price:,.2f}\n"
                f"Time: {datetime.now().strftime('%H:%M')}")

    st.markdown("---")

    # ── KEY LEVELS
    st.subheader("🎯 Key Price Levels")
    kc1,kc2,kc3 = st.columns(3)
    with kc1:
        st.markdown("**Support Levels**")
        for z in gold_sup[-4:]:
            dist = (gold_price - z["price"]) / gold_price * 100
            st.markdown(f'🟢 **${z["price"]:,.2f}** — -{dist:.2f}% below')
    with kc2:
        st.markdown("**Current Position**")
        st.metric("Price", f"${gold_price:,.2f}")
        st.metric("Zone", f"{lat['zone_pct']:.0f}%")
        st.metric("vs EMA200", f"${gold_price - lat['ema200']:+,.2f}")
    with kc3:
        st.markdown("**Resistance Levels**")
        for z in gold_res[-4:]:
            dist = (z["price"] - gold_price) / gold_price * 100
            st.markdown(f'🔴 **${z["price"]:,.2f}** — +{dist:.2f}% above')

    st.markdown("---")

    # ── GOLD TRADING GUIDE
    st.subheader("📚 Gold Trading Guide")
    tg1, tg2, tg3 = st.columns(3)
    with tg1:
        st.success("""
**✅ Best Times:**
• London Open 8-12 UTC
• NY Open 13-17 UTC
• Overlap 13-17 UTC 🔥

**✅ Best Setups:**
• Liquidity sweep + BOS
• OB retest in discount
• CHoCH after sweep
        """)
    with tg2:
        st.error("""
**❌ Avoid:**
• Asian session (choppy)
• 30min before news
• Friday after 5pm UTC
• When ADX below 20
• Revenge trading

**❌ Never:**
• Trade without SL
• Move SL against you
        """)
    with tg3:
        st.info("""
**💡 Gold Facts:**
• Gold up = USD down
• Check DXY daily
• 1 pip = $1 per 0.01 lot
• Daily range 1000-2000 pips
• Most volatile: NY open

**📱 Resources:**
• forexfactory.com/calendar
• tradingview.com XAUUSD
        """)

else:
    st.error("❌ Could not load Gold data")
    st.info("""
    **Try manually on TradingView:**
    1. Go to tradingview.com
    2. Search: XAUUSD
    3. Apply same SMC strategy
    4. Look for: Liquidity sweep → BOS → OB entry
    """)

# Auto refresh
if auto_refresh:
    time.sleep(60)
    st.rerun()

st.markdown("---")
st.caption("🥇 Gold Trading Dashboard | Education only. Never risk money you cannot afford to lose.")
