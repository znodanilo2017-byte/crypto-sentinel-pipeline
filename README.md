# 🐳 Real-Time Crypto Volatility Pipeline

### *End-to-End MLOps Pipeline on AWS*

**Live Dashboard:** [Streamlit App](https://meme-index.streamlit.app)

---

## 🚀 The Project
This system is an automated financial data infrastructure that captures high-frequency cryptocurrency trade data, detects "Whale" (large volume) anomalies, and visualizes market microstructure in real-time.

**The Problem:** High-frequency financial data usually costs $5,000/month.
**The Solution:** An engineered cloud-native pipeline that ingests, processes, and visualizes ~800,000 trade events per day for **$0** using AWS Free Tier.

## 🏗️ Architecture
The system is decoupled into two microservices:
1.  **The Sentinel (Backend):** A Dockerized Python bot on AWS EC2 that listens to Binance WebSockets, filters for "Whales" (> 1 BTC), sends Telegram alerts, and persists data to S3.
2.  **The Monitor (Frontend):** A Streamlit dashboard that reads from the S3 Data Lake, using smart pagination and resampling (1-min candles) to visualize millions of data points without lag.

![Architecture Diagram](./diagram_meme_index.png)

---

## 📸 Visuals

### 1. Real-Time Volatility Dashboard
*Optimized 4-hour window with 1-minute candlestick resampling for high performance.*
![Price Dashboard](./BitcoinPriceDashboard.png)

### 2. Whale Anomaly Detector
*Filters noise to show only institutional-grade liquidity events (> 0.5 BTC).*
![Whale Detector](./WhaleDetector.png)

### 3. Active Alerting (Telegram)
*Push notifications sent instantly when large trades occur.*
![Push Notifications](./PushNotif.png)

---

## 🛠️ Tech Stack

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Cloud Provider** | AWS (eu-central-1) | EC2, S3, IAM, ECR |
| **IaC** | Terraform | State-managed infrastructure deployment |
| **Container** | Docker | Multi-arch build (AMD64) running in detached mode |
| **Backend** | Python 3.11 | `websocket-client`, `boto3`, `requests` |
| **Frontend** | Streamlit | `plotly`, `pandas` (Resampling & Caching) |
| **Storage** | S3 Data Lake | Parquet format (Snappy compression) |
| **Alerting** | Telegram Bot API | Real-time push notifications |

---

## 📂 Project Structure
```bash
meme-index/
├── bot/                 # Backend Microservice
│   ├── main.py          # WebSocket Listener & Telegram Logic
│   ├── Dockerfile       # Optimized Python Image
│   └── requirements.txt
├── dashboard/           # Frontend Microservice
│   ├── app.py           # Streamlit Visualization
│   └── requirements.txt
├── main.tf              # Terraform Infrastructure (AWS)
└── ...
 ```
---

## 🔧 How to Run Locally

1. Deploying the Bot (Backend)
The bot is designed to run in a Docker container (locally or on EC2).

# Build the image
docker build -t crypto-bot ./bot

# Run with Environment Variables (Secrets)
docker run -d \
  -e TELEGRAM_TOKEN="your_token" \
  -e TELEGRAM_CHAT_ID="your_id" \
  --restart always \
  crypto-bot

2. Running the Dashboard (Frontend)
The dashboard connects to AWS S3 to visualize the data.

# Enter the right folder
cd meme-index

# Install dependencies
pip install -r dashboard/requirements.txt

# Run locally
streamlit run dashboard/app.py

---
*Built by Danylo Yuzefchyk - Infrastructure & Data Engineer*