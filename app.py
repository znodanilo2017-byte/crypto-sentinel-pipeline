import streamlit as st
import pandas as pd
import boto3
import plotly.express as px
from io import BytesIO

# --- CONFIG ---
BUCKET_NAME = "crypto-lake-taras-2025-november" # <--- YOUR BUCKET NAME
st.set_page_config(page_title="Crypto Volatility Monitor", layout="wide")

# --- AUTHENTICATION ---
# Check if we are in the Cloud (Streamlit Secrets exist) or on Laptop
if "aws" in st.secrets:
    # We are on Streamlit Cloud -> Use the secrets you pasted
    s3 = boto3.client('s3',
                      aws_access_key_id=st.secrets["aws"]["aws_access_key_id"],
                      aws_secret_access_key=st.secrets["aws"]["aws_secret_access_key"],
                      region_name=st.secrets["aws"]["aws_default_region"])
else:
    # We are on Laptop -> Use local ~/.aws/credentials automatically
    s3 = boto3.client('s3')

@st.cache_data(ttl=60) # Cache data for 60 seconds to save S3 costs/speed
def load_data():
    """Fetches the last 5 parquet files from S3 and merges them."""
    # 1. List files in bucket
    objects = s3.list_objects_v2(Bucket=BUCKET_NAME)
    
    if 'Contents' not in objects:
        return pd.DataFrame()
        
    # 2. Sort by date and take the last 5 (Most recent data)
    files = sorted(objects['Contents'], key=lambda x: x['LastModified'], reverse=True)[:5]
    
    all_data = []
    
    # 3. Download and read each file
    for file in files:
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=file['Key'])
        df = pd.read_parquet(BytesIO(obj['Body'].read()))
        all_data.append(df)
        
    if not all_data:
        return pd.DataFrame()
        
    return pd.concat(all_data)

# --- THE UI ---
st.title("🐋 Real-Time Whale Tracker")
st.markdown(f"**Data Source:** AWS S3 Data Lake ({BUCKET_NAME})")

if st.button("Refresh Data"):
    st.cache_data.clear()

# Load Data
df = load_data()

if not df.empty:
    # Convert time to datetime
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values(by='time')
    
    # KPI Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Trades Tracked", len(df))
    col2.metric("Bitcoin Price", f"${df['price'].iloc[-1]:,.2f}")
    col3.metric("Max Trade Size", f"{df['quantity'].max():.4f} BTC")

    # --- CHART 1: Price History ---
    st.subheader("Bitcoin Price Action")
    fig_price = px.line(df, x='time', y='price', title='BTC/USDT Real-Time Feed')
    st.plotly_chart(fig_price, use_container_width=True)

    # --- CHART 2: Whale Detector (Scatter Plot) ---
    st.subheader("Whale Volume Detection")
    # Filter for trades larger than 0.05 BTC
    whales = df[df['quantity'] > 0.05]
    
    if not whales.empty:
        fig_vol = px.scatter(
            whales, 
            x='time', 
            y='price', 
            size='quantity', 
            color='quantity',
            hover_data=['quantity', 'buyer_maker'],
            title='Large Trades (>0.05 BTC)'
        )
        st.plotly_chart(fig_vol, use_container_width=True)
    else:
        st.info("No whales detected in the last few minutes.")

    # --- RAW DATA TABLE ---
    with st.expander("View Raw Data (Parquet Stream)"):
        st.dataframe(df.sort_values(by='time', ascending=False))

else:
    st.warning("No data found in S3 yet. Is the bot running?")