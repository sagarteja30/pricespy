from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
import sqlite3
from typing import Optional
import requests
from bs4 import BeautifulSoup
import re

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

def get_camel_history(asin):
    try:
        url = f"https://camelcamelcamel.com/product/{asin}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.content, "html.parser")

        # Find price history data in the page scripts
        scripts = soup.find_all("script")
        prices = []

        for script in scripts:
            if script.string and "amazon" in str(script.string).lower():
                # Extract price numbers from script data
                numbers = re.findall(r'"y":(\d+\.?\d*)', str(script.string))
                if numbers and len(numbers) > 5:
                    prices = [float(n) for n in numbers if float(n) > 100]
                    if len(prices) > 5:
                        break

        return prices[-30:] if prices else []

    except Exception as e:
        print(f"Camel error: {e}")
        return []

def save_price(url, title, price):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO price_history (url, title, price) VALUES (?, ?, ?)",
        (url, title, price)
    )
    conn.commit()
    conn.close()

def get_local_history(url):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT price FROM price_history WHERE url LIKE ? ORDER BY scraped_at ASC",
        (f"%{extract_asin(url) or url}%",)
    ).fetchall()
    conn.close()
    return [row[0] for row in rows]

def predict(url, current_price):
    asin = extract_asin(url)

    # Try to get real historical data first
    camel_prices = []
    if asin:
        camel_prices = get_camel_history(asin)
        print(f"Camel prices found: {len(camel_prices)}")

    local_prices = get_local_history(url)

    # Combine all price sources
    if camel_prices:
        all_prices = camel_prices + local_prices + [current_price]
    elif local_prices:
        all_prices = local_prices + [current_price]
    else:
        all_prices = [current_price]

    arr = np.array(all_prices, dtype=float)
    x = np.arange(len(arr))

    if len(arr) >= 3:
        slope, intercept = np.polyfit(x, arr, 1)
        predicted = slope * (len(arr) + 14) + intercept
    else:
        predicted = current_price

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
    days = len(all_prices)

    return {
        "predicted_price": round(float(predicted)),
        "price_change": round(float(change)),
        "pct_change": round(float(pct), 1),
        "recommendation": rec,
        "reason": reason,
        "confidence": confidence,
        "best_price_30d": round(float(np.min(arr[-30:]))),
        "worst_price_30d": round(float(np.max(arr[-30:]))),
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
    return {"status": "PriceSpy running with real history"}