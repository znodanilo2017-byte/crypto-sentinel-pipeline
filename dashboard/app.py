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

# Initialize Session State for "Hours to Load"
if 'hours_to_load' not in st.session_state:
    st.session_state['hours_to_load'] = 4

# --- AUTHENTICATION ---
if "aws" in st.secrets:
    s3 = boto3.client('s3',
                      aws_access_key_id=st.secrets["aws"]["aws_access_key_id"],
                      aws_secret_access_key=st.secrets["aws"]["aws_secret_access_key"],
                      region_name=st.secrets["aws"]["aws_default_region"])
else:
    s3 = boto3.client('s3')

@st.cache_data(ttl=60)
def load_data(hours_window):
    """Fetches data based on the dynamic hours_window."""
    today = datetime.datetime.now()
    # If window is huge (>24h), we might need to look back more days.
    # For simplicity, we look back 2 days max here.
    prefixes = [
        f"btc_trades_{today.strftime('%Y%m%d')}",
        f"btc_trades_{(today - datetime.timedelta(days=1)).strftime('%Y%m%d')}"
    ]
    
    all_files = []
    paginator = s3.get_paginator('list_objects_v2')

    for prefix in prefixes:
        for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix):
            if 'Contents' in page:
                all_files.extend(page['Contents'])

    if not all_files:
        return pd.DataFrame()

    # Load more files if the window is larger
    # Rule of thumb: 60 files per hour (approx)
    files_needed = hours_window * 65 
    recent_files = sorted(all_files, key=lambda x: x['LastModified'], reverse=True)[:files_needed]
    
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
    
    # Precise Time Filter
    cutoff_time = pd.Timestamp.now() - pd.Timedelta(hours=hours_window)
    final_df = final_df[final_df['time'] > cutoff_time]
    
    final_df = final_df.sort_values(by='time')
    return final_df

# --- UI ---
st.title("🐋 Real-Time Whale Tracker")

# THE CONTROL BAR
col_control1, col_control2 = st.columns([3, 1])
with col_control1:
    st.markdown(f"**Monitoring Window:** Last {st.session_state['hours_to_load']} Hours")
with col_control2:
    if st.button("Load More History (+4h)"):
        st.session_state['hours_to_load'] += 4
        st.cache_data.clear() # Force reload
        st.rerun()

df = load_data(st.session_state['hours_to_load'])

if not df.empty:
    col1, col2, col3 = st.columns(3)
    col1.metric("Trades Loaded", f"{len(df):,}")
    col2.metric("Bitcoin Price", f"${df['price'].iloc[-1]:,.2f}")
    
    # 1. CANDLESTICK CHART
    # Dynamic Resampling: If looking at >12h, use 5min candles to stay fast
    resample_rule = '5min' if st.session_state['hours_to_load'] > 12 else '1min'
    
    df_resampled = df.set_index('time').resample(resample_rule).agg({
        'price': ['first', 'max', 'min', 'last'],
        'quantity': 'sum'
    })
    df_resampled.columns = ['open', 'high', 'low', 'close', 'volume']
    df_resampled = df_resampled.dropna()

    st.subheader(f"Price Action ({resample_rule} Candles)")
    fig_price = go.Figure(data=[go.Candlestick(
        x=df_resampled.index,
        open=df_resampled['open'], high=df_resampled['high'],
        low=df_resampled['low'], close=df_resampled['close']
    )])
    fig_price.update_layout(xaxis_rangeslider_visible=False, height=500)
    st.plotly_chart(fig_price, width='stretch')

    # 2. WHALE BUBBLES
    st.subheader("Whale Volume Detection (> 0.5 BTC)")
    whales = df[df['quantity'] > 0.5]
    if not whales.empty:
        fig_vol = px.scatter(
            whales, x='time', y='price', size='quantity', 
            color='quantity', color_continuous_scale='RdBu_r'
        )
        st.plotly_chart(fig_vol, use_container_width=True)
    else:
        st.info("No whales found in this window.")

else:
    st.warning("No data found.")