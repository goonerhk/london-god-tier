import streamlit as st
import pandas as pd
import pytz
from datetime import datetime, time, timedelta
from twelvedata import TDClient

st.set_page_config(page_title="LONDON GOD TIER", layout="wide")

# ========================= SECRETS =========================
API_KEY = st.secrets["TWELVE_DATA_KEY"]
td = TDClient(apikey=API_KEY)

# ========================= ASSETS & TIMEFRAMES =========================
ASSETS = [
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD", "USD/CAD", "NZD/USD",
    "EUR/GBP", "EUR/JPY", "EUR/CHF", "EUR/AUD", "EUR/CAD", "EUR/NZD",
    "GBP/JPY", "GBP/CHF", "GBP/AUD", "GBP/CAD", "GBP/NZD",
    "AUD/JPY", "AUD/CHF", "AUD/CAD", "AUD/NZD",
    "CAD/JPY", "CAD/CHF", "CHF/JPY", "NZD/JPY", "NZD/CHF"
]

TIMEFRAMES = {'1D': 'daily', '1h': '60min', '5m': '5min', '4h': '240min'}

HKT = pytz.timezone('Asia/Hong_Kong')
NYT = pytz.timezone('America/New_York')

# ========================= ALL YOUR ORIGINAL FUNCTIONS =========================
def get_session(t):
    if t is None: return None
    t = t.time()
    if time(14,0) <= t <= time(19,59): return "CBDR"
    if time(20,0) <= t or t < time(3,0): return "Asian"
    return None

def detect_prior_day_pattern(df):
    if len(df) < 3: return "Other"
    today = df.iloc[-1]; yesterday = df.iloc[-2]
    if (yesterday['close'] < yesterday['open'] and today['close'] > today['open'] and
        today['open'] < yesterday['close'] and today['close'] > yesterday['open']):
        return "Bullish Engulfing"
    if (yesterday['close'] > yesterday['open'] and today['close'] < today['open'] and
        today['open'] > yesterday['close'] and today['close'] < yesterday['open']):
        return "Bearish Engulfing"
    if today['high'] > yesterday['high'] and today['low'] > yesterday['low']: return "Bullish HH/HL"
    if today['high'] < yesterday['high'] and today['low'] < yesterday['low']: return "Bearish LH/LL"
    return "Other"

def get_daily_trend(df):
    if len(df) < 30: return "Neutral"
    sma10 = df['close'].rolling(10).mean().iloc[-1]
    sma20 = df['close'].rolling(20).mean().iloc[-1]
    return "Bullish" if sma10 > sma20 else "Bearish"

def get_candle_confirmation(df):
    if len(df) < 3: return ""
    yest = df.iloc[-2]; before = df.iloc[-3]
    if yest['close'] > before['high']: return "Bullish CC"
    if yest['close'] < before['low']: return "Bearish CC"
    return ""

def get_order_block(df):
    if len(df) < 3: return ""
    prior = df.iloc[-2]; before = df.iloc[-3]
    if (prior['close'] > prior['open'] and before['close'] < before['open'] and prior['high'] > before['high']):
        return "Bullish OB Confirmed"
    if (prior['close'] < prior['open'] and before['close'] > before['open'] and prior['low'] < before['low']):
        return "Bearish OB Confirmed"
    return ""

def get_fvg(df):
    if len(df) < 3: return ""
    last = df.iloc[-1]; two_before = df.iloc[-3]
    if last['low'] > two_before['high']: return "Bullish FVG Confirmed"
    if last['high'] < two_before['low']: return "Bearish FVG Confirmed"
    return ""

# ========================= FETCH DATA =========================
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_all_data():
    all_data = {}
    for asset in ASSETS:
        asset_data = {}
        for tf, interval in TIMEFRAMES.items():
            try:
                ts = td.time_series(symbol=asset, interval=interval, outputsize=200, timezone="America/New_York").as_pandas()
                ts = ts.reset_index()
                ts.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
                ts['datetime'] = pd.to_datetime(ts['datetime'])
                ts['date_ny'] = ts['datetime'].dt.date
                ts['time_ny'] = ts['datetime'].dt.time
                ts['session'] = ts['time_ny'].apply(get_session)
                asset_data[tf] = ts
            except Exception as e:
                st.error(f"Error {asset} {tf}: {e}")
        if asset_data: all_data[asset] = asset_data
    return all_data

# ========================= MAIN =========================
st.title("LONDON GOD TIER DASHBOARD")
st.caption(f"Last update: {datetime.now(HKT).strftime('%Y-%m-%d %H:%M HKT')} | Refreshes at 06:05, 07:05, 11:05, 13:05, 15:05, 19:05 HKT")

data = fetch_all_data()

rows = []
for asset, tfs in data.items():
    if '1D' not in tfs or '5m' not in tfs: continue
    
    dfd = tfs['1D'].copy()
    df5 = tfs['5m'].copy()
    df4h = tfs.get('4h', pd.DataFrame())
    
    latest = df5.iloc[-1]
    mult = 100 if 'JPY' in asset else 10000
    
    # CBDR & Asian
    today_ny = latest['datetime'].date()
    cbdr_today = df5[(df5['date_ny'] == today_ny) & (df5['session'] == 'CBDR')]
    asian_today = df5[(df5['date_ny'] == today_ny) & (df5['session'] == 'Asian')]
    
    cbdr_pips = round((cbdr_today['high'].max() - cbdr_today['low'].min()) * mult, 1) if not cbdr_today.empty else 0
    asian_pips = round((asian_today['high'].max() - asian_today['low'].min()) * mult, 1) if not asian_today.empty else 0
    
    ideal_cbdr = "Ideal" if cbdr_pips < 40 else ""
    ideal_asian = "Delayed Protraction" if asian_pips > 40 else "Ideal" if 20 <= asian_pips <= 30 else ""
    
    # Prior day & 5D ADR
    prior_day = dfd.iloc[-2] if len(dfd) >= 2 else None
    prior_pips = round((prior_day['high'] - prior_day['low']) * mult, 1) if prior_day is not None else 0
    adr5 = round(dfd.tail(6).head(5)['high'].sub(dfd.tail(6).head(5)['low']).mean() * mult, 1)
    
    # Analysis
    pattern = detect_prior_day_pattern(dfd.tail(10))
    trend = get_daily_trend(dfd.tail(30))
    cc = get_candle_confirmation(dfd.tail(10))
    ob = get_order_block(dfd.tail(10))
    fvg = get_fvg(dfd.tail(10))
    fourh_cc = get_candle_confirmation(df4h.tail(10)) if not df4h.empty else ""
    
    # Last 3D arrows
    arrows = "".join(
        "Up" if r['close'] >= r['open'] else "Down"
        for _, r in dfd.tail(3).iterrows()
    )
    
    rows.append({
        "Asset": asset.replace("/", ""),
        "CBDR": cbdr_pips,
        "Ideal CBDR": ideal_cbdr,
        "Asian": asian_pips,
        "Asian Status": ideal_asian,
        "Prior Day": prior_pips,
        "5D ADR": adr5,
        "Pattern": pattern,
        "Daily CC": cc,
        "Order Block": ob,
        "FVG": fvg,
        "4H CC": fourh_cc,
        "Trend": trend,
        "Last 3D": arrows,
    })

df = pd.DataFrame(rows)
df = df.sort_values(by="Asset", key=lambda x: x.map({a.replace("/", ""): i for i, a in enumerate(ASSETS)}))

# Color styling
def color_cells(val):
    if "Bullish" in str(val): return "color: #00FF00; font-weight: bold"
    if "Bearish" in str(val): return "color: #FF4444; font-weight: bold"
    if val == "Ideal": return "color: #00FF88"
    if "Delayed" in str(val): return "color: #FFAA00"
    return ""

styled = df.style.map(color_cells)
st.dataframe(styled, use_container_width=True, height=800)

st.success("27 Pairs · Live · Hong Kong Times · 100% Your Dashboard")
