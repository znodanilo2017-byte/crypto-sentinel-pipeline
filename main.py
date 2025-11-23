import os
import requests
import numpy as np
import json
import boto3  # <--- NEW IMPORT
from datetime import datetime, timedelta

# CONFIGURATION
COIN_ID = os.getenv('COIN_ID', 'pepe')
TABLE_NAME = os.getenv('TABLE_NAME') # <--- Get table name from Terraform
CURRENCY = 'usd'
DAYS = '30'
CACHE_DURATION_MINUTES = 5

# AWS CLIENTS
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE_NAME)

_CACHE = {"last_updated": None, "payload": None}

def fetch_market_data(coin_id):
    # ... (Keep existing fetch logic) ...
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {'vs_currency': CURRENCY, 'days': DAYS, 'interval': 'daily'}
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def calculate_index(data):
    # ... (Keep existing math logic) ...
    prices = [p[1] for p in data['prices']]
    returns = np.diff(prices) / prices[:-1]
    volatility = np.std(returns)
    current_price = prices[-1]
    sma_30 = np.mean(prices)
    momentum = (current_price - sma_30) / sma_30
    base_score = 50 + (momentum * 100) 
    return int(max(0, min(100, base_score)))

def save_to_history(coin, score, sentiment, timestamp):
    """Writes the data point to DynamoDB"""
    try:
        table.put_item(
            Item={
                'coin': coin,
                'timestamp': timestamp,
                'index_score': score,
                'sentiment': sentiment
            }
        )
        print(f"Saved to DB: {timestamp}")
    except Exception as e:
        print(f"DB Write Error: {e}")

def handler(event, context):
    global _CACHE
    now = datetime.now()
    
    # 1. CHECK CACHE
    if _CACHE["payload"] and _CACHE["last_updated"]:
        time_diff = now - _CACHE["last_updated"]
        if time_diff < timedelta(minutes=CACHE_DURATION_MINUTES):
            print("Serving from CACHE")
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(_CACHE["payload"])
            }

    # 2. FRESH CALCULATION
    data = fetch_market_data(COIN_ID)
    if not data:
        if _CACHE["payload"]: return {"statusCode": 200, "body": json.dumps(_CACHE["payload"])}
        return {"statusCode": 500, "body": json.dumps("Failed to fetch data")}
    
    index_score = calculate_index(data)
    sentiment = "Extreme Greed" if index_score > 75 else "Fear" if index_score < 25 else "Neutral"
    iso_timestamp = now.isoformat()
    
    # 3. SAVE TO DB (The New Part)
    # We only save when we do a fresh fetch (every 5 mins)
    save_to_history(COIN_ID, index_score, sentiment, iso_timestamp)

    result = {
        "coin": COIN_ID,
        "index_score": index_score,
        "sentiment": sentiment,
        "timestamp": iso_timestamp
    }
    
    _CACHE["payload"] = result
    _CACHE["last_updated"] = now
    
    return {
        "statusCode": 200, 
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(result)
    }