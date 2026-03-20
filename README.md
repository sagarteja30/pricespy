# PriceSpy

AI-powered Amazon price prediction tool - helps users make smarter purchasing decisions by predicting whether prices will rise or fall.

## Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL (Supabase)
- **ML**: Prophet, XGBoost, NumPy
- **Extension**: Chrome Extension (Manifest V3)
- **Deployment**: Railway

## Project Structure

```
├── backend/           # FastAPI backend
│   ├── main.py        # API endpoints
│   └── logging_config.py
├── scarper/           # Scheduled scraper
│   └── scraper.py
├── scraper/           # Data collection
│   └── collector.py
├── ml/                # ML predictions
│   └── predict.py
├── extension/         # Chrome extension
├── tests/             # Test suite
└── .github/workflows/ # CI/CD
```

## Setup

### Local Development

1. **Clone and setup environment:**
```bash
git clone <repo>
cd pricespy
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

2. **Copy environment template:**
```bash
cp .env.example .env
# Edit .env with your DATABASE_URL
```

3. **Run with Docker Compose:**
```bash
docker-compose up
```

### Running Tests

```bash
pytest tests/ -v
```

### Code Quality

```bash
# Lint
ruff check .

# Type check
mypy backend scraper scarper ml
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/predict` | POST | Get price prediction |

### Example Request

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"url": "https://amazon.in/dp/B09V3KXJPB", "current_price": 1499}'
```

## Deployment

The app deploys automatically via GitHub Actions on push to main. Manual deploy:

```bash
docker build -t pricespy .
docker push <registry>/pricespy
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `LOG_LEVEL` | Logging level (INFO, DEBUG) |
| `ENVIRONMENT` | dev/staging/production |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) |
