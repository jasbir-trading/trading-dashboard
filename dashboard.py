import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import requests
import time
import json

st.set_page_config(layout="wide", page_title="Full SMC Dashboard + AI", page_icon="📊")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;600;700&display=swap');
* { font-family: 'Rajdhani', sans-serif; }
.signal-master {
    padding: 16px; border-radius: 10px; text-align: center;
    font-size: 26px; font-weight: 700; letter-spacing: 2px; margin: 8px 0;
}
.bull-signal  { background: #0d3b1e; color: #00ff88; border: 1px solid #00ff88; box-shadow: 0 0 20px #00ff8833; }
.bear-signal  { background: #3b0d0d; color: #ff4444; border: 1px solid #ff4444; box-shadow: 0 0 20px #ff444433; }
.neutral-signal { background: #1a1a2e; color: #aaa; border: 1px solid #555; }
.zone-tag {
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 12px; font-weight: 600; margin: 2px;
}
.ob-bull  { background: #00ff8822; color: #00ff88; border: 1px solid #00ff8844; }
.ob-bear  { background: #ff444422; color: #ff4444; border: 1px solid #ff444444; }
.fvg-bull { background: #00bfff22; color: #00bfff; border: 1px solid #00bfff44; }
.fvg-bear { background: #ff880022; color: #ff8800; border: 1px solid #ff880044; }
.sr-sup   { background: #00ff8815; color: #00ff88; border: 1px solid #00ff8833; }
.sr-res   { background: #ff444415; color: #ff4444; border: 1px solid #ff444433; }
.liq-tag  { background: #bf00ff22; color: #bf00ff; border: 1px solid #bf00ff44; }
.smc-card { background: #0d0d1a; border: 1px solid #1e1e3a; border-radius: 8px; padding: 12px 16px; margin: 4px 0; }
.ai-box {
    background: linear-gradient(135deg, #0a0a1a, #0d0d2a);
    border: 1px solid #00bfff55;
    border-radius: 12px;
    padding: 20px;
    margin: 10px 0;
    box-shadow: 0 0 30px #00bfff11;
}
.ai-msg-user {
    background: #1a1a2e;
    border-left: 3px solid #00bfff;
    padding: 10px 14px;
    border-radius: 6px;
    margin: 6px 0;
    color: #ccc;
}
.ai-msg-assistant {
    background: #0d1f0d;
    border-left: 3px solid #00ff88;
    padding: 10px 14px;
    border-radius: 6px;
    margin: 6px 0;
    color: #00ff88;
    white-space: pre-wrap;
}
</style>
""", unsafe_allow_html=True)

# ── SIDEBAR
st.sidebar.title("Settings")
coin       = st.sidebar.selectbox("Coin", [
    "BTC/USDT","ETH/USDT","SOL/USDT","ADA/USDT","MATIC/USDT",
    "BNB/USDT","AVAX/USDT","LINK/USDT","DOT/USDT","ATOM/USDT",
    "NEAR/USDT","FTM/USDT","OP/USDT","ARB/USDT","APT/USDT",
    "DOGE/USDT","SHIB/USDT","XRP/USDT","LTC/USDT","TRX/USDT",
    "UNI/USDT","AAVE/USDT","INJ/USDT","SUI/USDT","SEI/USDT",
    "WLD/USDT","FET/USDT","RNDR/USDT","IMX/USDT","SAND/USDT"
])
# Multi timeframe setup
st.sidebar.markdown("**Timeframe Setup:**")
tf_daily  = st.sidebar.checkbox("Daily (Direction)", value=True, key="tf_d")
tf_4h     = st.sidebar.checkbox("4H (Direction)",    value=True, key="tf_4")
tf_1h     = st.sidebar.checkbox("1H (Liquidity)",    value=True, key="tf_1")
tf_entry  = st.sidebar.selectbox("Entry TF", ["15m","5m"], key="tf_e")
timeframe = "4h"   # used for main analysis
entry_tf  = tf_entry
limit      = st.sidebar.slider("Candles", 100, 500, 200, key="auto_2")
auto_refresh = st.sidebar.checkbox("Auto Refresh 30s", key="auto_3")
st.sidebar.markdown("---")
st.sidebar.subheader("Telegram")
tg_token   = st.sidebar.text_input("Bot Token", type="password", value="8247892871:AAEKDmYgPDFaJ0Biy6oOmBn339J-gCUjkDU", key="auto_4")
tg_chat_id = st.sidebar.text_input("Chat ID", value="5651074933", key="auto_5")
alerts_on  = st.sidebar.checkbox("Enable Alerts", value=True, key="auto_6")
st.sidebar.markdown("---")
alt_coins  = st.sidebar.multiselect("BTC Rotation Coins",
    ["ETH/USDT","SOL/USDT","ADA/USDT","MATIC/USDT","BNB/USDT","AVAX/USDT","LINK/USDT","DOT/USDT","ATOM/USDT","NEAR/USDT","OP/USDT","ARB/USDT","DOGE/USDT","XRP/USDT","INJ/USDT","SUI/USDT"], default=["SOL/USDT","ETH/USDT"])

# Auto refresh options
if auto_refresh:
    refresh_speed = st.sidebar.selectbox("Refresh Speed",
        ["30s","60s","2min","5min"], index=0, key="ref_speed")
    speed_map = {"30s":30,"60s":60,"2min":120,"5min":300}
    time.sleep(speed_map.get(refresh_speed, 30))
    st.rerun()

# Manual refresh button
if st.sidebar.button("🔄 Refresh Now"):
    st.cache_data.clear()
    st.rerun()

# ── HELPERS
def send_tg(token, chat_id, msg):
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}, timeout=5)
    except: pass

def detect_patterns(df):
    patterns = []
    n = len(df)
    if n < 20:
        return patterns

    highs  = df["high"].values
    lows   = df["low"].values
    closes = df["close"].values
    atr    = df["atr"].iloc[-1]
    tol    = atr * 0.5

    # Double Top
    for i in range(10, n-5):
        for j in range(i+5, n-3):
            h1 = highs[i]; h2 = highs[j]
            valley = min(lows[i:j])
            if (abs(h1-h2) < tol and h1 > valley + atr*2 and
                h2 > valley + atr*2 and closes[-1] < valley + tol):
                patterns.append({"name":"Double Top 🔴","type":"bearish",
                    "signal":"BEARISH REVERSAL",
                    "detail":f"Two peaks near ${(h1+h2)/2:,.0f} — expecting DROP",
                    "action":"Look for short after neckline break","strength":"🔥🔥🔥"})
                break

    # Double Bottom
    for i in range(10, n-5):
        for j in range(i+5, n-3):
            l1 = lows[i]; l2 = lows[j]
            peak = max(highs[i:j])
            if (abs(l1-l2) < tol and l1 < peak - atr*2 and
                l2 < peak - atr*2 and closes[-1] > peak - tol):
                patterns.append({"name":"Double Bottom 🟢","type":"bullish",
                    "signal":"BULLISH REVERSAL",
                    "detail":f"Two lows near ${(l1+l2)/2:,.0f} — expecting PUMP",
                    "action":"Look for long after neckline break","strength":"🔥🔥🔥"})
                break

    # Bull Flag
    if n >= 15:
        seg = df.tail(15)
        first5 = seg.head(5); last10 = seg.tail(10)
        pole_up = (first5["close"].iloc[-1]-first5["close"].iloc[0])/first5["close"].iloc[0] > 0.02
        flag_cons = abs(last10["close"].iloc[-1]-last10["close"].iloc[0])/last10["close"].iloc[0] < 0.01
        if pole_up and flag_cons:
            patterns.append({"name":"Bull Flag 🟢","type":"bullish",
                "signal":"BULLISH CONTINUATION",
                "detail":"Strong up move followed by tight consolidation",
                "action":"Enter long on breakout above flag","strength":"🔥🔥"})

    # Bear Flag
    if n >= 15:
        seg = df.tail(15)
        first5 = seg.head(5); last10 = seg.tail(10)
        pole_down = (first5["close"].iloc[-1]-first5["close"].iloc[0])/first5["close"].iloc[0] < -0.02
        flag_cons = abs(last10["close"].iloc[-1]-last10["close"].iloc[0])/last10["close"].iloc[0] < 0.01
        if pole_down and flag_cons:
            patterns.append({"name":"Bear Flag 🔴","type":"bearish",
                "signal":"BEARISH CONTINUATION",
                "detail":"Strong down move followed by tight consolidation",
                "action":"Enter short on breakdown below flag","strength":"🔥🔥"})

    # Ascending Triangle
    if n >= 20:
        seg = df.tail(20)
        flat_top = max(seg["high"].values)
        rising_lows = all(seg["low"].values[i] >= seg["low"].values[i-1]*0.998
                         for i in range(1, len(seg["low"].values)))
        if (rising_lows and abs(seg["high"].values[-1]-flat_top)/flat_top < 0.01):
            patterns.append({"name":"Ascending Triangle 🟢","type":"bullish",
                "signal":"BULLISH CONTINUATION",
                "detail":f"Flat resistance at ${flat_top:,.0f}, rising lows",
                "action":"Wait for breakout above resistance","strength":"🔥🔥"})

    # Descending Triangle
    if n >= 20:
        seg = df.tail(20)
        flat_bot = min(seg["low"].values)
        falling_highs = all(seg["high"].values[i] <= seg["high"].values[i-1]*1.002
                           for i in range(1, len(seg["high"].values)))
        if (falling_highs and abs(seg["low"].values[-1]-flat_bot)/flat_bot < 0.01):
            patterns.append({"name":"Descending Triangle 🔴","type":"bearish",
                "signal":"BEARISH CONTINUATION",
                "detail":f"Flat support at ${flat_bot:,.0f}, falling highs",
                "action":"Wait for breakdown below support","strength":"🔥🔥"})

    # Symmetrical Triangle
    if n >= 20:
        seg = df.tail(20)
        falling_highs = seg["high"].iloc[-1] < seg["high"].iloc[0]
        rising_lows   = seg["low"].iloc[-1]  > seg["low"].iloc[0]
        if falling_highs and rising_lows:
            patterns.append({"name":"Symmetrical Triangle ⚪","type":"neutral",
                "signal":"BREAKOUT PENDING",
                "detail":"Compression — big move coming either direction",
                "action":"Wait for breakout direction then follow","strength":"🔥🔥"})

    # Rising Wedge
    if n >= 20:
        seg = df.tail(20)
        h_rise = (seg["high"].iloc[-1]-seg["high"].iloc[0])/seg["high"].iloc[0]
        l_rise = (seg["low"].iloc[-1]-seg["low"].iloc[0])/seg["low"].iloc[0]
        if seg["high"].iloc[-1] > seg["high"].iloc[0] and seg["low"].iloc[-1] > seg["low"].iloc[0] and l_rise > h_rise*1.5:
            patterns.append({"name":"Rising Wedge 🔴","type":"bearish",
                "signal":"BEARISH REVERSAL",
                "detail":"Price rising but compressing — breakdown likely",
                "action":"Watch for break below lower trendline","strength":"🔥🔥"})

    # Falling Wedge
    if n >= 20:
        seg = df.tail(20)
        h_rise = (seg["high"].iloc[-1]-seg["high"].iloc[0])/seg["high"].iloc[0]
        l_rise = (seg["low"].iloc[-1]-seg["low"].iloc[0])/seg["low"].iloc[0]
        if seg["high"].iloc[-1] < seg["high"].iloc[0] and seg["low"].iloc[-1] < seg["low"].iloc[0] and abs(l_rise) > abs(h_rise)*1.5:
            patterns.append({"name":"Falling Wedge 🟢","type":"bullish",
                "signal":"BULLISH REVERSAL",
                "detail":"Price falling but compressing — breakout likely",
                "action":"Watch for break above upper trendline","strength":"🔥🔥"})

    # Channel Up
    if n >= 20:
        seg = df.tail(20)
        if (seg["high"].iloc[-1] > seg["high"].iloc[0] and
            seg["low"].iloc[-1] > seg["low"].iloc[0]):
            patterns.append({"name":"Channel Up 🟢","type":"bullish",
                "signal":"BULLISH TREND",
                "detail":"Price trending up in parallel channel",
                "action":"Buy near channel bottom sell near top","strength":"🔥🔥"})

    # Channel Down
    if n >= 20:
        seg = df.tail(20)
        if (seg["high"].iloc[-1] < seg["high"].iloc[0] and
            seg["low"].iloc[-1] < seg["low"].iloc[0]):
            patterns.append({"name":"Channel Down 🔴","type":"bearish",
                "signal":"BEARISH TREND",
                "detail":"Price trending down in parallel channel",
                "action":"Sell near channel top cover near bottom","strength":"🔥🔥"})

    return patterns


@st.cache_data(ttl=60)
def get_data(symbol, tf, lim):
    # Try multiple methods to get data
    symbol_clean = symbol.replace("/","")

    # Method 1: Direct Binance REST API
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol_clean}&interval={tf}&limit={lim}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            df = pd.DataFrame(data, columns=[
                "time","open","high","low","close","volume",
                "close_time","qav","trades","tbbav","tbqav","ignore"])
            df["time"] = pd.to_datetime(df["time"], unit="ms")
            for c in ["open","high","low","close","volume"]:
                df[c] = df[c].astype(float)
            return df[["time","open","high","low","close","volume"]]
    except: pass

    # Method 2: CCXT
    try:
        exchange = ccxt.binance({
            "enableRateLimit": True,
            "options": {"defaultType": "spot"}
        })
        candles = exchange.fetch_ohlcv(symbol, tf, limit=lim)
        df = pd.DataFrame(candles, columns=["time","open","high","low","close","volume"])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        for c in ["open","high","low","close","volume"]:
            df[c] = df[c].astype(float)
        return df
    except: pass

    # Method 3: Binance US API
    try:
        url = f"https://api.binance.us/api/v3/klines?symbol={symbol_clean}&interval={tf}&limit={lim}"
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            df = pd.DataFrame(data, columns=[
                "time","open","high","low","close","volume",
                "close_time","qav","trades","tbbav","tbqav","ignore"])
            df["time"] = pd.to_datetime(df["time"], unit="ms")
            for c in ["open","high","low","close","volume"]:
                df[c] = df[c].astype(float)
            return df[["time","open","high","low","close","volume"]]
    except: pass

    return pd.DataFrame()

# ── INDICATORS
def add_indicators(df):
    df = df.copy()
    df["rsi"]    = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    stoch = ta.momentum.StochRSIIndicator(df["close"])
    df["stoch_k"] = stoch.stochrsi_k()
    df["stoch_d"] = stoch.stochrsi_d()
    macd = ta.trend.MACD(df["close"])
    df["macd"]        = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"]   = macd.macd_diff()
    df["ema9"]   = ta.trend.EMAIndicator(df["close"], window=9).ema_indicator()
    df["ema20"]  = ta.trend.EMAIndicator(df["close"], window=20).ema_indicator()
    df["ema50"]  = ta.trend.EMAIndicator(df["close"], window=50).ema_indicator()
    df["ema200"] = ta.trend.EMAIndicator(df["close"], window=200).ema_indicator()
    bb = ta.volatility.BollingerBands(df["close"], window=20, window_dev=2)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_mid"]   = bb.bollinger_mavg()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]
    df["bb_pct"]   = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])
    df["vwap"]     = (df["close"] * df["volume"]).cumsum() / df["volume"].cumsum()
    df["vol_ma"]   = df["volume"].rolling(20).mean()
    df["vol_spike"] = df["volume"] > df["vol_ma"] * 1.5
    df["atr"]     = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"], window=14).average_true_range()
    df["atr_pct"] = df["atr"] / df["close"] * 100
    adx = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14)
    df["adx"]     = adx.adx()
    df["adx_pos"] = adx.adx_pos()
    df["adx_neg"] = adx.adx_neg()

    # ── BOOSTED MOVING AVERAGE (BMA)
    # BMA = EMA + momentum boost based on rate of change
    # When price is accelerating up = BMA rises faster than regular EMA
    # When price is decelerating = BMA gives early warning before price turns
    for period in [20, 50]:
        ema   = df["close"].ewm(span=period).mean()
        roc   = df["close"].pct_change(3) * 100          # 3-bar rate of change
        boost = ema * (1 + roc * 0.1)                    # boost = EMA amplified by momentum
        df[f"bma{period}"]        = boost
        df[f"bma{period}_signal"] = boost > ema           # True = boosted above EMA = bullish momentum
        df[f"bma{period}_diff"]   = boost - ema           # positive = accelerating up, negative = decelerating

    # BMA Cross signal
    df["bma_bull_cross"] = (df["bma20"] > df["bma50"]) & (df["bma20"].shift(1) <= df["bma50"].shift(1))
    df["bma_bear_cross"] = (df["bma20"] < df["bma50"]) & (df["bma20"].shift(1) >= df["bma50"].shift(1))

    # BMA Momentum color: strong up, weak up, weak down, strong down
    df["bma_momentum"] = "neutral"
    df.loc[df["bma20_diff"] > df["atr"]*0.5, "bma_momentum"]  = "strong_bull"
    df.loc[(df["bma20_diff"] > 0) & (df["bma20_diff"] <= df["atr"]*0.5), "bma_momentum"] = "weak_bull"
    df.loc[df["bma20_diff"] < -df["atr"]*0.5, "bma_momentum"] = "strong_bear"
    df.loc[(df["bma20_diff"] < 0) & (df["bma20_diff"] >= -df["atr"]*0.5), "bma_momentum"] = "weak_bear"

    return df

# ── SUPPORT & RESISTANCE
def detect_sr_zones(df, lookback=5, tolerance=0.002):
    n = len(df)
    highs = []; lows = []
    for i in range(lookback, n - lookback):
        if all(df["high"].iloc[i] >= df["high"].iloc[i-j] for j in range(1, lookback+1)) and \
           all(df["high"].iloc[i] >= df["high"].iloc[i+j] for j in range(1, lookback+1)):
            highs.append(df["high"].iloc[i])
        if all(df["low"].iloc[i] <= df["low"].iloc[i-j] for j in range(1, lookback+1)) and \
           all(df["low"].iloc[i] <= df["low"].iloc[i+j] for j in range(1, lookback+1)):
            lows.append(df["low"].iloc[i])

    def cluster(levels, tol):
        if not levels: return []
        levels = sorted(levels)
        clusters = []; group = [levels[0]]
        for lvl in levels[1:]:
            if (lvl - group[0]) / group[0] < tol:
                group.append(lvl)
            else:
                clusters.append({"price": np.mean(group), "touches": len(group)})
                group = [lvl]
        clusters.append({"price": np.mean(group), "touches": len(group)})
        return clusters

    res = sorted(cluster(highs, tolerance), key=lambda x: x["touches"], reverse=True)[:6]
    sup = sorted(cluster(lows,  tolerance), key=lambda x: x["touches"], reverse=True)[:6]
    return sup, res

# ── FULL SMC
def detect_smc(df):
    df = df.copy(); n = len(df)

    df["swing_high"] = False; df["swing_low"] = False
    for i in range(2, n - 2):
        if (df["high"].iloc[i] > df["high"].iloc[i-1] and df["high"].iloc[i] > df["high"].iloc[i-2] and
            df["high"].iloc[i] > df["high"].iloc[i+1] and df["high"].iloc[i] > df["high"].iloc[i+2]):
            df.at[df.index[i], "swing_high"] = True
        if (df["low"].iloc[i] < df["low"].iloc[i-1] and df["low"].iloc[i] < df["low"].iloc[i-2] and
            df["low"].iloc[i] < df["low"].iloc[i+1] and df["low"].iloc[i] < df["low"].iloc[i+2]):
            df.at[df.index[i], "swing_low"] = True

    df["structure"] = "—"; last_sh = last_sl = None
    for i in range(n):
        if df["swing_high"].iloc[i]:
            if last_sh is not None:
                df.at[df.index[i], "structure"] = "HH" if df["high"].iloc[i] > last_sh else "LH"
            last_sh = df["high"].iloc[i]
        if df["swing_low"].iloc[i]:
            if last_sl is not None:
                df.at[df.index[i], "structure"] = "HL" if df["low"].iloc[i] > last_sl else "LL"
            last_sl = df["low"].iloc[i]

    df["prev_high"] = df["high"].shift(1); df["prev_low"] = df["low"].shift(1)
    df["bos_bull"]   = (df["high"] > df["prev_high"]) & df["swing_high"].shift(1).fillna(False)
    df["bos_bear"]   = (df["low"]  < df["prev_low"])  & df["swing_low"].shift(1).fillna(False)
    df["choch_bull"] = (df["high"] > df["prev_high"]) & (df["structure"].shift(1) == "LH")
    df["choch_bear"] = (df["low"]  < df["prev_low"])  & (df["structure"].shift(1) == "HL")

    df["bull_ob"] = False; df["bear_ob"] = False
    df["bull_ob_high"] = np.nan; df["bull_ob_low"]  = np.nan
    df["bear_ob_high"] = np.nan; df["bear_ob_low"]  = np.nan
    for i in range(1, n - 1):
        if (df["close"].iloc[i] < df["open"].iloc[i] and
            df["close"].iloc[i+1] > df["open"].iloc[i] and df["close"].iloc[i+1] > df["high"].iloc[i]):
            df.at[df.index[i], "bull_ob"] = True
            df.at[df.index[i], "bull_ob_high"] = df["open"].iloc[i]
            df.at[df.index[i], "bull_ob_low"]  = df["low"].iloc[i]
        if (df["close"].iloc[i] > df["open"].iloc[i] and
            df["close"].iloc[i+1] < df["open"].iloc[i] and df["close"].iloc[i+1] < df["low"].iloc[i]):
            df.at[df.index[i], "bear_ob"] = True
            df.at[df.index[i], "bear_ob_high"] = df["high"].iloc[i]
            df.at[df.index[i], "bear_ob_low"]  = df["open"].iloc[i]

    df["fvg_bull"] = False; df["fvg_bear"] = False
    df["fvg_bull_top"] = np.nan; df["fvg_bull_bottom"] = np.nan
    df["fvg_bear_top"] = np.nan; df["fvg_bear_bottom"] = np.nan
    for i in range(2, n):
        if df["low"].iloc[i] > df["high"].iloc[i-2]:
            df.at[df.index[i-1], "fvg_bull"] = True
            df.at[df.index[i-1], "fvg_bull_top"]    = df["low"].iloc[i]
            df.at[df.index[i-1], "fvg_bull_bottom"] = df["high"].iloc[i-2]
        if df["high"].iloc[i] < df["low"].iloc[i-2]:
            df.at[df.index[i-1], "fvg_bear"] = True
            df.at[df.index[i-1], "fvg_bear_top"]    = df["low"].iloc[i-2]
            df.at[df.index[i-1], "fvg_bear_bottom"] = df["high"].iloc[i]

    df["buy_liq"]  = (df["low"] < df["prev_low"])   & (df["close"] > df["prev_low"])
    df["sell_liq"] = (df["high"] > df["prev_high"]) & (df["close"] < df["prev_high"])
    df["buyside_liq"]  = df["swing_high"].copy()
    df["sellside_liq"] = df["swing_low"].copy()

    df["body"]       = (df["close"] - df["open"]).abs()
    df["upper_wick"] = df["high"] - df[["open","close"]].max(axis=1)
    df["lower_wick"] = df[["open","close"]].min(axis=1) - df["low"]
    df["stop_hunt_bull"] = (df["lower_wick"] > df["body"] * 2) & (df["close"] > df["open"])
    df["stop_hunt_bear"] = (df["upper_wick"] > df["body"] * 2) & (df["close"] < df["open"])
    df["liq_void_bull"]  = (df["close"] > df["open"]) & (df["body"] > df["atr"] * 2) & (df["upper_wick"] < df["body"] * 0.1)
    df["liq_void_bear"]  = (df["close"] < df["open"]) & (df["body"] > df["atr"] * 2) & (df["lower_wick"] < df["body"] * 0.1)

    tol = 0.001
    df["equal_highs"] = False; df["equal_lows"] = False
    for i in range(1, n):
        if abs(df["high"].iloc[i] - df["high"].iloc[i-1]) / df["high"].iloc[i-1] < tol:
            df.at[df.index[i], "equal_highs"] = True
        if abs(df["low"].iloc[i] - df["low"].iloc[i-1]) / df["low"].iloc[i-1] < tol:
            df.at[df.index[i], "equal_lows"] = True

    df["inducement_bull"] = df["swing_low"]  & df["buy_liq"].shift(1).fillna(False)
    df["inducement_bear"] = df["swing_high"] & df["sell_liq"].shift(1).fillna(False)

    lb = 50
    df["range_high"]    = df["high"].rolling(lb).max()
    df["range_low"]     = df["low"].rolling(lb).min()
    df["equilibrium"]   = (df["range_high"] + df["range_low"]) / 2
    df["premium_zone"]  = df["close"] > df["equilibrium"]
    df["discount_zone"] = df["close"] < df["equilibrium"]
    df["zone_pct"]      = (df["close"] - df["range_low"]) / (df["range_high"] - df["range_low"]) * 100

    last20     = df["structure"].tail(20)
    bull_count = ((last20 == "HH") | (last20 == "HL")).sum()
    bear_count = ((last20 == "LH") | (last20 == "LL")).sum()
    if bull_count > bear_count:   df["trend_bias"] = "BULLISH"
    elif bear_count > bull_count: df["trend_bias"] = "BEARISH"
    else:                          df["trend_bias"] = "RANGING"

    return df

# ── SIGNAL ENGINE
def full_signal(df, support_zones, resistance_zones):
    lat = df.iloc[-1]; sc = 0; rs = []; price = lat["close"]
    bias = lat["trend_bias"]
    if bias == "BULLISH":  sc += 2; rs.append("Trend Bias: BULLISH 🟢")
    elif bias == "BEARISH": sc -= 2; rs.append("Trend Bias: BEARISH 🔴")
    if lat["close"] > lat["ema20"]:  sc += 1; rs.append("Above EMA20 ✅")
    if lat["close"] > lat["ema50"]:  sc += 1; rs.append("Above EMA50 ✅")
    if lat["close"] > lat["ema200"]: sc += 1; rs.append("Above EMA200 ✅")
    if lat["close"] > lat["vwap"]:   sc += 1; rs.append("Above VWAP ✅")
    if lat["bos_bull"]:   sc += 3; rs.append("Bullish BOS 🚀 ✅")
    if lat["bos_bear"]:   sc -= 3; rs.append("Bearish BOS ⚠️")
    if lat["choch_bull"]: sc += 3; rs.append("Bullish CHoCH — structure flip! 🚀")
    if lat["choch_bear"]: sc -= 3; rs.append("Bearish CHoCH — flip! ⚠️")
    if lat["buy_liq"]:    sc += 2; rs.append("Buy Liquidity Sweep ✅")
    if lat["sell_liq"]:   sc -= 2; rs.append("Sell Liquidity Sweep ⚠️")
    if lat["stop_hunt_bull"]: sc += 2; rs.append("Bullish Stop Hunt 🚀")
    if lat["stop_hunt_bear"]: sc -= 2; rs.append("Bearish Stop Hunt ⚠️")
    if lat["fvg_bull"]:   sc += 2; rs.append("Bullish FVG ✅")
    if lat["fvg_bear"]:   sc -= 2; rs.append("Bearish FVG ⚠️")
    if lat["bull_ob"]:    sc += 2; rs.append("Bullish Order Block ✅")
    if lat["bear_ob"]:    sc -= 2; rs.append("Bearish Order Block ⚠️")
    if lat["liq_void_bull"]: sc += 1; rs.append("Bullish Liquidity Void ✅")
    if lat["liq_void_bear"]: sc -= 1; rs.append("Bearish Liquidity Void ⚠️")
    if lat["discount_zone"]: sc += 1; rs.append("Discount Zone ✅")
    if lat["premium_zone"]:  sc -= 1; rs.append("Premium Zone ⚠️")
    if lat["equal_lows"]:    sc += 1; rs.append("Equal Lows — liq below ⚠️")
    if lat["equal_highs"]:   sc -= 1; rs.append("Equal Highs — liq above ⚠️")
    if lat["inducement_bull"]: sc += 1; rs.append("Bullish Inducement ✅")
    if lat["inducement_bear"]: sc -= 1; rs.append("Bearish Inducement ⚠️")
    for zone in support_zones:
        if abs(price - zone["price"]) / price < 0.005:
            sc += 2; rs.append(f"AT Support ${zone['price']:,.0f} ({zone['touches']} touches) ✅")
    for zone in resistance_zones:
        if abs(price - zone["price"]) / price < 0.005:
            sc -= 2; rs.append(f"AT Resistance ${zone['price']:,.0f} ({zone['touches']} touches) ⚠️")
    if 40 < lat["rsi"] < 65: sc += 1; rs.append("RSI healthy ✅")
    if lat["rsi"] > 75: sc -= 2; rs.append("RSI overbought ⚠️")
    if lat["rsi"] < 25: sc += 2; rs.append("RSI oversold ✅")
    if lat["macd"] > lat["macd_signal"]: sc += 1; rs.append("MACD bullish ✅")
    else: sc -= 1; rs.append("MACD bearish ⚠️")
    if lat["adx"] > 25: sc += 1; rs.append(f"ADX {lat['adx']:.1f} strong ✅")
    if lat["vol_spike"]: sc += 1; rs.append("Volume Spike ✅")
    if lat["bb_pct"] < 0.2: sc += 1; rs.append("Near BB Lower ✅")
    if lat["bb_pct"] > 0.8: sc -= 1; rs.append("Near BB Upper ⚠️")

    # Volume Profile signals
    try:
        vp_tmp = calculate_volume_profile(df, bins=30) if len(df) > 30 else pd.DataFrame()
        if not vp_tmp.empty:
            poc_tmp = vp_tmp[vp_tmp["is_poc"]]["price"].values[0]
            vah_tmp = vp_tmp["vah"].iloc[0]
            val_tmp = vp_tmp["val"].iloc[0]
            if price > vah_tmp:  sc += 1; rs.append("Price above Value Area — bullish ✅")
            elif price < val_tmp: sc -= 1; rs.append("Price below Value Area — bearish ⚠️")
            if abs(price - poc_tmp) / price < 0.003: rs.append(f"Price at POC ${poc_tmp:,.0f} — key level ⚠️")
    except: pass

    # BMA signals
    if lat["bma_momentum"] == "strong_bull": sc += 2; rs.append("BMA Strong Bullish Momentum 🚀 ✅")
    elif lat["bma_momentum"] == "weak_bull": sc += 1; rs.append("BMA Weak Bullish Momentum ✅")
    elif lat["bma_momentum"] == "strong_bear": sc -= 2; rs.append("BMA Strong Bearish Momentum ⚠️")
    elif lat["bma_momentum"] == "weak_bear":   sc -= 1; rs.append("BMA Weak Bearish Momentum ⚠️")
    if lat["bma_bull_cross"]: sc += 2; rs.append("BMA Bullish Cross — momentum accelerating! 🚀")
    if lat["bma_bear_cross"]: sc -= 2; rs.append("BMA Bearish Cross — momentum decelerating ⚠️")
    if sc >= 8:    sig, css = "STRONG BULLISH 🟢🟢", "bull-signal"
    elif sc >= 4:  sig, css = "BULLISH 🟢", "bull-signal"
    elif sc <= -8: sig, css = "STRONG BEARISH 🔴🔴", "bear-signal"
    elif sc <= -4: sig, css = "BEARISH 🔴", "bear-signal"
    else:           sig, css = "NEUTRAL — WAIT ⚪", "neutral-signal"
    return sig, css, sc, 30, rs, lat, bias

# ── HIGH PROBABILITY SETUP CHECKER
def check_high_prob_setup(df, sig, sc, rs, lat, bias):
    """
    Checks for perfect long and short setups
    Returns setup type, score and reasons
    """
    long_score  = 0
    short_score = 0
    long_reasons  = []
    short_reasons = []

    # ── LONG CHECKLIST
    if lat["rsi"] < 40:
        long_score += 1; long_reasons.append("RSI below 40 — oversold ✅")
    if lat["rsi"] < 30:
        long_score += 1; long_reasons.append("RSI below 30 — extreme oversold ✅")
    if lat["macd"] > lat["macd_signal"]:
        long_score += 1; long_reasons.append("MACD bullish cross ✅")
    if lat["adx"] > 25:
        long_score += 1; long_reasons.append("ADX strong trend ✅")
    if lat["bb_pct"] < 0.2:
        long_score += 1; long_reasons.append("Price at BB lower band ✅")
    if lat["stoch_k"] < 0.2 and lat["stoch_k"] > lat["stoch_d"]:
        long_score += 1; long_reasons.append("Stoch K crossing up from below 20 ✅")
    if lat["bma_momentum"] in ["strong_bull","weak_bull"]:
        long_score += 1; long_reasons.append("BMA bullish momentum ✅")
    if lat["bma_bull_cross"]:
        long_score += 1; long_reasons.append("BMA bull cross ✅")
    if lat["bos_bull"]:
        long_score += 1; long_reasons.append("BOS bullish on chart ✅")
    if lat["buy_liq"]:
        long_score += 1; long_reasons.append("Buy liquidity sweep ✅")
    if lat["discount_zone"]:
        long_score += 1; long_reasons.append("Discount zone ✅")
    if lat["choch_bull"]:
        long_score += 1; long_reasons.append("CHoCH bullish flip ✅")
    if lat["close"] > lat["vwap"]:
        long_score += 1; long_reasons.append("Above VWAP ✅")
    if bias == "BULLISH":
        long_score += 1; long_reasons.append("Trend bias bullish ✅")
    if lat["fvg_bull"]:
        long_score += 1; long_reasons.append("Bullish FVG present ✅")
    if lat["stop_hunt_bull"]:
        long_score += 1; long_reasons.append("Bullish stop hunt — reversal likely ✅")

    # ── SHORT CHECKLIST
    if lat["rsi"] > 60:
        short_score += 1; short_reasons.append("RSI above 60 — overbought ✅")
    if lat["rsi"] > 70:
        short_score += 1; short_reasons.append("RSI above 70 — extreme overbought ✅")
    if lat["macd"] < lat["macd_signal"]:
        short_score += 1; short_reasons.append("MACD bearish cross ✅")
    if lat["adx"] > 25:
        short_score += 1; short_reasons.append("ADX strong trend ✅")
    if lat["bb_pct"] > 0.8:
        short_score += 1; short_reasons.append("Price at BB upper band ✅")
    if lat["stoch_k"] > 0.8 and lat["stoch_k"] < lat["stoch_d"]:
        short_score += 1; short_reasons.append("Stoch K crossing down from above 80 ✅")
    if lat["bma_momentum"] in ["strong_bear","weak_bear"]:
        short_score += 1; short_reasons.append("BMA bearish momentum ✅")
    if lat["bma_bear_cross"]:
        short_score += 1; short_reasons.append("BMA bear cross ✅")
    if lat["bos_bear"]:
        short_score += 1; short_reasons.append("BOS bearish on chart ✅")
    if lat["sell_liq"]:
        short_score += 1; short_reasons.append("Sell liquidity sweep ✅")
    if lat["premium_zone"]:
        short_score += 1; short_reasons.append("Premium zone ✅")
    if lat["choch_bear"]:
        short_score += 1; short_reasons.append("CHoCH bearish flip ✅")
    if lat["close"] < lat["vwap"]:
        short_score += 1; short_reasons.append("Below VWAP ✅")
    if bias == "BEARISH":
        short_score += 1; short_reasons.append("Trend bias bearish ✅")
    if lat["fvg_bear"]:
        short_score += 1; short_reasons.append("Bearish FVG present ✅")
    if lat["stop_hunt_bear"]:
        short_score += 1; short_reasons.append("Bearish stop hunt — reversal likely ✅")

    # Determine setup quality
    long_quality  = "PERFECT" if long_score >= 10 else "STRONG" if long_score >= 7 else "MODERATE" if long_score >= 5 else "WEAK"
    short_quality = "PERFECT" if short_score >= 10 else "STRONG" if short_score >= 7 else "MODERATE" if short_score >= 5 else "WEAK"

    return {
        "long_score":    long_score,
        "short_score":   short_score,
        "long_quality":  long_quality,
        "short_quality": short_quality,
        "long_reasons":  long_reasons,
        "short_reasons": short_reasons,
        "max_score":     16
    }

# ── AI TRADE ASSISTANT
def build_market_context(df, lat, sig, sc, rs, bias, support_zones, resistance_zones, coin, timeframe):
    """Build a rich context string of current market data for the AI"""
    recent_struct = df["structure"].tail(10).tolist()
    bull_obs = df[df["bull_ob"]].tail(3)
    bear_obs  = df[df["bear_ob"]].tail(3)
    fvg_bulls = df[df["fvg_bull"]].tail(3)
    fvg_bears = df[df["fvg_bear"]].tail(3)
    eq_highs  = df[df["equal_highs"]].tail(3)
    eq_lows   = df[df["equal_lows"]].tail(3)

    ob_bull_str = ", ".join([f"${r['bull_ob_low']:,.0f}–${r['bull_ob_high']:,.0f}"
                             for _,r in bull_obs.iterrows() if not pd.isna(r["bull_ob_low"])])
    ob_bear_str = ", ".join([f"${r['bear_ob_low']:,.0f}–${r['bear_ob_high']:,.0f}"
                             for _,r in bear_obs.iterrows() if not pd.isna(r["bear_ob_low"])])
    fvg_bull_str = ", ".join([f"${r['fvg_bull_bottom']:,.0f}–${r['fvg_bull_top']:,.0f}"
                              for _,r in fvg_bulls.iterrows() if not pd.isna(r["fvg_bull_bottom"])])
    fvg_bear_str = ", ".join([f"${r['fvg_bear_bottom']:,.0f}–${r['fvg_bear_top']:,.0f}"
                              for _,r in fvg_bears.iterrows() if not pd.isna(r["fvg_bear_bottom"])])
    eqh_str = ", ".join([f"${r['high']:,.0f}" for _,r in eq_highs.iterrows()])
    eql_str = ", ".join([f"${r['low']:,.0f}"  for _,r in eq_lows.iterrows()])

    sup_str = ", ".join([f"${z['price']:,.0f}({z['touches']}x)" for z in support_zones[:4]])
    res_str = ", ".join([f"${z['price']:,.0f}({z['touches']}x)" for z in resistance_zones[:4]])

    context = f"""You are an expert SMC (Smart Money Concepts) crypto trading assistant.
You have access to LIVE market data for {coin} on the {timeframe} timeframe.
Answer questions clearly, concisely, and in a helpful beginner-friendly way.
Always base your answers on the data below. Never make up data.

=== LIVE MARKET DATA ===
Coin: {coin}
Timeframe: {timeframe}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}

Price: ${lat['close']:,.2f}
Signal: {sig}
Score: {sc}/30
Trend Bias: {bias}

=== INDICATORS ===
RSI: {lat['rsi']:.1f} {'(Overbought)' if lat['rsi']>70 else '(Oversold)' if lat['rsi']<30 else '(Healthy)'}
MACD: {lat['macd']:.2f} ({'Bullish' if lat['macd']>lat['macd_signal'] else 'Bearish'})
ADX: {lat['adx']:.1f} ({'Strong trend' if lat['adx']>25 else 'Weak trend'})
ATR: {lat['atr']:.2f} ({lat['atr_pct']:.2f}% of price)
EMA20: ${lat['ema20']:,.2f} ({'Price above' if lat['close']>lat['ema20'] else 'Price below'})
EMA50: ${lat['ema50']:,.2f} ({'Price above' if lat['close']>lat['ema50'] else 'Price below'})
EMA200: ${lat['ema200']:,.2f} ({'Price above' if lat['close']>lat['ema200'] else 'Price below'})
VWAP: ${lat['vwap']:,.2f} ({'Price above' if lat['close']>lat['vwap'] else 'Price below'})
BB%: {lat['bb_pct']*100:.0f}% ({'Near upper' if lat['bb_pct']>0.8 else 'Near lower' if lat['bb_pct']<0.2 else 'Middle'})
Volume: {'SPIKE 🚀' if lat['vol_spike'] else 'Normal'}

=== SMC ZONES ===
Zone Position: {lat['zone_pct']:.0f}% ({'Premium - sell area' if lat['premium_zone'] else 'Discount - buy area'})
Bullish Order Blocks: {ob_bull_str if ob_bull_str else 'None detected'}
Bearish Order Blocks: {ob_bear_str if ob_bear_str else 'None detected'}
Bullish FVGs: {fvg_bull_str if fvg_bull_str else 'None detected'}
Bearish FVGs: {fvg_bear_str if fvg_bear_str else 'None detected'}
Equal Highs (liquidity above): {eqh_str if eqh_str else 'None'}
Equal Lows (liquidity below): {eql_str if eql_str else 'None'}
BOS Bullish: {'YES' if lat['bos_bull'] else 'No'}
BOS Bearish: {'YES' if lat['bos_bear'] else 'No'}
CHoCH Bullish: {'YES' if lat['choch_bull'] else 'No'}
CHoCH Bearish: {'YES' if lat['choch_bear'] else 'No'}
Buy Liquidity Sweep: {'YES' if lat['buy_liq'] else 'No'}
Sell Liquidity Sweep: {'YES' if lat['sell_liq'] else 'No'}
Stop Hunt Bull: {'YES' if lat['stop_hunt_bull'] else 'No'}
Stop Hunt Bear: {'YES' if lat['stop_hunt_bear'] else 'No'}
Recent Market Structure: {recent_struct}

=== SUPPORT & RESISTANCE ===
Support Zones: {sup_str if sup_str else 'Calculating...'}
Resistance Zones: {res_str if res_str else 'Calculating...'}

=== ACTIVE SIGNAL FACTORS ===
{chr(10).join(rs)}
"""
    return context

def ask_ai(question, context, chat_history):
    """Call Claude API with market context"""
    try:
        messages = []
        # Add chat history
        for msg in chat_history[-6:]:  # last 6 messages for context
            messages.append({"role": msg["role"], "content": msg["content"]})
        # Add current question
        messages.append({"role": "user", "content": question})

        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1000,
                "system": context,
                "messages": messages
            },
            timeout=30
        )
        data = response.json()
        if "content" in data and len(data["content"]) > 0:
            return data["content"][0]["text"]
        elif "error" in data:
            return f"Error: {data['error']['message']}"
        else:
            return "Could not get response. Try again."
    except Exception as e:
        return f"Connection error: {str(e)}"

# ── LOAD DATA
with st.spinner("Loading live data..."):
    df = get_data(coin, timeframe, limit)
if df.empty:
    st.error("No data. Check connection."); st.stop()
df = add_indicators(df)
df = detect_smc(df)
support_zones, resistance_zones = detect_sr_zones(df)
sig, css, sc, max_sc, rs, lat, bias = full_signal(df, support_zones, resistance_zones)

df_entry = get_data(coin, entry_tf, 100)
if not df_entry.empty:
    df_entry = add_indicators(df_entry)
    df_entry = detect_smc(df_entry)

# ── HEADER
ca, cb, cc = st.columns([2,1,1])
with ca:
    st.title(f"📊 Full SMC + AI — {coin}")
    st.caption(f"Trend: {timeframe} | Entry: {entry_tf} | {datetime.now().strftime('%H:%M:%S')}")
with cb:
    prev = df["close"].iloc[-2]; pct = (lat["close"] - prev) / prev * 100
    st.metric("Price", f"${lat['close']:,.2f}", f"{'🟢' if pct>0 else '🔴'} {pct:.2f}%")
with cc:
    bc = "🟢" if bias=="BULLISH" else "🔴" if bias=="BEARISH" else "⚪"
    st.metric("Trend Bias", f"{bc} {bias}")

st.markdown(f'<div class="signal-master {css}">{sig} | Score: {sc}/{max_sc}</div>', unsafe_allow_html=True)

m1,m2,m3,m4,m5,m6,m7 = st.columns(7)
m1.metric("RSI",  f"{lat['rsi']:.1f}",  "OB" if lat["rsi"]>70 else "OS" if lat["rsi"]<30 else "OK")
m2.metric("MACD", f"{lat['macd']:.2f}", "Bull" if lat["macd"]>lat["macd_signal"] else "Bear")
m3.metric("ADX",  f"{lat['adx']:.1f}",  "Strong" if lat["adx"]>25 else "Weak")
m4.metric("ATR%", f"{lat['atr_pct']:.2f}%")
m5.metric("Vol",  "SPIKE 🚀" if lat["vol_spike"] else "Normal")
m6.metric("Zone", f"{lat['zone_pct']:.0f}%", "Premium" if lat["premium_zone"] else "Discount")
m7.metric("BB%",  f"{lat['bb_pct']*100:.0f}%")
st.markdown("---")

# ── HIGH PROBABILITY SETUP CHECKER
def check_high_prob_setup(df, sig, sc, rs, lat, bias):
    """
    Checks for perfect long and short setups
    Returns setup type, score and reasons
    """
    long_score  = 0
    short_score = 0
    long_reasons  = []
    short_reasons = []

    # ── LONG CHECKLIST
    if lat["rsi"] < 40:
        long_score += 1; long_reasons.append("RSI below 40 — oversold ✅")
    if lat["rsi"] < 30:
        long_score += 1; long_reasons.append("RSI below 30 — extreme oversold ✅")
    if lat["macd"] > lat["macd_signal"]:
        long_score += 1; long_reasons.append("MACD bullish cross ✅")
    if lat["adx"] > 25:
        long_score += 1; long_reasons.append("ADX strong trend ✅")
    if lat["bb_pct"] < 0.2:
        long_score += 1; long_reasons.append("Price at BB lower band ✅")
    if lat["stoch_k"] < 0.2 and lat["stoch_k"] > lat["stoch_d"]:
        long_score += 1; long_reasons.append("Stoch K crossing up from below 20 ✅")
    if lat["bma_momentum"] in ["strong_bull","weak_bull"]:
        long_score += 1; long_reasons.append("BMA bullish momentum ✅")
    if lat["bma_bull_cross"]:
        long_score += 1; long_reasons.append("BMA bull cross ✅")
    if lat["bos_bull"]:
        long_score += 1; long_reasons.append("BOS bullish on chart ✅")
    if lat["buy_liq"]:
        long_score += 1; long_reasons.append("Buy liquidity sweep ✅")
    if lat["discount_zone"]:
        long_score += 1; long_reasons.append("Discount zone ✅")
    if lat["choch_bull"]:
        long_score += 1; long_reasons.append("CHoCH bullish flip ✅")
    if lat["close"] > lat["vwap"]:
        long_score += 1; long_reasons.append("Above VWAP ✅")
    if bias == "BULLISH":
        long_score += 1; long_reasons.append("Trend bias bullish ✅")
    if lat["fvg_bull"]:
        long_score += 1; long_reasons.append("Bullish FVG present ✅")
    if lat["stop_hunt_bull"]:
        long_score += 1; long_reasons.append("Bullish stop hunt — reversal likely ✅")

    # ── SHORT CHECKLIST
    if lat["rsi"] > 60:
        short_score += 1; short_reasons.append("RSI above 60 — overbought ✅")
    if lat["rsi"] > 70:
        short_score += 1; short_reasons.append("RSI above 70 — extreme overbought ✅")
    if lat["macd"] < lat["macd_signal"]:
        short_score += 1; short_reasons.append("MACD bearish cross ✅")
    if lat["adx"] > 25:
        short_score += 1; short_reasons.append("ADX strong trend ✅")
    if lat["bb_pct"] > 0.8:
        short_score += 1; short_reasons.append("Price at BB upper band ✅")
    if lat["stoch_k"] > 0.8 and lat["stoch_k"] < lat["stoch_d"]:
        short_score += 1; short_reasons.append("Stoch K crossing down from above 80 ✅")
    if lat["bma_momentum"] in ["strong_bear","weak_bear"]:
        short_score += 1; short_reasons.append("BMA bearish momentum ✅")
    if lat["bma_bear_cross"]:
        short_score += 1; short_reasons.append("BMA bear cross ✅")
    if lat["bos_bear"]:
        short_score += 1; short_reasons.append("BOS bearish on chart ✅")
    if lat["sell_liq"]:
        short_score += 1; short_reasons.append("Sell liquidity sweep ✅")
    if lat["premium_zone"]:
        short_score += 1; short_reasons.append("Premium zone ✅")
    if lat["choch_bear"]:
        short_score += 1; short_reasons.append("CHoCH bearish flip ✅")
    if lat["close"] < lat["vwap"]:
        short_score += 1; short_reasons.append("Below VWAP ✅")
    if bias == "BEARISH":
        short_score += 1; short_reasons.append("Trend bias bearish ✅")
    if lat["fvg_bear"]:
        short_score += 1; short_reasons.append("Bearish FVG present ✅")
    if lat["stop_hunt_bear"]:
        short_score += 1; short_reasons.append("Bearish stop hunt — reversal likely ✅")

    # Determine setup quality
    long_quality  = "PERFECT" if long_score >= 10 else "STRONG" if long_score >= 7 else "MODERATE" if long_score >= 5 else "WEAK"
    short_quality = "PERFECT" if short_score >= 10 else "STRONG" if short_score >= 7 else "MODERATE" if short_score >= 5 else "WEAK"

    return {
        "long_score":    long_score,
        "short_score":   short_score,
        "long_quality":  long_quality,
        "short_quality": short_quality,
        "long_reasons":  long_reasons,
        "short_reasons": short_reasons,
        "max_score":     16
    }

# ── AI TRADE ASSISTANT SECTION
st.subheader("🤖 AI Trade Assistant")
st.caption("Ask anything about the current market. The AI reads your live chart data and answers.")

# Initialize chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "market_context" not in st.session_state:
    st.session_state.market_context = ""

# Build fresh context
market_context = build_market_context(df, lat, sig, sc, rs, bias, support_zones, resistance_zones, coin, timeframe)

# Quick question buttons
st.markdown("**Quick Questions:**")
qc1, qc2, qc3, qc4 = st.columns(4)
quick_q = None
with qc1:
    if st.button("Should I long now? 🟢", key="btn_1"):
        quick_q = "Should I go long on this coin right now? Analyse the current SMC data and give me a clear answer."
with qc2:
    if st.button("Should I short now? 🔴", key="btn_2"):
        quick_q = "Should I go short on this coin right now? Analyse the current SMC data and give me a clear answer."
with qc3:
    if st.button("Where is my entry? 🎯", key="btn_3"):
        quick_q = "Based on the current SMC zones, where is the best entry price for a trade? What should I wait for?"
with qc4:
    if st.button("Where is my SL & TP? 📏", key="btn_4"):
        quick_q = "Based on the current data, where should I place my stop loss and take profit levels?"

qc5, qc6, qc7, qc8 = st.columns(4)
with qc5:
    if st.button("What is BTC doing? 📊", key="btn_5"):
        quick_q = "Explain what the market structure is showing right now. Is it bullish or bearish and why?"
with qc6:
    if st.button("Explain the OBs 📦", key="btn_6"):
        quick_q = "Explain the current Order Blocks on the chart. Which ones are important and why?"
with qc7:
    if st.button("Explain FVGs 🔵", key="btn_7"):
        quick_q = "Explain the current Fair Value Gaps. What do they mean for the next price move?"
with qc8:
    if st.button("Liquidity levels? 💧", key="btn_8"):
        quick_q = "Where is the liquidity sitting right now? Where might smart money push price to grab liquidity?"

# Chat input
st.markdown(" ")
user_input = st.chat_input("Ask your AI trading assistant anything... e.g. 'Is this a good time to buy?'")

# Handle input
question_to_ask = quick_q if quick_q else user_input

if question_to_ask:
    # Add to history
    st.session_state.chat_history.append({"role": "user", "content": question_to_ask})
    # Get AI response
    with st.spinner("AI is analysing the market..."):
        ai_response = ask_ai(question_to_ask, market_context, st.session_state.chat_history[:-1])
    st.session_state.chat_history.append({"role": "assistant", "content": ai_response})

# Display chat history
if st.session_state.chat_history:
    st.markdown('<div class="ai-box">', unsafe_allow_html=True)
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(f'<div class="ai-msg-user">👤 You: {msg["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="ai-msg-assistant">🤖 AI: {msg["content"]}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if st.button("🗑️ Clear Chat", key="btn_9"):
        st.session_state.chat_history = []
        st.rerun()

st.markdown("---")

# ── SIGNAL BREAKDOWN
with st.expander("📋 Full Signal Breakdown"):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Bullish Factors**")
        for r in rs:
            if "✅" in r: st.success(r)
    with c2:
        st.markdown("**Bearish / Warning Factors**")
        for r in rs:
            if "⚠️" in r: st.error(r)

# ── HIGH PROBABILITY SETUP CHECKER
st.markdown("---")
st.subheader("🎯 High Probability Trade Setup Checker")
st.caption("Checks ALL timeframes — Daily, 4H, 1H, 15m — alerts fire when 7+ conditions met on ANY timeframe")

# ── Run checker on ALL timeframes
all_setups = {}
bull_count = 0
bear_count = 0
bvol = 0
svol = 0

# Load extra timeframes if not already loaded
try:
    _df_daily = get_data(coin, "1d", 200)
    _df_daily = add_indicators(_df_daily) if not _df_daily.empty else pd.DataFrame()
    if not _df_daily.empty: _df_daily = detect_smc(_df_daily)
except: _df_daily = pd.DataFrame()

try:
    _df_4h = get_data(coin, "4h", 200)
    _df_4h = add_indicators(_df_4h) if not _df_4h.empty else pd.DataFrame()
    if not _df_4h.empty: _df_4h = detect_smc(_df_4h)
except: _df_4h = pd.DataFrame()

try:
    _df_1h = get_data(coin, "1h", 200)
    _df_1h = add_indicators(_df_1h) if not _df_1h.empty else pd.DataFrame()
    if not _df_1h.empty: _df_1h = detect_smc(_df_1h)
except: _df_1h = pd.DataFrame()

try:
    _df_entry = get_data(coin, tf_entry, 150)
    _df_entry = add_indicators(_df_entry) if not _df_entry.empty else pd.DataFrame()
    if not _df_entry.empty: _df_entry = detect_smc(_df_entry)
except: _df_entry = pd.DataFrame()

tf_map = {
    "Daily":   (_df_daily, "1d"),
    "4H":      (_df_4h,    "4h"),
    "1H":      (_df_1h,    "1h"),
    tf_entry:  (_df_entry, tf_entry),
}

for tf_label, (df_tmp, tf_str) in tf_map.items():
    if not df_tmp.empty:
        try:
            tmp_sup, tmp_res = detect_sr_zones(df_tmp)
            tmp_sig, tmp_css, tmp_sc, tmp_max, tmp_rs, tmp_lat, tmp_bias = full_signal(df_tmp, tmp_sup, tmp_res)
            all_setups[tf_label] = check_high_prob_setup(df_tmp, tmp_sig, tmp_sc, tmp_rs, tmp_lat, tmp_bias)
            all_setups[tf_label]["tf_str"] = tf_str
            all_setups[tf_label]["lat"]    = tmp_lat
            all_setups[tf_label]["bias"]   = tmp_bias
        except:
            pass

# Use 4H as main for display
setup = all_setups.get("4H", check_high_prob_setup(df, sig, sc, rs, lat, bias))
long_score  = setup["long_score"]
short_score = setup["short_score"]
max_score   = setup["max_score"]

# ── MULTI-TF SETUP SUMMARY
st.markdown("### 📊 Setup Score Across All Timeframes")
tf_cols = st.columns(len(all_setups))
for idx, (tf_label, s) in enumerate(all_setups.items()):
    with tf_cols[idx]:
        ls = s["long_score"]; ss = s["short_score"]
        if ls >= 10:   l_color = "#00ff88"; l_tag = "PERFECT LONG 🔥🔥🔥"
        elif ls >= 7:  l_color = "#00cc66"; l_tag = "STRONG LONG 🔥🔥"
        elif ls >= 5:  l_color = "#88ff88"; l_tag = "MODERATE 🔥"
        else:          l_color = "#444";    l_tag = "WEAK ⚪"
        if ss >= 10:   s_color = "#ff4444"; s_tag = "PERFECT SHORT 🔥🔥🔥"
        elif ss >= 7:  s_color = "#cc3333"; s_tag = "STRONG SHORT 🔥🔥"
        elif ss >= 5:  s_color = "#ff8888"; s_tag = "MODERATE 🔥"
        else:          s_color = "#444";    s_tag = "WEAK ⚪"
        st.markdown(f"""
        <div style="background:#0d0d1a;border:1px solid #1e1e3a;border-radius:8px;padding:10px;text-align:center;margin:3px;">
        <b style="color:#aaa;font-size:13px;">{tf_label}</b><br>
        <span style="color:{l_color};font-size:12px;">Long: {ls}/16 — {l_tag}</span><br>
        <span style="color:{s_color};font-size:12px;">Short: {ss}/16 — {s_tag}</span>
        </div>
        """, unsafe_allow_html=True)

        # ── CONFLUENCE FILTER — only alert when signals agree
        if alerts_on and tg_token and tg_chat_id:
            # Get patterns for this TF
            try:
                tf_patterns = detect_patterns(df_tmp) if not df_tmp.empty else []
            except:
                tf_patterns = []
            bull_patterns = [p for p in tf_patterns if p["type"] == "bullish"]
            bear_patterns = [p for p in tf_patterns if p["type"] == "bearish"]
            has_bull_pattern = len(bull_patterns) > 0
            has_bear_pattern = len(bear_patterns) > 0

            # LONG alert — only if NO strong bearish patterns AND bias agrees
            long_confluence = (
                ls >= 7 and
                not (has_bear_pattern and len(bear_patterns) >= 2) and
                s["bias"] in ["BULLISH", "RANGING"]
            )
            # SHORT alert — only if NO strong bullish patterns AND bias agrees
            short_confluence = (
                ss >= 7 and
                not (has_bull_pattern and len(bull_patterns) >= 2) and
                s["bias"] in ["BEARISH", "RANGING"]
            )
            # Conflicting — send caution instead
            if ls >= 7 and ss >= 7:
                send_tg(tg_token, tg_chat_id,
                    f"⚠️ <b>CONFLICTING SIGNALS — {coin} {tf_label}</b>\n"
                    f"Long Score: {ls}/16 | Short Score: {ss}/16\n"
                    f"Price: ${s['lat']['close']:,.2f}\n"
                    f"⏳ WAIT — signals not aligned. Do NOT trade!")
            elif long_confluence:
                emoji = "🟢🟢🟢" if ls >= 10 else "🟢🟢"
                quality = "PERFECT" if ls >= 10 else "STRONG"
                pattern_txt = f"\nPattern: {bull_patterns[0]['name']}" if has_bull_pattern else ""
                send_tg(tg_token, tg_chat_id,
                    f"{emoji} <b>{quality} LONG — {coin} {tf_label}</b>\n"
                    f"Score: {ls}/16 | Bias: {s['bias']}{pattern_txt}\n"
                    f"Price: ${s['lat']['close']:,.2f}\n"
                    f"Time: {datetime.now().strftime('%H:%M')}\n"
                    f"✅ CONFLUENCE CONFIRMED — signals agree!\n\n"
                    + "\n".join([f"✅ {r}" for r in s['long_reasons'][:8]])
                )
            elif short_confluence:
                emoji = "🔴🔴🔴" if ss >= 10 else "🔴🔴"
                quality = "PERFECT" if ss >= 10 else "STRONG"
                pattern_txt = f"\nPattern: {bear_patterns[0]['name']}" if has_bear_pattern else ""
                send_tg(tg_token, tg_chat_id,
                    f"{emoji} <b>{quality} SHORT — {coin} {tf_label}</b>\n"
                    f"Score: {ss}/16 | Bias: {s['bias']}{pattern_txt}\n"
                    f"Price: ${s['lat']['close']:,.2f}\n"
                    f"Time: {datetime.now().strftime('%H:%M')}\n"
                    f"✅ CONFLUENCE CONFIRMED — signals agree!\n\n"
                    + "\n".join([f"✅ {r}" for r in s['short_reasons'][:8]])
                )

st.markdown("---")

hc1, hc2 = st.columns(2)

with hc1:
    long_pct = int(long_score / max_score * 100)
    if long_score >= 10:   lq_color, lq_emoji = "#00ff88", "🔥🔥🔥 PERFECT LONG!"
    elif long_score >= 7:  lq_color, lq_emoji = "#00cc66", "🔥🔥 STRONG LONG"
    elif long_score >= 5:  lq_color, lq_emoji = "#88ff88", "🔥 MODERATE LONG"
    else:                   lq_color, lq_emoji = "#444",    "⚪ WEAK — WAIT"

    st.markdown(f"""
    <div style="background:#0d0d1a;border:2px solid {lq_color};border-radius:12px;padding:16px;text-align:center;">
    <b style="color:{lq_color};font-size:22px;">LONG SETUP</b><br>
    <b style="color:{lq_color};font-size:36px;">{long_score}/{max_score}</b><br>
    <b style="color:{lq_color};font-size:16px;">{lq_emoji}</b><br>
    <div style="background:#111;border-radius:4px;height:8px;margin:8px 0;">
    <div style="background:{lq_color};width:{long_pct}%;height:100%;border-radius:4px;"></div>
    </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("**Long Checklist:**")
    long_checks = [
        ("RSI below 40", lat["rsi"] < 40),
        ("MACD bullish cross", lat["macd"] > lat["macd_signal"]),
        ("ADX above 25", lat["adx"] > 25),
        ("Price at BB lower", lat["bb_pct"] < 0.2),
        ("Stoch oversold + up", lat["stoch_k"] < 0.2),
        ("BMA bullish", lat["bma_momentum"] in ["strong_bull","weak_bull"]),
        ("BMA bull cross", lat["bma_bull_cross"]),
        ("BOS bullish", lat["bos_bull"]),
        ("Buy liq sweep", lat["buy_liq"]),
        ("Discount zone", lat["discount_zone"]),
        ("CHoCH bullish", lat["choch_bull"]),
        ("Above VWAP", lat["close"] > lat["vwap"]),
        ("Trend bullish", bias == "BULLISH"),
        ("Bullish FVG", lat["fvg_bull"]),
        ("Bull stop hunt", lat["stop_hunt_bull"]),
        ("Bull OB present", lat["bull_ob"]),
    ]
    for check_name, check_val in long_checks:
        icon = "✅" if check_val else "❌"
        color = "#00ff88" if check_val else "#333"
        st.markdown(f'<span style="color:{color};font-size:13px;">{icon} {check_name}</span>', unsafe_allow_html=True)

with hc2:
    short_pct = int(short_score / max_score * 100)
    if short_score >= 10:   sq_color, sq_emoji = "#ff4444", "🔥🔥🔥 PERFECT SHORT!"
    elif short_score >= 7:  sq_color, sq_emoji = "#cc3333", "🔥🔥 STRONG SHORT"
    elif short_score >= 5:  sq_color, sq_emoji = "#ff8888", "🔥 MODERATE SHORT"
    else:                    sq_color, sq_emoji = "#444",    "⚪ WEAK — WAIT"

    st.markdown(f"""
    <div style="background:#0d0d1a;border:2px solid {sq_color};border-radius:12px;padding:16px;text-align:center;">
    <b style="color:{sq_color};font-size:22px;">SHORT SETUP</b><br>
    <b style="color:{sq_color};font-size:36px;">{short_score}/{max_score}</b><br>
    <b style="color:{sq_color};font-size:16px;">{sq_emoji}</b><br>
    <div style="background:#111;border-radius:4px;height:8px;margin:8px 0;">
    <div style="background:{sq_color};width:{short_pct}%;height:100%;border-radius:4px;"></div>
    </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("**Short Checklist:**")
    short_checks = [
        ("RSI above 60", lat["rsi"] > 60),
        ("MACD bearish cross", lat["macd"] < lat["macd_signal"]),
        ("ADX above 25", lat["adx"] > 25),
        ("Price at BB upper", lat["bb_pct"] > 0.8),
        ("Stoch overbought + down", lat["stoch_k"] > 0.8),
        ("BMA bearish", lat["bma_momentum"] in ["strong_bear","weak_bear"]),
        ("BMA bear cross", lat["bma_bear_cross"]),
        ("BOS bearish", lat["bos_bear"]),
        ("Sell liq sweep", lat["sell_liq"]),
        ("Premium zone", lat["premium_zone"]),
        ("CHoCH bearish", lat["choch_bear"]),
        ("Below VWAP", lat["close"] < lat["vwap"]),
        ("Trend bearish", bias == "BEARISH"),
        ("Bearish FVG", lat["fvg_bear"]),
        ("Bear stop hunt", lat["stop_hunt_bear"]),
        ("Bear OB present", lat["bear_ob"]),
    ]
    for check_name, check_val in short_checks:
        icon = "✅" if check_val else "❌"
        color = "#ff4444" if check_val else "#333"
        st.markdown(f'<span style="color:{color};font-size:13px;">{icon} {check_name}</span>', unsafe_allow_html=True)

# Risk levels
st.markdown(" ")
rc1, rc2, rc3 = st.columns(3)
with rc1:
    st.markdown("""
    <div style="background:#0d1f0d;border:1px solid #00ff8844;border-radius:8px;padding:10px;text-align:center;">
    <b style="color:#00ff88;">10+/16 = PERFECT</b><br>
    <span style="color:#aaa;font-size:12px;">All conditions aligned<br>Highest probability</span>
    </div>
    """, unsafe_allow_html=True)
with rc2:
    st.markdown("""
    <div style="background:#1a1a0d;border:1px solid #FFD70044;border-radius:8px;padding:10px;text-align:center;">
    <b style="color:#FFD700;">7-9/16 = STRONG</b><br>
    <span style="color:#aaa;font-size:12px;">Good setup<br>Trade with confidence</span>
    </div>
    """, unsafe_allow_html=True)
with rc3:
    st.markdown("""
    <div style="background:#1a0d0d;border:1px solid #ff444444;border-radius:8px;padding:10px;text-align:center;">
    <b style="color:#ff8888;">Below 5 = WAIT</b><br>
    <span style="color:#aaa;font-size:12px;">Not enough confluence<br>Be patient</span>
    </div>
    """, unsafe_allow_html=True)

# ── TELEGRAM ALERTS FOR HIGH PROB SETUPS
if alerts_on and tg_token and tg_chat_id:
    # Perfect Long Alert
    if long_score >= 10:
        long_msg = f"""🟢🟢🟢 <b>PERFECT LONG SETUP!</b>

Coin: {coin} | TF: {timeframe}
Score: {long_score}/{max_score} conditions met
Price: ${lat['close']:,.2f}
Time: {datetime.now().strftime('%H:%M')}

✅ Conditions Met:
"""
        long_reasons_str = "\n".join([f"✅ {c_name}" for c_name, c_val in long_checks if c_val])
        long_msg += long_reasons_str
        send_tg(tg_token, tg_chat_id, long_msg)
        st.sidebar.success("🟢 Perfect Long Alert Sent! 📱")

    elif long_score >= 7:
        long_msg = f"""🟢🟢 <b>STRONG LONG SETUP</b>

Coin: {coin} | TF: {timeframe}
Score: {long_score}/{max_score} conditions met
Price: ${lat['close']:,.2f}
Time: {datetime.now().strftime('%H:%M')}

Top conditions:
"""
        long_msg += "\n".join([f"✅ {c_name}" for c_name, c_val in long_checks[:8] if c_val])
        send_tg(tg_token, tg_chat_id, long_msg)
        st.sidebar.success("🟢 Strong Long Alert Sent! 📱")

    # Perfect Short Alert
    if short_score >= 10:
        short_msg = f"""🔴🔴🔴 <b>PERFECT SHORT SETUP!</b>

Coin: {coin} | TF: {timeframe}
Score: {short_score}/{max_score} conditions met
Price: ${lat['close']:,.2f}
Time: {datetime.now().strftime('%H:%M')}

✅ Conditions Met:
"""
        short_msg += "\n".join([f"✅ {c_name}" for c_name, c_val in short_checks if c_val])
        send_tg(tg_token, tg_chat_id, short_msg)
        st.sidebar.error("🔴 Perfect Short Alert Sent! 📱")

    elif short_score >= 7:
        short_msg = f"""🔴🔴 <b>STRONG SHORT SETUP</b>

Coin: {coin} | TF: {timeframe}
Score: {short_score}/{max_score} conditions met
Price: ${lat['close']:,.2f}
Time: {datetime.now().strftime('%H:%M')}

Top conditions:
"""
        short_msg += "\n".join([f"✅ {c_name}" for c_name, c_val in short_checks[:8] if c_val])
        send_tg(tg_token, tg_chat_id, short_msg)
        st.sidebar.error("🔴 Strong Short Alert Sent! 📱")

# ── ZONES
st.subheader("🧱 SMC + Liquidity + S/R Zones")
tab_zones1, tab_zones2, tab_zones3 = st.tabs(["📦 Order Blocks + FVG", "💧 Liquidity", "📏 Support & Resistance"])

with tab_zones1:
    zc1,zc2,zc3,zc4 = st.columns(4)
    with zc1:
        st.markdown("**Bullish OBs**")
        for _,row in df[df["bull_ob"]].tail(4).iterrows():
            if not pd.isna(row["bull_ob_low"]):
                st.markdown(f'<span class="zone-tag ob-bull">OB ${row["bull_ob_low"]:,.0f}–${row["bull_ob_high"]:,.0f}</span>', unsafe_allow_html=True)
    with zc2:
        st.markdown("**Bearish OBs**")
        for _,row in df[df["bear_ob"]].tail(4).iterrows():
            if not pd.isna(row["bear_ob_low"]):
                st.markdown(f'<span class="zone-tag ob-bear">OB ${row["bear_ob_low"]:,.0f}–${row["bear_ob_high"]:,.0f}</span>', unsafe_allow_html=True)
    with zc3:
        st.markdown("**Bull FVGs**")
        for _,row in df[df["fvg_bull"]].tail(4).iterrows():
            if not pd.isna(row["fvg_bull_bottom"]):
                st.markdown(f'<span class="zone-tag fvg-bull">FVG ${row["fvg_bull_bottom"]:,.0f}–${row["fvg_bull_top"]:,.0f}</span>', unsafe_allow_html=True)
    with zc4:
        st.markdown("**Bear FVGs**")
        for _,row in df[df["fvg_bear"]].tail(4).iterrows():
            if not pd.isna(row["fvg_bear_bottom"]):
                st.markdown(f'<span class="zone-tag fvg-bear">FVG ${row["fvg_bear_bottom"]:,.0f}–${row["fvg_bear_top"]:,.0f}</span>', unsafe_allow_html=True)

with tab_zones2:
    lc1,lc2,lc3,lc4,lc5 = st.columns(5)
    with lc1:
        st.markdown("**Buyside Liq**")
        st.caption("Stops resting above")
        for _,row in df[df["buyside_liq"]].tail(4).iterrows():
            st.markdown(f'<span class="zone-tag liq-tag">BSL ${row["high"]:,.0f}</span>', unsafe_allow_html=True)
    with lc2:
        st.markdown("**Sellside Liq**")
        st.caption("Stops resting below")
        for _,row in df[df["sellside_liq"]].tail(4).iterrows():
            st.markdown(f'<span class="zone-tag ob-bull">SSL ${row["low"]:,.0f}</span>', unsafe_allow_html=True)
    with lc3:
        st.markdown("**Equal Highs**")
        st.caption("Double top = liq above")
        for _,row in df[df["equal_highs"]].tail(4).iterrows():
            st.markdown(f'<span class="zone-tag ob-bear">EQH ${row["high"]:,.0f}</span>', unsafe_allow_html=True)
    with lc4:
        st.markdown("**Equal Lows**")
        st.caption("Double bottom = liq below")
        for _,row in df[df["equal_lows"]].tail(4).iterrows():
            st.markdown(f'<span class="zone-tag ob-bull">EQL ${row["low"]:,.0f}</span>', unsafe_allow_html=True)
    with lc5:
        st.markdown("**Stop Hunts**")
        st.caption("Big wick = stops grabbed")
        for _,row in df[df["stop_hunt_bull"]].tail(3).iterrows():
            st.markdown(f'<span class="zone-tag ob-bull">Bull ${row["low"]:,.0f}</span>', unsafe_allow_html=True)
        for _,row in df[df["stop_hunt_bear"]].tail(3).iterrows():
            st.markdown(f'<span class="zone-tag ob-bear">Bear ${row["high"]:,.0f}</span>', unsafe_allow_html=True)

with tab_zones3:
    sc1, sc2 = st.columns(2)
    with sc1:
        st.markdown("**Support Zones**")
        for zone in support_zones:
            strength = "🔥🔥🔥" if zone["touches"] >= 3 else "🔥🔥" if zone["touches"] == 2 else "🔥"
            dist = abs(lat["close"] - zone["price"]) / lat["close"] * 100
            near = " ← NEAR!" if dist < 1.0 else ""
            st.markdown(f'<span class="zone-tag sr-sup">S ${zone["price"]:,.0f} | {zone["touches"]}x {strength}{near}</span>', unsafe_allow_html=True)
    with sc2:
        st.markdown("**Resistance Zones**")
        for zone in resistance_zones:
            strength = "🔥🔥🔥" if zone["touches"] >= 3 else "🔥🔥" if zone["touches"] == 2 else "🔥"
            dist = abs(lat["close"] - zone["price"]) / lat["close"] * 100
            near = " ← NEAR!" if dist < 1.0 else ""
            st.markdown(f'<span class="zone-tag sr-res">R ${zone["price"]:,.0f} | {zone["touches"]}x {strength}{near}</span>', unsafe_allow_html=True)
    st.info("💡 More touches = stronger zone. Price near a zone = potential trade setup.")

st.markdown("---")

# ── CHARTS
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📅 Daily Direction", "📊 4H Direction", "💧 1H Liquidity", f"⚡ {tf_entry} Entry", "📈 Indicators"])

with tab1:
    # Chart layer toggles
    st.markdown("**Chart Layers — tick to show/hide:**")
    tg1,tg2,tg3,tg4,tg5,tg6,tg7,tg8 = st.columns(8)
    show_ema  = tg1.checkbox("EMAs",      value=True,  key="t1")
    show_vwap = tg2.checkbox("VWAP",      value=True,  key="t2")
    show_bb   = tg3.checkbox("Bollinger", value=False, key="t3")
    show_sr   = tg4.checkbox("S/R Zones", value=True,  key="t4")
    show_ob   = tg5.checkbox("Order Blk", value=True,  key="t5")
    show_fvg  = tg6.checkbox("FVG",       value=False, key="t6")
    show_liq  = tg7.checkbox("Liquidity", value=True,  key="t7")
    show_eqhl = tg8.checkbox("EQH/EQL",   value=False, key="t8")

    fig = make_subplots(rows=4, cols=1, shared_xaxes=True,
        row_heights=[0.55,0.15,0.15,0.15], vertical_spacing=0.02)

    # Candles always shown
    fig.add_trace(go.Candlestick(
        x=df["time"], open=df["open"], high=df["high"],
        low=df["low"], close=df["close"], name="Price",
        increasing_line_color="#00ff88", decreasing_line_color="#ff4444"
    ), row=1, col=1)

    # EMAs
    if show_ema:
        fig.add_trace(go.Scatter(x=df["time"],y=df["ema20"], name="EMA20", line=dict(color="#FFD700",width=1.2)), row=1,col=1)
        fig.add_trace(go.Scatter(x=df["time"],y=df["ema50"], name="EMA50", line=dict(color="#FF8C00",width=1.2)), row=1,col=1)
        fig.add_trace(go.Scatter(x=df["time"],y=df["ema200"],name="EMA200",line=dict(color="#FF4500",width=1.5,dash="dash")), row=1,col=1)

    # BMA lines — always shown, key indicator
    bma_colors = {
        "strong_bull": "#00ff00",
        "weak_bull":   "#88ff88",
        "neutral":     "#888888",
        "weak_bear":   "#ff8888",
        "strong_bear": "#ff0000"
    }
    # BMA20 line with momentum coloring
    fig.add_trace(go.Scatter(
        x=df["time"], y=df["bma20"],
        name="BMA20",
        line=dict(color="#ff00ff", width=2),
        mode="lines"
    ), row=1, col=1)
    # BMA50 line
    fig.add_trace(go.Scatter(
        x=df["time"], y=df["bma50"],
        name="BMA50",
        line=dict(color="#ff88ff", width=1.5, dash="dash"),
        mode="lines"
    ), row=1, col=1)
    # BMA Bull Cross markers
    bma_bc = df[df["bma_bull_cross"]]
    if not bma_bc.empty:
        fig.add_trace(go.Scatter(
            x=bma_bc["time"], y=bma_bc["bma20"]*0.998,
            mode="markers+text",
            marker=dict(symbol="circle",color="#ff00ff",size=12,
                line=dict(color="white",width=2)),
            text=["BMA✅"]*len(bma_bc),
            textposition="bottom center",
            textfont=dict(color="#ff00ff",size=9),
            name="BMA Bull Cross"
        ), row=1, col=1)
    # BMA Bear Cross markers
    bma_brc = df[df["bma_bear_cross"]]
    if not bma_brc.empty:
        fig.add_trace(go.Scatter(
            x=bma_brc["time"], y=bma_brc["bma20"]*1.002,
            mode="markers+text",
            marker=dict(symbol="circle",color="#ff44ff",size=12,
                line=dict(color="white",width=2)),
            text=["BMA⚠️"]*len(bma_brc),
            textposition="top center",
            textfont=dict(color="#ff44ff",size=9),
            name="BMA Bear Cross"
        ), row=1, col=1)

    # VWAP
    if show_vwap:
        fig.add_trace(go.Scatter(x=df["time"],y=df["vwap"],name="VWAP",line=dict(color="#00bfff",width=1.5,dash="dot")), row=1,col=1)

    # Bollinger Bands
    if show_bb:
        fig.add_trace(go.Scatter(x=df["time"],y=df["bb_upper"],name="BB+",line=dict(color="#555",width=1,dash="dash"),showlegend=False), row=1,col=1)
        fig.add_trace(go.Scatter(x=df["time"],y=df["bb_lower"],name="BB-",line=dict(color="#555",width=1,dash="dash"),fill="tonexty",fillcolor="rgba(100,100,100,0.04)",showlegend=False), row=1,col=1)

    # Support and Resistance
    if show_sr:
        for zone in support_zones[:4]:
            fig.add_hrect(y0=zone["price"]*0.998,y1=zone["price"]*1.002,
                fillcolor="rgba(0,255,136,0.10)",line_width=1,line_color="rgba(0,255,136,0.6)",
                row=1,col=1,annotation_text=f"S {zone['touches']}x",
                annotation_font_color="#00ff88",annotation_position="right")
        for zone in resistance_zones[:4]:
            fig.add_hrect(y0=zone["price"]*0.998,y1=zone["price"]*1.002,
                fillcolor="rgba(255,68,68,0.10)",line_width=1,line_color="rgba(255,68,68,0.6)",
                row=1,col=1,annotation_text=f"R {zone['touches']}x",
                annotation_font_color="#ff4444",annotation_position="right")

    # ── Volume Profile lines on main chart
    try:
        vp_main = calculate_volume_profile(df, bins=30)
        if not vp_main.empty:
            poc_p = vp_main[vp_main["is_poc"]]["price"].values[0]
            vah_p = vp_main["vah"].iloc[0]
            val_p = vp_main["val"].iloc[0]
            fig.add_hline(y=poc_p, line_dash="dot", line_color="#FFD700", line_width=1.5,
                annotation_text="POC", annotation_font_color="#FFD700",
                annotation_position="right", row=1, col=1)
            fig.add_hline(y=vah_p, line_dash="dot", line_color="#00bfff", line_width=1,
                annotation_text="VAH", annotation_font_color="#00bfff",
                annotation_position="right", row=1, col=1)
            fig.add_hline(y=val_p, line_dash="dot", line_color="#00bfff", line_width=1,
                annotation_text="VAL", annotation_font_color="#00bfff",
                annotation_position="right", row=1, col=1)
    except: pass

    # BOS markers always shown
    bos_b = df[df["bos_bull"]].tail(6)
    if not bos_b.empty:
        fig.add_trace(go.Scatter(x=bos_b["time"],y=bos_b["high"]*1.002,mode="markers+text",
            marker=dict(symbol="triangle-up",color="#00ff88",size=14),
            text=["BOS"]*len(bos_b),textposition="top center",
            textfont=dict(color="#00ff88",size=10),name="BOS Bull"), row=1,col=1)
    bos_br = df[df["bos_bear"]].tail(6)
    if not bos_br.empty:
        fig.add_trace(go.Scatter(x=bos_br["time"],y=bos_br["low"]*0.998,mode="markers+text",
            marker=dict(symbol="triangle-down",color="#ff4444",size=14),
            text=["BOS"]*len(bos_br),textposition="bottom center",
            textfont=dict(color="#ff4444",size=10),name="BOS Bear"), row=1,col=1)

    # CHoCH always shown
    chb = df[df["choch_bull"]].tail(4)
    if not chb.empty:
        fig.add_trace(go.Scatter(x=chb["time"],y=chb["high"]*1.003,mode="markers+text",
            marker=dict(symbol="diamond",color="#00ffff",size=12),
            text=["CHoCH"]*len(chb),textposition="top center",
            textfont=dict(color="#00ffff",size=10),name="CHoCH Bull"), row=1,col=1)
    chbr = df[df["choch_bear"]].tail(4)
    if not chbr.empty:
        fig.add_trace(go.Scatter(x=chbr["time"],y=chbr["low"]*0.997,mode="markers+text",
            marker=dict(symbol="diamond",color="#ff8800",size=12),
            text=["CHoCH"]*len(chbr),textposition="bottom center",
            textfont=dict(color="#ff8800",size=10),name="CHoCH Bear"), row=1,col=1)

    # Liquidity
    if show_liq:
        bl = df[df["buy_liq"]].tail(8)
        if not bl.empty:
            fig.add_trace(go.Scatter(x=bl["time"],y=bl["low"]*0.999,mode="markers",
                marker=dict(symbol="star",color="#00ffff",size=14),name="Buy Liq"), row=1,col=1)
        sl2 = df[df["sell_liq"]].tail(8)
        if not sl2.empty:
            fig.add_trace(go.Scatter(x=sl2["time"],y=sl2["high"]*1.001,mode="markers",
                marker=dict(symbol="star",color="#ff8800",size=14),name="Sell Liq"), row=1,col=1)
        sth_b = df[df["stop_hunt_bull"]].tail(5)
        if not sth_b.empty:
            fig.add_trace(go.Scatter(x=sth_b["time"],y=sth_b["low"]*0.998,mode="markers",
                marker=dict(symbol="arrow-up",color="#00ff88",size=16),name="Stop Hunt Bull"), row=1,col=1)
        sth_br = df[df["stop_hunt_bear"]].tail(5)
        if not sth_br.empty:
            fig.add_trace(go.Scatter(x=sth_br["time"],y=sth_br["high"]*1.002,mode="markers",
                marker=dict(symbol="arrow-down",color="#ff4444",size=16),name="Stop Hunt Bear"), row=1,col=1)

    # Order Blocks last 3 only
    if show_ob:
        for _,row in df[df["bull_ob"]].tail(3).iterrows():
            if not pd.isna(row["bull_ob_low"]):
                fig.add_hrect(y0=row["bull_ob_low"],y1=row["bull_ob_high"],
                    fillcolor="rgba(0,255,136,0.10)",line_width=1.5,
                    line_color="rgba(0,255,136,0.5)",row=1,col=1,
                    annotation_text="Bull OB",annotation_font_color="#00ff88",annotation_position="left")
        for _,row in df[df["bear_ob"]].tail(3).iterrows():
            if not pd.isna(row["bear_ob_low"]):
                fig.add_hrect(y0=row["bear_ob_low"],y1=row["bear_ob_high"],
                    fillcolor="rgba(255,68,68,0.10)",line_width=1.5,
                    line_color="rgba(255,68,68,0.5)",row=1,col=1,
                    annotation_text="Bear OB",annotation_font_color="#ff4444",annotation_position="left")

    # FVG last 2 only
    if show_fvg:
        for _,row in df[df["fvg_bull"]].tail(2).iterrows():
            if not pd.isna(row["fvg_bull_bottom"]):
                fig.add_hrect(y0=row["fvg_bull_bottom"],y1=row["fvg_bull_top"],
                    fillcolor="rgba(0,191,255,0.10)",line_width=1,
                    line_color="rgba(0,191,255,0.5)",row=1,col=1,
                    annotation_text="FVG",annotation_font_color="#00bfff",annotation_position="left")
        for _,row in df[df["fvg_bear"]].tail(2).iterrows():
            if not pd.isna(row["fvg_bear_bottom"]):
                fig.add_hrect(y0=row["fvg_bear_bottom"],y1=row["fvg_bear_top"],
                    fillcolor="rgba(255,136,0,0.10)",line_width=1,
                    line_color="rgba(255,136,0,0.5)",row=1,col=1,
                    annotation_text="FVG",annotation_font_color="#ff8800",annotation_position="left")

    # Equal Highs Lows
    if show_eqhl:
        for _,row in df[df["equal_highs"]].tail(2).iterrows():
            fig.add_hline(y=row["high"],line_dash="dot",line_color="rgba(255,68,68,0.6)",
                annotation_text="EQH",annotation_font_color="#ff4444",row=1,col=1)
        for _,row in df[df["equal_lows"]].tail(2).iterrows():
            fig.add_hline(y=row["low"],line_dash="dot",line_color="rgba(0,255,136,0.6)",
                annotation_text="EQL",annotation_font_color="#00ff88",row=1,col=1)

    # Volume
    vclrs = ["#00ff88" if c>=o else "#ff4444" for c,o in zip(df["close"],df["open"])]
    fig.add_trace(go.Bar(x=df["time"],y=df["volume"],name="Vol",marker_color=vclrs,opacity=0.7), row=2,col=1)
    fig.add_trace(go.Scatter(x=df["time"],y=df["vol_ma"],name="VolMA",line=dict(color="white",width=1)), row=2,col=1)

    # RSI
    fig.add_trace(go.Scatter(x=df["time"],y=df["rsi"],name="RSI",line=dict(color="#bf00ff",width=1.5)), row=3,col=1)
    fig.add_hrect(y0=70,y1=100,fillcolor="rgba(255,68,68,0.05)",line_width=0,row=3,col=1)
    fig.add_hrect(y0=0,y1=30,fillcolor="rgba(0,255,136,0.05)",line_width=0,row=3,col=1)
    fig.add_hline(y=70,line_dash="dash",line_color="rgba(255,68,68,0.5)",row=3,col=1)
    fig.add_hline(y=50,line_dash="dot",line_color="rgba(255,255,255,0.2)",row=3,col=1)
    fig.add_hline(y=30,line_dash="dash",line_color="rgba(0,255,136,0.5)",row=3,col=1)

    # MACD
    mclrs = ["#00ff88" if v>=0 else "#ff4444" for v in df["macd_hist"]]
    fig.add_trace(go.Bar(x=df["time"],y=df["macd_hist"],name="Hist",marker_color=mclrs,opacity=0.6), row=4,col=1)
    fig.add_trace(go.Scatter(x=df["time"],y=df["macd"],name="MACD",line=dict(color="#00bfff",width=1.2)), row=4,col=1)
    fig.add_trace(go.Scatter(x=df["time"],y=df["macd_signal"],name="Sig",line=dict(color="#FFD700",width=1.2)), row=4,col=1)

    fig.update_layout(height=900,template="plotly_dark",xaxis_rangeslider_visible=False,
        paper_bgcolor="#050508",plot_bgcolor="#050508",
        legend=dict(orientation="h",y=1.02,font=dict(size=11),
            bgcolor="rgba(5,5,8,0.8)",bordercolor="#222",borderwidth=1),
        margin=dict(t=40,b=20,l=10,r=80))
    for r in [1,2,3,4]:
        fig.update_xaxes(gridcolor="#0d0d18",showgrid=True,row=r,col=1)
        fig.update_yaxes(gridcolor="#0d0d18",showgrid=True,row=r,col=1)
    fig.update_yaxes(title_text="Price",  row=1,col=1)
    fig.update_yaxes(title_text="Volume", row=2,col=1)
    fig.update_yaxes(title_text="RSI",    row=3,col=1)
    fig.update_yaxes(title_text="MACD",   row=4,col=1)
    st.plotly_chart(fig,use_container_width=True, key="pc_1")


# ─── helper to build a direction chart (Daily / 4H)
def build_direction_chart(df_d, label, emas, show_200=True):
    """Daily/4H chart — EMA 50+200, VWAP, BOS, CHoCH, OB, S/R"""
    fig_d = make_subplots(rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.6,0.2,0.2], vertical_spacing=0.02)
    fig_d.add_trace(go.Candlestick(x=df_d["time"],open=df_d["open"],
        high=df_d["high"],low=df_d["low"],close=df_d["close"],name="Price",
        increasing_line_color="#00ff88",decreasing_line_color="#ff4444"), row=1,col=1)
    for ema_name, ema_col, ema_color in emas:
        fig_d.add_trace(go.Scatter(x=df_d["time"],y=df_d[ema_col],
            name=ema_name,line=dict(color=ema_color,width=1.5)), row=1,col=1)
    fig_d.add_trace(go.Scatter(x=df_d["time"],y=df_d["vwap"],
        name="VWAP",line=dict(color="#00bfff",width=1.5,dash="dot")), row=1,col=1)
    for zone in support_zones[:3]:
        fig_d.add_hrect(y0=zone["price"]*0.998,y1=zone["price"]*1.002,
            fillcolor="rgba(0,255,136,0.10)",line_width=1,
            line_color="rgba(0,255,136,0.6)",row=1,col=1,
            annotation_text=f"S{zone['touches']}x",annotation_font_color="#00ff88",annotation_position="right")
    for zone in resistance_zones[:3]:
        fig_d.add_hrect(y0=zone["price"]*0.998,y1=zone["price"]*1.002,
            fillcolor="rgba(255,68,68,0.10)",line_width=1,
            line_color="rgba(255,68,68,0.6)",row=1,col=1,
            annotation_text=f"R{zone['touches']}x",annotation_font_color="#ff4444",annotation_position="right")
    bos_b = df_d[df_d["bos_bull"]].tail(4)
    if not bos_b.empty:
        fig_d.add_trace(go.Scatter(x=bos_b["time"],y=bos_b["high"]*1.002,mode="markers+text",
            marker=dict(symbol="triangle-up",color="#00ff88",size=14),
            text=["BOS"]*len(bos_b),textposition="top center",
            textfont=dict(color="#00ff88",size=10),name="BOS Bull"), row=1,col=1)
    bos_br = df_d[df_d["bos_bear"]].tail(4)
    if not bos_br.empty:
        fig_d.add_trace(go.Scatter(x=bos_br["time"],y=bos_br["low"]*0.998,mode="markers+text",
            marker=dict(symbol="triangle-down",color="#ff4444",size=14),
            text=["BOS"]*len(bos_br),textposition="bottom center",
            textfont=dict(color="#ff4444",size=10),name="BOS Bear"), row=1,col=1)
    chb = df_d[df_d["choch_bull"]].tail(3)
    if not chb.empty:
        fig_d.add_trace(go.Scatter(x=chb["time"],y=chb["high"]*1.003,mode="markers+text",
            marker=dict(symbol="diamond",color="#00ffff",size=12),
            text=["CHoCH"]*len(chb),textposition="top center",
            textfont=dict(color="#00ffff",size=10),name="CHoCH Bull"), row=1,col=1)
    chbr = df_d[df_d["choch_bear"]].tail(3)
    if not chbr.empty:
        fig_d.add_trace(go.Scatter(x=chbr["time"],y=chbr["low"]*0.997,mode="markers+text",
            marker=dict(symbol="diamond",color="#ff8800",size=12),
            text=["CHoCH"]*len(chbr),textposition="bottom center",
            textfont=dict(color="#ff8800",size=10),name="CHoCH Bear"), row=1,col=1)
    for _,row in df_d[df_d["bull_ob"]].tail(3).iterrows():
        if not pd.isna(row["bull_ob_low"]):
            fig_d.add_hrect(y0=row["bull_ob_low"],y1=row["bull_ob_high"],
                fillcolor="rgba(0,255,136,0.10)",line_width=1.5,
                line_color="rgba(0,255,136,0.5)",row=1,col=1,
                annotation_text="Bull OB",annotation_font_color="#00ff88",annotation_position="left")
    for _,row in df_d[df_d["bear_ob"]].tail(3).iterrows():
        if not pd.isna(row["bear_ob_low"]):
            fig_d.add_hrect(y0=row["bear_ob_low"],y1=row["bear_ob_high"],
                fillcolor="rgba(255,68,68,0.10)",line_width=1.5,
                line_color="rgba(255,68,68,0.5)",row=1,col=1,
                annotation_text="Bear OB",annotation_font_color="#ff4444",annotation_position="left")
    vclrs = ["#00ff88" if c>=o else "#ff4444" for c,o in zip(df_d["close"],df_d["open"])]
    fig_d.add_trace(go.Bar(x=df_d["time"],y=df_d["volume"],name="Vol",marker_color=vclrs,opacity=0.7), row=2,col=1)
    fig_d.add_trace(go.Scatter(x=df_d["time"],y=df_d["vol_ma"],name="VolMA",line=dict(color="white",width=1)), row=2,col=1)
    fig_d.add_trace(go.Scatter(x=df_d["time"],y=df_d["adx"],name="ADX",line=dict(color="#FFD700",width=1.5)), row=3,col=1)
    fig_d.add_trace(go.Scatter(x=df_d["time"],y=df_d["adx_pos"],name="+DI",line=dict(color="#00ff88",width=1)), row=3,col=1)
    fig_d.add_trace(go.Scatter(x=df_d["time"],y=df_d["adx_neg"],name="-DI",line=dict(color="#ff4444",width=1)), row=3,col=1)
    fig_d.add_hline(y=25,line_dash="dash",line_color="white",opacity=0.3,row=3,col=1)
    fig_d.update_layout(height=750,template="plotly_dark",xaxis_rangeslider_visible=False,
        paper_bgcolor="#050508",plot_bgcolor="#050508",
        legend=dict(orientation="h",y=1.02,font=dict(size=10)),
        title=dict(text=f"{label} — Trend Direction | EMAs: {', '.join([e[0] for e in emas])} + VWAP | Focus: BOS, CHoCH, OB",
            font=dict(color="#aaa",size=13)),
        margin=dict(t=60,b=20,l=10,r=80))
    for r in [1,2,3]:
        fig_d.update_xaxes(gridcolor="#0d0d18",row=r,col=1)
        fig_d.update_yaxes(gridcolor="#0d0d18",row=r,col=1)
    fig_d.update_yaxes(title_text="Price",row=1,col=1)
    fig_d.update_yaxes(title_text="Volume",row=2,col=1)
    fig_d.update_yaxes(title_text="ADX",row=3,col=1)
    return fig_d

def build_liquidity_chart(df_1h, label):
    """1H chart — EMA 20+50, VWAP, all liquidity, FVG, S/R levels"""
    fig_l = make_subplots(rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.6,0.2,0.2], vertical_spacing=0.02)
    fig_l.add_trace(go.Candlestick(x=df_1h["time"],open=df_1h["open"],
        high=df_1h["high"],low=df_1h["low"],close=df_1h["close"],name="Price",
        increasing_line_color="#00ff88",decreasing_line_color="#ff4444"), row=1,col=1)
    fig_l.add_trace(go.Scatter(x=df_1h["time"],y=df_1h["ema20"],name="EMA20",line=dict(color="#FFD700",width=1.2)), row=1,col=1)
    fig_l.add_trace(go.Scatter(x=df_1h["time"],y=df_1h["ema50"],name="EMA50",line=dict(color="#FF8C00",width=1.2)), row=1,col=1)
    fig_l.add_trace(go.Scatter(x=df_1h["time"],y=df_1h["vwap"],name="VWAP",line=dict(color="#00bfff",width=1.5,dash="dot")), row=1,col=1)
    # All liquidity levels
    for zone in support_zones[:5]:
        fig_l.add_hline(y=zone["price"],line_dash="dash",line_color="rgba(0,255,136,0.6)",
            annotation_text=f"S ${zone['price']:,.0f}",annotation_font_color="#00ff88",
            annotation_position="right",row=1,col=1)
    for zone in resistance_zones[:5]:
        fig_l.add_hline(y=zone["price"],line_dash="dash",line_color="rgba(255,68,68,0.6)",
            annotation_text=f"R ${zone['price']:,.0f}",annotation_font_color="#ff4444",
            annotation_position="right",row=1,col=1)
    # Buy/Sell Liquidity sweeps
    bl = df_1h[df_1h["buy_liq"]].tail(10)
    if not bl.empty:
        fig_l.add_trace(go.Scatter(x=bl["time"],y=bl["low"]*0.999,mode="markers",
            marker=dict(symbol="star",color="#00ffff",size=14),name="Buy Liq Sweep"), row=1,col=1)
    sl = df_1h[df_1h["sell_liq"]].tail(10)
    if not sl.empty:
        fig_l.add_trace(go.Scatter(x=sl["time"],y=sl["high"]*1.001,mode="markers",
            marker=dict(symbol="star",color="#ff8800",size=14),name="Sell Liq Sweep"), row=1,col=1)
    # Stop hunts
    sth_b = df_1h[df_1h["stop_hunt_bull"]].tail(5)
    if not sth_b.empty:
        fig_l.add_trace(go.Scatter(x=sth_b["time"],y=sth_b["low"]*0.998,mode="markers",
            marker=dict(symbol="arrow-up",color="#00ff88",size=16),name="Bull Stop Hunt"), row=1,col=1)
    sth_br = df_1h[df_1h["stop_hunt_bear"]].tail(5)
    if not sth_br.empty:
        fig_l.add_trace(go.Scatter(x=sth_br["time"],y=sth_br["high"]*1.002,mode="markers",
            marker=dict(symbol="arrow-down",color="#ff4444",size=16),name="Bear Stop Hunt"), row=1,col=1)
    # EQH EQL
    for _,row in df_1h[df_1h["equal_highs"]].tail(4).iterrows():
        fig_l.add_hline(y=row["high"],line_dash="dot",line_color="rgba(255,68,68,0.5)",
            annotation_text="EQH",annotation_font_color="#ff4444",row=1,col=1)
    for _,row in df_1h[df_1h["equal_lows"]].tail(4).iterrows():
        fig_l.add_hline(y=row["low"],line_dash="dot",line_color="rgba(0,255,136,0.5)",
            annotation_text="EQL",annotation_font_color="#00ff88",row=1,col=1)
    # FVG
    for _,row in df_1h[df_1h["fvg_bull"]].tail(3).iterrows():
        if not pd.isna(row["fvg_bull_bottom"]):
            fig_l.add_hrect(y0=row["fvg_bull_bottom"],y1=row["fvg_bull_top"],
                fillcolor="rgba(0,191,255,0.10)",line_width=1,line_color="rgba(0,191,255,0.5)",
                row=1,col=1,annotation_text="FVG",annotation_font_color="#00bfff",annotation_position="left")
    for _,row in df_1h[df_1h["fvg_bear"]].tail(3).iterrows():
        if not pd.isna(row["fvg_bear_bottom"]):
            fig_l.add_hrect(y0=row["fvg_bear_bottom"],y1=row["fvg_bear_top"],
                fillcolor="rgba(255,136,0,0.10)",line_width=1,line_color="rgba(255,136,0,0.5)",
                row=1,col=1,annotation_text="FVG",annotation_font_color="#ff8800",annotation_position="left")
    # Inducement markers
    ind_b = df_1h[df_1h["inducement_bull"]].tail(4)
    if not ind_b.empty:
        fig_l.add_trace(go.Scatter(x=ind_b["time"],y=ind_b["low"]*0.997,mode="markers+text",
            marker=dict(symbol="circle",color="#bf00ff",size=10),
            text=["IND"]*len(ind_b),textposition="bottom center",
            textfont=dict(color="#bf00ff",size=9),name="Inducement"), row=1,col=1)
    # RSI
    fig_l.add_trace(go.Scatter(x=df_1h["time"],y=df_1h["rsi"],name="RSI",line=dict(color="#bf00ff",width=1.5)), row=2,col=1)
    fig_l.add_hline(y=70,line_dash="dash",line_color="rgba(255,68,68,0.5)",row=2,col=1)
    fig_l.add_hline(y=50,line_dash="dot",line_color="rgba(255,255,255,0.2)",row=2,col=1)
    fig_l.add_hline(y=30,line_dash="dash",line_color="rgba(0,255,136,0.5)",row=2,col=1)
    # Volume
    vclrs = ["#00ff88" if c>=o else "#ff4444" for c,o in zip(df_1h["close"],df_1h["open"])]
    fig_l.add_trace(go.Bar(x=df_1h["time"],y=df_1h["volume"],name="Vol",marker_color=vclrs,opacity=0.7), row=3,col=1)
    fig_l.add_trace(go.Scatter(x=df_1h["time"],y=df_1h["vol_ma"],name="VolMA",line=dict(color="white",width=1)), row=3,col=1)
    fig_l.update_layout(height=750,template="plotly_dark",xaxis_rangeslider_visible=False,
        paper_bgcolor="#050508",plot_bgcolor="#050508",
        legend=dict(orientation="h",y=1.02,font=dict(size=10)),
        title=dict(text=f"{label} — Liquidity Check | EMA20+50 + VWAP | Focus: S/R, Sweeps, FVG, EQH/EQL",
            font=dict(color="#aaa",size=13)),
        margin=dict(t=60,b=20,l=10,r=100))
    for r in [1,2,3]:
        fig_l.update_xaxes(gridcolor="#0d0d18",row=r,col=1)
        fig_l.update_yaxes(gridcolor="#0d0d18",row=r,col=1)
    return fig_l

def build_entry_chart(df_en, label):
    """15m/5m chart — EMA 9+20, VWAP, BOS, CHoCH, OB, Liquidity, MACD"""
    fig_e = make_subplots(rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.6,0.2,0.2], vertical_spacing=0.02)
    fig_e.add_trace(go.Candlestick(x=df_en["time"],open=df_en["open"],
        high=df_en["high"],low=df_en["low"],close=df_en["close"],name="Price",
        increasing_line_color="#00ff88",decreasing_line_color="#ff4444"), row=1,col=1)
    fig_e.add_trace(go.Scatter(x=df_en["time"],y=df_en["ema9"], name="EMA9", line=dict(color="#ffffff",width=1.2)), row=1,col=1)
    fig_e.add_trace(go.Scatter(x=df_en["time"],y=df_en["ema20"],name="EMA20",line=dict(color="#FFD700",width=1.2)), row=1,col=1)
    fig_e.add_trace(go.Scatter(x=df_en["time"],y=df_en["vwap"],name="VWAP",line=dict(color="#00bfff",width=1.5,dash="dot")), row=1,col=1)
    for zone in support_zones[:3]:
        fig_e.add_hline(y=zone["price"],line_dash="dash",line_color="rgba(0,255,136,0.5)",
            annotation_text=f"S",annotation_font_color="#00ff88",annotation_position="right",row=1,col=1)
    for zone in resistance_zones[:3]:
        fig_e.add_hline(y=zone["price"],line_dash="dash",line_color="rgba(255,68,68,0.5)",
            annotation_text=f"R",annotation_font_color="#ff4444",annotation_position="right",row=1,col=1)
    bos_e = df_en[df_en["bos_bull"]].tail(5)
    if not bos_e.empty:
        fig_e.add_trace(go.Scatter(x=bos_e["time"],y=bos_e["high"]*1.001,mode="markers+text",
            marker=dict(symbol="triangle-up",color="#00ff88",size=12),
            text=["BOS"]*len(bos_e),textposition="top center",
            textfont=dict(color="#00ff88",size=10),name="BOS Bull"), row=1,col=1)
    bos_eb = df_en[df_en["bos_bear"]].tail(5)
    if not bos_eb.empty:
        fig_e.add_trace(go.Scatter(x=bos_eb["time"],y=bos_eb["low"]*0.999,mode="markers+text",
            marker=dict(symbol="triangle-down",color="#ff4444",size=12),
            text=["BOS"]*len(bos_eb),textposition="bottom center",
            textfont=dict(color="#ff4444",size=10),name="BOS Bear"), row=1,col=1)
    chb_e = df_en[df_en["choch_bull"]].tail(3)
    if not chb_e.empty:
        fig_e.add_trace(go.Scatter(x=chb_e["time"],y=chb_e["high"]*1.002,mode="markers+text",
            marker=dict(symbol="diamond",color="#00ffff",size=10),
            text=["CHoCH"]*len(chb_e),textposition="top center",
            textfont=dict(color="#00ffff",size=9),name="CHoCH"), row=1,col=1)
    bl_e = df_en[df_en["buy_liq"]].tail(8)
    if not bl_e.empty:
        fig_e.add_trace(go.Scatter(x=bl_e["time"],y=bl_e["low"]*0.999,mode="markers",
            marker=dict(symbol="star",color="#00ffff",size=12),name="Buy Liq"), row=1,col=1)
    sl_e = df_en[df_en["sell_liq"]].tail(8)
    if not sl_e.empty:
        fig_e.add_trace(go.Scatter(x=sl_e["time"],y=sl_e["high"]*1.001,mode="markers",
            marker=dict(symbol="star",color="#ff8800",size=12),name="Sell Liq"), row=1,col=1)
    for _,row in df_en[df_en["bull_ob"]].tail(3).iterrows():
        if not pd.isna(row["bull_ob_low"]):
            fig_e.add_hrect(y0=row["bull_ob_low"],y1=row["bull_ob_high"],
                fillcolor="rgba(0,255,136,0.10)",line_width=1.5,
                line_color="rgba(0,255,136,0.5)",row=1,col=1,
                annotation_text="Bull OB",annotation_font_color="#00ff88",annotation_position="left")
    for _,row in df_en[df_en["fvg_bull"]].tail(2).iterrows():
        if not pd.isna(row["fvg_bull_bottom"]):
            fig_e.add_hrect(y0=row["fvg_bull_bottom"],y1=row["fvg_bull_top"],
                fillcolor="rgba(0,191,255,0.08)",line_width=1,
                line_color="rgba(0,191,255,0.4)",row=1,col=1,
                annotation_text="FVG",annotation_font_color="#00bfff",annotation_position="left")
    sth_e = df_en[df_en["stop_hunt_bull"]].tail(4)
    if not sth_e.empty:
        fig_e.add_trace(go.Scatter(x=sth_e["time"],y=sth_e["low"]*0.998,mode="markers",
            marker=dict(symbol="arrow-up",color="#00ff88",size=14),name="Stop Hunt"), row=1,col=1)
    mclrs = ["#00ff88" if v>=0 else "#ff4444" for v in df_en["macd_hist"]]
    fig_e.add_trace(go.Bar(x=df_en["time"],y=df_en["macd_hist"],name="Hist",marker_color=mclrs,opacity=0.6), row=2,col=1)
    fig_e.add_trace(go.Scatter(x=df_en["time"],y=df_en["macd"],name="MACD",line=dict(color="#00bfff",width=1.2)), row=2,col=1)
    fig_e.add_trace(go.Scatter(x=df_en["time"],y=df_en["macd_signal"],name="Sig",line=dict(color="#FFD700",width=1.2)), row=2,col=1)
    fig_e.add_trace(go.Scatter(x=df_en["time"],y=df_en["rsi"],name="RSI",line=dict(color="#bf00ff",width=1.5)), row=3,col=1)
    fig_e.add_hline(y=70,line_dash="dash",line_color="rgba(255,68,68,0.5)",row=3,col=1)
    fig_e.add_hline(y=50,line_dash="dot", line_color="rgba(255,255,255,0.2)",row=3,col=1)
    fig_e.add_hline(y=30,line_dash="dash",line_color="rgba(0,255,136,0.5)",row=3,col=1)
    fig_e.update_layout(height=750,template="plotly_dark",xaxis_rangeslider_visible=False,
        paper_bgcolor="#050508",plot_bgcolor="#050508",
        legend=dict(orientation="h",y=1.02,font=dict(size=10)),
        title=dict(text=f"{label} — Entry TF | EMA9+20 + VWAP | Focus: BOS, CHoCH, OB, Liquidity",
            font=dict(color="#aaa",size=13)),
        margin=dict(t=60,b=20,l=10,r=80))
    for r in [1,2,3]:
        fig_e.update_xaxes(gridcolor="#0d0d18",row=r,col=1)
        fig_e.update_yaxes(gridcolor="#0d0d18",row=r,col=1)
    return fig_e

# ── Load all 4 timeframes
with st.spinner("Loading all timeframes..."):
    df_daily_raw = get_data(coin, "1d", 200)
    df_4h_raw    = get_data(coin, "4h", 200)
    df_1h_raw    = get_data(coin, "1h", 200)
    df_entry_raw = get_data(coin, tf_entry, 150)

df_daily = add_indicators(df_daily_raw) if not df_daily_raw.empty else pd.DataFrame()
df_4h_c  = add_indicators(df_4h_raw)   if not df_4h_raw.empty   else pd.DataFrame()
df_1h_c  = add_indicators(df_1h_raw)   if not df_1h_raw.empty   else pd.DataFrame()
df_entry = add_indicators(df_entry_raw) if not df_entry_raw.empty else pd.DataFrame()

if not df_daily.empty: df_daily = detect_smc(df_daily)
if not df_4h_c.empty:  df_4h_c  = detect_smc(df_4h_c)
if not df_1h_c.empty:  df_1h_c  = detect_smc(df_1h_c)
if not df_entry.empty: df_entry = detect_smc(df_entry)

# ── Multi-TF bias summary
st.markdown("### 🗺️ Multi-Timeframe Bias Summary")
mb1,mb2,mb3,mb4 = st.columns(4)
def get_bias_color(b):
    return "#00ff88" if b=="BULLISH" else "#ff4444" if b=="BEARISH" else "#888"

for col, df_tmp, label, purpose in [
    (mb1, df_daily, "Daily",  "Direction"),
    (mb2, df_4h_c,  "4H",     "Direction"),
    (mb3, df_1h_c,  "1H",     "Liquidity"),
    (mb4, df_entry, tf_entry, "Entry"),
]:
    if not df_tmp.empty:
        b = df_tmp["trend_bias"].iloc[-1]
        c = get_bias_color(b)
        col.markdown(f"""
        <div style="background:#0d0d1a;border:1px solid {c}44;border-left:3px solid {c};
        border-radius:8px;padding:10px;text-align:center;">
        <b style="color:#aaa;font-size:12px;">{label} ({purpose})</b><br>
        <b style="color:{c};font-size:18px;">{b}</b>
        </div>
        """, unsafe_allow_html=True)

# ── ENHANCED ALIGNMENT CHECK WITH CONFLUENCE SCORE
all_biases = []
all_tf_data = []
for df_tmp, tf_name in [(df_daily,"Daily"),(df_4h_c,"4H"),(df_1h_c,"1H")]:
    if not df_tmp.empty:
        b = df_tmp["trend_bias"].iloc[-1]
        all_biases.append(b)
        all_tf_data.append((tf_name, b, df_tmp))

bull_count = all_biases.count("BULLISH")
bear_count = all_biases.count("BEARISH")

# Calculate alignment score
alignment_score = max(bull_count, bear_count)
alignment_pct   = alignment_score / len(all_biases) * 100 if all_biases else 0

if bull_count == 3:
    st.success("🚀 ALL 3 TIMEFRAMES BULLISH — STRONGEST possible long setup! Enter on 15m confirmation")
    if alerts_on and tg_token and tg_chat_id:
        send_tg(tg_token, tg_chat_id,
            f"🚀🚀🚀 <b>ALL TF ALIGNED BULLISH!</b>\n"
            f"{coin} — Daily+4H+1H all BULLISH\n"
            f"Price: ${lat['close']:,.2f}\n"
            f"⚡ Wait for 15m BOS then ENTER LONG!")
elif bull_count == 2:
    st.info("📊 2/3 timeframes bullish — Good long bias. Wait for 15m entry signal")
elif bear_count == 3:
    st.error("🔴 ALL 3 TIMEFRAMES BEARISH — STRONGEST possible short setup!")
    if alerts_on and tg_token and tg_chat_id:
        send_tg(tg_token, tg_chat_id,
            f"🔴🔴🔴 <b>ALL TF ALIGNED BEARISH!</b>\n"
            f"{coin} — Daily+4H+1H all BEARISH\n"
            f"Price: ${lat['close']:,.2f}\n"
            f"⚡ Wait for 15m BOS down then ENTER SHORT!")
elif bear_count == 2:
    st.warning("📊 2/3 timeframes bearish — Moderate short bias")
else:
    st.warning("⚪ Mixed signals — DO NOT TRADE. Wait for alignment")

# Alignment meter
st.markdown(f"**Timeframe Alignment: {alignment_pct:.0f}%**")
align_color = "#00ff88" if alignment_pct >= 100 else "#FFD700" if alignment_pct >= 66 else "#ff4444"
st.markdown(f"""
<div style="background:#1a1a2e;border-radius:8px;overflow:hidden;height:12px;margin:4px 0;">
<div style="background:{align_color};width:{alignment_pct:.0f}%;height:100%;border-radius:8px;"></div>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

with tab2:
    st.markdown("### 📅 Daily Chart — Trend Direction")
    st.info("**Purpose:** Find overall market direction. EMAs 50+200. Look for: Which way is trend? Above or below EMA200? BOS confirmed?")
    if not df_daily.empty:
        st.plotly_chart(build_direction_chart(df_daily, f"{coin} Daily",
            [("EMA50","ema50","#FF8C00"),("EMA200","ema200","#FF4500")], show_200=True),
            use_container_width=True)
        # Daily key levels
        dl = df_daily.iloc[-1]
        dc1,dc2,dc3,dc4 = st.columns(4)
        dc1.metric("Daily Close",  f"${dl['close']:,.2f}")
        dc2.metric("Daily Bias",   dl["trend_bias"])
        dc3.metric("Above EMA200", "YES ✅" if dl["close"]>dl["ema200"] else "NO ⚠️")
        dc4.metric("Daily RSI",    f"{dl['rsi']:.1f}")
    else:
        st.warning("Could not load daily data")

with tab3:
    st.markdown("### 💧 1H Chart — Liquidity Check")
    st.info("**Purpose:** Find all liquidity levels. EMA 20+50. Look for: EQH/EQL, FVGs, OBs, where are the stop hunts?")
    if not df_1h_c.empty:
        st.plotly_chart(build_liquidity_chart(df_1h_c, f"{coin} 1H"), use_container_width=True, key="pc_3")
        hl = df_1h_c.iloc[-1]
        hc1,hc2,hc3,hc4 = st.columns(4)
        hc1.metric("1H Price",  f"${hl['close']:,.2f}")
        hc2.metric("1H Bias",   hl["trend_bias"])
        hc3.metric("1H RSI",    f"{hl['rsi']:.1f}")
        hc4.metric("1H Vol",    "SPIKE 🚀" if hl["vol_spike"] else "Normal")
        # Show all liquidity levels
        st.markdown("**Key Liquidity Levels on 1H:**")
        lc1,lc2,lc3 = st.columns(3)
        with lc1:
            st.markdown("**Buyside Liquidity (above)**")
            for _,row in df_1h_c[df_1h_c["buyside_liq"]].tail(4).iterrows():
                st.markdown(f'<span class="zone-tag liq-tag">BSL ${row["high"]:,.0f}</span>', unsafe_allow_html=True)
        with lc2:
            st.markdown("**Sellside Liquidity (below)**")
            for _,row in df_1h_c[df_1h_c["sellside_liq"]].tail(4).iterrows():
                st.markdown(f'<span class="zone-tag ob-bull">SSL ${row["low"]:,.0f}</span>', unsafe_allow_html=True)
        with lc3:
            st.markdown("**Equal Highs / Lows**")
            for _,row in df_1h_c[df_1h_c["equal_highs"]].tail(3).iterrows():
                st.markdown(f'<span class="zone-tag ob-bear">EQH ${row["high"]:,.0f}</span>', unsafe_allow_html=True)
            for _,row in df_1h_c[df_1h_c["equal_lows"]].tail(3).iterrows():
                st.markdown(f'<span class="zone-tag ob-bull">EQL ${row["low"]:,.0f}</span>', unsafe_allow_html=True)
    else:
        st.warning("Could not load 1H data")

with tab4:
    st.markdown(f"### ⚡ {tf_entry} Chart — Entry")
    st.info(f"**Purpose:** Find exact entry. EMA 9+20 + VWAP. Look for: BOS on entry TF after liquidity sweep, CHoCH, OB retest")
    if not df_entry.empty:
        st.plotly_chart(build_entry_chart(df_entry, f"{coin} {tf_entry}"), use_container_width=True, key="pc_4")
        el = df_entry.iloc[-1]
        ec1,ec2,ec3,ec4 = st.columns(4)
        ec1.metric("Entry TF Price", f"${el['close']:,.2f}")
        ec2.metric("Entry Bias",     el["trend_bias"])
        ec3.metric("RSI",            f"{el['rsi']:.1f}")
        ec4.metric("MACD",           "Bull ✅" if el["macd"]>el["macd_signal"] else "Bear ⚠️")
    else:
        st.warning(f"Could not load {tf_entry} data")

with tab5:
    ic1, ic2 = st.columns(2)
    with ic1:
        fs = go.Figure()
        fs.add_trace(go.Scatter(x=df["time"],y=df["stoch_k"]*100,name="K",line=dict(color="#00ff88",width=1.5)))
        fs.add_trace(go.Scatter(x=df["time"],y=df["stoch_d"]*100,name="D",line=dict(color="#FFD700",width=1.5)))
        fs.add_hline(y=80,line_dash="dash",line_color="red",opacity=0.5)
        fs.add_hline(y=20,line_dash="dash",line_color="green",opacity=0.5)
        fs.update_layout(height=250,template="plotly_dark",title="Stochastic RSI",paper_bgcolor="#050508",plot_bgcolor="#050508",margin=dict(t=30,b=10))
        st.plotly_chart(fs,use_container_width=True, key="pc_5")
    with ic2:
        fa = go.Figure()
        fa.add_trace(go.Scatter(x=df["time"],y=df["adx"],name="ADX",line=dict(color="#FFD700",width=2)))
        fa.add_trace(go.Scatter(x=df["time"],y=df["adx_pos"],name="+DI",line=dict(color="#00ff88",width=1)))
        fa.add_trace(go.Scatter(x=df["time"],y=df["adx_neg"],name="-DI",line=dict(color="#ff4444",width=1)))
        fa.add_hline(y=25,line_dash="dash",line_color="white",opacity=0.3)
        fa.update_layout(height=250,template="plotly_dark",title="ADX Trend Strength",paper_bgcolor="#050508",plot_bgcolor="#050508",margin=dict(t=30,b=10))
        st.plotly_chart(fa,use_container_width=True, key="pc_6")
    fb = go.Figure()
    fb.add_trace(go.Scatter(x=df["time"],y=df["bb_width"],name="BB Width",line=dict(color="#00bfff",width=1.5),fill="tozeroy",fillcolor="rgba(0,191,255,0.05)"))
    fb.update_layout(height=200,template="plotly_dark",title="BB Width — Squeeze Detector",paper_bgcolor="#050508",plot_bgcolor="#050508",margin=dict(t=30,b=10))
    st.plotly_chart(fb,use_container_width=True, key="pc_7")

def get_correlation_data(coins, tf, lim):
    tf_mins = {"1m":1,"3m":3,"5m":5,"15m":15,"30m":30,"1h":60,"2h":120,"4h":240,"6h":360,"12h":720,"1d":1440}
    mins_per_candle = tf_mins.get(tf, 60)
    results = []
    btc = get_data("BTC/USDT", tf, lim)
    if btc.empty: return [], btc
    btc = add_indicators(btc)
    btc_v = btc["volume"]
    btc_vn = (btc_v - btc_v.min()) / (btc_v.max() - btc_v.min())
    btc_p = btc["close"]
    btc_pn = (btc_p - btc_p.min()) / (btc_p.max() - btc_p.min())

    for c in coins:
        try:
            adf = get_data(c, tf, lim)
            if adf.empty: continue
            adf = add_indicators(adf)
            av = adf["volume"]; av_n = (av - av.min()) / (av.max() - av.min())
            ap = adf["close"];  ap_n = (ap - ap.min()) / (ap.max() - ap.min())

            # Volume correlation
            vol_corr = float(btc_vn.corr(av_n))

            # Price correlation
            price_corr = float(btc_pn.corr(ap_n))

            # Lag correlation — find which lag gives highest correlation
            best_lag = 0
            best_lag_corr = vol_corr
            for lag in range(1, 6):
                lagged = btc_vn.shift(lag)
                lc = float(lagged.corr(av_n))
                if lc > best_lag_corr:
                    best_lag_corr = lc
                    best_lag = lag

            lag_mins = best_lag * mins_per_candle

            # Current spike status
            spike_now = bool(adf["vol_spike"].iloc[-1])
            btc_spike_now = bool(btc["vol_spike"].iloc[-1])

            # Price change vs BTC
            btc_pct = (btc["close"].iloc[-1] - btc["close"].iloc[-5]) / btc["close"].iloc[-5] * 100
            alt_pct = (adf["close"].iloc[-1] - adf["close"].iloc[-5]) / adf["close"].iloc[-5] * 100
            beta = alt_pct / btc_pct if btc_pct != 0 else 0

            results.append({
                "coin":       c.replace("/USDT",""),
                "price":      adf["close"].iloc[-1],
                "vol_corr":   vol_corr,
                "price_corr": price_corr,
                "best_lag":   best_lag,
                "lag_mins":   lag_mins,
                "lag_corr":   best_lag_corr,
                "spike_now":  spike_now,
                "btc_pct":    btc_pct,
                "alt_pct":    alt_pct,
                "beta":       beta,
                "df":         adf,
                "btc_vn":     btc_vn,
                "btc_df":     btc
            })
        except: continue

    results = sorted(results, key=lambda x: x["vol_corr"], reverse=True)
    return results, btc

ALL_COINS = [
    "BTC/USDT","ETH/USDT","SOL/USDT","BNB/USDT","ADA/USDT",
    "MATIC/USDT","AVAX/USDT","LINK/USDT","DOT/USDT","DOGE/USDT",
    "XRP/USDT","INJ/USDT","SUI/USDT","ARB/USDT","OP/USDT","TRX/USDT"
]
corr_results, btc_df_main = get_correlation_data(ALL_COINS, timeframe, limit)

if corr_results:
    # ── BTC STATUS
    btc_spike_now = bool(btc_df_main["vol_spike"].iloc[-1])
    btc_price_chg = (btc_df_main["close"].iloc[-1] - btc_df_main["close"].iloc[-5]) / btc_df_main["close"].iloc[-5] * 100
    btc_rsi       = btc_df_main["rsi"].iloc[-1]

    bc1, bc2, bc3 = st.columns(3)
    bc1.metric("BTC Price",  f"${btc_df_main['close'].iloc[-1]:,.2f}", f"{btc_price_chg:.2f}%")
    bc2.metric("BTC Volume", "SPIKE 🚀" if btc_spike_now else "Normal")
    bc3.metric("BTC RSI",    f"{btc_rsi:.1f}", "OB" if btc_rsi>70 else "OS" if btc_rsi<30 else "OK")

    if btc_spike_now:
        st.success("🚨 BTC Volume Spike RIGHT NOW — watch for altcoin rotation in next few candles!")
    elif btc_price_chg > 1:
        st.success(f"📈 BTC up {btc_price_chg:.2f}% — altcoins may follow soon")
    elif btc_price_chg < -1:
        st.warning(f"📉 BTC down {btc_price_chg:.2f}% — altcoins likely to drop too")

    st.markdown("---")

    # ── CORRELATION TABLE
    st.markdown("### 📊 Correlation Rankings — All Coins vs BTC")
    st.caption("Sorted by strongest volume correlation. Best coins to trade after BTC moves.")

    # Build display table
    table_data = []
    for r in corr_results:
        vol_str   = "🔥🔥🔥" if r["vol_corr"] > 0.75 else "🔥🔥" if r["vol_corr"] > 0.5 else "🔥"
        lag_str   = f"~{r['lag_mins']} mins" if r["best_lag"] > 0 else "Instant"
        beta_str  = f"{r['beta']:.2f}x" if r["beta"] != 0 else "—"
        spike_str = "YES 🚀" if r["spike_now"] else "No"
        table_data.append({
            "Coin":        r["coin"],
            "Price":       f"${r['price']:,.2f}",
            "Vol Corr":    f"{r['vol_corr']:.2f} {vol_str}",
            "Price Corr":  f"{r['price_corr']:.2f}",
            "Lag After BTC": lag_str,
            "Beta vs BTC": beta_str,
            "5c Change":   f"{r['alt_pct']:.2f}%",
            "Vol Spike":   spike_str,
        })
    tdf = pd.DataFrame(table_data)
    st.dataframe(tdf, use_container_width=True, hide_index=True)

    st.markdown(" ")
    st.markdown("**Legend:**")
    lc1,lc2,lc3,lc4 = st.columns(4)
    lc1.info("**Vol Corr** — how closely coin volume follows BTC volume. Higher = stronger.")
    lc2.info("**Lag** — how many minutes AFTER BTC the coin volume tends to spike.")
    lc3.info("**Beta** — if BTC moves 1%, this coin moves Beta x%. >1 = more volatile.")
    lc4.info("**5c Change** — price change over last 5 candles vs BTC.")

    st.markdown("---")

    # ── LAG ANALYSIS CHART
    st.markdown("### ⏱ Volume Lag Analysis — Who Follows BTC First?")
    st.caption("When BTC volume spikes, which coin volume follows and how quickly?")

    lag_fig = go.Figure()
    btc_vn_main = corr_results[0]["btc_vn"]
    btc_times   = btc_df_main["time"]
    lag_fig.add_trace(go.Scatter(
        x=btc_times, y=btc_vn_main,
        name="BTC Volume", line=dict(color="#F7931A", width=3)
    ))
    colors = ["#00ff88","#00bfff","#bf00ff","#FFD700","#FF8C00","#ff4444","#00ffff","#ff8800"]
    for idx, r in enumerate(corr_results[:6]):
        av = r["df"]["volume"]
        av_n = (av - av.min()) / (av.max() - av.min())
        lag_fig.add_trace(go.Scatter(
            x=r["df"]["time"], y=av_n,
            name=f"{r['coin']} (lag {r['lag_mins']}m, r={r['vol_corr']:.2f})",
            line=dict(color=colors[idx % len(colors)], width=1.5),
            opacity=0.85
        ))
    lag_fig.update_layout(
        height=350, template="plotly_dark",
        paper_bgcolor="#050508", plot_bgcolor="#050508",
        title="Volume Rotation — Normalised 0 to 1 (BTC orange, altcoins coloured)",
        legend=dict(orientation="h", y=-0.3),
        margin=dict(t=40, b=80)
    )
    lag_fig.update_xaxes(gridcolor="#111118")
    lag_fig.update_yaxes(gridcolor="#111118")
    st.plotly_chart(lag_fig, use_container_width=True, key="pc_8")

    st.markdown("---")

    # ── INDIVIDUAL COIN CARDS
    st.markdown("### 🪙 Coin by Coin Analysis")
    num_cols = 4
    rows_needed = (len(corr_results) + num_cols - 1) // num_cols
    for row_i in range(rows_needed):
        cols = st.columns(num_cols)
        for col_i in range(num_cols):
            idx = row_i * num_cols + col_i
            if idx >= len(corr_results): break
            r = corr_results[idx]
            with cols[col_i]:
                vol_strength = "🔥🔥🔥 Strong" if r["vol_corr"]>0.75 else "🔥🔥 Medium" if r["vol_corr"]>0.5 else "🔥 Weak"
                trend_emoji = "🟢" if r["alt_pct"] > 0 else "🔴"
                card_border = "#00ff88" if r["spike_now"] else "#1e1e3a"
                st.markdown(f"""
                <div style="background:#0d0d1a;border:1px solid {card_border};border-radius:10px;padding:14px;margin:4px 0;">
                <b style="font-size:18px;">{r['coin']}</b><br>
                <span style="color:#aaa;font-size:13px;">${r['price']:,.2f} {trend_emoji} {r['alt_pct']:+.2f}%</span><br><br>
                <span style="color:#F7931A;">Vol Corr: {r['vol_corr']:.2f}</span> {vol_strength}<br>
                <span style="color:#00bfff;">Price Corr: {r['price_corr']:.2f}</span><br>
                <span style="color:#FFD700;">Lag: ~{r['lag_mins']} mins after BTC</span><br>
                <span style="color:#bf00ff;">Beta: {r['beta']:.2f}x BTC move</span><br>
                <span style="color:{'#00ff88' if r['spike_now'] else '#888'};">
                Vol Spike: {'YES 🚀' if r['spike_now'] else 'No'}</span>
                </div>
                """, unsafe_allow_html=True)

                # Telegram alert for rotating coins
                if alerts_on and tg_token and tg_chat_id and r["spike_now"] and btc_spike_now:
                    send_tg(tg_token, tg_chat_id,
                        f"🔄 <b>ROTATION ALERT</b>\n"
                        f"BTC spiking + {r['coin']} volume spike NOW\n"
                        f"Correlation: {r['vol_corr']:.2f} {vol_strength}\n"
                        f"Lag: ~{r['lag_mins']} mins\n"
                        f"Beta: {r['beta']:.2f}x\n"
                        f"Price: ${r['price']:,.2f}")

    st.markdown("---")

    # ── PRICE CORRELATION CHART
    st.markdown("### 📈 Price Correlation vs BTC")
    st.caption("How closely each coin price moves with BTC price")

    btc_p  = btc_df_main["close"]
    btc_pn = (btc_p - btc_p.min()) / (btc_p.max() - btc_p.min())
    pc_fig = go.Figure()
    pc_fig.add_trace(go.Scatter(
        x=btc_df_main["time"], y=btc_pn,
        name="BTC Price", line=dict(color="#F7931A", width=3)
    ))
    for idx, r in enumerate(corr_results[:5]):
        ap = r["df"]["close"]
        ap_n = (ap - ap.min()) / (ap.max() - ap.min())
        pc_fig.add_trace(go.Scatter(
            x=r["df"]["time"], y=ap_n,
            name=f"{r['coin']} (r={r['price_corr']:.2f})",
            line=dict(color=colors[idx % len(colors)], width=1.5)
        ))
    pc_fig.update_layout(
        height=300, template="plotly_dark",
        paper_bgcolor="#050508", plot_bgcolor="#050508",
        title="Price Correlation — Normalised 0 to 1",
        legend=dict(orientation="h", y=-0.4),
        margin=dict(t=40, b=80)
    )
    pc_fig.update_xaxes(gridcolor="#111118")
    pc_fig.update_yaxes(gridcolor="#111118")
    st.plotly_chart(pc_fig, use_container_width=True, key="pc_9")

    # ── BEST TRADE RECOMMENDATION
    st.markdown("---")
    st.markdown("### 🎯 Best Altcoin To Trade Right Now")
    best = corr_results[0]
    second = corr_results[1] if len(corr_results) > 1 else None
    rec_col1, rec_col2 = st.columns(2)
    with rec_col1:
        st.success(f"""
**🥇 {best['coin']}**
Volume Correlation: {best['vol_corr']:.2f} 🔥
Lag after BTC: ~{best['lag_mins']} minutes
Beta: {best['beta']:.2f}x
Current Price: ${best['price']:,.2f}
Vol Spike Now: {'YES 🚀' if best['spike_now'] else 'No'}
        """)
    if second:
        with rec_col2:
            st.info(f"""
**🥈 {second['coin']}**
Volume Correlation: {second['vol_corr']:.2f}
Lag after BTC: ~{second['lag_mins']} minutes
Beta: {second['beta']:.2f}x
Current Price: ${second['price']:,.2f}
Vol Spike Now: {'YES 🚀' if second['spike_now'] else 'No'}
            """)

    st.caption("💡 Highest correlation + shortest lag = best coin to trade after BTC makes a move")

else:
    st.warning("Could not load correlation data. Check your internet connection.")


# ════════════════════════════════════════════════════════════════
# ── MULTI COIN SCANNER
# ════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("🔍 Multi Coin Scanner")
st.caption("Scans all coins at once and shows which has the strongest signal right now")

SCAN_COINS = ["BTC/USDT","ETH/USDT","SOL/USDT","ADA/USDT","MATIC/USDT","BNB/USDT","AVAX/USDT","LINK/USDT","DOT/USDT","ATOM/USDT","NEAR/USDT","OP/USDT","ARB/USDT","DOGE/USDT","XRP/USDT","INJ/USDT","SUI/USDT","APT/USDT"]

@st.cache_data(ttl=120)
def scan_all_coins(coins, tf, lim):
    results = []
    for c in coins:
        try:
            d = get_data(c, tf, lim)
            if d.empty: continue
            d = add_indicators(d)
            d = detect_smc(d)
            sup, res = detect_sr_zones(d)
            s, css, score, ms, reasons, lat2, b = full_signal(d, sup, res)
            pct = (lat2["close"] - d["close"].iloc[-2]) / d["close"].iloc[-2] * 100
            results.append({
                "coin": c.replace("/USDT",""),
                "price": lat2["close"],
                "pct": pct,
                "signal": s,
                "score": score,
                "bias": b,
                "rsi": lat2["rsi"],
                "vol_spike": lat2["vol_spike"],
                "bos": lat2["bos_bull"] or lat2["bos_bear"],
                "choch": lat2["choch_bull"] or lat2["choch_bear"],
                "css": css
            })
        except: continue
    return sorted(results, key=lambda x: abs(x["score"]), reverse=True)

if st.button("🔄 Scan All Coins Now", key="btn_10"):
    st.cache_data.clear()

scan_results = scan_all_coins(SCAN_COINS, timeframe, limit)

if scan_results:
    # Summary bar
    bullish_count = sum(1 for r in scan_results if r["score"] >= 4)
    bearish_count = sum(1 for r in scan_results if r["score"] <= -4)
    neutral_count = len(scan_results) - bullish_count - bearish_count
    sb1, sb2, sb3 = st.columns(3)
    sb1.metric("Bullish Coins 🟢", bullish_count)
    sb2.metric("Neutral Coins ⚪", neutral_count)
    sb3.metric("Bearish Coins 🔴", bearish_count)

    # Scanner cards
    num_cols = 4
    for row_i in range((len(scan_results) + num_cols - 1) // num_cols):
        cols = st.columns(num_cols)
        for col_i in range(num_cols):
            idx = row_i * num_cols + col_i
            if idx >= len(scan_results): break
            r = scan_results[idx]
            with cols[col_i]:
                color = "#00ff88" if r["score"] >= 4 else "#ff4444" if r["score"] <= -4 else "#888"
                pct_arrow = "🟢" if r["pct"] > 0 else "🔴"
                st.markdown(f"""
                <div style="background:#0d0d1a;border:1px solid {color}33;border-left:3px solid {color};
                border-radius:8px;padding:12px;margin:3px 0;">
                <b style="font-size:16px;color:{color};">{r['coin']}</b>
                <span style="float:right;color:#aaa;font-size:12px;">{pct_arrow}{r['pct']:+.2f}%</span><br>
                <span style="color:#ddd;font-size:13px;">${r['price']:,.2f}</span><br>
                <span style="color:{color};font-size:12px;font-weight:700;">Score: {r['score']}/30</span><br>
                <span style="color:#aaa;font-size:11px;">RSI: {r['rsi']:.0f} | {r['bias']}</span><br>
                <span style="color:#aaa;font-size:11px;">
                {'🚀 Vol Spike' if r['vol_spike'] else ''}
                {'⚡ BOS' if r['bos'] else ''}
                {'🔄 CHoCH' if r['choch'] else ''}
                </span>
                </div>
                """, unsafe_allow_html=True)

    # Best opportunity
    if scan_results:
        best_scan = scan_results[0]
        bc = "#00ff88" if best_scan["score"] >= 4 else "#ff4444" if best_scan["score"] <= -4 else "#888"
        st.markdown(f"""
        <div style="background:#0d0d1a;border:2px solid {bc};border-radius:10px;padding:16px;margin:12px 0;text-align:center;">
        <b style="font-size:20px;color:{bc};">🎯 Strongest Signal: {best_scan['coin']} — Score {best_scan['score']}/30</b><br>
        <span style="color:#aaa;">Switch coin selector to {best_scan['coin']} to see full analysis</span>
        </div>
        """, unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════
# ── SESSION TIMES
# ════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("🕐 Trading Session Times")
st.caption("Big moves happen at session opens. Know when to watch the market.")

now_utc = datetime.utcnow()
sessions = [
    {"name": "Asia",   "open": 0,  "close": 9,  "color": "#FFD700", "desc": "Tokyo/Singapore — lower volume, ranging"},
    {"name": "London", "open": 8,  "close": 17, "color": "#00bfff", "desc": "Most liquidity grabs happen here"},
    {"name": "New York","open": 13, "close": 22, "color": "#00ff88", "desc": "Highest volume — biggest moves"},
    {"name": "Overlap", "open": 13, "close": 17, "color": "#bf00ff", "desc": "London+NY overlap — most volatile!"},
]
current_hour = now_utc.hour
sc1, sc2, sc3, sc4 = st.columns(4)
for col, sess in zip([sc1, sc2, sc3, sc4], sessions):
    is_open = sess["open"] <= current_hour < sess["close"]
    status  = "🟢 OPEN NOW" if is_open else "🔴 Closed"
    with col:
        st.markdown(f"""
        <div style="background:#0d0d1a;border:1px solid {sess['color']}44;border-left:3px solid {sess['color']};
        border-radius:8px;padding:12px;margin:3px 0;">
        <b style="color:{sess['color']};font-size:16px;">{sess['name']}</b><br>
        <span style="color:#ddd;font-size:13px;">{sess['open']:02d}:00 – {sess['close']:02d}:00 UTC</span><br>
        <span style="font-size:13px;">{status}</span><br>
        <span style="color:#888;font-size:11px;">{sess['desc']}</span>
        </div>
        """, unsafe_allow_html=True)

# Session chart
st.markdown(" ")
sess_fig = go.Figure()
for sess in sessions:
    sess_fig.add_vrect(
        x0=sess["open"], x1=sess["close"],
        fillcolor=sess["color"], opacity=0.08,
        line_width=1, line_color=sess["color"],
        annotation_text=sess["name"],
        annotation_font_color=sess["color"],
        annotation_position="top left"
    )
sess_fig.add_vline(x=current_hour, line_dash="solid", line_color="white",
    line_width=2, annotation_text=f"NOW {current_hour:02d}:00 UTC",
    annotation_font_color="white")
sess_fig.update_xaxes(range=[0,24], tickvals=list(range(0,25,2)),
    ticktext=[f"{h:02d}:00" for h in range(0,25,2)], title="UTC Hour")
sess_fig.update_yaxes(visible=False)
sess_fig.update_layout(height=180, template="plotly_dark",
    paper_bgcolor="#050508", plot_bgcolor="#050508",
    title="24h Session Map — Current UTC Time Shown",
    margin=dict(t=40, b=40, l=10, r=10))
st.plotly_chart(sess_fig, use_container_width=True, key="pc_10")

# ════════════════════════════════════════════════════════════════
# ── HEAT MAP
# ════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("🌡️ Crypto Heat Map")
st.caption("See which coins are pumping or dumping right now")

@st.cache_data(ttl=120)
def get_heatmap_data():
    coins = ["BTC","ETH","SOL","ADA","MATIC","BNB","AVAX","LINK","DOT","ATOM","NEAR","FTM","OP","ARB","APT","DOGE","XRP","LTC","UNI","AAVE","INJ","SUI","SEI","WLD","FET","RNDR","IMX","SAND","TRX","NEAR"]
    data  = []
    ex    = ccxt.binance()
    for c in coins:
        try:
            ticker = ex.fetch_ticker(f"{c}/USDT")
            data.append({
                "coin": c,
                "price": ticker["last"],
                "pct_1h": ticker.get("percentage", 0) or 0,
                "volume": ticker.get("quoteVolume", 0) or 0,
            })
        except: continue
    return data

hmap_data = get_heatmap_data()

if hmap_data:
    # Sort by % change
    hmap_data = sorted(hmap_data, key=lambda x: x["pct_1h"], reverse=True)

    cols_per_row = 5
    for row_i in range((len(hmap_data) + cols_per_row - 1) // cols_per_row):
        cols = st.columns(cols_per_row)
        for col_i in range(cols_per_row):
            idx = row_i * cols_per_row + col_i
            if idx >= len(hmap_data): break
            d = hmap_data[idx]
            pct = d["pct_1h"]
            if pct >= 3:   bg, tc = "#0d4a1e", "#00ff88"
            elif pct >= 1: bg, tc = "#0a3a15", "#00cc66"
            elif pct >= 0: bg, tc = "#0a2a10", "#00aa44"
            elif pct >= -1: bg, tc = "#3a0d0d", "#ff6666"
            elif pct >= -3: bg, tc = "#4a0d0d", "#ff4444"
            else:           bg, tc = "#5a0d0d", "#ff2222"
            with cols[col_i]:
                st.markdown(f"""
                <div style="background:{bg};border-radius:8px;padding:12px;margin:3px;text-align:center;">
                <b style="color:{tc};font-size:16px;">{d['coin']}</b><br>
                <span style="color:{tc};font-size:18px;font-weight:700;">{pct:+.2f}%</span><br>
                <span style="color:#aaa;font-size:11px;">${d['price']:,.2f}</span>
                </div>
                """, unsafe_allow_html=True)

    # Heatmap bar chart
    hmap_fig = go.Figure(go.Bar(
        x=[d["coin"] for d in hmap_data],
        y=[d["pct_1h"] for d in hmap_data],
        marker_color=["#00ff88" if d["pct_1h"] >= 0 else "#ff4444" for d in hmap_data],
        text=[f"{d['pct_1h']:+.2f}%" for d in hmap_data],
        textposition="outside"
    ))
    hmap_fig.update_layout(
        height=300, template="plotly_dark",
        paper_bgcolor="#050508", plot_bgcolor="#050508",
        title="24h Price Change % — All Coins",
        margin=dict(t=40, b=20)
    )
    hmap_fig.add_hline(y=0, line_color="white", line_width=1, opacity=0.3)
    st.plotly_chart(hmap_fig, use_container_width=True, key="pc_11")

# ════════════════════════════════════════════════════════════════
# ── NEWS FEED
# ════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("📰 Live Crypto News")
st.caption("Latest crypto news — always know what is moving the market")

@st.cache_data(ttl=300)
def get_crypto_news():
    try:
        url = "https://api.coingecko.com/api/v3/news"
        r   = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data.get("data", [])[:10]
    except: pass
    # Fallback — CryptoPanic public RSS
    try:
        url = "https://cryptopanic.com/api/v1/posts/?auth_token=public&kind=news&public=true"
        r   = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            posts = data.get("results", [])[:10]
            return [{"title": p["title"], "url": p["url"],
                     "published_at": p.get("published_at",""), "source": p.get("source",{}).get("title","")} for p in posts]
    except: pass
    return []

news_items = get_crypto_news()
if news_items:
    for item in news_items[:8]:
        title  = item.get("title","")
        url    = item.get("url","#")
        source = item.get("source","") or item.get("author","")
        date   = str(item.get("published_at","") or item.get("created_at",""))[:16]
        # Sentiment colour
        bull_words = ["surge","pump","bull","rise","gain","rally","up","high","buy","moon"]
        bear_words = ["crash","dump","bear","fall","drop","down","low","sell","fear","loss"]
        title_lower = title.lower()
        if any(w in title_lower for w in bull_words):   nc = "#00ff8833"
        elif any(w in title_lower for w in bear_words): nc = "#ff444433"
        else:                                            nc = "#1e1e3a"
        st.markdown(f"""
        <div style="background:{nc};border-radius:8px;padding:10px 14px;margin:4px 0;border:1px solid #333;">
        <a href="{url}" target="_blank" style="color:#ddd;text-decoration:none;font-size:14px;font-weight:600;">{title}</a><br>
        <span style="color:#888;font-size:11px;">{source} &nbsp;|&nbsp; {date}</span>
        </div>
        """, unsafe_allow_html=True)
else:
    st.info("News feed loading... Check your internet connection or try refreshing.")
    st.markdown("""
    **Top crypto news sources to check manually:**
    - [CoinDesk](https://coindesk.com)
    - [CoinTelegraph](https://cointelegraph.com)
    - [CryptoPanic](https://cryptopanic.com)
    """)

# ════════════════════════════════════════════════════════════════
# ── TRADING JOURNAL
# ════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("📓 Trading Journal")
st.caption("Log every trade. This is the most important habit for improving.")

if "journal" not in st.session_state:
    st.session_state.journal = []

with st.expander("➕ Log A New Trade", expanded=False):
    jc1, jc2, jc3 = st.columns(3)
    j_coin    = jc1.selectbox("Coin", ["BTC","ETH","SOL","ADA","MATIC","BNB","AVAX","LINK","DOT","ATOM","NEAR","OP","ARB","DOGE","XRP","INJ","SUI","APT","FET","RNDR"], key="j_coin")
    j_dir     = jc2.selectbox("Direction", ["LONG","SHORT"], key="j_dir")
    j_result  = jc3.selectbox("Result", ["WIN","LOSS","BREAKEVEN"], key="j_result")
    jc4, jc5, jc6 = st.columns(3)
    j_entry   = jc4.number_input("Entry Price", value=0.0, key="j_entry")
    j_exit    = jc5.number_input("Exit Price",  value=0.0, key="j_exit")
    j_size    = jc6.number_input("Position Size (USDT)", value=10.0, key="j_size")
    jc7, jc8  = st.columns(2)
    j_signal  = jc7.selectbox("Signal That Triggered",
        ["BOS","CHoCH","OB Retest","FVG Fill","Liquidity Sweep","Support Bounce","Resistance Reject","Other"], key="j_signal")
    j_tf      = jc8.selectbox("Timeframe Used", ["15m","1h","4h","1d"], key="j_tf")
    j_notes   = st.text_area("Notes / What I Learned", placeholder="Why did I take this trade? What happened? What would I do differently?", key="j_notes")

    if st.button("💾 Save Trade", key="btn_11"):
        if j_entry > 0 and j_exit > 0:
            pnl = (j_exit - j_entry) / j_entry * 100 if j_dir == "LONG" else (j_entry - j_exit) / j_entry * 100
            pnl_usdt = j_size * (pnl / 100)
            st.session_state.journal.append({
                "date":    datetime.now().strftime("%Y-%m-%d %H:%M"),
                "coin":    j_coin,
                "dir":     j_dir,
                "entry":   j_entry,
                "exit":    j_exit,
                "result":  j_result,
                "pnl_pct": round(pnl, 2),
                "pnl_usdt":round(pnl_usdt, 2),
                "signal":  j_signal,
                "tf":      j_tf,
                "notes":   j_notes,
                "size":    j_size
            })
            st.success("Trade saved! ✅")
        else:
            st.warning("Please enter entry and exit prices.")

if st.session_state.journal:
    jdf = pd.DataFrame(st.session_state.journal)

    # ── Win Rate Calculator
    st.markdown("---")
    st.subheader("📊 Win Rate Calculator")
    wins      = len(jdf[jdf["result"] == "WIN"])
    losses    = len(jdf[jdf["result"] == "LOSS"])
    total     = len(jdf)
    win_rate  = wins / total * 100 if total > 0 else 0
    total_pnl = jdf["pnl_usdt"].sum()
    avg_win   = jdf[jdf["result"]=="WIN"]["pnl_usdt"].mean() if wins > 0 else 0
    avg_loss  = jdf[jdf["result"]=="LOSS"]["pnl_usdt"].mean() if losses > 0 else 0
    rr_ratio  = abs(avg_win / avg_loss) if avg_loss != 0 else 0

    wc1,wc2,wc3,wc4,wc5,wc6 = st.columns(6)
    wc1.metric("Total Trades", total)
    wc2.metric("Win Rate",    f"{win_rate:.1f}%", f"{wins}W / {losses}L")
    wc3.metric("Total P&L",   f"${total_pnl:.2f}", "Profit" if total_pnl > 0 else "Loss")
    wc4.metric("Avg Win",     f"${avg_win:.2f}")
    wc5.metric("Avg Loss",    f"${avg_loss:.2f}")
    wc6.metric("R:R Ratio",   f"{rr_ratio:.2f}")

    # Profitability check
    if win_rate >= 50 and rr_ratio >= 1.5:
        st.success("✅ Strategy is profitable! Keep following the rules.")
    elif win_rate >= 40 and rr_ratio >= 2.0:
        st.success("✅ Low win rate but good R:R — strategy can still be profitable!")
    elif total >= 5:
        st.warning("⚠️ Strategy needs improvement. Review your losing trades.")

    # Win rate by signal
    if len(jdf) >= 3:
        st.markdown("**Win Rate by Signal:**")
        sig_stats = jdf.groupby("signal").apply(
            lambda x: pd.Series({"Trades": len(x), "Wins": (x["result"]=="WIN").sum(),
                                  "Win%": round((x["result"]=="WIN").mean()*100,1),
                                  "P&L": round(x["pnl_usdt"].sum(),2)})
        ).reset_index()
        st.dataframe(sig_stats, use_container_width=True, hide_index=True)

    # P&L chart
    if len(jdf) >= 2:
        jdf["cumulative_pnl"] = jdf["pnl_usdt"].cumsum()
        pnl_fig = go.Figure()
        pnl_fig.add_trace(go.Scatter(
            x=jdf["date"], y=jdf["cumulative_pnl"],
            name="Cumulative P&L", fill="tozeroy",
            line=dict(color="#00ff88" if total_pnl >= 0 else "#ff4444", width=2),
            fillcolor="rgba(0,255,136,0.08)" if total_pnl >= 0 else "rgba(255,68,68,0.08)"
        ))
        pnl_fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.3)
        pnl_fig.update_layout(height=250, template="plotly_dark",
            paper_bgcolor="#050508", plot_bgcolor="#050508",
            title="Cumulative P&L ($)", margin=dict(t=30, b=20))
        st.plotly_chart(pnl_fig, use_container_width=True, key="pc_12")

    # Full journal table
    st.markdown("**All Trades:**")
    display_cols = ["date","coin","dir","entry","exit","result","pnl_pct","pnl_usdt","signal","tf"]
    jdf_display  = jdf[display_cols].copy()
    jdf_display.columns = ["Date","Coin","Dir","Entry","Exit","Result","P&L%","P&L$","Signal","TF"]
    st.dataframe(jdf_display, use_container_width=True, hide_index=True)

    if st.button("🗑️ Clear Journal", key="btn_12"):
        st.session_state.journal = []
        st.rerun()
else:
    st.info("No trades logged yet. Use the form above to log your first trade!")

# ════════════════════════════════════════════════════════════════
# ── PAPER TRADING TRACKER
# ════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("📄 Paper Trading Tracker")
st.caption("Practice trading with fake money. Build confidence before using real money.")

if "paper_balance" not in st.session_state:
    st.session_state.paper_balance  = 1000.0
if "paper_trades" not in st.session_state:
    st.session_state.paper_trades   = []
if "paper_position" not in st.session_state:
    st.session_state.paper_position = None

current_price = float(lat["close"])
pb1, pb2, pb3 = st.columns(3)
pb1.metric("Paper Balance", f"${st.session_state.paper_balance:.2f}")
pb2.metric("Current Price", f"${current_price:,.2f}")
pb3.metric("Position", "OPEN 📈" if st.session_state.paper_position else "None")

if st.session_state.paper_position is None:
    # Open trade
    st.markdown("**Open Paper Trade:**")
    pc1, pc2, pc3 = st.columns(3)
    p_dir    = pc1.selectbox("Direction", ["LONG","SHORT"], key="p_dir")
    p_size   = pc2.number_input("Trade Size (USDT)", value=50.0, min_value=1.0, max_value=st.session_state.paper_balance, key="p_size")
    p_lev    = pc3.selectbox("Leverage", ["1x","2x","3x","5x","10x"], key="p_lev")
    p_sl     = st.number_input("Stop Loss Price", value=round(current_price * 0.98, 2), key="p_sl")
    p_tp     = st.number_input("Take Profit Price", value=round(current_price * 1.03, 2), key="p_tp")

    if st.button("📈 Open Paper Trade", key="btn_13"):
        lev_val = int(p_lev.replace("x",""))
        st.session_state.paper_position = {
            "coin":    coin, "dir": p_dir, "entry": current_price,
            "size":    p_size, "leverage": lev_val,
            "sl":      p_sl, "tp": p_tp,
            "time":    datetime.now().strftime("%H:%M"),
            "signal":  sig
        }
        st.success(f"Paper trade opened! {p_dir} {coin} at ${current_price:,.2f}")
        st.rerun()
else:
    pos = st.session_state.paper_position
    # Calculate live P&L
    if pos["dir"] == "LONG":
        pnl_pct = (current_price - pos["entry"]) / pos["entry"] * 100 * pos["leverage"]
    else:
        pnl_pct = (pos["entry"] - current_price) / pos["entry"] * 100 * pos["leverage"]
    pnl_usdt = pos["size"] * (pnl_pct / 100)

    pc1, pc2, pc3, pc4 = st.columns(4)
    pc1.metric("Direction",   pos["dir"])
    pc2.metric("Entry Price", f"${pos['entry']:,.2f}")
    pc3.metric("Live P&L",    f"${pnl_usdt:.2f}", f"{pnl_pct:.2f}%")
    pc4.metric("Leverage",    f"{pos['leverage']}x")

    col_sl, col_tp = st.columns(2)
    col_sl.metric("Stop Loss",   f"${pos['sl']:,.2f}")
    col_tp.metric("Take Profit", f"${pos['tp']:,.2f}")

    # Check if SL or TP hit
    sl_hit = (pos["dir"]=="LONG" and current_price <= pos["sl"]) or (pos["dir"]=="SHORT" and current_price >= pos["sl"])
    tp_hit = (pos["dir"]=="LONG" and current_price >= pos["tp"]) or (pos["dir"]=="SHORT" and current_price <= pos["tp"])

    if sl_hit:
        st.error("🔴 STOP LOSS HIT!")
    elif tp_hit:
        st.success("🟢 TAKE PROFIT HIT!")

    if st.button("❌ Close Paper Trade", key="btn_14"):
        new_balance = st.session_state.paper_balance + pnl_usdt
        result = "WIN" if pnl_usdt > 0 else "LOSS"
        st.session_state.paper_trades.append({
            "date":     datetime.now().strftime("%Y-%m-%d %H:%M"),
            "coin":     pos["coin"], "dir": pos["dir"],
            "entry":    pos["entry"], "exit": current_price,
            "pnl_pct":  round(pnl_pct, 2), "pnl_usdt": round(pnl_usdt, 2),
            "result":   result, "leverage": pos["leverage"],
            "signal":   pos["signal"]
        })
        st.session_state.paper_balance  = new_balance
        st.session_state.paper_position = None
        st.success(f"Trade closed! P&L: ${pnl_usdt:.2f} | New Balance: ${new_balance:.2f}")
        st.rerun()

if st.session_state.paper_trades:
    st.markdown("**Paper Trade History:**")
    ptdf = pd.DataFrame(st.session_state.paper_trades)
    ptdf["cumulative"] = ptdf["pnl_usdt"].cumsum() + 1000
    pt_wins = len(ptdf[ptdf["result"]=="WIN"])
    pt_wr   = pt_wins / len(ptdf) * 100
    pp1, pp2, pp3 = st.columns(3)
    pp1.metric("Paper Win Rate", f"{pt_wr:.1f}%")
    pp2.metric("Total Trades",   len(ptdf))
    pp3.metric("Final Balance",  f"${st.session_state.paper_balance:.2f}",
               f"${st.session_state.paper_balance-1000:.2f}")
    st.dataframe(ptdf[["date","coin","dir","entry","exit","pnl_pct","pnl_usdt","result","leverage"]],
                 use_container_width=True, hide_index=True)
    if st.button("🔄 Reset Paper Account", key="btn_15"):
        st.session_state.paper_balance  = 1000.0
        st.session_state.paper_trades   = []
        st.session_state.paper_position = None
        st.rerun()

# ════════════════════════════════════════════════════════════════
# ── BACKTESTING
# ════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("🔬 Simple Backtesting")
st.caption("Test how the BOS and CHoCH signals performed on past data")

bt_col1, bt_col2 = st.columns(2)
bt_signal = bt_col1.selectbox("Signal To Test", ["BOS Bullish","CHoCH Bullish","Buy Liquidity Sweep","Volume Spike + BOS"], key="auto_ced1ac")
bt_hold   = bt_col2.selectbox("Hold For (candles)", [1, 2, 3, 5, 10], key="auto_6433ad")

if st.button("▶️ Run Backtest", key="btn_16"):
    with st.spinner("Running backtest on historical data..."):
        bt_results = []
        for i in range(10, len(df) - bt_hold):
            row     = df.iloc[i]
            future  = df.iloc[i + bt_hold]
            triggered = False

            if bt_signal == "BOS Bullish"            and row["bos_bull"]:   triggered = True
            elif bt_signal == "CHoCH Bullish"         and row["choch_bull"]: triggered = True
            elif bt_signal == "Buy Liquidity Sweep"   and row["buy_liq"]:   triggered = True
            elif bt_signal == "Volume Spike + BOS"    and row["bos_bull"] and row["vol_spike"]: triggered = True

            if triggered:
                entry  = row["close"]
                exit_p = future["close"]
                pnl    = (exit_p - entry) / entry * 100
                bt_results.append({
                    "time":   row["time"].strftime("%m/%d %H:%M"),
                    "entry":  round(entry, 2),
                    "exit":   round(exit_p, 2),
                    "pnl%":   round(pnl, 2),
                    "result": "WIN" if pnl > 0 else "LOSS"
                })

        if bt_results:
            btdf    = pd.DataFrame(bt_results)
            bt_wins = len(btdf[btdf["result"]=="WIN"])
            bt_wr   = bt_wins / len(btdf) * 100
            bt_avg  = btdf["pnl%"].mean()
            bt_tot  = btdf["pnl%"].sum()

            bc1, bc2, bc3, bc4 = st.columns(4)
            bc1.metric("Signals Found",  len(btdf))
            bc2.metric("Win Rate",       f"{bt_wr:.1f}%")
            bc3.metric("Avg P&L",        f"{bt_avg:.2f}%")
            bc4.metric("Total Return",   f"{bt_tot:.2f}%",
                       "✅ Profitable" if bt_tot > 0 else "❌ Losing")

            # P&L distribution
            bt_fig = go.Figure()
            bt_fig.add_trace(go.Bar(
                x=btdf["time"], y=btdf["pnl%"],
                marker_color=["#00ff88" if p > 0 else "#ff4444" for p in btdf["pnl%"]],
                name="P&L %"
            ))
            bt_fig.add_hline(y=0, line_color="white", line_width=1, opacity=0.3)
            bt_fig.update_layout(height=250, template="plotly_dark",
                paper_bgcolor="#050508", plot_bgcolor="#050508",
                title=f"Backtest Results — {bt_signal} | Hold {bt_hold} candles",
                margin=dict(t=30, b=20))
            st.plotly_chart(bt_fig, use_container_width=True, key="pc_13")
            st.dataframe(btdf, use_container_width=True, hide_index=True)

            if bt_wr >= 55:
                st.success(f"✅ Signal '{bt_signal}' has a {bt_wr:.1f}% win rate on {timeframe} — worth using!")
            elif bt_wr >= 45:
                st.warning(f"⚠️ Signal '{bt_signal}' has {bt_wr:.1f}% win rate — acceptable with good R:R")
            else:
                st.error(f"❌ Signal '{bt_signal}' has only {bt_wr:.1f}% win rate on {timeframe} — use with caution")
        else:
            st.warning("No signals found in this data range. Try a different signal or increase candles.")


# ════════════════════════════════════════════════════════════════
# ── MARKET CORRELATIONS
# ════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("🌍 Market Correlations & Sentiment")
st.caption("Key external data that moves crypto markets — check these every day")

# ── FEAR & GREED
@st.cache_data(ttl=3600)
def get_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=30", timeout=10)
        data = r.json()
        return data.get("data", [])
    except:
        return []

# ── FUNDING RATES
@st.cache_data(ttl=300)
def get_funding_rates():
    try:
        exchange = ccxt.binance()
        coins = ["BTC/USDT:USDT","ETH/USDT:USDT","SOL/USDT:USDT","ADA/USDT:USDT"]
        results = []
        for c in coins:
            try:
                info = exchange.fetch_funding_rate(c)
                results.append({
                    "coin": c.split("/")[0],
                    "rate": float(info.get("fundingRate", 0)) * 100,
                    "next": str(info.get("fundingDatetime",""))[:16]
                })
            except:
                continue
        return results
    except:
        return []

# ── OPEN INTEREST
@st.cache_data(ttl=300)
def get_open_interest():
    results = []
    coins = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","ADAUSDT"]
    for c in coins:
        try:
            url = f"https://fapi.binance.com/fapi/v1/openInterest?symbol={c}"
            r = requests.get(url, timeout=10)
            data = r.json()
            oi_qty = float(data.get("openInterest", 0))
            # Get current price to calculate USD value
            url2 = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={c}"
            r2 = requests.get(url2, timeout=10)
            price = float(r2.json().get("price", 0))
            oi_usdt = oi_qty * price
            results.append({
                "coin": c.replace("USDT",""),
                "oi": oi_qty,
                "oi_usdt": oi_usdt
            })
        except:
            continue
    return results

# ── BTC DOMINANCE
@st.cache_data(ttl=3600)
def get_btc_dominance():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=10)
        data = r.json().get("data", {})
        dom  = data.get("market_cap_percentage", {})
        return {
            "btc":  round(dom.get("btc", 0), 2),
            "eth":  round(dom.get("eth", 0), 2),
            "others": round(100 - dom.get("btc", 0) - dom.get("eth", 0), 2),
            "total_mcap": data.get("total_market_cap", {}).get("usd", 0),
            "total_volume": data.get("total_volume", {}).get("usd", 0),
            "mcap_change": data.get("market_cap_change_percentage_24h_usd", 0)
        }
    except:
        return {}

with st.spinner("Loading market data..."):
    fg_data   = get_fear_greed()
    fr_data   = get_funding_rates()
    oi_data   = get_open_interest()
    dom_data  = get_btc_dominance()

# ── ROW 1: FEAR & GREED + BTC DOMINANCE
fgc1, fgc2 = st.columns(2)

with fgc1:
    st.markdown("### 😱 Fear & Greed Index")
    if fg_data:
        current_fg    = fg_data[0]
        fg_value      = int(current_fg["value"])
        fg_class      = current_fg["value_classification"]
        fg_date       = current_fg["timestamp"]

        # Color based on value
        if fg_value <= 25:   fg_color, fg_emoji = "#ff4444", "😱 Extreme Fear"
        elif fg_value <= 45: fg_color, fg_emoji = "#ff8800", "😰 Fear"
        elif fg_value <= 55: fg_color, fg_emoji = "#FFD700", "😐 Neutral"
        elif fg_value <= 75: fg_color, fg_emoji = "#00cc66", "😊 Greed"
        else:                fg_color, fg_emoji = "#00ff88", "🤑 Extreme Greed"

        st.markdown(f"""
        <div style="background:#0d0d1a;border:1px solid {fg_color}44;border-radius:12px;padding:20px;text-align:center;">
        <div style="font-size:60px;font-weight:900;color:{fg_color};">{fg_value}</div>
        <div style="font-size:20px;color:{fg_color};font-weight:700;">{fg_emoji}</div>
        <div style="color:#888;font-size:13px;margin-top:8px;">Updated daily</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(" ")

        # Trading interpretation
        if fg_value <= 25:
            st.success("💡 Extreme Fear = GOOD TIME TO BUY — everyone is scared, smart money accumulates")
        elif fg_value <= 45:
            st.info("💡 Fear = Possible buy opportunity — market is cautious")
        elif fg_value <= 55:
            st.info("💡 Neutral — no strong signal from sentiment")
        elif fg_value <= 75:
            st.warning("💡 Greed = Be careful — market getting overheated")
        else:
            st.error("💡 Extreme Greed = CONSIDER SELLING — everyone is euphoric, top may be near")

        # 30 day chart
        if len(fg_data) >= 7:
            fg_vals  = [int(d["value"]) for d in reversed(fg_data[:30])]
            fg_dates = [datetime.fromtimestamp(int(d["timestamp"])).strftime("%m/%d") for d in reversed(fg_data[:30])]
            fg_colors = ["#ff4444" if v <= 25 else "#ff8800" if v <= 45 else "#FFD700" if v <= 55 else "#00cc66" if v <= 75 else "#00ff88" for v in fg_vals]
            fg_fig = go.Figure()
            fg_fig.add_trace(go.Bar(x=fg_dates, y=fg_vals, marker_color=fg_colors, name="Fear & Greed"))
            fg_fig.add_hline(y=25, line_dash="dash", line_color="red",   opacity=0.5, annotation_text="Extreme Fear")
            fg_fig.add_hline(y=75, line_dash="dash", line_color="green", opacity=0.5, annotation_text="Extreme Greed")
            fg_fig.add_hline(y=50, line_dash="dot",  line_color="white", opacity=0.2)
            fg_fig.update_layout(height=200, template="plotly_dark",
                paper_bgcolor="#050508", plot_bgcolor="#050508",
                title="30 Day Fear & Greed History",
                margin=dict(t=30, b=20), showlegend=False)
            st.plotly_chart(fg_fig, use_container_width=True, key="pc_14")
    else:
        st.warning("Could not load Fear & Greed data")

with fgc2:
    st.markdown("### 👑 BTC Dominance")
    if dom_data:
        btc_dom = dom_data.get("btc", 0)
        eth_dom = dom_data.get("eth", 0)
        oth_dom = dom_data.get("others", 0)
        total_mcap = dom_data.get("total_mcap", 0)
        mcap_chg   = dom_data.get("mcap_change", 0)

        dc1, dc2, dc3 = st.columns(3)
        dc1.metric("BTC Dom",   f"{btc_dom}%",  "↑ Alts bleeding" if btc_dom > 50 else "↓ Alt season")
        dc2.metric("ETH Dom",   f"{eth_dom}%")
        dc3.metric("Total MCap",f"${total_mcap/1e12:.2f}T", f"{mcap_chg:.2f}%")

        # Dominance interpretation
        if btc_dom > 55:
            st.warning(f"⚠️ BTC Dominance HIGH at {btc_dom}% — money in BTC, altcoins struggling")
        elif btc_dom > 48:
            st.info(f"ℹ️ BTC Dominance NEUTRAL at {btc_dom}% — balanced market")
        else:
            st.success(f"✅ BTC Dominance LOW at {btc_dom}% — altcoin season possible!")

        # Pie chart
        dom_fig = go.Figure(go.Pie(
            labels=["BTC", "ETH", "Others"],
            values=[btc_dom, eth_dom, oth_dom],
            marker_colors=["#F7931A", "#627EEA", "#888888"],
            hole=0.4,
            textinfo="label+percent"
        ))
        dom_fig.update_layout(
            height=250, template="plotly_dark",
            paper_bgcolor="#050508",
            title="Market Cap Distribution",
            margin=dict(t=40, b=20),
            showlegend=False
        )
        st.plotly_chart(dom_fig, use_container_width=True, key="pc_15")

        # Alt season signal
        st.markdown(f"""
        <div style="background:#0d0d1a;border:1px solid #F7931A44;border-radius:8px;padding:12px;">
        <b style="color:#F7931A;">Altcoin Season Signal:</b><br>
        {'🟢 BTC dom falling = Alt season starting — rotate into SOL, ETH, ADA' if btc_dom < 48 else
         '🔴 BTC dom rising = Stay in BTC or stable — altcoins losing value' if btc_dom > 52 else
         '⚪ Neutral — watch BTC.D direction on TradingView'}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("Could not load dominance data")

st.markdown("---")

# ── ROW 2: FUNDING RATES + OPEN INTEREST
fc1, fc2 = st.columns(2)

with fc1:
    st.markdown("### 💰 Funding Rates")
    st.caption("Positive = longs paying shorts. Negative = shorts paying longs.")
    if fr_data:
        for r in fr_data:
            rate = r["rate"]
            if rate > 0.05:    rc, emoji, msg = "#ff4444", "🔴", "Very high — longs overloaded, DROP likely"
            elif rate > 0.01:  rc, emoji, msg = "#ff8800", "🟠", "High — market leaning long, be careful"
            elif rate > 0:     rc, emoji, msg = "#00ff88", "🟢", "Healthy — slight long bias, normal"
            elif rate > -0.01: rc, emoji, msg = "#00bfff", "🔵", "Slightly negative — slight short bias"
            else:              rc, emoji, msg = "#bf00ff", "🟣", "Very negative — shorts overloaded, PUMP likely"

            st.markdown(f"""
            <div style="background:#0d0d1a;border:1px solid {rc}44;border-left:3px solid {rc};
            border-radius:8px;padding:10px;margin:4px 0;">
            <b style="color:{rc};">{emoji} {r['coin']}</b>
            <span style="float:right;color:{rc};font-weight:700;">{rate:.4f}%</span><br>
            <span style="color:#888;font-size:12px;">{msg}</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown(" ")
        st.info("💡 Extreme positive funding = market too bullish = price may drop soon\n\nExtreme negative funding = market too bearish = price may pump soon")
    else:
        st.warning("Could not load funding rates")

with fc2:
    st.markdown("### 📊 Open Interest")
    st.caption("Total value of open futures contracts — shows market conviction")
    if oi_data:
        for r in oi_data:
            oi_val = r["oi_usdt"]
            st.markdown(f"""
            <div style="background:#0d0d1a;border:1px solid #00bfff33;border-left:3px solid #00bfff;
            border-radius:8px;padding:10px;margin:4px 0;">
            <b style="color:#00bfff;">{r['coin']}</b>
            <span style="float:right;color:#FFD700;font-weight:700;">${oi_val/1e9:.2f}B</span><br>
            <span style="color:#888;font-size:12px;">{r['oi']:,.0f} contracts open</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown(" ")
        st.markdown("""
        <div style="background:#0d0d1a;border:1px solid #FFD70033;border-radius:8px;padding:12px;">
        <b style="color:#FFD700;">How To Read Open Interest:</b><br>
        <span style="color:#00ff88;">Price UP + OI UP = Strong bull trend ✅</span><br>
        <span style="color:#ff8800;">Price UP + OI DOWN = Weak move, reversal possible ⚠️</span><br>
        <span style="color:#ff4444;">Price DOWN + OI UP = Strong bear trend 🔴</span><br>
        <span style="color:#00bfff;">Price DOWN + OI DOWN = Shorts closing, bounce coming ✅</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("Could not load open interest data")

st.markdown("---")

# ── ROW 3: COMBINED MARKET SIGNAL
st.markdown("### 🎯 Combined Market Signal")
st.caption("All correlations combined into one overall market reading")

if fg_data and dom_data:
    fg_val  = int(fg_data[0]["value"])
    btc_dom = dom_data.get("btc", 50)

    bull_points = 0
    bear_points = 0
    signals     = []

    # Fear & Greed
    if fg_val <= 30:
        bull_points += 2
        signals.append("😱 Extreme Fear — historically good buy zone ✅")
    elif fg_val >= 75:
        bear_points += 2
        signals.append("🤑 Extreme Greed — historically good sell zone ⚠️")

    # BTC Dominance
    if btc_dom < 45:
        bull_points += 1
        signals.append("👑 Low BTC dominance — altcoin season possible ✅")
    elif btc_dom > 55:
        bear_points += 1
        signals.append("👑 High BTC dominance — alts struggling ⚠️")

    # Funding rates
    if fr_data:
        avg_rate = sum(r["rate"] for r in fr_data) / len(fr_data)
        if avg_rate < -0.01:
            bull_points += 2
            signals.append("💰 Negative funding — shorts overloaded, pump likely ✅")
        elif avg_rate > 0.05:
            bear_points += 2
            signals.append("💰 Very high funding — longs overloaded, drop likely ⚠️")

    # Dashboard signal
    if sc >= 4:
        bull_points += 2
        signals.append(f"📊 Dashboard signal BULLISH score {sc}/30 ✅")
    elif sc <= -4:
        bear_points += 2
        signals.append(f"📊 Dashboard signal BEARISH score {sc}/30 ⚠️")

    total_pts = bull_points + bear_points
    if total_pts > 0:
        bull_pct = bull_points / total_pts * 100
    else:
        bull_pct = 50

    if bull_points > bear_points + 1:
        overall = "BULLISH CONFLUENCE 🟢"
        oc = "#00ff88"
    elif bear_points > bull_points + 1:
        overall = "BEARISH CONFLUENCE 🔴"
        oc = "#ff4444"
    else:
        overall = "MIXED — WAIT FOR CLARITY ⚪"
        oc = "#888888"

    st.markdown(f"""
    <div style="background:#0d0d1a;border:2px solid {oc};border-radius:12px;padding:20px;text-align:center;margin:10px 0;">
    <div style="font-size:24px;font-weight:700;color:{oc};">{overall}</div>
    <div style="color:#aaa;font-size:14px;margin-top:8px;">
    Bullish factors: {bull_points} | Bearish factors: {bear_points}
    </div>
    </div>
    """, unsafe_allow_html=True)

    # Progress bar
    st.markdown(f"**Market Bias: {bull_pct:.0f}% Bullish**")
    st.progress(int(bull_pct) / 100)

    # All signals
    st.markdown("**All Confluence Factors:**")
    for s in signals:
        if "✅" in s: st.success(s)
        elif "⚠️" in s: st.error(s)
        else: st.info(s)

st.markdown("---")

# ── USEFUL LINKS
st.subheader("🔗 Useful Daily Resources")
lc1, lc2, lc3, lc4 = st.columns(4)
with lc1:
    st.markdown("""
    **📊 Market Data**
    - [Fear & Greed](https://alternative.me/crypto/fear-and-greed-index/)
    - [CoinGlass](https://coinglass.com)
    - [TradingView](https://tradingview.com)
    - [CoinMarketCap](https://coinmarketcap.com)
    """)
with lc2:
    st.markdown("""
    **📰 News**
    - [CoinDesk](https://coindesk.com)
    - [CoinTelegraph](https://cointelegraph.com)
    - [CryptoPanic](https://cryptopanic.com)
    - [The Block](https://theblock.co)
    """)
with lc3:
    st.markdown("""
    **🐋 Whale Tracking**
    - [Whale Alert](https://whale-alert.io)
    - [Glassnode](https://glassnode.com)
    - [CryptoQuant](https://cryptoquant.com)
    - [Santiment](https://santiment.net)
    """)
with lc4:
    st.markdown("""
    **📈 Futures Data**
    - [Coinglass OI](https://coinglass.com/OpenInterest)
    - [Coinglass FR](https://coinglass.com/FundingRate)
    - [Bybt](https://bybt.com)
    - [Binance Futures](https://binance.com/futures)
    """)

st.markdown("---")
st.subheader("📖 Order Book Analysis")
st.caption("Live order book — see whale orders, buy/sell walls, and market pressure")

ob_symbol = coin.replace("/USDT","") + "USDT"

@st.cache_data(ttl=15)
def get_ob(symbol):
    try:
        url = f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit=100"
        r = requests.get(url, timeout=10)
        d = r.json()
        return {"bids":[[float(p),float(q)] for p,q in d.get("bids",[])],
                "asks":[[float(p),float(q)] for p,q in d.get("asks",[])]}
    except: return {}

@st.cache_data(ttl=15)
def get_trades(symbol):
    try:
        url = f"https://api.binance.com/api/v3/trades?symbol={symbol}&limit=500"
        r = requests.get(url, timeout=10)
        rows = [{"price":float(t["price"]),"qty":float(t["qty"]),
                 "value":float(t["price"])*float(t["qty"]),
                 "is_buyer":not t["isBuyerMaker"],
                 "time":pd.to_datetime(t["time"],unit="ms")} for t in r.json()]
        return pd.DataFrame(rows)
    except: return pd.DataFrame()

with st.spinner("Loading order book..."):
    ob  = get_ob(ob_symbol)
    tdf = get_trades(ob_symbol)

if ob and "bids" in ob and "asks" in ob and len(ob["bids"]) > 0 and len(ob["asks"]) > 0:
    bids = ob["bids"][:50]; asks = ob["asks"][:50]
    if not bids or not asks:
        st.warning("Order book empty — Binance may restrict this region")
        bids = []; asks = []
    else:
        bp = [b[0] for b in bids]; bq = [b[1] for b in bids]
        ap = [a[0] for a in asks]; aq = [a[1] for a in asks]
        mid = (bp[0]+ap[0])/2 if bp and ap else 0
    tbv = sum(p*q for p,q in bids); tav = sum(p*q for p,q in asks)
    tv  = tbv+tav
    bpct = tbv/tv*100 if tv>0 else 50; apct = tav/tv*100 if tv>0 else 50
    imb  = bpct - apct

    m1,m2,m3,m4,m5 = st.columns(5)
    m1.metric("Mid Price", f"${mid:,.2f}")
    m2.metric("Bid Vol",   f"${tbv/1e6:.2f}M", f"{bpct:.1f}%")
    m3.metric("Ask Vol",   f"${tav/1e6:.2f}M", f"{apct:.1f}%")
    m4.metric("Spread",    f"${ap[0]-bp[0]:.2f}")
    m5.metric("Imbalance", f"{imb:+.1f}%", "Buy pres" if imb>5 else "Sell pres" if imb<-5 else "Neutral")

    if imb>10:    st.success(f"Strong buy pressure! Bids dominating {imb:.1f}%")
    elif imb>5:   st.info(f"Moderate buy pressure {imb:.1f}%")
    elif imb<-10: st.error(f"Strong sell pressure! Asks dominating {abs(imb):.1f}%")
    elif imb<-5:  st.warning(f"Moderate sell pressure {abs(imb):.1f}%")

    st.markdown("---")
    st.markdown("### 📊 Order Book Depth Chart")
    cb=[]; r2=0
    for q in bq: r2+=q; cb.append(r2)
    ca=[]; r2=0
    for q in aq: r2+=q; ca.append(r2)
    df2=go.Figure()
    df2.add_trace(go.Scatter(x=bp,y=cb,name="Bids",fill="tozeroy",line=dict(color="#00ff88",width=2),fillcolor="rgba(0,255,136,0.15)"))
    df2.add_trace(go.Scatter(x=ap,y=ca,name="Asks",fill="tozeroy",line=dict(color="#ff4444",width=2),fillcolor="rgba(255,68,68,0.15)"))
    df2.add_vline(x=mid,line_dash="dash",line_color="white",line_width=2,annotation_text=f"${mid:,.0f}",annotation_font_color="white")
    df2.update_layout(height=320,template="plotly_dark",paper_bgcolor="#050508",plot_bgcolor="#050508",
        title="Cumulative Depth — Green=Buys Red=Sells",xaxis_title="Price",yaxis_title="Cum Qty",margin=dict(t=40,b=30,l=10,r=10))
    df2.update_xaxes(gridcolor="#0d0d18"); df2.update_yaxes(gridcolor="#0d0d18")
    st.plotly_chart(df2,use_container_width=True, key="pc_16")

    st.markdown("---")
    st.markdown("### 🐋 Whale Order Walls")
    bu = sorted([(p,q,p*q) for p,q in bids],key=lambda x:x[2],reverse=True)[:8]
    au = sorted([(p,q,p*q) for p,q in asks],key=lambda x:x[2],reverse=True)[:8]
    wc1,wc2 = st.columns(2)
    with wc1:
        st.markdown("**Buy Walls — price may bounce UP here**")
        for i,(p,q,u) in enumerate(bu):
            bar=int(u/bu[0][2]*100); em="🐋🐋🐋" if i==0 else "🐋🐋" if i<3 else "🐋"
            dist=(mid-p)/mid*100
            st.markdown(f"**${p:,.2f}** {em} — ${u/1e3:.1f}K | -{dist:.2f}% below price")
    with wc2:
        st.markdown("**Sell Walls — price may reverse DOWN here**")
        for i,(p,q,u) in enumerate(au):
            bar=int(u/au[0][2]*100); em="🐋🐋🐋" if i==0 else "🐋🐋" if i<3 else "🐋"
            dist=(p-mid)/mid*100
            st.markdown(f"**${p:,.2f}** {em} — ${u/1e3:.1f}K | +{dist:.2f}% above price")

    if not tdf.empty:
        st.markdown("---")
        st.markdown("### 💹 Cumulative Delta")
        tdf["delta"]     = tdf.apply(lambda x: x["value"] if x["is_buyer"] else -x["value"],axis=1)
        tdf["cum_delta"] = tdf["delta"].cumsum()
        bvol = tdf[tdf["is_buyer"]]["value"].sum()
        svol = tdf[~tdf["is_buyer"]]["value"].sum()
        tv2  = bvol+svol; bpct2 = bvol/tv2*100 if tv2>0 else 50

        dc1,dc2,dc3 = st.columns(3)
        dc1.metric("Buy Vol",  f"${bvol/1e3:.1f}K", f"{bpct2:.1f}%")
        dc2.metric("Sell Vol", f"${svol/1e3:.1f}K", f"{100-bpct2:.1f}%")
        dc3.metric("Delta",    f"${(bvol-svol)/1e3:+.1f}K","Buyers winning" if bvol>svol else "Sellers winning")

        dfig = make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[0.5,0.5],vertical_spacing=0.05)
        dfig.add_trace(go.Scatter(x=tdf["time"],y=tdf["price"],name="Price",line=dict(color="#aaa",width=1)),row=1,col=1)
        dfig.add_trace(go.Scatter(x=tdf["time"],y=tdf["cum_delta"],name="Cum Delta",fill="tozeroy",
            line=dict(color="#00bfff",width=1.5),fillcolor="rgba(0,191,255,0.08)"),row=2,col=1)
        dfig.add_hline(y=0,line_dash="dash",line_color="white",opacity=0.3,row=2,col=1)
        dfig.update_layout(height=300,template="plotly_dark",paper_bgcolor="#050508",plot_bgcolor="#050508",
            title="Price + Cumulative Delta — Rising = more buying",margin=dict(t=40,b=20,l=10,r=10))
        dfig.update_xaxes(gridcolor="#0d0d18"); dfig.update_yaxes(gridcolor="#0d0d18")
        st.plotly_chart(dfig,use_container_width=True, key="pc_17")

        st.markdown("**Large Trades >$10K:**")
        lg = tdf[tdf["value"]>=10000].tail(15)
        if not lg.empty:
            for _,t in lg.iterrows():
                dr = "BUY" if t["is_buyer"] else "SELL"
                cl = "#00ff88" if t["is_buyer"] else "#ff4444"
                em = "🐋🐋🐋" if t["value"]>100000 else "🐋🐋" if t["value"]>50000 else "🐋"
                st.markdown(f"<span style='color:{cl};font-weight:700;'>{dr}</span> ${t['value']/1e3:.1f}K @ ${t['price']:,.2f} — {t['time'].strftime('%H:%M:%S')} {em}",unsafe_allow_html=True)
            if alerts_on and tg_token and tg_chat_id:
                for _,t in tdf[tdf["value"]>=100000].tail(2).iterrows():
                    send_tg(tg_token,tg_chat_id,f"🐋 WHALE TRADE\n{coin} {'BUY' if t['is_buyer'] else 'SELL'}\n${t['value']/1e3:.0f}K @ ${t['price']:,.2f}")
        else:
            st.info("No large trades in last 500 trades")

    st.markdown("---")
    st.markdown("### 🎯 Order Book Signal")
    obs=0; obr=[]
    if imb>10:    obs+=2; obr.append("Strong bid dominance ✅")
    elif imb>5:   obs+=1; obr.append("Moderate bid dominance ✅")
    elif imb<-10: obs-=2; obr.append("Strong ask dominance ⚠️")
    elif imb<-5:  obs-=1; obr.append("Moderate ask dominance ⚠️")
    if bu and abs(mid-bu[0][0])/mid<0.005: obs+=2; obr.append(f"Near biggest buy wall ${bu[0][0]:,.0f} ✅")
    if au and abs(mid-au[0][0])/mid<0.005: obs-=2; obr.append(f"Near biggest sell wall ${au[0][0]:,.0f} ⚠️")
    if not tdf.empty:
        if bvol>svol*1.3: obs+=1; obr.append("Buyers winning recent trades ✅")
        elif svol>bvol*1.3: obs-=1; obr.append("Sellers winning recent trades ⚠️")
    if obs>=2:   oss,osc="ORDER BOOK BULLISH 🟢","bull-signal"
    elif obs<=-2: oss,osc="ORDER BOOK BEARISH 🔴","bear-signal"
    else:         oss,osc="ORDER BOOK NEUTRAL ⚪","neutral-signal"
    st.markdown(f'<div class="signal-master {osc}">{oss} | Score: {obs}</div>',unsafe_allow_html=True)
    oc1,oc2=st.columns(2)
    with oc1:
        st.markdown("**Bullish:**")
        for r in obr:
            if "✅" in r: st.success(r)
    with oc2:
        st.markdown("**Bearish:**")
        for r in obr:
            if "⚠️" in r: st.error(r)
    if bu and au:
        st.info(f"Biggest Buy Wall: ${bu[0][0]:,.2f} (${bu[0][2]/1e3:.0f}K) | Biggest Sell Wall: ${au[0][0]:,.2f} (${au[0][2]/1e3:.0f}K)")
else:
    st.warning("Could not load order book. Check internet connection.")

# ════════════════════════════════════════════════════════════════
# LIQUIDATION LEVEL ESTIMATOR
# ════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("💥 Liquidation Level Estimator")
st.caption("Estimates where leveraged traders will get liquidated — price is magnetic to these levels (similar to CoinGlass heatmap)")

@st.cache_data(ttl=60)
def get_liquidation_data(symbol):
    try:
        # Get funding rate history
        url_fr = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}&limit=100"
        r_fr = requests.get(url_fr, timeout=10)
        fr_data = r_fr.json()

        # Get open interest history
        url_oi = f"https://fapi.binance.com/futures/data/openInterestHist?symbol={symbol}&period=1h&limit=48"
        r_oi = requests.get(url_oi, timeout=10)
        oi_data = r_oi.json()

        # Get mark price klines for price range
        url_mk = f"https://fapi.binance.com/fapi/v1/markPriceKlines?symbol={symbol}&interval=1h&limit=48"
        r_mk = requests.get(url_mk, timeout=10)
        mk_data = r_mk.json()

        return fr_data, oi_data, mk_data
    except Exception as e:
        return [], [], []

@st.cache_data(ttl=30)
def get_long_short_ratio(symbol):
    try:
        url = f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=1h&limit=24"
        r = requests.get(url, timeout=10)
        return r.json()
    except:
        return []

@st.cache_data(ttl=30)
def get_top_trader_ratio(symbol):
    try:
        url = f"https://fapi.binance.com/futures/data/topLongShortPositionRatio?symbol={symbol}&period=1h&limit=24"
        r = requests.get(url, timeout=10)
        return r.json()
    except:
        return []

futures_symbol = coin.replace("/USDT","") + "USDT"

with st.spinner("Loading liquidation data..."):
    fr_data, oi_data, mk_data = get_liquidation_data(futures_symbol)
    ls_ratio  = get_long_short_ratio(futures_symbol)
    top_ratio = get_top_trader_ratio(futures_symbol)

# Current price
curr_price = float(lat["close"])

# ── LONG SHORT RATIO
st.markdown("### ⚖️ Long/Short Ratio")
st.caption("More longs = more liquidations below. More shorts = more liquidations above.")

if ls_ratio and isinstance(ls_ratio, list) and len(ls_ratio) > 0 and isinstance(ls_ratio[0], dict):
    try:
        ls_df = pd.DataFrame(ls_ratio)
        ls_df["timestamp"] = pd.to_datetime(ls_df["timestamp"].astype(float), unit="ms")
        ls_df["longShortRatio"] = ls_df["longShortRatio"].astype(float)
        ls_df["longAccount"]    = ls_df["longAccount"].astype(float)
        ls_df["shortAccount"]   = ls_df["shortAccount"].astype(float)
    except Exception as e:
        st.warning(f"Long/Short ratio data unavailable from this region: {e}")
        ls_ratio = []

    latest_ls = ls_df.iloc[-1]
    lsr = float(latest_ls["longShortRatio"])
    long_pct  = float(latest_ls["longAccount"]) * 100
    short_pct = float(latest_ls["shortAccount"]) * 100

    lc1,lc2,lc3 = st.columns(3)
    lc1.metric("Long/Short Ratio", f"{lsr:.2f}",
               "More longs" if lsr > 1 else "More shorts")
    lc2.metric("Long Accounts",  f"{long_pct:.1f}%")
    lc3.metric("Short Accounts", f"{short_pct:.1f}%")

    if lsr > 1.5:
        st.warning(f"⚠️ {long_pct:.1f}% of traders are LONG — lots of liquidations BELOW current price. Smart money may push DOWN to grab them first!")
    elif lsr < 0.7:
        st.success(f"✅ {short_pct:.1f}% of traders are SHORT — lots of liquidations ABOVE current price. Smart money may push UP to grab them first!")
    else:
        st.info(f"⚪ Balanced market — {long_pct:.1f}% long vs {short_pct:.1f}% short")

    # L/S ratio chart
    ls_fig = go.Figure()
    ls_fig.add_trace(go.Scatter(
        x=ls_df["timestamp"], y=ls_df["longAccount"]*100,
        name="Longs %", fill="tozeroy",
        line=dict(color="#00ff88",width=2),
        fillcolor="rgba(0,255,136,0.15)"
    ))
    ls_fig.add_trace(go.Scatter(
        x=ls_df["timestamp"], y=ls_df["shortAccount"]*100,
        name="Shorts %", fill="tozeroy",
        line=dict(color="#ff4444",width=2),
        fillcolor="rgba(255,68,68,0.15)"
    ))
    ls_fig.add_hline(y=50, line_dash="dash", line_color="white", opacity=0.3)
    ls_fig.update_layout(
        height=250, template="plotly_dark",
        paper_bgcolor="#050508", plot_bgcolor="#050508",
        title="Long vs Short Account Ratio — 24H History",
        yaxis_title="% of Accounts",
        legend=dict(orientation="h"),
        margin=dict(t=40,b=20,l=10,r=10)
    )
    ls_fig.update_xaxes(gridcolor="#0d0d18")
    ls_fig.update_yaxes(gridcolor="#0d0d18")
    st.plotly_chart(ls_fig, use_container_width=True, key="pc_18")

# ── TOP TRADER RATIO
if top_ratio and isinstance(top_ratio, list) and len(top_ratio) > 0 and isinstance(top_ratio[0], dict):
    st.markdown("### 🏆 Top Trader Long/Short Ratio")
    st.caption("What are the BIG traders doing? This matters more than retail.")
    try:
        tt_df = pd.DataFrame(top_ratio)
        tt_df["timestamp"]       = pd.to_datetime(tt_df["timestamp"].astype(float), unit="ms")
        tt_df["longShortRatio"]  = tt_df["longShortRatio"].astype(float)
        tt_df["longAccount"]     = tt_df["longAccount"].astype(float)
        tt_df["shortAccount"]    = tt_df["shortAccount"].astype(float)
    except:
        tt_df = pd.DataFrame()

    latest_tt = tt_df.iloc[-1]
    tt_lsr    = float(latest_tt["longShortRatio"])
    tt_long   = float(latest_tt["longAccount"]) * 100
    tt_short  = float(latest_tt["shortAccount"]) * 100

    tc1,tc2,tc3 = st.columns(3)
    tc1.metric("Top Trader L/S", f"{tt_lsr:.2f}",
               "Whales buying" if tt_lsr > 1 else "Whales selling")
    tc2.metric("Top Trader Longs",  f"{tt_long:.1f}%")
    tc3.metric("Top Trader Shorts", f"{tt_short:.1f}%")

    if tt_lsr > 1.3:
        st.success(f"✅ Top traders {tt_long:.1f}% LONG — whales are bullish! Follow the smart money UP")
    elif tt_lsr < 0.8:
        st.error(f"🔴 Top traders {tt_short:.1f}% SHORT — whales are bearish! Follow the smart money DOWN")
    else:
        st.info("⚪ Top traders balanced — no clear whale direction")

    tt_fig = go.Figure()
    tt_fig.add_trace(go.Scatter(
        x=tt_df["timestamp"], y=tt_df["longAccount"]*100,
        name="Top Long %", line=dict(color="#FFD700",width=2)
    ))
    tt_fig.add_trace(go.Scatter(
        x=tt_df["timestamp"], y=tt_df["shortAccount"]*100,
        name="Top Short %", line=dict(color="#ff8800",width=2)
    ))
    tt_fig.add_hline(y=50, line_dash="dash", line_color="white", opacity=0.3)
    tt_fig.update_layout(
        height=220, template="plotly_dark",
        paper_bgcolor="#050508", plot_bgcolor="#050508",
        title="Top Trader Positions — 24H",
        legend=dict(orientation="h"),
        margin=dict(t=40,b=20,l=10,r=10)
    )
    tt_fig.update_xaxes(gridcolor="#0d0d18")
    tt_fig.update_yaxes(gridcolor="#0d0d18")
    st.plotly_chart(tt_fig, use_container_width=True, key="pc_19")

st.markdown("---")

# ── LIQUIDATION LEVEL ESTIMATOR
st.markdown("### 💥 Estimated Liquidation Clusters")
st.caption("Based on price range + leverage levels. Yellow = biggest cluster = price magnet!")

# Build liquidation heatmap estimation
# Most retail traders use 5x, 10x, 20x leverage
# At 10x leverage: liquidated at 10% move
# At 20x leverage: liquidated at 5% move
# At 5x leverage:  liquidated at 20% move

leverage_levels = {
    "2x":  0.50,  # liquidated at 50% move
    "3x":  0.33,  # liquidated at 33% move
    "5x":  0.20,  # liquidated at 20% move
    "10x": 0.10,  # liquidated at 10% move
    "20x": 0.05,  # liquidated at 5% move
    "50x": 0.02,  # liquidated at 2% move
    "100x":0.01,  # liquidated at 1% move
}

# Most popular leverage = 10x and 20x
# Generate liquidation price levels
liq_levels = []
price_range = curr_price * 0.15  # look 15% each side

for lev_name, liq_pct in leverage_levels.items():
    # Long liquidations (below current price)
    long_liq_price = curr_price * (1 - liq_pct)
    # Short liquidations (above current price)
    short_liq_price = curr_price * (1 + liq_pct)

    # Weight by popularity of leverage (10x and 20x most popular)
    weight_map = {"2x":0.5,"3x":0.6,"5x":0.8,"10x":1.0,"20x":0.9,"50x":0.6,"100x":0.4}
    weight = weight_map.get(lev_name, 0.5)

    liq_levels.append({
        "leverage":    lev_name,
        "long_liq":    long_liq_price,
        "short_liq":   short_liq_price,
        "weight":      weight,
        "liq_pct":     liq_pct * 100,
        "type":        "long"
    })

# Sort by price
long_liqs  = sorted(liq_levels, key=lambda x: x["long_liq"],  reverse=True)
short_liqs = sorted(liq_levels, key=lambda x: x["short_liq"])

liq_col1, liq_col2 = st.columns(2)

with liq_col1:
    st.markdown("**🔴 Long Liquidation Levels (below price)**")
    st.caption("If price drops here → these longs get liquidated")
    for item in long_liqs:
        price  = item["long_liq"]
        weight = item["weight"]
        dist   = (curr_price - price) / curr_price * 100
        bar    = int(weight * 100)
        if weight >= 0.9:   color, emoji = "#ff4444", "🔥🔥🔥 MAJOR"
        elif weight >= 0.7: color, emoji = "#ff8800", "🔥🔥 Strong"
        else:               color, emoji = "#ff4444", "🔥 Moderate"
        st.markdown(f"""
        <div style="background:#0d0d1a;border-left:3px solid {color};
        border-radius:4px;padding:8px;margin:3px 0;position:relative;overflow:hidden;">
        <div style="position:absolute;top:0;left:0;height:100%;width:{bar}%;
        background:rgba(255,68,68,{weight*0.2:.2f});"></div>
        <b style="color:{color};">${price:,.0f}</b>
        <span style="float:right;font-size:11px;">{emoji}</span><br>
        <span style="color:#aaa;font-size:12px;">
        {item['leverage']} leverage | -{dist:.1f}% from price
        </span>
        </div>
        """, unsafe_allow_html=True)

with liq_col2:
    st.markdown("**🟢 Short Liquidation Levels (above price)**")
    st.caption("If price rises here → these shorts get liquidated")
    for item in short_liqs:
        price  = item["short_liq"]
        weight = item["weight"]
        dist   = (price - curr_price) / curr_price * 100
        bar    = int(weight * 100)
        if weight >= 0.9:   color, emoji = "#00ff88", "🔥🔥🔥 MAJOR"
        elif weight >= 0.7: color, emoji = "#00cc66", "🔥🔥 Strong"
        else:               color, emoji = "#00aa44", "🔥 Moderate"
        st.markdown(f"""
        <div style="background:#0d0d1a;border-left:3px solid {color};
        border-radius:4px;padding:8px;margin:3px 0;position:relative;overflow:hidden;">
        <div style="position:absolute;top:0;left:0;height:100%;width:{bar}%;
        background:rgba(0,255,136,{weight*0.2:.2f});"></div>
        <b style="color:{color};">${price:,.0f}</b>
        <span style="float:right;font-size:11px;">{emoji}</span><br>
        <span style="color:#aaa;font-size:12px;">
        {item['leverage']} leverage | +{dist:.1f}% from price
        </span>
        </div>
        """, unsafe_allow_html=True)

# ── LIQUIDATION HEATMAP CHART
st.markdown(" ")
st.markdown("### 🌡️ Liquidation Heatmap Chart")
st.caption("Similar to CoinGlass — thicker/brighter bar = bigger liquidation cluster = stronger price magnet")

heat_fig = go.Figure()

# Add price line
heat_fig.add_hline(
    y=curr_price,
    line_dash="solid", line_color="white", line_width=2,
    annotation_text=f"Current ${curr_price:,.0f}",
    annotation_font_color="white",
    annotation_position="right"
)

# Plot long liquidation bars
for item in long_liqs:
    price  = item["long_liq"]
    weight = item["weight"]
    opacity = weight * 0.8
    bar_width = weight * 0.8
    color_intensity = int(weight * 255)
    heat_fig.add_shape(
        type="rect",
        x0=0, x1=weight,
        y0=price - curr_price*0.002,
        y1=price + curr_price*0.002,
        fillcolor=f"rgba({color_intensity},50,50,{opacity:.2f})",
        line=dict(color=f"rgba(255,50,50,{opacity:.2f})", width=1),
    )
    heat_fig.add_annotation(
        x=weight + 0.02, y=price,
        text=f"{item['leverage']} — ${price:,.0f}",
        showarrow=False,
        font=dict(color="#ff8888", size=10),
        xanchor="left"
    )

# Plot short liquidation bars
for item in short_liqs:
    price  = item["short_liq"]
    weight = item["weight"]
    opacity = weight * 0.8
    color_intensity = int(weight * 255)
    heat_fig.add_shape(
        type="rect",
        x0=0, x1=weight,
        y0=price - curr_price*0.002,
        y1=price + curr_price*0.002,
        fillcolor=f"rgba(50,{color_intensity},80,{opacity:.2f})",
        line=dict(color=f"rgba(50,255,100,{opacity:.2f})", width=1),
    )
    heat_fig.add_annotation(
        x=weight + 0.02, y=price,
        text=f"{item['leverage']} — ${price:,.0f}",
        showarrow=False,
        font=dict(color="#88ff88", size=10),
        xanchor="left"
    )

# Price range
all_prices = [item["long_liq"] for item in long_liqs] + [item["short_liq"] for item in short_liqs]
y_min = min(all_prices) * 0.998
y_max = max(all_prices) * 1.002

heat_fig.update_layout(
    height=500,
    template="plotly_dark",
    paper_bgcolor="#050508",
    plot_bgcolor="#0a0a0f",
    title=f"Estimated Liquidation Heatmap — {coin} @ ${curr_price:,.0f}",
    xaxis=dict(visible=False, range=[0, 1.3]),
    yaxis=dict(
        title="Price Level",
        range=[y_min, y_max],
        gridcolor="#0d0d18"
    ),
    margin=dict(t=50, b=20, l=80, r=150),
    showlegend=False
)
st.plotly_chart(heat_fig, use_container_width=True, key="pc_20")

# ── KEY LIQUIDATION TARGETS
st.markdown("### 🎯 Key Liquidation Price Targets")
st.caption("Smart money hunts these levels. Watch for price to sweep here then reverse!")

# Most important levels — 10x and 20x (most popular leverage)
major_long_liq  = curr_price * 0.90   # 10x long liq
major_short_liq = curr_price * 1.10   # 10x short liq
liq_20x_long    = curr_price * 0.95   # 20x long liq
liq_20x_short   = curr_price * 1.05   # 20x short liq
liq_50x_long    = curr_price * 0.98   # 50x long liq
liq_50x_short   = curr_price * 1.02   # 50x short liq

kc1,kc2,kc3 = st.columns(3)
with kc1:
    st.markdown(f"""
    <div style="background:#0d0d1a;border:1px solid #ff444433;border-radius:8px;padding:12px;text-align:center;">
    <b style="color:#ff4444;">50x Long Liq</b><br>
    <b style="font-size:20px;color:#ff4444;">${liq_50x_long:,.0f}</b><br>
    <span style="color:#888;font-size:12px;">-2% from price<br>🔥🔥🔥 Nearest target</span>
    </div>
    """, unsafe_allow_html=True)
with kc2:
    st.markdown(f"""
    <div style="background:#0d0d1a;border:1px solid #ff880033;border-radius:8px;padding:12px;text-align:center;">
    <b style="color:#ff8800;">20x Long Liq</b><br>
    <b style="font-size:20px;color:#ff8800;">${liq_20x_long:,.0f}</b><br>
    <span style="color:#888;font-size:12px;">-5% from price<br>🔥🔥 Strong target</span>
    </div>
    """, unsafe_allow_html=True)
with kc3:
    st.markdown(f"""
    <div style="background:#0d0d1a;border:1px solid #ff444433;border-radius:8px;padding:12px;text-align:center;">
    <b style="color:#ff4444;">10x Long Liq</b><br>
    <b style="font-size:20px;color:#ff4444;">${major_long_liq:,.0f}</b><br>
    <span style="color:#888;font-size:12px;">-10% from price<br>🔥 Major target</span>
    </div>
    """, unsafe_allow_html=True)

kc4,kc5,kc6 = st.columns(3)
with kc4:
    st.markdown(f"""
    <div style="background:#0d0d1a;border:1px solid #00ff8833;border-radius:8px;padding:12px;text-align:center;">
    <b style="color:#00ff88;">50x Short Liq</b><br>
    <b style="font-size:20px;color:#00ff88;">${liq_50x_short:,.0f}</b><br>
    <span style="color:#888;font-size:12px;">+2% from price<br>🔥🔥🔥 Nearest target</span>
    </div>
    """, unsafe_allow_html=True)
with kc5:
    st.markdown(f"""
    <div style="background:#0d0d1a;border:1px solid #00ff8833;border-radius:8px;padding:12px;text-align:center;">
    <b style="color:#00ff88;">20x Short Liq</b><br>
    <b style="font-size:20px;color:#00ff88;">${liq_20x_short:,.0f}</b><br>
    <span style="color:#888;font-size:12px;">+5% from price<br>🔥🔥 Strong target</span>
    </div>
    """, unsafe_allow_html=True)
with kc6:
    st.markdown(f"""
    <div style="background:#0d0d1a;border:1px solid #00ff8833;border-radius:8px;padding:12px;text-align:center;">
    <b style="color:#00ff88;">10x Short Liq</b><br>
    <b style="font-size:20px;color:#00ff88;">${major_short_liq:,.0f}</b><br>
    <span style="color:#888;font-size:12px;">+10% from price<br>🔥 Major target</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ── HOW TO TRADE LIQUIDATION LEVELS
st.markdown("### 📚 How To Trade Liquidation Levels")
col_a, col_b = st.columns(2)
with col_a:
    st.success("""
**LONG Setup using liquidation levels:**

1. Price drops toward long liq level (e.g. $74,000)
2. You see a liquidity sweep on 15m
3. BOS forms on 15m after the sweep
4. CHoCH confirms reversal
5. Enter long — target: next short liq above
6. SL: below the liq level
    """)
with col_b:
    st.error("""
**SHORT Setup using liquidation levels:**

1. Price pumps toward short liq level (e.g. $76,000)
2. You see a sell liquidity sweep on 15m
3. BOS forms down on 15m
4. CHoCH confirms reversal down
5. Enter short — target: next long liq below
6. SL: above the liq level
    """)

st.info("""
💡 **Pro Tip:** Combine liquidation levels with your dashboard signals!
- Liquidation level + Discount Zone + BOS = Very strong long setup
- Liquidation level + Premium Zone + CHoCH = Very strong short setup
- Always wait for CONFIRMATION before entering — never trade into the level
""")

# ════════════════════════════════════════════════════════════════
# CHART PATTERN DETECTION
# ════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("🔍 Multi Coin Scanner")
st.caption("Scans all coins at once and shows which has the strongest signal right now")

SCAN_COINS = ["BTC/USDT","ETH/USDT","SOL/USDT","ADA/USDT","MATIC/USDT","BNB/USDT","AVAX/USDT","LINK/USDT","DOT/USDT","ATOM/USDT","NEAR/USDT","OP/USDT","ARB/USDT","DOGE/USDT","XRP/USDT","INJ/USDT","SUI/USDT","APT/USDT"]

@st.cache_data(ttl=120)
def scan_all_coins(coins, tf, lim):
    results = []
    for c in coins:
        try:
            d = get_data(c, tf, lim)
            if d.empty: continue
            d = add_indicators(d)
            d = detect_smc(d)
            sup, res = detect_sr_zones(d)
            s, css, score, ms, reasons, lat2, b = full_signal(d, sup, res)
            pct = (lat2["close"] - d["close"].iloc[-2]) / d["close"].iloc[-2] * 100
            results.append({
                "coin": c.replace("/USDT",""),
                "price": lat2["close"],
                "pct": pct,
                "signal": s,
                "score": score,
                "bias": b,
                "rsi": lat2["rsi"],
                "vol_spike": lat2["vol_spike"],
                "bos": lat2["bos_bull"] or lat2["bos_bear"],
                "choch": lat2["choch_bull"] or lat2["choch_bear"],
                "css": css
            })
        except: continue
    return sorted(results, key=lambda x: abs(x["score"]), reverse=True)

if st.button("🔄 Scan All Coins Now", key="btn_17"):
    st.cache_data.clear()

scan_results = scan_all_coins(SCAN_COINS, timeframe, limit)

if scan_results:
    # Summary bar
    bullish_count = sum(1 for r in scan_results if r["score"] >= 4)
    bearish_count = sum(1 for r in scan_results if r["score"] <= -4)
    neutral_count = len(scan_results) - bullish_count - bearish_count
    sb1, sb2, sb3 = st.columns(3)
    sb1.metric("Bullish Coins 🟢", bullish_count)
    sb2.metric("Neutral Coins ⚪", neutral_count)
    sb3.metric("Bearish Coins 🔴", bearish_count)

    # Scanner cards
    num_cols = 4
    for row_i in range((len(scan_results) + num_cols - 1) // num_cols):
        cols = st.columns(num_cols)
        for col_i in range(num_cols):
            idx = row_i * num_cols + col_i
            if idx >= len(scan_results): break
            r = scan_results[idx]
            with cols[col_i]:
                color = "#00ff88" if r["score"] >= 4 else "#ff4444" if r["score"] <= -4 else "#888"
                pct_arrow = "🟢" if r["pct"] > 0 else "🔴"
                st.markdown(f"""
                <div style="background:#0d0d1a;border:1px solid {color}33;border-left:3px solid {color};
                border-radius:8px;padding:12px;margin:3px 0;">
                <b style="font-size:16px;color:{color};">{r['coin']}</b>
                <span style="float:right;color:#aaa;font-size:12px;">{pct_arrow}{r['pct']:+.2f}%</span><br>
                <span style="color:#ddd;font-size:13px;">${r['price']:,.2f}</span><br>
                <span style="color:{color};font-size:12px;font-weight:700;">Score: {r['score']}/30</span><br>
                <span style="color:#aaa;font-size:11px;">RSI: {r['rsi']:.0f} | {r['bias']}</span><br>
                <span style="color:#aaa;font-size:11px;">
                {'🚀 Vol Spike' if r['vol_spike'] else ''}
                {'⚡ BOS' if r['bos'] else ''}
                {'🔄 CHoCH' if r['choch'] else ''}
                </span>
                </div>
                """, unsafe_allow_html=True)

    # Best opportunity
    if scan_results:
        best_scan = scan_results[0]
        bc = "#00ff88" if best_scan["score"] >= 4 else "#ff4444" if best_scan["score"] <= -4 else "#888"
        st.markdown(f"""
        <div style="background:#0d0d1a;border:2px solid {bc};border-radius:10px;padding:16px;margin:12px 0;text-align:center;">
        <b style="font-size:20px;color:{bc};">🎯 Strongest Signal: {best_scan['coin']} — Score {best_scan['score']}/30</b><br>
        <span style="color:#aaa;">Switch coin selector to {best_scan['coin']} to see full analysis</span>
        </div>
        """, unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════
# ── SESSION TIMES
# ════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("🕐 Trading Session Times")
st.caption("Big moves happen at session opens. Know when to watch the market.")

now_utc = datetime.utcnow()
sessions = [
    {"name": "Asia",   "open": 0,  "close": 9,  "color": "#FFD700", "desc": "Tokyo/Singapore — lower volume, ranging"},
    {"name": "London", "open": 8,  "close": 17, "color": "#00bfff", "desc": "Most liquidity grabs happen here"},
    {"name": "New York","open": 13, "close": 22, "color": "#00ff88", "desc": "Highest volume — biggest moves"},
    {"name": "Overlap", "open": 13, "close": 17, "color": "#bf00ff", "desc": "London+NY overlap — most volatile!"},
]
current_hour = now_utc.hour
sc1, sc2, sc3, sc4 = st.columns(4)
for col, sess in zip([sc1, sc2, sc3, sc4], sessions):
    is_open = sess["open"] <= current_hour < sess["close"]
    status  = "🟢 OPEN NOW" if is_open else "🔴 Closed"
    with col:
        st.markdown(f"""
        <div style="background:#0d0d1a;border:1px solid {sess['color']}44;border-left:3px solid {sess['color']};
        border-radius:8px;padding:12px;margin:3px 0;">
        <b style="color:{sess['color']};font-size:16px;">{sess['name']}</b><br>
        <span style="color:#ddd;font-size:13px;">{sess['open']:02d}:00 – {sess['close']:02d}:00 UTC</span><br>
        <span style="font-size:13px;">{status}</span><br>
        <span style="color:#888;font-size:11px;">{sess['desc']}</span>
        </div>
        """, unsafe_allow_html=True)

# Session chart
st.markdown(" ")
sess_fig = go.Figure()
for sess in sessions:
    sess_fig.add_vrect(
        x0=sess["open"], x1=sess["close"],
        fillcolor=sess["color"], opacity=0.08,
        line_width=1, line_color=sess["color"],
        annotation_text=sess["name"],
        annotation_font_color=sess["color"],
        annotation_position="top left"
    )
sess_fig.add_vline(x=current_hour, line_dash="solid", line_color="white",
    line_width=2, annotation_text=f"NOW {current_hour:02d}:00 UTC",
    annotation_font_color="white")
sess_fig.update_xaxes(range=[0,24], tickvals=list(range(0,25,2)),
    ticktext=[f"{h:02d}:00" for h in range(0,25,2)], title="UTC Hour")
sess_fig.update_yaxes(visible=False)
sess_fig.update_layout(height=180, template="plotly_dark",
    paper_bgcolor="#050508", plot_bgcolor="#050508",
    title="24h Session Map — Current UTC Time Shown",
    margin=dict(t=40, b=40, l=10, r=10))
st.plotly_chart(sess_fig, use_container_width=True, key="pc_21")

# ════════════════════════════════════════════════════════════════
# ── HEAT MAP
# ════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("🌡️ Crypto Heat Map")
st.caption("See which coins are pumping or dumping right now")

@st.cache_data(ttl=120)
def get_heatmap_data():
    coins = ["BTC","ETH","SOL","ADA","MATIC","BNB","AVAX","LINK","DOT","ATOM","NEAR","FTM","OP","ARB","APT","DOGE","XRP","LTC","UNI","AAVE","INJ","SUI","SEI","WLD","FET","RNDR","IMX","SAND","TRX","NEAR"]
    data  = []
    ex    = ccxt.binance()
    for c in coins:
        try:
            ticker = ex.fetch_ticker(f"{c}/USDT")
            data.append({
                "coin": c,
                "price": ticker["last"],
                "pct_1h": ticker.get("percentage", 0) or 0,
                "volume": ticker.get("quoteVolume", 0) or 0,
            })
        except: continue
    return data

hmap_data = get_heatmap_data()

if hmap_data:
    # Sort by % change
    hmap_data = sorted(hmap_data, key=lambda x: x["pct_1h"], reverse=True)

    cols_per_row = 5
    for row_i in range((len(hmap_data) + cols_per_row - 1) // cols_per_row):
        cols = st.columns(cols_per_row)
        for col_i in range(cols_per_row):
            idx = row_i * cols_per_row + col_i
            if idx >= len(hmap_data): break
            d = hmap_data[idx]
            pct = d["pct_1h"]
            if pct >= 3:   bg, tc = "#0d4a1e", "#00ff88"
            elif pct >= 1: bg, tc = "#0a3a15", "#00cc66"
            elif pct >= 0: bg, tc = "#0a2a10", "#00aa44"
            elif pct >= -1: bg, tc = "#3a0d0d", "#ff6666"
            elif pct >= -3: bg, tc = "#4a0d0d", "#ff4444"
            else:           bg, tc = "#5a0d0d", "#ff2222"
            with cols[col_i]:
                st.markdown(f"""
                <div style="background:{bg};border-radius:8px;padding:12px;margin:3px;text-align:center;">
                <b style="color:{tc};font-size:16px;">{d['coin']}</b><br>
                <span style="color:{tc};font-size:18px;font-weight:700;">{pct:+.2f}%</span><br>
                <span style="color:#aaa;font-size:11px;">${d['price']:,.2f}</span>
                </div>
                """, unsafe_allow_html=True)

    # Heatmap bar chart
    hmap_fig = go.Figure(go.Bar(
        x=[d["coin"] for d in hmap_data],
        y=[d["pct_1h"] for d in hmap_data],
        marker_color=["#00ff88" if d["pct_1h"] >= 0 else "#ff4444" for d in hmap_data],
        text=[f"{d['pct_1h']:+.2f}%" for d in hmap_data],
        textposition="outside"
    ))
    hmap_fig.update_layout(
        height=300, template="plotly_dark",
        paper_bgcolor="#050508", plot_bgcolor="#050508",
        title="24h Price Change % — All Coins",
        margin=dict(t=40, b=20)
    )
    hmap_fig.add_hline(y=0, line_color="white", line_width=1, opacity=0.3)
    st.plotly_chart(hmap_fig, use_container_width=True, key="pc_22")

# ════════════════════════════════════════════════════════════════
# ── NEWS FEED
# ════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("📰 Live Crypto News")
st.caption("Latest crypto news — always know what is moving the market")

@st.cache_data(ttl=300)
def get_crypto_news():
    try:
        url = "https://api.coingecko.com/api/v3/news"
        r   = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data.get("data", [])[:10]
    except: pass
    # Fallback — CryptoPanic public RSS
    try:
        url = "https://cryptopanic.com/api/v1/posts/?auth_token=public&kind=news&public=true"
        r   = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            posts = data.get("results", [])[:10]
            return [{"title": p["title"], "url": p["url"],
                     "published_at": p.get("published_at",""), "source": p.get("source",{}).get("title","")} for p in posts]
    except: pass
    return []

news_items = get_crypto_news()
if news_items:
    for item in news_items[:8]:
        title  = item.get("title","")
        url    = item.get("url","#")
        source = item.get("source","") or item.get("author","")
        date   = str(item.get("published_at","") or item.get("created_at",""))[:16]
        # Sentiment colour
        bull_words = ["surge","pump","bull","rise","gain","rally","up","high","buy","moon"]
        bear_words = ["crash","dump","bear","fall","drop","down","low","sell","fear","loss"]
        title_lower = title.lower()
        if any(w in title_lower for w in bull_words):   nc = "#00ff8833"
        elif any(w in title_lower for w in bear_words): nc = "#ff444433"
        else:                                            nc = "#1e1e3a"
        st.markdown(f"""
        <div style="background:{nc};border-radius:8px;padding:10px 14px;margin:4px 0;border:1px solid #333;">
        <a href="{url}" target="_blank" style="color:#ddd;text-decoration:none;font-size:14px;font-weight:600;">{title}</a><br>
        <span style="color:#888;font-size:11px;">{source} &nbsp;|&nbsp; {date}</span>
        </div>
        """, unsafe_allow_html=True)
else:
    st.info("News feed loading... Check your internet connection or try refreshing.")
    st.markdown("""
    **Top crypto news sources to check manually:**
    - [CoinDesk](https://coindesk.com)
    - [CoinTelegraph](https://cointelegraph.com)
    - [CryptoPanic](https://cryptopanic.com)
    """)

# ════════════════════════════════════════════════════════════════
# ── TRADING JOURNAL
# ════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("📓 Trading Journal")
st.caption("Log every trade. This is the most important habit for improving.")

if "journal" not in st.session_state:
    st.session_state.journal = []

with st.expander("➕ Log A New Trade", expanded=False):
    jc1, jc2, jc3 = st.columns(3)
    j_coin    = jc1.selectbox("Coin", ["BTC","ETH","SOL","ADA","MATIC","BNB","AVAX","LINK","DOT","ATOM","NEAR","OP","ARB","DOGE","XRP","INJ","SUI","APT","FET","RNDR"], key="j_coin_2")
    j_dir     = jc2.selectbox("Direction", ["LONG","SHORT"], key="j_dir_2")
    j_result  = jc3.selectbox("Result", ["WIN","LOSS","BREAKEVEN"], key="j_result_2")
    jc4, jc5, jc6 = st.columns(3)
    j_entry   = jc4.number_input("Entry Price", value=0.0, key="j_entry_2")
    j_exit    = jc5.number_input("Exit Price",  value=0.0, key="j_exit_2")
    j_size    = jc6.number_input("Position Size (USDT)", value=10.0, key="j_size_2")
    jc7, jc8  = st.columns(2)
    j_signal  = jc7.selectbox("Signal That Triggered",
        ["BOS","CHoCH","OB Retest","FVG Fill","Liquidity Sweep","Support Bounce","Resistance Reject","Other"], key="j_signal_2")
    j_tf      = jc8.selectbox("Timeframe Used", ["15m","1h","4h","1d"], key="j_tf_2")
    j_notes   = st.text_area("Notes / What I Learned", placeholder="Why did I take this trade? What happened? What would I do differently?", key="j_notes_2")

    if st.button("💾 Save Trade", key="btn_18"):
        if j_entry > 0 and j_exit > 0:
            pnl = (j_exit - j_entry) / j_entry * 100 if j_dir == "LONG" else (j_entry - j_exit) / j_entry * 100
            pnl_usdt = j_size * (pnl / 100)
            st.session_state.journal.append({
                "date":    datetime.now().strftime("%Y-%m-%d %H:%M"),
                "coin":    j_coin,
                "dir":     j_dir,
                "entry":   j_entry,
                "exit":    j_exit,
                "result":  j_result,
                "pnl_pct": round(pnl, 2),
                "pnl_usdt":round(pnl_usdt, 2),
                "signal":  j_signal,
                "tf":      j_tf,
                "notes":   j_notes,
                "size":    j_size
            })
            st.success("Trade saved! ✅")
        else:
            st.warning("Please enter entry and exit prices.")

if st.session_state.journal:
    jdf = pd.DataFrame(st.session_state.journal)

    # ── Win Rate Calculator
    st.markdown("---")
    st.subheader("📊 Win Rate Calculator")
    wins      = len(jdf[jdf["result"] == "WIN"])
    losses    = len(jdf[jdf["result"] == "LOSS"])
    total     = len(jdf)
    win_rate  = wins / total * 100 if total > 0 else 0
    total_pnl = jdf["pnl_usdt"].sum()
    avg_win   = jdf[jdf["result"]=="WIN"]["pnl_usdt"].mean() if wins > 0 else 0
    avg_loss  = jdf[jdf["result"]=="LOSS"]["pnl_usdt"].mean() if losses > 0 else 0
    rr_ratio  = abs(avg_win / avg_loss) if avg_loss != 0 else 0

    wc1,wc2,wc3,wc4,wc5,wc6 = st.columns(6)
    wc1.metric("Total Trades", total)
    wc2.metric("Win Rate",    f"{win_rate:.1f}%", f"{wins}W / {losses}L")
    wc3.metric("Total P&L",   f"${total_pnl:.2f}", "Profit" if total_pnl > 0 else "Loss")
    wc4.metric("Avg Win",     f"${avg_win:.2f}")
    wc5.metric("Avg Loss",    f"${avg_loss:.2f}")
    wc6.metric("R:R Ratio",   f"{rr_ratio:.2f}")

    # Profitability check
    if win_rate >= 50 and rr_ratio >= 1.5:
        st.success("✅ Strategy is profitable! Keep following the rules.")
    elif win_rate >= 40 and rr_ratio >= 2.0:
        st.success("✅ Low win rate but good R:R — strategy can still be profitable!")
    elif total >= 5:
        st.warning("⚠️ Strategy needs improvement. Review your losing trades.")

    # Win rate by signal
    if len(jdf) >= 3:
        st.markdown("**Win Rate by Signal:**")
        sig_stats = jdf.groupby("signal").apply(
            lambda x: pd.Series({"Trades": len(x), "Wins": (x["result"]=="WIN").sum(),
                                  "Win%": round((x["result"]=="WIN").mean()*100,1),
                                  "P&L": round(x["pnl_usdt"].sum(),2)})
        ).reset_index()
        st.dataframe(sig_stats, use_container_width=True, hide_index=True)

    # P&L chart
    if len(jdf) >= 2:
        jdf["cumulative_pnl"] = jdf["pnl_usdt"].cumsum()
        pnl_fig = go.Figure()
        pnl_fig.add_trace(go.Scatter(
            x=jdf["date"], y=jdf["cumulative_pnl"],
            name="Cumulative P&L", fill="tozeroy",
            line=dict(color="#00ff88" if total_pnl >= 0 else "#ff4444", width=2),
            fillcolor="rgba(0,255,136,0.08)" if total_pnl >= 0 else "rgba(255,68,68,0.08)"
        ))
        pnl_fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.3)
        pnl_fig.update_layout(height=250, template="plotly_dark",
            paper_bgcolor="#050508", plot_bgcolor="#050508",
            title="Cumulative P&L ($)", margin=dict(t=30, b=20))
        st.plotly_chart(pnl_fig, use_container_width=True, key="pc_23")

    # Full journal table
    st.markdown("**All Trades:**")
    display_cols = ["date","coin","dir","entry","exit","result","pnl_pct","pnl_usdt","signal","tf"]
    jdf_display  = jdf[display_cols].copy()
    jdf_display.columns = ["Date","Coin","Dir","Entry","Exit","Result","P&L%","P&L$","Signal","TF"]
    st.dataframe(jdf_display, use_container_width=True, hide_index=True)

    if st.button("🗑️ Clear Journal", key="btn_19"):
        st.session_state.journal = []
        st.rerun()
else:
    st.info("No trades logged yet. Use the form above to log your first trade!")

# ════════════════════════════════════════════════════════════════
# ── PAPER TRADING TRACKER
# ════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("📄 Paper Trading Tracker")
st.caption("Practice trading with fake money. Build confidence before using real money.")

if "paper_balance" not in st.session_state:
    st.session_state.paper_balance  = 1000.0
if "paper_trades" not in st.session_state:
    st.session_state.paper_trades   = []
if "paper_position" not in st.session_state:
    st.session_state.paper_position = None

current_price = float(lat["close"])
pb1, pb2, pb3 = st.columns(3)
pb1.metric("Paper Balance", f"${st.session_state.paper_balance:.2f}")
pb2.metric("Current Price", f"${current_price:,.2f}")
pb3.metric("Position", "OPEN 📈" if st.session_state.paper_position else "None")

if st.session_state.paper_position is None:
    # Open trade
    st.markdown("**Open Paper Trade:**")
    pc1, pc2, pc3 = st.columns(3)
    p_dir    = pc1.selectbox("Direction", ["LONG","SHORT"], key="p_dir_2")
    p_size   = pc2.number_input("Trade Size (USDT)", value=50.0, min_value=1.0, max_value=st.session_state.paper_balance, key="p_size_2")
    p_lev    = pc3.selectbox("Leverage", ["1x","2x","3x","5x","10x"], key="p_lev_2")
    p_sl     = st.number_input("Stop Loss Price", value=round(current_price * 0.98, 2), key="p_sl_2")
    p_tp     = st.number_input("Take Profit Price", value=round(current_price * 1.03, 2), key="p_tp_2")

    if st.button("📈 Open Paper Trade", key="btn_20"):
        lev_val = int(p_lev.replace("x",""))
        st.session_state.paper_position = {
            "coin":    coin, "dir": p_dir, "entry": current_price,
            "size":    p_size, "leverage": lev_val,
            "sl":      p_sl, "tp": p_tp,
            "time":    datetime.now().strftime("%H:%M"),
            "signal":  sig
        }
        st.success(f"Paper trade opened! {p_dir} {coin} at ${current_price:,.2f}")
        st.rerun()
else:
    pos = st.session_state.paper_position
    # Calculate live P&L
    if pos["dir"] == "LONG":
        pnl_pct = (current_price - pos["entry"]) / pos["entry"] * 100 * pos["leverage"]
    else:
        pnl_pct = (pos["entry"] - current_price) / pos["entry"] * 100 * pos["leverage"]
    pnl_usdt = pos["size"] * (pnl_pct / 100)

    pc1, pc2, pc3, pc4 = st.columns(4)
    pc1.metric("Direction",   pos["dir"])
    pc2.metric("Entry Price", f"${pos['entry']:,.2f}")
    pc3.metric("Live P&L",    f"${pnl_usdt:.2f}", f"{pnl_pct:.2f}%")
    pc4.metric("Leverage",    f"{pos['leverage']}x")

    col_sl, col_tp = st.columns(2)
    col_sl.metric("Stop Loss",   f"${pos['sl']:,.2f}")
    col_tp.metric("Take Profit", f"${pos['tp']:,.2f}")

    # Check if SL or TP hit
    sl_hit = (pos["dir"]=="LONG" and current_price <= pos["sl"]) or (pos["dir"]=="SHORT" and current_price >= pos["sl"])
    tp_hit = (pos["dir"]=="LONG" and current_price >= pos["tp"]) or (pos["dir"]=="SHORT" and current_price <= pos["tp"])

    if sl_hit:
        st.error("🔴 STOP LOSS HIT!")
    elif tp_hit:
        st.success("🟢 TAKE PROFIT HIT!")

    if st.button("❌ Close Paper Trade", key="btn_21"):
        new_balance = st.session_state.paper_balance + pnl_usdt
        result = "WIN" if pnl_usdt > 0 else "LOSS"
        st.session_state.paper_trades.append({
            "date":     datetime.now().strftime("%Y-%m-%d %H:%M"),
            "coin":     pos["coin"], "dir": pos["dir"],
            "entry":    pos["entry"], "exit": current_price,
            "pnl_pct":  round(pnl_pct, 2), "pnl_usdt": round(pnl_usdt, 2),
            "result":   result, "leverage": pos["leverage"],
            "signal":   pos["signal"]
        })
        st.session_state.paper_balance  = new_balance
        st.session_state.paper_position = None
        st.success(f"Trade closed! P&L: ${pnl_usdt:.2f} | New Balance: ${new_balance:.2f}")
        st.rerun()

if st.session_state.paper_trades:
    st.markdown("**Paper Trade History:**")
    ptdf = pd.DataFrame(st.session_state.paper_trades)
    ptdf["cumulative"] = ptdf["pnl_usdt"].cumsum() + 1000
    pt_wins = len(ptdf[ptdf["result"]=="WIN"])
    pt_wr   = pt_wins / len(ptdf) * 100
    pp1, pp2, pp3 = st.columns(3)
    pp1.metric("Paper Win Rate", f"{pt_wr:.1f}%")
    pp2.metric("Total Trades",   len(ptdf))
    pp3.metric("Final Balance",  f"${st.session_state.paper_balance:.2f}",
               f"${st.session_state.paper_balance-1000:.2f}")
    st.dataframe(ptdf[["date","coin","dir","entry","exit","pnl_pct","pnl_usdt","result","leverage"]],
                 use_container_width=True, hide_index=True)
    if st.button("🔄 Reset Paper Account", key="btn_22"):
        st.session_state.paper_balance  = 1000.0
        st.session_state.paper_trades   = []
        st.session_state.paper_position = None
        st.rerun()

# ════════════════════════════════════════════════════════════════
# ── BACKTESTING
# ════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("🔬 Simple Backtesting")
st.caption("Test how the BOS and CHoCH signals performed on past data")

bt_col1, bt_col2 = st.columns(2)
bt_signal = bt_col1.selectbox("Signal To Test", ["BOS Bullish","CHoCH Bullish","Buy Liquidity Sweep","Volume Spike + BOS"], key="auto_ced1ac_2")
bt_hold   = bt_col2.selectbox("Hold For (candles)", [1, 2, 3, 5, 10], key="auto_6433ad_2")

if st.button("▶️ Run Backtest", key="btn_23"):
    with st.spinner("Running backtest on historical data..."):
        bt_results = []
        for i in range(10, len(df) - bt_hold):
            row     = df.iloc[i]
            future  = df.iloc[i + bt_hold]
            triggered = False

            if bt_signal == "BOS Bullish"            and row["bos_bull"]:   triggered = True
            elif bt_signal == "CHoCH Bullish"         and row["choch_bull"]: triggered = True
            elif bt_signal == "Buy Liquidity Sweep"   and row["buy_liq"]:   triggered = True
            elif bt_signal == "Volume Spike + BOS"    and row["bos_bull"] and row["vol_spike"]: triggered = True

            if triggered:
                entry  = row["close"]
                exit_p = future["close"]
                pnl    = (exit_p - entry) / entry * 100
                bt_results.append({
                    "time":   row["time"].strftime("%m/%d %H:%M"),
                    "entry":  round(entry, 2),
                    "exit":   round(exit_p, 2),
                    "pnl%":   round(pnl, 2),
                    "result": "WIN" if pnl > 0 else "LOSS"
                })

        if bt_results:
            btdf    = pd.DataFrame(bt_results)
            bt_wins = len(btdf[btdf["result"]=="WIN"])
            bt_wr   = bt_wins / len(btdf) * 100
            bt_avg  = btdf["pnl%"].mean()
            bt_tot  = btdf["pnl%"].sum()

            bc1, bc2, bc3, bc4 = st.columns(4)
            bc1.metric("Signals Found",  len(btdf))
            bc2.metric("Win Rate",       f"{bt_wr:.1f}%")
            bc3.metric("Avg P&L",        f"{bt_avg:.2f}%")
            bc4.metric("Total Return",   f"{bt_tot:.2f}%",
                       "✅ Profitable" if bt_tot > 0 else "❌ Losing")

            # P&L distribution
            bt_fig = go.Figure()
            bt_fig.add_trace(go.Bar(
                x=btdf["time"], y=btdf["pnl%"],
                marker_color=["#00ff88" if p > 0 else "#ff4444" for p in btdf["pnl%"]],
                name="P&L %"
            ))
            bt_fig.add_hline(y=0, line_color="white", line_width=1, opacity=0.3)
            bt_fig.update_layout(height=250, template="plotly_dark",
                paper_bgcolor="#050508", plot_bgcolor="#050508",
                title=f"Backtest Results — {bt_signal} | Hold {bt_hold} candles",
                margin=dict(t=30, b=20))
            st.plotly_chart(bt_fig, use_container_width=True, key="pc_24")
            st.dataframe(btdf, use_container_width=True, hide_index=True)

            if bt_wr >= 55:
                st.success(f"✅ Signal '{bt_signal}' has a {bt_wr:.1f}% win rate on {timeframe} — worth using!")
            elif bt_wr >= 45:
                st.warning(f"⚠️ Signal '{bt_signal}' has {bt_wr:.1f}% win rate — acceptable with good R:R")
            else:
                st.error(f"❌ Signal '{bt_signal}' has only {bt_wr:.1f}% win rate on {timeframe} — use with caution")
        else:
            st.warning("No signals found in this data range. Try a different signal or increase candles.")


# ════════════════════════════════════════════════════════════════
# ── MARKET CORRELATIONS
# ════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("🌍 Market Correlations & Sentiment")
st.caption("Key external data that moves crypto markets — check these every day")

# ── FEAR & GREED
@st.cache_data(ttl=3600)
def get_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=30", timeout=10)
        data = r.json()
        return data.get("data", [])
    except:
        return []

# ── FUNDING RATES
@st.cache_data(ttl=300)
def get_funding_rates():
    try:
        exchange = ccxt.binance()
        coins = ["BTC/USDT:USDT","ETH/USDT:USDT","SOL/USDT:USDT","ADA/USDT:USDT"]
        results = []
        for c in coins:
            try:
                info = exchange.fetch_funding_rate(c)
                results.append({
                    "coin": c.split("/")[0],
                    "rate": float(info.get("fundingRate", 0)) * 100,
                    "next": str(info.get("fundingDatetime",""))[:16]
                })
            except:
                continue
        return results
    except:
        return []

# ── OPEN INTEREST
@st.cache_data(ttl=300)
def get_open_interest():
    results = []
    coins = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","ADAUSDT"]
    for c in coins:
        try:
            url = f"https://fapi.binance.com/fapi/v1/openInterest?symbol={c}"
            r = requests.get(url, timeout=10)
            data = r.json()
            oi_qty = float(data.get("openInterest", 0))
            # Get current price to calculate USD value
            url2 = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={c}"
            r2 = requests.get(url2, timeout=10)
            price = float(r2.json().get("price", 0))
            oi_usdt = oi_qty * price
            results.append({
                "coin": c.replace("USDT",""),
                "oi": oi_qty,
                "oi_usdt": oi_usdt
            })
        except:
            continue
    return results

# ── BTC DOMINANCE
@st.cache_data(ttl=3600)
def get_btc_dominance():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=10)
        data = r.json().get("data", {})
        dom  = data.get("market_cap_percentage", {})
        return {
            "btc":  round(dom.get("btc", 0), 2),
            "eth":  round(dom.get("eth", 0), 2),
            "others": round(100 - dom.get("btc", 0) - dom.get("eth", 0), 2),
            "total_mcap": data.get("total_market_cap", {}).get("usd", 0),
            "total_volume": data.get("total_volume", {}).get("usd", 0),
            "mcap_change": data.get("market_cap_change_percentage_24h_usd", 0)
        }
    except:
        return {}

with st.spinner("Loading market data..."):
    fg_data   = get_fear_greed()
    fr_data   = get_funding_rates()
    oi_data   = get_open_interest()
    dom_data  = get_btc_dominance()

# ── ROW 1: FEAR & GREED + BTC DOMINANCE
fgc1, fgc2 = st.columns(2)

with fgc1:
    st.markdown("### 😱 Fear & Greed Index")
    if fg_data:
        current_fg    = fg_data[0]
        fg_value      = int(current_fg["value"])
        fg_class      = current_fg["value_classification"]
        fg_date       = current_fg["timestamp"]

        # Color based on value
        if fg_value <= 25:   fg_color, fg_emoji = "#ff4444", "😱 Extreme Fear"
        elif fg_value <= 45: fg_color, fg_emoji = "#ff8800", "😰 Fear"
        elif fg_value <= 55: fg_color, fg_emoji = "#FFD700", "😐 Neutral"
        elif fg_value <= 75: fg_color, fg_emoji = "#00cc66", "😊 Greed"
        else:                fg_color, fg_emoji = "#00ff88", "🤑 Extreme Greed"

        st.markdown(f"""
        <div style="background:#0d0d1a;border:1px solid {fg_color}44;border-radius:12px;padding:20px;text-align:center;">
        <div style="font-size:60px;font-weight:900;color:{fg_color};">{fg_value}</div>
        <div style="font-size:20px;color:{fg_color};font-weight:700;">{fg_emoji}</div>
        <div style="color:#888;font-size:13px;margin-top:8px;">Updated daily</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(" ")

        # Trading interpretation
        if fg_value <= 25:
            st.success("💡 Extreme Fear = GOOD TIME TO BUY — everyone is scared, smart money accumulates")
        elif fg_value <= 45:
            st.info("💡 Fear = Possible buy opportunity — market is cautious")
        elif fg_value <= 55:
            st.info("💡 Neutral — no strong signal from sentiment")
        elif fg_value <= 75:
            st.warning("💡 Greed = Be careful — market getting overheated")
        else:
            st.error("💡 Extreme Greed = CONSIDER SELLING — everyone is euphoric, top may be near")

        # 30 day chart
        if len(fg_data) >= 7:
            fg_vals  = [int(d["value"]) for d in reversed(fg_data[:30])]
            fg_dates = [datetime.fromtimestamp(int(d["timestamp"])).strftime("%m/%d") for d in reversed(fg_data[:30])]
            fg_colors = ["#ff4444" if v <= 25 else "#ff8800" if v <= 45 else "#FFD700" if v <= 55 else "#00cc66" if v <= 75 else "#00ff88" for v in fg_vals]
            fg_fig = go.Figure()
            fg_fig.add_trace(go.Bar(x=fg_dates, y=fg_vals, marker_color=fg_colors, name="Fear & Greed"))
            fg_fig.add_hline(y=25, line_dash="dash", line_color="red",   opacity=0.5, annotation_text="Extreme Fear")
            fg_fig.add_hline(y=75, line_dash="dash", line_color="green", opacity=0.5, annotation_text="Extreme Greed")
            fg_fig.add_hline(y=50, line_dash="dot",  line_color="white", opacity=0.2)
            fg_fig.update_layout(height=200, template="plotly_dark",
                paper_bgcolor="#050508", plot_bgcolor="#050508",
                title="30 Day Fear & Greed History",
                margin=dict(t=30, b=20), showlegend=False)
            st.plotly_chart(fg_fig, use_container_width=True, key="pc_25")
    else:
        st.warning("Could not load Fear & Greed data")

with fgc2:
    st.markdown("### 👑 BTC Dominance")
    if dom_data:
        btc_dom = dom_data.get("btc", 0)
        eth_dom = dom_data.get("eth", 0)
        oth_dom = dom_data.get("others", 0)
        total_mcap = dom_data.get("total_mcap", 0)
        mcap_chg   = dom_data.get("mcap_change", 0)

        dc1, dc2, dc3 = st.columns(3)
        dc1.metric("BTC Dom",   f"{btc_dom}%",  "↑ Alts bleeding" if btc_dom > 50 else "↓ Alt season")
        dc2.metric("ETH Dom",   f"{eth_dom}%")
        dc3.metric("Total MCap",f"${total_mcap/1e12:.2f}T", f"{mcap_chg:.2f}%")

        # Dominance interpretation
        if btc_dom > 55:
            st.warning(f"⚠️ BTC Dominance HIGH at {btc_dom}% — money in BTC, altcoins struggling")
        elif btc_dom > 48:
            st.info(f"ℹ️ BTC Dominance NEUTRAL at {btc_dom}% — balanced market")
        else:
            st.success(f"✅ BTC Dominance LOW at {btc_dom}% — altcoin season possible!")

        # Pie chart
        dom_fig = go.Figure(go.Pie(
            labels=["BTC", "ETH", "Others"],
            values=[btc_dom, eth_dom, oth_dom],
            marker_colors=["#F7931A", "#627EEA", "#888888"],
            hole=0.4,
            textinfo="label+percent"
        ))
        dom_fig.update_layout(
            height=250, template="plotly_dark",
            paper_bgcolor="#050508",
            title="Market Cap Distribution",
            margin=dict(t=40, b=20),
            showlegend=False
        )
        st.plotly_chart(dom_fig, use_container_width=True, key="pc_26")

        # Alt season signal
        st.markdown(f"""
        <div style="background:#0d0d1a;border:1px solid #F7931A44;border-radius:8px;padding:12px;">
        <b style="color:#F7931A;">Altcoin Season Signal:</b><br>
        {'🟢 BTC dom falling = Alt season starting — rotate into SOL, ETH, ADA' if btc_dom < 48 else
         '🔴 BTC dom rising = Stay in BTC or stable — altcoins losing value' if btc_dom > 52 else
         '⚪ Neutral — watch BTC.D direction on TradingView'}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("Could not load dominance data")

st.markdown("---")

# ── ROW 2: FUNDING RATES + OPEN INTEREST
fc1, fc2 = st.columns(2)

with fc1:
    st.markdown("### 💰 Funding Rates")
    st.caption("Positive = longs paying shorts. Negative = shorts paying longs.")
    if fr_data:
        for r in fr_data:
            rate = r["rate"]
            if rate > 0.05:    rc, emoji, msg = "#ff4444", "🔴", "Very high — longs overloaded, DROP likely"
            elif rate > 0.01:  rc, emoji, msg = "#ff8800", "🟠", "High — market leaning long, be careful"
            elif rate > 0:     rc, emoji, msg = "#00ff88", "🟢", "Healthy — slight long bias, normal"
            elif rate > -0.01: rc, emoji, msg = "#00bfff", "🔵", "Slightly negative — slight short bias"
            else:              rc, emoji, msg = "#bf00ff", "🟣", "Very negative — shorts overloaded, PUMP likely"

            st.markdown(f"""
            <div style="background:#0d0d1a;border:1px solid {rc}44;border-left:3px solid {rc};
            border-radius:8px;padding:10px;margin:4px 0;">
            <b style="color:{rc};">{emoji} {r['coin']}</b>
            <span style="float:right;color:{rc};font-weight:700;">{rate:.4f}%</span><br>
            <span style="color:#888;font-size:12px;">{msg}</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown(" ")
        st.info("💡 Extreme positive funding = market too bullish = price may drop soon\n\nExtreme negative funding = market too bearish = price may pump soon")
    else:
        st.warning("Could not load funding rates")

with fc2:
    st.markdown("### 📊 Open Interest")
    st.caption("Total value of open futures contracts — shows market conviction")
    if oi_data:
        for r in oi_data:
            oi_val = r["oi_usdt"]
            st.markdown(f"""
            <div style="background:#0d0d1a;border:1px solid #00bfff33;border-left:3px solid #00bfff;
            border-radius:8px;padding:10px;margin:4px 0;">
            <b style="color:#00bfff;">{r['coin']}</b>
            <span style="float:right;color:#FFD700;font-weight:700;">${oi_val/1e9:.2f}B</span><br>
            <span style="color:#888;font-size:12px;">{r['oi']:,.0f} contracts open</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown(" ")
        st.markdown("""
        <div style="background:#0d0d1a;border:1px solid #FFD70033;border-radius:8px;padding:12px;">
        <b style="color:#FFD700;">How To Read Open Interest:</b><br>
        <span style="color:#00ff88;">Price UP + OI UP = Strong bull trend ✅</span><br>
        <span style="color:#ff8800;">Price UP + OI DOWN = Weak move, reversal possible ⚠️</span><br>
        <span style="color:#ff4444;">Price DOWN + OI UP = Strong bear trend 🔴</span><br>
        <span style="color:#00bfff;">Price DOWN + OI DOWN = Shorts closing, bounce coming ✅</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("Could not load open interest data")

st.markdown("---")

# ── ROW 3: COMBINED MARKET SIGNAL
st.markdown("### 🎯 Combined Market Signal")
st.caption("All correlations combined into one overall market reading")

if fg_data and dom_data:
    fg_val  = int(fg_data[0]["value"])
    btc_dom = dom_data.get("btc", 50)

    bull_points = 0
    bear_points = 0
    signals     = []

    # Fear & Greed
    if fg_val <= 30:
        bull_points += 2
        signals.append("😱 Extreme Fear — historically good buy zone ✅")
    elif fg_val >= 75:
        bear_points += 2
        signals.append("🤑 Extreme Greed — historically good sell zone ⚠️")

    # BTC Dominance
    if btc_dom < 45:
        bull_points += 1
        signals.append("👑 Low BTC dominance — altcoin season possible ✅")
    elif btc_dom > 55:
        bear_points += 1
        signals.append("👑 High BTC dominance — alts struggling ⚠️")

    # Funding rates
    if fr_data:
        avg_rate = sum(r["rate"] for r in fr_data) / len(fr_data)
        if avg_rate < -0.01:
            bull_points += 2
            signals.append("💰 Negative funding — shorts overloaded, pump likely ✅")
        elif avg_rate > 0.05:
            bear_points += 2
            signals.append("💰 Very high funding — longs overloaded, drop likely ⚠️")

    # Dashboard signal
    if sc >= 4:
        bull_points += 2
        signals.append(f"📊 Dashboard signal BULLISH score {sc}/30 ✅")
    elif sc <= -4:
        bear_points += 2
        signals.append(f"📊 Dashboard signal BEARISH score {sc}/30 ⚠️")

    total_pts = bull_points + bear_points
    if total_pts > 0:
        bull_pct = bull_points / total_pts * 100
    else:
        bull_pct = 50

    if bull_points > bear_points + 1:
        overall = "BULLISH CONFLUENCE 🟢"
        oc = "#00ff88"
    elif bear_points > bull_points + 1:
        overall = "BEARISH CONFLUENCE 🔴"
        oc = "#ff4444"
    else:
        overall = "MIXED — WAIT FOR CLARITY ⚪"
        oc = "#888888"

    st.markdown(f"""
    <div style="background:#0d0d1a;border:2px solid {oc};border-radius:12px;padding:20px;text-align:center;margin:10px 0;">
    <div style="font-size:24px;font-weight:700;color:{oc};">{overall}</div>
    <div style="color:#aaa;font-size:14px;margin-top:8px;">
    Bullish factors: {bull_points} | Bearish factors: {bear_points}
    </div>
    </div>
    """, unsafe_allow_html=True)

    # Progress bar
    st.markdown(f"**Market Bias: {bull_pct:.0f}% Bullish**")
    st.progress(int(bull_pct) / 100)

    # All signals
    st.markdown("**All Confluence Factors:**")
    for s in signals:
        if "✅" in s: st.success(s)
        elif "⚠️" in s: st.error(s)
        else: st.info(s)

st.markdown("---")

# ── USEFUL LINKS
st.subheader("🔗 Useful Daily Resources")
lc1, lc2, lc3, lc4 = st.columns(4)
with lc1:
    st.markdown("""
    **📊 Market Data**
    - [Fear & Greed](https://alternative.me/crypto/fear-and-greed-index/)
    - [CoinGlass](https://coinglass.com)
    - [TradingView](https://tradingview.com)
    - [CoinMarketCap](https://coinmarketcap.com)
    """)
with lc2:
    st.markdown("""
    **📰 News**
    - [CoinDesk](https://coindesk.com)
    - [CoinTelegraph](https://cointelegraph.com)
    - [CryptoPanic](https://cryptopanic.com)
    - [The Block](https://theblock.co)
    """)
with lc3:
    st.markdown("""
    **🐋 Whale Tracking**
    - [Whale Alert](https://whale-alert.io)
    - [Glassnode](https://glassnode.com)
    - [CryptoQuant](https://cryptoquant.com)
    - [Santiment](https://santiment.net)
    """)
with lc4:
    st.markdown("""
    **📈 Futures Data**
    - [Coinglass OI](https://coinglass.com/OpenInterest)
    - [Coinglass FR](https://coinglass.com/FundingRate)
    - [Bybt](https://bybt.com)
    - [Binance Futures](https://binance.com/futures)
    """)

st.markdown("---")
st.subheader("📖 Order Book Analysis")
st.caption("Live order book — see whale orders, buy/sell walls, and market pressure")

ob_symbol = coin.replace("/USDT","") + "USDT"

@st.cache_data(ttl=15)
def get_ob(symbol):
    try:
        url = f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit=100"
        r = requests.get(url, timeout=10)
        d = r.json()
        return {"bids":[[float(p),float(q)] for p,q in d.get("bids",[])],
                "asks":[[float(p),float(q)] for p,q in d.get("asks",[])]}
    except: return {}

@st.cache_data(ttl=15)
def get_trades(symbol):
    try:
        url = f"https://api.binance.com/api/v3/trades?symbol={symbol}&limit=500"
        r = requests.get(url, timeout=10)
        rows = [{"price":float(t["price"]),"qty":float(t["qty"]),
                 "value":float(t["price"])*float(t["qty"]),
                 "is_buyer":not t["isBuyerMaker"],
                 "time":pd.to_datetime(t["time"],unit="ms")} for t in r.json()]
        return pd.DataFrame(rows)
    except: return pd.DataFrame()

with st.spinner("Loading order book..."):
    ob  = get_ob(ob_symbol)
    tdf = get_trades(ob_symbol)

if ob and "bids" in ob and "asks" in ob and len(ob["bids"]) > 0 and len(ob["asks"]) > 0:
    bids = ob["bids"][:50]; asks = ob["asks"][:50]
    if not bids or not asks:
        st.warning("Order book empty — Binance may restrict this region")
        bids = []; asks = []
    else:
        bp = [b[0] for b in bids]; bq = [b[1] for b in bids]
        ap = [a[0] for a in asks]; aq = [a[1] for a in asks]
        mid = (bp[0]+ap[0])/2 if bp and ap else 0
    tbv = sum(p*q for p,q in bids); tav = sum(p*q for p,q in asks)
    tv  = tbv+tav
    bpct = tbv/tv*100 if tv>0 else 50; apct = tav/tv*100 if tv>0 else 50
    imb  = bpct - apct

    m1,m2,m3,m4,m5 = st.columns(5)
    m1.metric("Mid Price", f"${mid:,.2f}")
    m2.metric("Bid Vol",   f"${tbv/1e6:.2f}M", f"{bpct:.1f}%")
    m3.metric("Ask Vol",   f"${tav/1e6:.2f}M", f"{apct:.1f}%")
    m4.metric("Spread",    f"${ap[0]-bp[0]:.2f}")
    m5.metric("Imbalance", f"{imb:+.1f}%", "Buy pres" if imb>5 else "Sell pres" if imb<-5 else "Neutral")

    if imb>10:    st.success(f"Strong buy pressure! Bids dominating {imb:.1f}%")
    elif imb>5:   st.info(f"Moderate buy pressure {imb:.1f}%")
    elif imb<-10: st.error(f"Strong sell pressure! Asks dominating {abs(imb):.1f}%")
    elif imb<-5:  st.warning(f"Moderate sell pressure {abs(imb):.1f}%")

    st.markdown("---")
    st.markdown("### 📊 Order Book Depth Chart")
    cb=[]; r2=0
    for q in bq: r2+=q; cb.append(r2)
    ca=[]; r2=0
    for q in aq: r2+=q; ca.append(r2)
    df2=go.Figure()
    df2.add_trace(go.Scatter(x=bp,y=cb,name="Bids",fill="tozeroy",line=dict(color="#00ff88",width=2),fillcolor="rgba(0,255,136,0.15)"))
    df2.add_trace(go.Scatter(x=ap,y=ca,name="Asks",fill="tozeroy",line=dict(color="#ff4444",width=2),fillcolor="rgba(255,68,68,0.15)"))
    df2.add_vline(x=mid,line_dash="dash",line_color="white",line_width=2,annotation_text=f"${mid:,.0f}",annotation_font_color="white")
    df2.update_layout(height=320,template="plotly_dark",paper_bgcolor="#050508",plot_bgcolor="#050508",
        title="Cumulative Depth — Green=Buys Red=Sells",xaxis_title="Price",yaxis_title="Cum Qty",margin=dict(t=40,b=30,l=10,r=10))
    df2.update_xaxes(gridcolor="#0d0d18"); df2.update_yaxes(gridcolor="#0d0d18")
    st.plotly_chart(df2,use_container_width=True, key="pc_27")

    st.markdown("---")
    st.markdown("### 🐋 Whale Order Walls")
    bu = sorted([(p,q,p*q) for p,q in bids],key=lambda x:x[2],reverse=True)[:8]
    au = sorted([(p,q,p*q) for p,q in asks],key=lambda x:x[2],reverse=True)[:8]
    wc1,wc2 = st.columns(2)
    with wc1:
        st.markdown("**Buy Walls — price may bounce UP here**")
        for i,(p,q,u) in enumerate(bu):
            bar=int(u/bu[0][2]*100); em="🐋🐋🐋" if i==0 else "🐋🐋" if i<3 else "🐋"
            dist=(mid-p)/mid*100
            st.markdown(f"**${p:,.2f}** {em} — ${u/1e3:.1f}K | -{dist:.2f}% below price")
    with wc2:
        st.markdown("**Sell Walls — price may reverse DOWN here**")
        for i,(p,q,u) in enumerate(au):
            bar=int(u/au[0][2]*100); em="🐋🐋🐋" if i==0 else "🐋🐋" if i<3 else "🐋"
            dist=(p-mid)/mid*100
            st.markdown(f"**${p:,.2f}** {em} — ${u/1e3:.1f}K | +{dist:.2f}% above price")

    if not tdf.empty:
        st.markdown("---")
        st.markdown("### 💹 Cumulative Delta")
        tdf["delta"]     = tdf.apply(lambda x: x["value"] if x["is_buyer"] else -x["value"],axis=1)
        tdf["cum_delta"] = tdf["delta"].cumsum()
        bvol = tdf[tdf["is_buyer"]]["value"].sum()
        svol = tdf[~tdf["is_buyer"]]["value"].sum()
        tv2  = bvol+svol; bpct2 = bvol/tv2*100 if tv2>0 else 50

        dc1,dc2,dc3 = st.columns(3)
        dc1.metric("Buy Vol",  f"${bvol/1e3:.1f}K", f"{bpct2:.1f}%")
        dc2.metric("Sell Vol", f"${svol/1e3:.1f}K", f"{100-bpct2:.1f}%")
        dc3.metric("Delta",    f"${(bvol-svol)/1e3:+.1f}K","Buyers winning" if bvol>svol else "Sellers winning")

        dfig = make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[0.5,0.5],vertical_spacing=0.05)
        dfig.add_trace(go.Scatter(x=tdf["time"],y=tdf["price"],name="Price",line=dict(color="#aaa",width=1)),row=1,col=1)
        dfig.add_trace(go.Scatter(x=tdf["time"],y=tdf["cum_delta"],name="Cum Delta",fill="tozeroy",
            line=dict(color="#00bfff",width=1.5),fillcolor="rgba(0,191,255,0.08)"),row=2,col=1)
        dfig.add_hline(y=0,line_dash="dash",line_color="white",opacity=0.3,row=2,col=1)
        dfig.update_layout(height=300,template="plotly_dark",paper_bgcolor="#050508",plot_bgcolor="#050508",
            title="Price + Cumulative Delta — Rising = more buying",margin=dict(t=40,b=20,l=10,r=10))
        dfig.update_xaxes(gridcolor="#0d0d18"); dfig.update_yaxes(gridcolor="#0d0d18")
        st.plotly_chart(dfig,use_container_width=True, key="pc_28")

        st.markdown("**Large Trades >$10K:**")
        lg = tdf[tdf["value"]>=10000].tail(15)
        if not lg.empty:
            for _,t in lg.iterrows():
                dr = "BUY" if t["is_buyer"] else "SELL"
                cl = "#00ff88" if t["is_buyer"] else "#ff4444"
                em = "🐋🐋🐋" if t["value"]>100000 else "🐋🐋" if t["value"]>50000 else "🐋"
                st.markdown(f"<span style='color:{cl};font-weight:700;'>{dr}</span> ${t['value']/1e3:.1f}K @ ${t['price']:,.2f} — {t['time'].strftime('%H:%M:%S')} {em}",unsafe_allow_html=True)
            if alerts_on and tg_token and tg_chat_id:
                for _,t in tdf[tdf["value"]>=100000].tail(2).iterrows():
                    send_tg(tg_token,tg_chat_id,f"🐋 WHALE TRADE\n{coin} {'BUY' if t['is_buyer'] else 'SELL'}\n${t['value']/1e3:.0f}K @ ${t['price']:,.2f}")
        else:
            st.info("No large trades in last 500 trades")

    st.markdown("---")
    st.markdown("### 🎯 Order Book Signal")
    obs=0; obr=[]
    if imb>10:    obs+=2; obr.append("Strong bid dominance ✅")
    elif imb>5:   obs+=1; obr.append("Moderate bid dominance ✅")
    elif imb<-10: obs-=2; obr.append("Strong ask dominance ⚠️")
    elif imb<-5:  obs-=1; obr.append("Moderate ask dominance ⚠️")
    if bu and abs(mid-bu[0][0])/mid<0.005: obs+=2; obr.append(f"Near biggest buy wall ${bu[0][0]:,.0f} ✅")
    if au and abs(mid-au[0][0])/mid<0.005: obs-=2; obr.append(f"Near biggest sell wall ${au[0][0]:,.0f} ⚠️")
    if not tdf.empty:
        if bvol>svol*1.3: obs+=1; obr.append("Buyers winning recent trades ✅")
        elif svol>bvol*1.3: obs-=1; obr.append("Sellers winning recent trades ⚠️")
    if obs>=2:   oss,osc="ORDER BOOK BULLISH 🟢","bull-signal"
    elif obs<=-2: oss,osc="ORDER BOOK BEARISH 🔴","bear-signal"
    else:         oss,osc="ORDER BOOK NEUTRAL ⚪","neutral-signal"
    st.markdown(f'<div class="signal-master {osc}">{oss} | Score: {obs}</div>',unsafe_allow_html=True)
    oc1,oc2=st.columns(2)
    with oc1:
        st.markdown("**Bullish:**")
        for r in obr:
            if "✅" in r: st.success(r)
    with oc2:
        st.markdown("**Bearish:**")
        for r in obr:
            if "⚠️" in r: st.error(r)
    if bu and au:
        st.info(f"Biggest Buy Wall: ${bu[0][0]:,.2f} (${bu[0][2]/1e3:.0f}K) | Biggest Sell Wall: ${au[0][0]:,.2f} (${au[0][2]/1e3:.0f}K)")
else:
    st.warning("Could not load order book. Check internet connection.")

# ════════════════════════════════════════════════════════════════
# LIQUIDATION LEVEL ESTIMATOR
# ════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("💥 Liquidation Level Estimator")
st.caption("Estimates where leveraged traders will get liquidated — price is magnetic to these levels (similar to CoinGlass heatmap)")

@st.cache_data(ttl=60)
def get_liquidation_data(symbol):
    try:
        # Get funding rate history
        url_fr = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}&limit=100"
        r_fr = requests.get(url_fr, timeout=10)
        fr_data = r_fr.json()

        # Get open interest history
        url_oi = f"https://fapi.binance.com/futures/data/openInterestHist?symbol={symbol}&period=1h&limit=48"
        r_oi = requests.get(url_oi, timeout=10)
        oi_data = r_oi.json()

        # Get mark price klines for price range
        url_mk = f"https://fapi.binance.com/fapi/v1/markPriceKlines?symbol={symbol}&interval=1h&limit=48"
        r_mk = requests.get(url_mk, timeout=10)
        mk_data = r_mk.json()

        return fr_data, oi_data, mk_data
    except Exception as e:
        return [], [], []

@st.cache_data(ttl=30)
def get_long_short_ratio(symbol):
    try:
        url = f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=1h&limit=24"
        r = requests.get(url, timeout=10)
        return r.json()
    except:
        return []

@st.cache_data(ttl=30)
def get_top_trader_ratio(symbol):
    try:
        url = f"https://fapi.binance.com/futures/data/topLongShortPositionRatio?symbol={symbol}&period=1h&limit=24"
        r = requests.get(url, timeout=10)
        return r.json()
    except:
        return []

futures_symbol = coin.replace("/USDT","") + "USDT"

with st.spinner("Loading liquidation data..."):
    fr_data, oi_data, mk_data = get_liquidation_data(futures_symbol)
    ls_ratio  = get_long_short_ratio(futures_symbol)
    top_ratio = get_top_trader_ratio(futures_symbol)

# Current price
curr_price = float(lat["close"])

# ── LONG SHORT RATIO
st.markdown("### ⚖️ Long/Short Ratio")
st.caption("More longs = more liquidations below. More shorts = more liquidations above.")

if ls_ratio and isinstance(ls_ratio, list) and len(ls_ratio) > 0 and isinstance(ls_ratio[0], dict):
    try:
        ls_df = pd.DataFrame(ls_ratio)
        ls_df["timestamp"] = pd.to_datetime(ls_df["timestamp"].astype(float), unit="ms")
        ls_df["longShortRatio"] = ls_df["longShortRatio"].astype(float)
        ls_df["longAccount"]    = ls_df["longAccount"].astype(float)
        ls_df["shortAccount"]   = ls_df["shortAccount"].astype(float)
    except Exception as e:
        st.warning(f"Long/Short ratio data unavailable from this region: {e}")
        ls_ratio = []

    latest_ls = ls_df.iloc[-1]
    lsr = float(latest_ls["longShortRatio"])
    long_pct  = float(latest_ls["longAccount"]) * 100
    short_pct = float(latest_ls["shortAccount"]) * 100

    lc1,lc2,lc3 = st.columns(3)
    lc1.metric("Long/Short Ratio", f"{lsr:.2f}",
               "More longs" if lsr > 1 else "More shorts")
    lc2.metric("Long Accounts",  f"{long_pct:.1f}%")
    lc3.metric("Short Accounts", f"{short_pct:.1f}%")

    if lsr > 1.5:
        st.warning(f"⚠️ {long_pct:.1f}% of traders are LONG — lots of liquidations BELOW current price. Smart money may push DOWN to grab them first!")
    elif lsr < 0.7:
        st.success(f"✅ {short_pct:.1f}% of traders are SHORT — lots of liquidations ABOVE current price. Smart money may push UP to grab them first!")
    else:
        st.info(f"⚪ Balanced market — {long_pct:.1f}% long vs {short_pct:.1f}% short")

    # L/S ratio chart
    ls_fig = go.Figure()
    ls_fig.add_trace(go.Scatter(
        x=ls_df["timestamp"], y=ls_df["longAccount"]*100,
        name="Longs %", fill="tozeroy",
        line=dict(color="#00ff88",width=2),
        fillcolor="rgba(0,255,136,0.15)"
    ))
    ls_fig.add_trace(go.Scatter(
        x=ls_df["timestamp"], y=ls_df["shortAccount"]*100,
        name="Shorts %", fill="tozeroy",
        line=dict(color="#ff4444",width=2),
        fillcolor="rgba(255,68,68,0.15)"
    ))
    ls_fig.add_hline(y=50, line_dash="dash", line_color="white", opacity=0.3)
    ls_fig.update_layout(
        height=250, template="plotly_dark",
        paper_bgcolor="#050508", plot_bgcolor="#050508",
        title="Long vs Short Account Ratio — 24H History",
        yaxis_title="% of Accounts",
        legend=dict(orientation="h"),
        margin=dict(t=40,b=20,l=10,r=10)
    )
    ls_fig.update_xaxes(gridcolor="#0d0d18")
    ls_fig.update_yaxes(gridcolor="#0d0d18")
    st.plotly_chart(ls_fig, use_container_width=True, key="pc_29")

# ── TOP TRADER RATIO
if top_ratio and isinstance(top_ratio, list) and len(top_ratio) > 0 and isinstance(top_ratio[0], dict):
    st.markdown("### 🏆 Top Trader Long/Short Ratio")
    st.caption("What are the BIG traders doing? This matters more than retail.")
    try:
        tt_df = pd.DataFrame(top_ratio)
        tt_df["timestamp"]       = pd.to_datetime(tt_df["timestamp"].astype(float), unit="ms")
        tt_df["longShortRatio"]  = tt_df["longShortRatio"].astype(float)
        tt_df["longAccount"]     = tt_df["longAccount"].astype(float)
        tt_df["shortAccount"]    = tt_df["shortAccount"].astype(float)
    except:
        tt_df = pd.DataFrame()

    latest_tt = tt_df.iloc[-1]
    tt_lsr    = float(latest_tt["longShortRatio"])
    tt_long   = float(latest_tt["longAccount"]) * 100
    tt_short  = float(latest_tt["shortAccount"]) * 100

    tc1,tc2,tc3 = st.columns(3)
    tc1.metric("Top Trader L/S", f"{tt_lsr:.2f}",
               "Whales buying" if tt_lsr > 1 else "Whales selling")
    tc2.metric("Top Trader Longs",  f"{tt_long:.1f}%")
    tc3.metric("Top Trader Shorts", f"{tt_short:.1f}%")

    if tt_lsr > 1.3:
        st.success(f"✅ Top traders {tt_long:.1f}% LONG — whales are bullish! Follow the smart money UP")
    elif tt_lsr < 0.8:
        st.error(f"🔴 Top traders {tt_short:.1f}% SHORT — whales are bearish! Follow the smart money DOWN")
    else:
        st.info("⚪ Top traders balanced — no clear whale direction")

    tt_fig = go.Figure()
    tt_fig.add_trace(go.Scatter(
        x=tt_df["timestamp"], y=tt_df["longAccount"]*100,
        name="Top Long %", line=dict(color="#FFD700",width=2)
    ))
    tt_fig.add_trace(go.Scatter(
        x=tt_df["timestamp"], y=tt_df["shortAccount"]*100,
        name="Top Short %", line=dict(color="#ff8800",width=2)
    ))
    tt_fig.add_hline(y=50, line_dash="dash", line_color="white", opacity=0.3)
    tt_fig.update_layout(
        height=220, template="plotly_dark",
        paper_bgcolor="#050508", plot_bgcolor="#050508",
        title="Top Trader Positions — 24H",
        legend=dict(orientation="h"),
        margin=dict(t=40,b=20,l=10,r=10)
    )
    tt_fig.update_xaxes(gridcolor="#0d0d18")
    tt_fig.update_yaxes(gridcolor="#0d0d18")
    st.plotly_chart(tt_fig, use_container_width=True, key="pc_30")

st.markdown("---")

# ── LIQUIDATION LEVEL ESTIMATOR
st.markdown("### 💥 Estimated Liquidation Clusters")
st.caption("Based on price range + leverage levels. Yellow = biggest cluster = price magnet!")

# Build liquidation heatmap estimation
# Most retail traders use 5x, 10x, 20x leverage
# At 10x leverage: liquidated at 10% move
# At 20x leverage: liquidated at 5% move
# At 5x leverage:  liquidated at 20% move

leverage_levels = {
    "2x":  0.50,  # liquidated at 50% move
    "3x":  0.33,  # liquidated at 33% move
    "5x":  0.20,  # liquidated at 20% move
    "10x": 0.10,  # liquidated at 10% move
    "20x": 0.05,  # liquidated at 5% move
    "50x": 0.02,  # liquidated at 2% move
    "100x":0.01,  # liquidated at 1% move
}

# Most popular leverage = 10x and 20x
# Generate liquidation price levels
liq_levels = []
price_range = curr_price * 0.15  # look 15% each side

for lev_name, liq_pct in leverage_levels.items():
    # Long liquidations (below current price)
    long_liq_price = curr_price * (1 - liq_pct)
    # Short liquidations (above current price)
    short_liq_price = curr_price * (1 + liq_pct)

    # Weight by popularity of leverage (10x and 20x most popular)
    weight_map = {"2x":0.5,"3x":0.6,"5x":0.8,"10x":1.0,"20x":0.9,"50x":0.6,"100x":0.4}
    weight = weight_map.get(lev_name, 0.5)

    liq_levels.append({
        "leverage":    lev_name,
        "long_liq":    long_liq_price,
        "short_liq":   short_liq_price,
        "weight":      weight,
        "liq_pct":     liq_pct * 100,
        "type":        "long"
    })

# Sort by price
long_liqs  = sorted(liq_levels, key=lambda x: x["long_liq"],  reverse=True)
short_liqs = sorted(liq_levels, key=lambda x: x["short_liq"])

liq_col1, liq_col2 = st.columns(2)

with liq_col1:
    st.markdown("**🔴 Long Liquidation Levels (below price)**")
    st.caption("If price drops here → these longs get liquidated")
    for item in long_liqs:
        price  = item["long_liq"]
        weight = item["weight"]
        dist   = (curr_price - price) / curr_price * 100
        bar    = int(weight * 100)
        if weight >= 0.9:   color, emoji = "#ff4444", "🔥🔥🔥 MAJOR"
        elif weight >= 0.7: color, emoji = "#ff8800", "🔥🔥 Strong"
        else:               color, emoji = "#ff4444", "🔥 Moderate"
        st.markdown(f"""
        <div style="background:#0d0d1a;border-left:3px solid {color};
        border-radius:4px;padding:8px;margin:3px 0;position:relative;overflow:hidden;">
        <div style="position:absolute;top:0;left:0;height:100%;width:{bar}%;
        background:rgba(255,68,68,{weight*0.2:.2f});"></div>
        <b style="color:{color};">${price:,.0f}</b>
        <span style="float:right;font-size:11px;">{emoji}</span><br>
        <span style="color:#aaa;font-size:12px;">
        {item['leverage']} leverage | -{dist:.1f}% from price
        </span>
        </div>
        """, unsafe_allow_html=True)

with liq_col2:
    st.markdown("**🟢 Short Liquidation Levels (above price)**")
    st.caption("If price rises here → these shorts get liquidated")
    for item in short_liqs:
        price  = item["short_liq"]
        weight = item["weight"]
        dist   = (price - curr_price) / curr_price * 100
        bar    = int(weight * 100)
        if weight >= 0.9:   color, emoji = "#00ff88", "🔥🔥🔥 MAJOR"
        elif weight >= 0.7: color, emoji = "#00cc66", "🔥🔥 Strong"
        else:               color, emoji = "#00aa44", "🔥 Moderate"
        st.markdown(f"""
        <div style="background:#0d0d1a;border-left:3px solid {color};
        border-radius:4px;padding:8px;margin:3px 0;position:relative;overflow:hidden;">
        <div style="position:absolute;top:0;left:0;height:100%;width:{bar}%;
        background:rgba(0,255,136,{weight*0.2:.2f});"></div>
        <b style="color:{color};">${price:,.0f}</b>
        <span style="float:right;font-size:11px;">{emoji}</span><br>
        <span style="color:#aaa;font-size:12px;">
        {item['leverage']} leverage | +{dist:.1f}% from price
        </span>
        </div>
        """, unsafe_allow_html=True)

# ── LIQUIDATION HEATMAP CHART
st.markdown(" ")
st.markdown("### 🌡️ Liquidation Heatmap Chart")
st.caption("Similar to CoinGlass — thicker/brighter bar = bigger liquidation cluster = stronger price magnet")

heat_fig = go.Figure()

# Add price line
heat_fig.add_hline(
    y=curr_price,
    line_dash="solid", line_color="white", line_width=2,
    annotation_text=f"Current ${curr_price:,.0f}",
    annotation_font_color="white",
    annotation_position="right"
)

# Plot long liquidation bars
for item in long_liqs:
    price  = item["long_liq"]
    weight = item["weight"]
    opacity = weight * 0.8
    bar_width = weight * 0.8
    color_intensity = int(weight * 255)
    heat_fig.add_shape(
        type="rect",
        x0=0, x1=weight,
        y0=price - curr_price*0.002,
        y1=price + curr_price*0.002,
        fillcolor=f"rgba({color_intensity},50,50,{opacity:.2f})",
        line=dict(color=f"rgba(255,50,50,{opacity:.2f})", width=1),
    )
    heat_fig.add_annotation(
        x=weight + 0.02, y=price,
        text=f"{item['leverage']} — ${price:,.0f}",
        showarrow=False,
        font=dict(color="#ff8888", size=10),
        xanchor="left"
    )

# Plot short liquidation bars
for item in short_liqs:
    price  = item["short_liq"]
    weight = item["weight"]
    opacity = weight * 0.8
    color_intensity = int(weight * 255)
    heat_fig.add_shape(
        type="rect",
        x0=0, x1=weight,
        y0=price - curr_price*0.002,
        y1=price + curr_price*0.002,
        fillcolor=f"rgba(50,{color_intensity},80,{opacity:.2f})",
        line=dict(color=f"rgba(50,255,100,{opacity:.2f})", width=1),
    )
    heat_fig.add_annotation(
        x=weight + 0.02, y=price,
        text=f"{item['leverage']} — ${price:,.0f}",
        showarrow=False,
        font=dict(color="#88ff88", size=10),
        xanchor="left"
    )

# Price range
all_prices = [item["long_liq"] for item in long_liqs] + [item["short_liq"] for item in short_liqs]
y_min = min(all_prices) * 0.998
y_max = max(all_prices) * 1.002

heat_fig.update_layout(
    height=500,
    template="plotly_dark",
    paper_bgcolor="#050508",
    plot_bgcolor="#0a0a0f",
    title=f"Estimated Liquidation Heatmap — {coin} @ ${curr_price:,.0f}",
    xaxis=dict(visible=False, range=[0, 1.3]),
    yaxis=dict(
        title="Price Level",
        range=[y_min, y_max],
        gridcolor="#0d0d18"
    ),
    margin=dict(t=50, b=20, l=80, r=150),
    showlegend=False
)
st.plotly_chart(heat_fig, use_container_width=True, key="pc_31")

# ── KEY LIQUIDATION TARGETS
st.markdown("### 🎯 Key Liquidation Price Targets")
st.caption("Smart money hunts these levels. Watch for price to sweep here then reverse!")

# Most important levels — 10x and 20x (most popular leverage)
major_long_liq  = curr_price * 0.90   # 10x long liq
major_short_liq = curr_price * 1.10   # 10x short liq
liq_20x_long    = curr_price * 0.95   # 20x long liq
liq_20x_short   = curr_price * 1.05   # 20x short liq
liq_50x_long    = curr_price * 0.98   # 50x long liq
liq_50x_short   = curr_price * 1.02   # 50x short liq

kc1,kc2,kc3 = st.columns(3)
with kc1:
    st.markdown(f"""
    <div style="background:#0d0d1a;border:1px solid #ff444433;border-radius:8px;padding:12px;text-align:center;">
    <b style="color:#ff4444;">50x Long Liq</b><br>
    <b style="font-size:20px;color:#ff4444;">${liq_50x_long:,.0f}</b><br>
    <span style="color:#888;font-size:12px;">-2% from price<br>🔥🔥🔥 Nearest target</span>
    </div>
    """, unsafe_allow_html=True)
with kc2:
    st.markdown(f"""
    <div style="background:#0d0d1a;border:1px solid #ff880033;border-radius:8px;padding:12px;text-align:center;">
    <b style="color:#ff8800;">20x Long Liq</b><br>
    <b style="font-size:20px;color:#ff8800;">${liq_20x_long:,.0f}</b><br>
    <span style="color:#888;font-size:12px;">-5% from price<br>🔥🔥 Strong target</span>
    </div>
    """, unsafe_allow_html=True)
with kc3:
    st.markdown(f"""
    <div style="background:#0d0d1a;border:1px solid #ff444433;border-radius:8px;padding:12px;text-align:center;">
    <b style="color:#ff4444;">10x Long Liq</b><br>
    <b style="font-size:20px;color:#ff4444;">${major_long_liq:,.0f}</b><br>
    <span style="color:#888;font-size:12px;">-10% from price<br>🔥 Major target</span>
    </div>
    """, unsafe_allow_html=True)

kc4,kc5,kc6 = st.columns(3)
with kc4:
    st.markdown(f"""
    <div style="background:#0d0d1a;border:1px solid #00ff8833;border-radius:8px;padding:12px;text-align:center;">
    <b style="color:#00ff88;">50x Short Liq</b><br>
    <b style="font-size:20px;color:#00ff88;">${liq_50x_short:,.0f}</b><br>
    <span style="color:#888;font-size:12px;">+2% from price<br>🔥🔥🔥 Nearest target</span>
    </div>
    """, unsafe_allow_html=True)
with kc5:
    st.markdown(f"""
    <div style="background:#0d0d1a;border:1px solid #00ff8833;border-radius:8px;padding:12px;text-align:center;">
    <b style="color:#00ff88;">20x Short Liq</b><br>
    <b style="font-size:20px;color:#00ff88;">${liq_20x_short:,.0f}</b><br>
    <span style="color:#888;font-size:12px;">+5% from price<br>🔥🔥 Strong target</span>
    </div>
    """, unsafe_allow_html=True)
with kc6:
    st.markdown(f"""
    <div style="background:#0d0d1a;border:1px solid #00ff8833;border-radius:8px;padding:12px;text-align:center;">
    <b style="color:#00ff88;">10x Short Liq</b><br>
    <b style="font-size:20px;color:#00ff88;">${major_short_liq:,.0f}</b><br>
    <span style="color:#888;font-size:12px;">+10% from price<br>🔥 Major target</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ── HOW TO TRADE LIQUIDATION LEVELS
st.markdown("### 📚 How To Trade Liquidation Levels")
col_a, col_b = st.columns(2)
with col_a:
    st.success("""
**LONG Setup using liquidation levels:**

1. Price drops toward long liq level (e.g. $74,000)
2. You see a liquidity sweep on 15m
3. BOS forms on 15m after the sweep
4. CHoCH confirms reversal
5. Enter long — target: next short liq above
6. SL: below the liq level
    """)
with col_b:
    st.error("""
**SHORT Setup using liquidation levels:**

1. Price pumps toward short liq level (e.g. $76,000)
2. You see a sell liquidity sweep on 15m
3. BOS forms down on 15m
4. CHoCH confirms reversal down
5. Enter short — target: next long liq below
6. SL: above the liq level
    """)

st.info("""
💡 **Pro Tip:** Combine liquidation levels with your dashboard signals!
- Liquidation level + Discount Zone + BOS = Very strong long setup
- Liquidation level + Premium Zone + CHoCH = Very strong short setup
- Always wait for CONFIRMATION before entering — never trade into the level
""")

# ════════════════════════════════════════════════════════════════
# CHART PATTERN DETECTION
# ════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("📐 Chart Pattern Detection")
st.caption("Automatically scans your chart for the most important trading patterns")



# ── VOLUME PROFILE
def calculate_volume_profile(df, bins=30):
    price_min = df["low"].min()
    price_max = df["high"].max()
    price_range = price_max - price_min
    if price_range == 0:
        return pd.DataFrame()
    bin_size = price_range / bins
    vp = []
    for i in range(bins):
        level_low  = price_min + i * bin_size
        level_high = price_min + (i + 1) * bin_size
        level_mid  = (level_low + level_high) / 2
        mask = (df["high"] >= level_low) & (df["low"] <= level_high)
        vol_at_level = df.loc[mask, "volume"].sum()
        buy_vol  = df.loc[mask & (df["close"] >= df["open"]), "volume"].sum()
        sell_vol = df.loc[mask & (df["close"] <  df["open"]), "volume"].sum()
        vp.append({"price":level_mid,"volume":vol_at_level,
                   "buy_vol":buy_vol,"sell_vol":sell_vol,
                   "level_low":level_low,"level_high":level_high})
    vp_df = pd.DataFrame(vp)
    if not vp_df.empty and vp_df["volume"].sum() > 0:
        max_vol = vp_df["volume"].max()
        vp_df["vol_pct"] = vp_df["volume"] / max_vol * 100
        poc_idx = vp_df["volume"].idxmax()
        vp_df["is_poc"] = False
        vp_df.at[poc_idx, "is_poc"] = True
        total_vol = vp_df["volume"].sum()
        va_threshold = total_vol * 0.70
        sorted_vp = vp_df.sort_values("volume", ascending=False)
        va_vol = 0; va_prices = []
        for _, row in sorted_vp.iterrows():
            va_vol += row["volume"]
            va_prices.append(row["price"])
            if va_vol >= va_threshold:
                break
        vp_df["in_value_area"] = vp_df["price"].isin(va_prices)
        vp_df["vah"] = max(va_prices) if va_prices else price_max
        vp_df["val"] = min(va_prices) if va_prices else price_min
    return vp_df

st.markdown("---")
st.caption("Education only. Never risk money you cannot afford to lose.")
