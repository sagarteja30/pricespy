import pandas as pd
import numpy as np
from prophet import Prophet
from xgboost import XGBRegressor
from sklearn.preprocessing import StandardScaler
import joblib
import psycopg2

def get_price_history(url, conn):
    df = pd.read_sql("""
        SELECT price, scraped_at as ds
        FROM price_history
        WHERE url = %s
        ORDER BY scraped_at ASC
    """, conn, params=[url])
    df['ds'] = pd.to_datetime(df['ds'])
    df['y'] = df['price']
    return df

def predict_price(url, conn, days=14):
    df = get_price_history(url, conn)

    if len(df) < 10:
        return {"error": "Not enough data yet. Check back in 3 days."}

    # Prophet for trend
    model = Prophet(
        daily_seasonality=True,
        weekly_seasonality=True,
        changepoint_prior_scale=0.05
    )
    model.fit(df[['ds', 'y']])

    future = model.make_future_dataframe(periods=days)
    forecast = model.predict(future)

    current_price = df['y'].iloc[-1]
    predicted_price = forecast['yhat'].iloc[-1]
    lower = forecast['yhat_lower'].iloc[-1]
    upper = forecast['yhat_upper'].iloc[-1]

    # Direction decision
    change = predicted_price - current_price
    pct_change = (change / current_price) * 100

    if pct_change < -3:
        recommendation = "WAIT"
        reason = f"Price likely to drop ₹{abs(change):.0f} in {days} days"
    elif pct_change > 3:
        recommendation = "BUY NOW"
        reason = f"Price likely to rise ₹{abs(change):.0f} — buy before it does"
    else:
        recommendation = "BUY NOW"
        reason = "Price is stable — no significant change expected"

    # Confidence score
    range_size = upper - lower
    confidence = max(40, min(95, int(100 - (range_size / current_price * 100))))

    return {
        "current_price": round(current_price),
        "predicted_price": round(predicted_price),
        "price_change": round(change),
        "pct_change": round(pct_change, 1),
        "recommendation": recommendation,
        "reason": reason,
        "confidence": confidence,
        "best_price_30d": round(df['y'].tail(30).min()),
        "worst_price_30d": round(df['y'].tail(30).max()),
        "days_tracked": len(df)
    }