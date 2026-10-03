from typing import Literal
from fastapi import FastAPI, Query
from app.schemas import Product

app = FastAPI(title="shop-api")

PRODUCTS = {
    1: {"id":1, "name":"T-shirt", "price":499},
    2: {"id": 2, "name": "Jeans", "price": 1299},
    3: {"id": 3, "name": "Cap", "price": 299},
}

@app.get("/")
def root():
    return {"message": "Hello from shop-api"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/version")
def version():
    return {"version": "0.1.0"}

@app.get("/products/{product_id}")
def get_product(product_id: int):
    return PRODUCTS.get(product_id)

@app.get("/products", response_model=list[Product])
def list_products(
    limit: int = Query(default=10, ge=1, le=100),
    max_price: int | None = Query(default=None, ge=0),
    sort: Literal["name", "price"] | None =None,
    order: Literal["asc", "desc"] = "asc",
):
    items = list(PRODUCTS.values())
    if max_price is not None:
        items=[p for p in items if p["price"]<= max_price]

    if sort is not None:
        items = sorted(items, key=lambda p: p[sort], reverse=(order == "desc"))

    return items[:limit]