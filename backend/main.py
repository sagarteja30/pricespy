from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
import sqlite3
from typing import Optional
import requests
import re
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "pricespy.db"
KEEPA_KEY = os.getenv("KEEPA_KEY", "")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            title TEXT,
            price REAL NOT NULL,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

def extract_asin(url):
    patterns = [
        r'/dp/([A-Z0-9]{10})',
        r'/gp/product/([A-Z0-9]{10})',
        r'/gp/aw/d/([A-Z0-9]{10})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_keepa_history(asin):
    if not KEEPA_KEY:
        return []
    try:
        url = f"https://api.keepa.com/product?key={KEEPA_KEY}&domain=10&asin={asin}&history=1"
        res = requests.get(url, timeout=10)
        data = res.json()

        if not data.get("products"):
            return []

        product = data["products"][0]
        csv = product.get("csv", [])

        # Index 0 = Amazon price history
        # Format: [timestamp, price, timestamp, price, ...]
        if not csv or not csv[0]:
            return []

        raw = csv[0]
        prices = []

        for i in range(1, len(raw), 2):
            if raw[i] and raw[i] > 0:
                # Keepa stores prices in cents (Indian paise)
                price = raw[i] / 100
                if price > 100:
                    prices.append(price)

        # Return last 60 data points
        return prices[-60:] if prices else []

    except Exception as e:
        print(f"Keepa error: {e}")
        return []

def save_price(url, title, price):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO price_history (url, title, price) VALUES (?, ?, ?)",
        (url, title, price)
    )
    conn.commit()
    conn.close()

def get_local_history(asin):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT price FROM price_history WHERE url LIKE ? ORDER BY scraped_at ASC",
        (f"%{asin}%",)
    ).fetchall()
    conn.close()
    return [row[0] for row in rows]

def predict(url, current_price):
    asin = extract_asin(url)
    print(f"ASIN: {asin}")

    keepa_prices = get_keepa_history(asin) if asin else []
    local_prices = get_local_history(asin) if asin else []

    print(f"Keepa prices: {len(keepa_prices)}")
    print(f"Local prices: {len(local_prices)}")

    if keepa_prices:
        all_prices = keepa_prices + local_prices + [current_price]
    elif local_prices:
        all_prices = local_prices + [current_price]
    else:
        all_prices = [current_price]

    arr = np.array(all_prices, dtype=float)

    if len(arr) >= 5:
        x = np.arange(len(arr))
        slope, intercept = np.polyfit(x, arr, 1)
        predicted = slope * (len(arr) + 14) + intercept

        recent_avg = float(np.mean(arr[-7:]))
        older_avg = float(np.mean(arr[:7]))
        momentum = recent_avg - older_avg
        predicted = predicted + (momentum * 0.3)
    else:
        predicted = current_price

    change = predicted - current_price
    pct = (change / current_price) * 100

    min_price = float(np.min(arr))
    max_price = float(np.max(arr))
    price_range = max_price - min_price

    if pct < -3:
        rec = "WAIT"
        reason = f"Price likely to drop Rs.{abs(change):.0f} in ~14 days"
    elif pct > 3:
        rec = "BUY NOW"
        reason = f"Price rising — buy before it goes up Rs.{abs(change):.0f}"
    elif current_price <= (min_price + price_range * 0.2):
        rec = "BUY NOW"
        reason = f"Near 30-day low — great time to buy"
    elif current_price >= (max_price - price_range * 0.2):
        rec = "WAIT"
        reason = f"Near 30-day high — price may drop soon"
    else:
        rec = "BUY NOW"
        reason = "Price is stable — safe to buy now"

    confidence = min(92, max(50, 50 + len(all_prices)))
    days = len(all_prices)

    return {
        "predicted_price": round(float(predicted)),
        "price_change": round(float(change)),
        "pct_change": round(float(pct), 1),
        "recommendation": rec,
        "reason": reason,
        "confidence": confidence,
        "best_price_30d": round(min_price),
        "worst_price_30d": round(max_price),
        "days_tracked": days
    }

class PriceRequest(BaseModel):
    url: str
    price: Optional[float] = None
    title: Optional[str] = "Unknown Product"

@app.post("/analyze")
async def analyze_price(req: PriceRequest):
    if not req.price or req.price <= 0:
        return {"recommendation": "UNAVAILABLE", "reason": "No price found"}

    save_price(req.url, req.title, req.price)
    prediction = predict(req.url, req.price)

    return {
        "product": req.title,
        "current_price": round(req.price),
        **prediction
    }

@app.get("/health")
def health():
    return {"status": "PriceSpy running with Keepa history"}