# shop-api

Fake e-commerce API (FastAPI) that we break on purpose for the RCA agent.

## Run locally
```bash
cd shop
source ../.venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000 --reload
```

## Endpoints
| Method | Path | Notes |
|---|---|---|
| GET | / | hello message |
| GET | /health | liveness check |
| GET | /version | running version |
| GET | /products | query: limit (default 10), max_price |
| GET | /products/{product_id} | one product by id |

Interactive docs: http://127.0.0.1:8000/docs

## Quick test
```bash
curl -i http://127.0.0.1:8000/health
curl -i "http://127.0.0.1:8000/products?max_price=500&limit=1"
curl -i http://127.0.0.1:8000/products/abc   # expect 422
```