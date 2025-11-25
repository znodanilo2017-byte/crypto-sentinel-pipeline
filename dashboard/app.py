import streamlit as st
import pandas as pd
import boto3
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import datetime

# --- CONFIG ---
BUCKET_NAME = "crypto-lake-taras-2025-november"
st.set_page_config(page_title="Crypto Volatility Monitor", layout="wide")

# --- AUTHENTICATION ---
if "aws" in st.secrets:
    s3 = boto3.client('s3',
                      aws_access_key_id=st.secrets["aws"]["aws_access_key_id"],
                      aws_secret_access_key=st.secrets["aws"]["aws_secret_access_key"],
                      region_name=st.secrets["aws"]["aws_default_region"])
else:
    s3 = boto3.client('s3')

@st.cache_data(ttl=60)
def load_data(hours_to_load):
    """Fetches data based on the user's selected time window."""
    today = datetime.datetime.now()
    # If user wants 24h, we might need yesterday's file too
    prefixes = [f"btc_trades_{today.strftime('%Y%m%d')}"]
    if hours_to_load > 12:
        yesterday = today - datetime.timedelta(days=1)
        prefixes.append(f"btc_trades_{yesterday.strftime('%Y%m%d')}")
    
    all_files = []
    paginator = s3.get_paginator('list_objects_v2')

    for prefix in prefixes:
        for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix):
            if 'Contents' in page:
                all_files.extend(page['Contents'])

    if not all_files:
        return pd.DataFrame()

    # Sort and take recent files based on window size (heuristic)
    # 4h ~ 240 files | 24h ~ 1440 files
    limit = 300 if hours_to_load <= 4 else 1500
    recent_files = sorted(all_files, key=lambda x: x['LastModified'], reverse=True)[:limit]
    
    data_frames = []
    for file in recent_files:
        try:
            obj = s3.get_object(Bucket=BUCKET_NAME, Key=file['Key'])
            df = pd.read_parquet(BytesIO(obj['Body'].read()))
            data_frames.append(df)
        except Exception:
            continue

    if not data_frames:
        return pd.DataFrame()

    final_df = pd.concat(data_frames)
    final_df['time'] = pd.to_datetime(final_df['time'])
    
    # Filter by selected hours
    cutoff_time = pd.Timestamp.now() - pd.Timedelta(hours=hours_to_load)
    final_df = final_df[final_df['time'] > cutoff_time]
    
    final_df = final_df.sort_values(by='time')
    return final_df

# --- SIDEBAR CONTROLS ---
st.sidebar.title("🎛️ Control Panel")

# 1. Time Slider
time_window = st.sidebar.selectbox(
    "Time Window",
    options=[1, 4, 12, 24],
    index=1, # Default to 4 hours
    format_func=lambda x: f"Last {x} Hours"
)

# 2. Bubble Threshold (The "More Dots" Slider)
# Default is 0.1 (Sensitive) so you see lots of bubbles like before
whale_threshold = st.sidebar.slider(
    "Whale Threshold (BTC)",
    min_value=0.05,
    max_value=2.0,
    value=0.1, 
    step=0.05,
    help="Lower this number to see smaller trades (more bubbles)."
)

# --- MAIN APP ---
st.title("🐋 Real-Time Whale Tracker")
st.markdown(f"Monitoring BTC/USDT • **Last {time_window} Hours**")

if st.sidebar.button("🔴 Refresh Data"):
    st.cache_data.clear()

# Load data based on sidebar choice
df = load_data(time_window)

if not df.empty:
    col1, col2, col3 = st.columns(3)
    col1.metric("Trades Loaded", f"{len(df):,}")
    col2.metric("Bitcoin Price", f"${df['price'].iloc[-1]:,.2f}")
    
    # --- CHART 1: CANDLES (Resampled) ---
    df_resampled = df.set_index('time').resample('1min').agg({
        'price': ['first', 'max', 'min', 'last'],
        'quantity': 'sum'
    })
    df_resampled.columns = ['open', 'high', 'low', 'close', 'volume']
    df_resampled = df_resampled.dropna()

    st.subheader("Price Action")
    fig_price = go.Figure(data=[go.Candlestick(
        x=df_resampled.index,
        open=df_resampled['open'], high=df_resampled['high'],
        low=df_resampled['low'], close=df_resampled['close']
    )])
    fig_price.update_layout(xaxis_rangeslider_visible=False, height=500)
    st.plotly_chart(fig_price, width='stretch')

    # --- CHART 2: WHALES (Interactive Threshold) ---
    st.subheader(f"Whale Volume (> {whale_threshold} BTC)")
    
    # Filter using the SIDEBAR value
    whales = df[df['quantity'] > whale_threshold]
    
    if not whales.empty:
        fig_vol = px.scatter(
            whales, x='time', y='price', size='quantity', 
            color='quantity', color_continuous_scale='RdBu_r',
            title=f"Detected {len(whales)} Large Trades"
        )
        st.plotly_chart(fig_vol, use_container_width=True)
    else:
        st.info(f"No trades larger than {whale_threshold} BTC found.")

else:
    st.warning("No recent data found.")