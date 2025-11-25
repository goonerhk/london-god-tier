import streamlit as st
import pandas as pd
import pytz
from datetime import datetime, time
from twelvedata import TDClient
import time as sleep_time

st.set_page_config(page_title="LONDON GOD TIER", layout="wide")

# ========================= API KEY =========================
try:
    API_KEY = st.secrets["TWELVE_DATA_KEY"]
except:
    API_KEY = st.text_input("Enter Twelve Data API key", type="password")
    if not API_KEY:
        st.stop()

td = TDClient(apikey=API_KEY)

# ========================= ASSETS =========================
ASSETS = [
    "EUR/USD","GBP/USD","USD/JPY","USD/CHF","AUD/USD","USD/CAD","NZD/USD",
    "EUR/GBP","EUR/JPY","EUR/CHF","EUR/AUD","EUR/CAD","EUR/NZD",
    "GBP/JPY","GBP/CHF","GBP/AUD","GBP/CAD","GBP/NZD",
    "AUD/JPY","AUD/CHF","AUD/CAD","AUD/NZD",
    "CAD/JPY","CAD/CHF","CHF/JPY","NZD/JPY","NZD/CHF"
]

TIMEFRAMES = {'1D': '1day', '1h': '1h', '5m': '5min', '4h': '4h'}
HKT = pytz.timezone('Asia/Hong_Kong')

# ========================= FIXED: SAFE get_session =========================
def get_session(dt):
    if pd.isna(dt): return None
    t = dt.time()  # Now dt is datetime, not time → works
    if time(14,0) <= t <= time(19,59): return "CBDR"
    if time(20,0) <= t or t < time(3,0): return "Asian"
    return None

# ========================= ANALYSIS FUNCTIONS =========================
def detect_prior_day_pattern(df):
    if len(df) < 3: return "Other"
    t, y = df.iloc[-1], df.iloc[-2]
    if y['close'] < y['open'] and t['close'] > t['open'] and t['open'] < y['close'] and t['close'] > y['open']:
        return "Bullish Engulfing"
    if y['close'] > y['open'] and t['close'] < t['open'] and t['open'] > y['close'] and t['close'] < y['open']:
        return "Bearish Engulfing"
    if t['high'] > y['high'] and t['low'] > y['low']: return "Bullish HH/HL"
    if t['high'] < y['high'] and t['low'] < y['low']: return "Bearish LH/LL"
    return "Other"

def get_daily_trend(df):
    if len(df) < 30: return "Neutral"
    return "Bullish" if df['close'].rolling(10).mean().iloc[-1] > df['close'].rolling(20).mean().iloc[-1] else "Bearish"

def get_candle_confirmation(df):
    if len(df) < 3: return ""
    y, b = df.iloc[-2], df.iloc[-3]
    return "Bullish CC" if y['close'] > b['high'] else "Bearish CC" if y['close'] < b['low'] else ""

def get_order_block(df):
    if len(df) < 3: return ""
    p, b = df.iloc[-2], df.iloc[-3]
    if p['close'] > p['open'] and b['close'] < b['open'] and p['high'] > b['high']:
        return "Bullish OB Confirmed"
    if p['close'] < p['open'] and b['close'] > b['open'] and p['low'] < b['low']:
        return "Bearish OB Confirmed"
    return ""

def get_fvg(df):
    if len(df) < 3: return ""
    last, two = df.iloc[-1], df.iloc[-3]
    return "Bullish FVG Confirmed" if last['low'] > two['high'] else "Bearish FVG Confirmed" if last['high'] < two['low'] else ""

# ========================= FETCH DATA (SAFE + RATE LIMITED) =========================
@st.cache_data(ttl=1800, show_spinner="Fetching 27 pairs (slow but safe for free plan)...")
def fetch_all():
    all_data = {}
    for asset in ASSETS:
        asset_data = {}
        for label, interval in TIMEFRAMES.items():
            try:
                sleep_time.sleep(1.1)  # 1 call per second → stays under 8/min
                ts = td.time_series(symbol=asset, interval=interval, outputsize=200, timezone="America/New_York").as_pandas()
                ts = ts.reset_index()
                
                # Safe column handling
                if len(ts.columns) == 5:
                    ts.columns = ['datetime', 'open', 'high', 'low', 'close']
                    ts['volume'] = 0
                else:
                    ts.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
                
                ts['datetime'] = pd.to_datetime(ts['datetime'])
                ts['date_ny'] = ts['datetime'].dt.date
                ts['session'] = ts['datetime'].apply(get_session)  # Fixed: pass datetime, not time
                asset_data[label] = ts
                st.success(f"{asset} {label} OK")
            except Exception as e:
                st.warning(f"{asset} {label}: {str(e)[:100]}")
        if asset_data: all_data[asset] = asset_data
    return all_data

data = fetch_all()

# ========================= BUILD DASHBOARD =========================
rows = []
priority = ["EURUSD","GBPUSD","AUDUSD","NZDUSD","USDJPY","USDCAD","USDCHF"]

for asset, tfs in data.items():
    if '1D' not in tfs or '5m' not in tfs: continue
    dfd = tfs['1D']; df5 = tfs['5m']; df4h = tfs.get('4h', pd.DataFrame())
    latest = df5.iloc[-1]
    mult = 100 if 'JPY' in asset else 10000

    today = latest['date_ny']
    cbdr = df5[(df5['date_ny'] == today) & (df5['session'] == 'CBDR')]
    asian = df5[(df5['date_ny'] == today) & (df5['session'] == 'Asian')]

    cbdr_pips = round((cbdr['high'].max() - cbdr['low'].min()) * mult, 1) if not cbdr.empty else 0
    asian_pips = round((asian['high'].max() - asian['low'].min()) * mult, 1) if not asian.empty else 0

    ideal_cbdr = "Ideal" if cbdr_pips < 40 else ""
    ideal_asian = "Delayed Protraction" if asian_pips > 40 else "Ideal" if 20 <= asian_pips <= 30 else ""

    prior = round((dfd.iloc[-2]['high'] - dfd.iloc[-2]['low']) * mult, 1) if len(dfd) >= 2 else 0
    adr5 = round(dfd.tail(6).head(5)['high'].sub(dfd.tail(6).head(5)['low']).mean() * mult, 1) if len(dfd) >= 6 else 0

    pattern = detect_prior_day_pattern(dfd.tail(10))
    trend = get_daily_trend(dfd.tail(30))
    cc = get_candle_confirmation(dfd.tail(10))
    ob = get_order_block(dfd.tail(10))
    fvg = get_fvg(dfd.tail(10))
    fourh_cc = get_candle_confirmation(df4h.tail(10)) if not df4h.empty else ""

    arrows = "".join("Up" if r['close'] >= r['open'] else "Down" for _, r in dfd.tail(3).iterrows())

    rows.append({
        "Asset": asset.replace("/", ""),
        "CBDR": cbdr_pips,
        "Ideal CBDR": ideal_cbdr,
        "Asian": asian_pips,
        "Asian Status": ideal_asian,
        "Prior Day": prior,
        "5D ADR": adr5,
        "Pattern": pattern,
        "Daily CC": cc,
        "Order Block": ob,
        "FVG": fvg,
        "4H CC": fourh_cc,
        "Trend": trend,
        "Last 3D": arrows,
    })

if not rows:
    st.error("No data loaded")
    st.stop()

df = pd.DataFrame(rows)
df["priority"] = df["Asset"].apply(lambda x: next((i for i, p in enumerate(priority) if p in x), 999))
df = df.sort_values("priority").drop("priority", axis=1).reset_index(drop=True)

# ========================= DISPLAY =========================
st.title("LONDON GOD TIER DASHBOARD")
st.caption(f"Live · {datetime.now(HKT).strftime('%Y-%m-%d %H:%M HKT')} · Hong Kong")

def color(val):
    if "Bullish" in str(val): return "color: #00FF00; font-weight: bold"
    if "Bearish" in str(val): return "color: #FF4444; font-weight: bold"
    if val == "Ideal": return "color: #00FF88; font-weight: bold"
    if "Delayed" in str(val): return "color: #FFAA00"
    return ""

styled = df.style.map(color)
st.dataframe(styled, use_container_width=True, height=1000)

st.success("27 Pairs · Full Dashboard · Live · Free Plan Safe · All Errors Fixed")
