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

## Planned endpoints (Phase 2 contract)

| Method + path | Input | Success | Failure |
|---|---|---|---|
| `GET /products` | query: `limit`, `max_price`, `sort` (name/price), `order` (asc/desc) | 200 + filtered list | 422 bad param value |
| `POST /users/{user_id}/cart` | body: `{"product_id": 2, "qty": 1}` | 200 + updated cart | 404 product not found, 422 qty ≤ 0 |
| `POST /users/{user_id}/checkout` | none | 201 + order id, total | 400 cart empty |

Rule: planned failures are 4xx (client's fault). 5xx only means our code or infra broke.

## Quick test
```bash
curl -i http://127.0.0.1:8000/health
curl -i "http://127.0.0.1:8000/products?max_price=500&limit=1"
curl -i http://127.0.0.1:8000/products/abc   # expect 422
```

## Run Postgres locally

docker run -d --name shop-db \
  -e POSTGRES_USER=shop -e POSTGRES_PASSWORD=shop -e POSTGRES_DB=shop \
  -p 5432:5432 -v shop-pgdata:/var/lib/postgresql/data postgres:16

Open psql: `docker exec -it shop-db psql -U shop -d shop`
Stop / start: `docker stop shop-db` / `docker start shop-db`

