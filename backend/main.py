from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
import sqlite3
from typing import Optional

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
    conn.commit()
    conn.close()

init_db()

def save_price(url, title, price):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO price_history (url, title, price) VALUES (?, ?, ?)",
        (url, title, price)
    )
    conn.commit()
    conn.close()

def get_history(url):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT price FROM price_history WHERE url = ? ORDER BY scraped_at ASC",
        (url,)
    ).fetchall()
    conn.close()
    return [row[0] for row in rows]

def predict(url, current_price):
    history = get_history(url)

    if len(history) < 3:
        prices = history + [current_price]
    else:
        prices = history

    arr = np.array(prices, dtype=float)
    x = np.arange(len(arr))
    slope, intercept = np.polyfit(x, arr, 1)
    predicted = slope * (len(arr) + 14) + intercept

    change = predicted - current_price
    pct = (change / current_price) * 100

    if pct < -3:
        rec = "WAIT"
        reason = f"Price likely to drop Rs.{abs(change):.0f} in ~14 days"
    elif pct > 3:
        rec = "BUY NOW"
        reason = f"Price rising — buy before it goes up Rs.{abs(change):.0f}"
    else:
        rec = "BUY NOW"
        reason = "Price is stable — safe to buy now"

    confidence = max(50, min(92, int(80 - abs(pct) * 1.5)))

    return {
        "predicted_price": round(float(predicted)),
        "price_change": round(float(change)),
        "pct_change": round(float(pct), 1),
        "recommendation": rec,
        "reason": reason,
        "confidence": confidence,
        "best_price_30d": round(float(np.min(arr[-30:]))),
        "worst_price_30d": round(float(np.max(arr[-30:]))),
        "days_tracked": len(prices)
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
    return {"status": "PriceSpy is running"}