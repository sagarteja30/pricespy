import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from psycopg2.extensions import connection as Conn
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings

from backend.logging_config import get_logger, setup_logging


class Settings(BaseSettings):
    database_url: str = Field(..., alias="DATABASE_URL")
    log_level: str = "INFO"
    environment: str = "production"
    cors_origins: str = "*"
    api_key: str | None = None
    rate_limit_requests: int = 100
    rate_limit_window: int = 60

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
setup_logging(level=settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting PriceSpy API in {settings.environment} mode")
    yield
    logger.info("Shutting down PriceSpy API")


app = FastAPI(
    title="PriceSpy API",
    description="AI-powered Amazon price prediction tool",
    version="1.0.0",
    lifespan=lifespan,
)

origins = settings.cors_origins.split(",") if settings.cors_origins != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class PricePredictionRequest(BaseModel):
    url: str = Field(..., description="Amazon product URL")
    current_price: float = Field(..., gt=0, description="Current product price")
    user_id: str | None = Field(None, description="Optional user ID for tracking")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not any(domain in v for domain in ["amazon.in", "amazon.com", "flipkart.com"]):
            raise ValueError("URL must be from Amazon or Flipkart")
        return v


class PricePredictionResponse(BaseModel):
    current_price: float
    predicted_price: int
    price_change: int
    pct_change: float
    recommendation: str
    reason: str
    confidence: int
    best_price_30d: int
    worst_price_30d: int
    days_tracked: int


class AnalyzeRequest(BaseModel):
    url: str
    price: float
    title: str
    user_id: str | None = None


def get_db() -> Conn:
    return psycopg2.connect(settings.database_url, connect_timeout=5)


def extract_asin(url: str) -> str | None:
    patterns = [
        r"/dp/([A-Z0-9]{10})",
        r"/gp/product/([A-Z0-9]{10})",
        r"/gp/aw/d/([A-Z0-9]{10})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def save_price(url: str, title: str, price: float) -> bool:
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO price_history (url, title, price) VALUES (%s, %s, %s)",
            (url, title, price),
        )
        conn.commit()
        cur.close()
        conn.close()
        logger.debug(f"Saved price for {url}: {price}")
        return True
    except Exception as e:
        logger.error(f"save_price error: {e}")
        return False


def track_user(user_id: str, title: str, url: str, price: float, recommendation: str) -> bool:
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO users (user_id, total_scans)
            VALUES (%s, 1)
            ON CONFLICT(user_id) DO UPDATE SET
                last_seen = NOW(),
                total_scans = users.total_scans + 1
            """,
            (user_id,),
        )
        cur.execute(
            """
            INSERT INTO scans (user_id, product_title, product_url, price, recommendation)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, title, url, price, recommendation),
        )
        conn.commit()
        cur.close()
        conn.close()
        logger.debug(f"Tracked user {user_id} for {url}")
        return True
    except Exception as e:
        logger.error(f"track_user error: {e}")
        return False


def get_local_history(asin: str) -> list[float]:
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT price FROM price_history WHERE url LIKE %s ORDER BY scraped_at ASC",
            (f"%{asin}%",),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [float(row[0]) for row in rows]
    except Exception as e:
        logger.error(f"get_history error: {e}")
        return []


def predict(url: str, current_price: float) -> dict[str, any]:
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
            reason = "Below average price — good time to buy"
        else:
            rec = "WAIT"
            reason = "Above average price — better deals coming"

    elif n < 5:
        rec = "TRACKING"
        reason = f"Still collecting data — {5 - n} more days for full prediction"

    else:
        rec = "BUY NOW"
        reason = "Price is stable — safe to buy now"

    return {
        "current_price": current_price,
        "predicted_price": round(float(predicted)),
        "price_change": round(float(change)),
        "pct_change": round(float(pct), 1),
        "recommendation": rec,
        "reason": reason,
        "confidence": confidence,
        "best_price_30d": round(min_price),
        "worst_price_30d": round(max_price),
        "days_tracked": n,
    }


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "environment": settings.environment}


@app.post("/predict", response_model=PricePredictionResponse)
async def get_prediction(request: PricePredictionRequest) -> PricePredictionResponse:
    try:
        result = predict(request.url, request.current_price)

        if request.user_id:
            track_user(
                request.user_id,
                "Product",
                request.url,
                request.current_price,
                result["recommendation"],
            )

        return PricePredictionResponse(**result)
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail="Prediction failed") from None


@app.post("/analyze")
async def analyze_product(request: AnalyzeRequest):
    """Endpoint for Chrome extension - saves price and returns prediction."""
    try:
        save_price(request.url, request.title, request.price)
        
        result = predict(request.url, request.price)
        
        if request.user_id:
            track_user(
                request.user_id,
                request.title,
                request.url,
                request.price,
                result["recommendation"],
            )
        
        return result
    except Exception as e:
        logger.error(f"Analyze error: {e}")
        raise HTTPException(status_code=500, detail="Analysis failed") from None


@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = Path("templates/index.html")
    if html_path.exists():
        return FileResponse(str(html_path))
    return {
        "message": "PriceSpy API - AI-powered price prediction",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "predict": "POST /predict",
            "analyze": "POST /analyze",
            "docs": "/docs"
        }
    }
