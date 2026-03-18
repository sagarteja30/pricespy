from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
import sqlite3
from typing import Optional
import requests
import re
import os
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "pricespy.db"

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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_scans INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            product_title TEXT,
            product_url TEXT,
            price REAL,
            recommendation TEXT,
            scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

def save_price(url, title, price):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO price_history (url, title, price) VALUES (?, ?, ?)",
        (url, title, price)
    )
    conn.commit()
    conn.close()

def track_user(user_id, title, url, price, recommendation):
    conn = sqlite3.connect(DB_PATH)
    
    # Add user if new, update if existing
    conn.execute("""
        INSERT INTO users (user_id, total_scans)
        VALUES (?, 1)
        ON CONFLICT(user_id) DO UPDATE SET
            last_seen = CURRENT_TIMESTAMP,
            total_scans = total_scans + 1
    """, (user_id,))

    # Save scan record
    conn.execute("""
        INSERT INTO scans (user_id, product_title, product_url, price, recommendation)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, title, url, price, recommendation))

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
    local_prices = get_local_history(asin) if asin else []

    if local_prices:
        all_prices = local_prices + [current_price]
    else:
        all_prices = [current_price]

    arr = np.array(all_prices, dtype=float)

    if len(arr) >= 5:
        x = np.arange(len(arr))
        slope, intercept = np.polyfit(x, arr, 1)
        predicted = slope * (len(arr) + 14) + intercept
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
    elif price_range > 500 and current_price <= (min_price + price_range * 0.2):
        rec = "BUY NOW"
        reason = "Near 30-day low — great time to buy"
    elif price_range > 500 and current_price >= (max_price - price_range * 0.2):
        rec = "WAIT"
        reason = "Near 30-day high — price may drop soon"
    else:
        rec = "BUY NOW"
        reason = "Price is stable — safe to buy now"

    confidence = min(92, max(50, 50 + len(all_prices)))

    return {
        "predicted_price": round(float(predicted)),
        "price_change": round(float(change)),
        "pct_change": round(float(pct), 1),
        "recommendation": rec,
        "reason": reason,
        "confidence": confidence,
        "best_price_30d": round(min_price),
        "worst_price_30d": round(max_price),
        "days_tracked": len(all_prices)
    }

class PriceRequest(BaseModel):
    url: str
    price: Optional[float] = None
    title: Optional[str] = "Unknown Product"
    user_id: Optional[str] = "anonymous"

@app.post("/analyze")
async def analyze_price(req: PriceRequest):
    if not req.price or req.price <= 0:
        return {"recommendation": "UNAVAILABLE", "reason": "No price found"}

    save_price(req.url, req.title, req.price)
    prediction = predict(req.url, req.price)

    # Track this user
    track_user(
        req.user_id,
        req.title,
        req.url,
        req.price,
        prediction["recommendation"]
    )

    return {
        "product": req.title,
        "current_price": round(req.price),
        **prediction
    }

@app.get("/health")
def health():
    return {"status": "PriceSpy running"}

@app.get("/dashboard")
def dashboard():
    conn = sqlite3.connect(DB_PATH)
    
    total_users = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]
    
    total_scans = conn.execute(
        "SELECT COUNT(*) FROM scans"
    ).fetchone()[0]
    
    today_scans = conn.execute(
        "SELECT COUNT(*) FROM scans WHERE date(scanned_at) = date('now')"
    ).fetchone()[0]

    today_users = conn.execute(
        "SELECT COUNT(DISTINCT user_id) FROM scans WHERE date(scanned_at) = date('now')"
    ).fetchone()[0]

    top_products = conn.execute("""
        SELECT product_title, COUNT(*) as views, AVG(price) as avg_price
        FROM scans
        GROUP BY product_title
        ORDER BY views DESC
        LIMIT 10
    """).fetchall()

    recent_users = conn.execute("""
        SELECT user_id, total_scans, first_seen, last_seen
        FROM users
        ORDER BY last_seen DESC
        LIMIT 20
    """).fetchall()

    conn.close()

    return {
        "total_users": total_users,
        "total_scans": total_scans,
        "today_scans": today_scans,
        "today_active_users": today_users,
        "top_products": [
            {
                "title": row[0],
                "views": row[1],
                "avg_price": round(row[2])
            }
            for row in top_products
        ],
        "recent_users": [
            {
                "user_id": row[0],
                "total_scans": row[1],
                "first_seen": row[2],
                "last_seen": row[3]
            }
            for row in recent_users
        ]
    }