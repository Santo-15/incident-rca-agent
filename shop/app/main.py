from typing import Literal
from fastapi import FastAPI, Query, HTTPException
from app.schemas import Product, CartItemIn, CartOut

app = FastAPI(title="shop-api")

PRODUCTS = {
    1: {"id":1, "name":"T-shirt", "price":499},
    2: {"id": 2, "name": "Jeans", "price": 1299},
    3: {"id": 3, "name": "Cap", "price": 299},
}
CARTS: dict[int, dict[int, int]] ={}  #{user_id: {product_id: qty}}
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

def build_cart(user_id: int) -> dict:
    cart = CARTS.get(user_id, {})
    items = []
    for product_id, qty in cart.items():
        product = PRODUCTS[product_id]
        items.append({
            "product_id": product_id,
            "name": product["name"],
            "price": product["price"],
            "qty": qty,
        })
    total = sum(item["price"] * item["qty"] for item in items)
    return {"user_id": user_id, "items": items, "total": total}

@app.post("/users/{user_id}/cart", response_model=CartOut)
def add_to_cart(user_id: int, item: CartItemIn):
    if item.product_id not in PRODUCTS:
        raise HTTPException (status_code=404, detail="Product not found")
    cart = CARTS.setdefault(user_id, {})
    cart[item.product_id] = cart.get(item.product_id, 0) + item.qty
    return build_cart(user_id)