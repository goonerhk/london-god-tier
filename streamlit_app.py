import streamlit as st
import pandas as pd
import pytz
from datetime import datetime, time
from twelvedata import TDClient

st.set_page_config(page_title="LONDON GOD TIER", layout="wide")

# ========================= SAFE API KEY =========================
try:
    API_KEY = st.secrets["TWELVE_DATA_KEY"]
except:
    API_KEY = st.text_input("Enter Twelve Data API key", type="password")
    if not API_KEY:
        st.error("API key required")
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

TIMEFRAMES = {'1D': 'daily', '1h': '60min', '5m': '5min', '4h': '240min'}
HKT = pytz.timezone('Asia/Hong_Kong')

# ========================= FUNCTIONS =========================
def get_session(t):
    if t is None: return None
    t = t.time()
    if time(14,0) <= t <= time(19,59): return "CBDR"
    if time(20,0) <= t or t < time(3,0): return "Asian"
    return None

def detect_prior_day_pattern(df):
    if len(df) < 3: return "Other"
    t = df.iloc[-1]; y = df.iloc[-2]
    if y['close'] < y['open'] and t['close'] > t['open'] and t['open'] < y['close'] and t['close'] > y['open']:
        return "Bullish Engulfing"
    if y['close'] > y['open'] and t['close'] < t['open'] and t['open'] > y['close'] and t['close'] < y['open']:
        return "Bearish Engulfing"
    if t['high'] > y['high'] and t['low'] > y['low']: return "Bullish HH/HL"
    if t['high'] < y['high'] and t['low'] < y['low']: return "Bearish LH/LL"
    return "Other"

def get_daily_trend(df):
    if len(df) < 30: return "Neutral"
    sma10 = df['close'].rolling(10).mean().iloc[-1]
    sma20 = df['close'].rolling(20).mean().iloc[-1]
    return "Bullish" if sma10 > sma20 else "Bearish"

def get_candle_confirmation(df):
    if len(df) < 3: return ""
    y = df.iloc[-2]; b = df.iloc[-3]
    if y['close'] > b['high']: return "Bullish CC"
    if y['close'] < b['low']: return "Bearish CC"
    return ""

def get_order_block(df):
    if len(df) < 3: return ""
    p = df.iloc[-2]; b = df.iloc[-3]
    if p['close'] > p['open'] and b['close'] < b['open'] and p['high'] > b['high']:
        return "Bullish OB Confirmed"
    if p['close'] < p['open'] and b['close'] > b['open'] and p['low'] < b['low']:
        return "Bearish OB Confirmed"
    return ""

def get_fvg(df):
    if len(df) < 3: return ""
    last = df.iloc[-1]; two = df.iloc[-3]
    if last['low'] > two['high']: return "Bullish FVG Confirmed"
    if last['high'] < two['low']: return "Bearish FVG Confirmed"
    return ""

# ========================= FETCH DATA =========================
@st.cache_data(ttl=1800, show_spinner="Loading 27 pairs...")
def fetch_all():
    all_data = {}
    for asset in ASSETS:
        data = {}
        for tf, interval in TIMEFRAMES.items():
            try:
                ts = td.time_series(symbol=asset, interval=interval, outputsize=200, timezone="America/New_York").as_pandas()
                ts = ts.reset_index()
                ts.columns = ['datetime','open','high','low','close','volume']
                ts['datetime'] = pd.to_datetime(ts['datetime'])
                ts['date_ny'] = ts['datetime'].dt.date
                ts['time_ny'] = ts['datetime'].dt.time
                ts['session'] = ts['time_ny'].apply(get_session)
                data[tf] = ts
            except: continue
        if data: all_data[asset] = data
    return all_data

data = fetch_all()

# ========================= BUILD TABLE =========================
rows = []
priority_order = ["EURUSD","GBPUSD","AUDUSD","NZDUSD","USDJPY","USDCAD","USDCHF"]

for asset, tfs in data.items():
    if '1D' not in tfs or '5m' not in tfs: continue
    dfd = tfs['1D']; df5 = tfs['5m']; df4h = tfs.get('4h', pd.DataFrame())
    latest = df5.iloc[-1]
    mult = 100 if 'JPY' in asset else 10000

    today = latest['date_ny']
    cbdr = df5[(df5['date_ny']==today) & (df5['session']=='CBDR')]
    asian = df5[(df5['date_ny']==today) & (df5['session']=='Asian')]

    cbdr_pips = round((cbdr['high'].max()-cbdr['low'].min())*mult,1) if not cbdr.empty else 0
    asian_pips = round((asian['high'].max()-asian['low'].min())*mult,1) if not asian.empty else 0

    ideal_cbdr = "Ideal" if cbdr_pips < 40 else ""
    ideal_asian = "Delayed Protraction" if asian_pips > 40 else "Ideal" if 20<=asian_pips<=30 else ""

    prior = round((dfd.iloc[-2]['high']-dfd.iloc[-2]['low'])*mult,1) if len(dfd)>=2 else 0
    adr5 = round(dfd.tail(6).head(5)['high'].sub(dfd.tail(6).head(5)['low']).mean()*mult,1)

    pattern = detect_prior_day_pattern(dfd.tail(10))
    trend = get_daily_trend(dfd.tail(30))
    cc = get_candle_confirmation(dfd.tail(10))
    ob = get_order_block(dfd.tail(10))
    fvg = get_fvg(dfd.tail(10))
    fourh_cc = get_candle_confirmation(df4h.tail(10)) if not df4h.empty else ""

    arrows = "".join("Up" if r['close']>=r['open'] else "Down" for _,r in dfd.tail(3).iterrows())

    rows.append({
        "Asset": asset.replace("/",""),
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

df = pd.DataFrame(rows)

# FIXED SORTING
def sort_priority(x):
    return x.map(lambda a: priority_order.index(a) if a in priority_order else 999)

df["sort"] = df["Asset"].apply(sort_priority)
df = df.sort_values("sort").drop("sort", axis=1)

# ========================= DISPLAY =========================
st.title("LONDON GOD TIER DASHBOARD")
st.caption(f"Live · {datetime.now(HKT).strftime('%Y-%m-%d %H:%M HKT')}")

def color(val):
    if "Bullish" in str(val): return "color: #00FF00; font-weight: bold"
    if "Bearish" in str(val): return "color: #FF4444; font-weight: bold"
    if val == "Ideal": return "color: #00FF88"
    if "Delayed" in str(val): return "color: #FFAA00"
    return ""

styled = df.style.map(color)
st.dataframe(styled, use_container_width=True, height=900)

st.success("27 Pairs · Full Dashboard · Refreshes 06:05, 07:05, 11:05, 13:05, 15:05, 19:05 HKT")
