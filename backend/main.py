from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
from typing import Optional
import re
import os
import psycopg2

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db():
    return psycopg2.connect(DATABASE_URL)

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
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO price_history (url, title, price) VALUES (%s, %s, %s)",
            (url, title, price)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"save_price error: {e}")

def track_user(user_id, title, url, price, recommendation):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (user_id, total_scans)
            VALUES (%s, 1)
            ON CONFLICT(user_id) DO UPDATE SET
                last_seen = NOW(),
                total_scans = users.total_scans + 1
        """, (user_id,))
        cur.execute("""
            INSERT INTO scans (user_id, product_title, product_url, price, recommendation)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, title, url, price, recommendation))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"track_user error: {e}")

def get_local_history(asin):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT price FROM price_history WHERE url LIKE %s ORDER BY scraped_at ASC",
            (f"%{asin}%",)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [row[0] for row in rows]
    except Exception as e:
        print(f"get_history error: {e}")
        return []


def predict(url, current_price):
    asin = extract_asin(url)
    local_prices = get_local_history(asin) if asin else []

    if local_prices:
        all_prices = local_prices + [current_price]
    else:
        all_prices = [current_price]

    arr = np.array(all_prices, dtype=float)
    n = len(arr)

    min_price = float(np.min(arr))
    max_price = float(np.max(arr))
    price_range = max_price - min_price

    if n >= 5:
        x = np.arange(n)
        slope, intercept = np.polyfit(x, arr, 1)
        predicted = slope * (n + 14) + intercept
        confidence = min(92, 50 + (n * 2))
    else:
        predicted = current_price
        confidence = 50

    change = predicted - current_price
    pct = (change / current_price) * 100

    # Smart recommendation using price position
    if n >= 5 and pct < -2:
        rec = "WAIT"
        reason = f"Price dropping — likely Rs.{abs(change):.0f} cheaper in 14 days"

    elif n >= 5 and pct > 2:
        rec = "BUY NOW"
        reason = f"Price rising fast — buy before it goes up Rs.{abs(change):.0f}"

    elif price_range > 300 and current_price <= (min_price + price_range * 0.20):
        rec = "BUY NOW"
        reason = f"At 30-day low — best price right now. High was Rs.{round(max_price)}"

    elif price_range > 300 and current_price >= (max_price - price_range * 0.20):
        rec = "WAIT"
        reason = f"At 30-day high — usually drops Rs.{round(price_range * 0.4):.0f} from here"

    elif price_range > 1000:
        mid = min_price + price_range * 0.5
        if current_price < mid:
            rec = "BUY NOW"
            reason = f"Below average price — good time to buy"
        else:
            rec = "WAIT"
            reason = f"Above average price — better deals coming"

    elif n < 5:
        rec = "TRACKING"
        reason = f"Still collecting data — {5 - n} more days for full prediction"

    else:
        rec = "BUY NOW"
        reason = "Price is stable — safe to buy now"

    return {
        "predicted_price": round(float(predicted)),
        "price_change": round(float(change)),
        "pct_change": round(float(pct), 1),
        "recommendation": rec,
        "reason": reason,
        "confidence": confidence,
        "best_price_30d": round(min_price),
        "worst_price_30d": round(max_price),
        "days_tracked": n
    }







# def predict(url, current_price):
#     asin = extract_asin(url)
#     local_prices = get_local_history(asin) if asin else []

#     if local_prices:
#         all_prices = local_prices + [current_price]
#     else:
#         all_prices = [current_price]

#     arr = np.array(all_prices, dtype=float)
#     n = len(arr)

#     if n >= 30:
#         # Full ML prediction with trend + momentum
#         x = np.arange(n)
        
#         # Linear trend
#         slope, intercept = np.polyfit(x, arr, 1)
#         trend_predicted = slope * (n + 14) + intercept
        
#         # Momentum (recent vs older)
#         recent = float(np.mean(arr[-7:]))
#         older = float(np.mean(arr[-14:-7]))
#         momentum = recent - older
        
#         # Volatility
#         volatility = float(np.std(arr[-14:]))
        
#         # Combined prediction
#         predicted = trend_predicted + (momentum * 0.5)
        
#         # Confidence based on data quality
#         confidence = min(92, 60 + (n // 5) + int(10 / (1 + volatility/1000)))

#     elif n >= 7:
#         # Week of data — basic trend
#         x = np.arange(n)
#         slope, intercept = np.polyfit(x, arr, 1)
#         predicted = slope * (n + 14) + intercept
#         confidence = min(75, 50 + n)

#     else:
#         # Not enough data
#         predicted = current_price
#         confidence = 50

#     change = predicted - current_price
#     pct = (change / current_price) * 100

#     min_price = float(np.min(arr))
#     max_price = float(np.max(arr))
#     price_range = max_price - min_price

#     # Smart recommendation
#     if n >= 7:
#         if pct < -3:
#             rec = "WAIT"
#             reason = f"Price dropping — save Rs.{abs(change):.0f} in ~14 days"
#         elif pct > 3:
#             rec = "BUY NOW"
#             reason = f"Price rising — buy before it goes up Rs.{abs(change):.0f}"
#         elif price_range > 1000 and current_price <= (min_price + price_range * 0.15):
#             rec = "BUY NOW"
#             reason = f"At 30-day low — best price right now"
#         elif price_range > 1000 and current_price >= (max_price - price_range * 0.15):
#             rec = "WAIT"
#             reason = f"At 30-day high — price usually drops from here"
#         else:
#             rec = "BUY NOW"
#             reason = "Price is stable — safe to buy"
#     else:
#         rec = "TRACKING"
#         reason = f"Collecting price data — check back in {7 - n} days for prediction"

#     return {
#         "predicted_price": round(float(predicted)),
#         "price_change": round(float(change)),
#         "pct_change": round(float(pct), 1),
#         "recommendation": rec,
#         "reason": reason,
#         "confidence": confidence,
#         "best_price_30d": round(min_price),
#         "worst_price_30d": round(max_price),
#         "days_tracked": n
#     }