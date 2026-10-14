from typing import Literal
import redis
from fastapi import Depends, FastAPI, Query, HTTPException  
from sqlalchemy import select  
from sqlalchemy.orm import Session  
from app.db import get_db 
from app.cache import get_redis, CART_TTL_SECONDS
from app import models 
from app.schemas import Product, CartItemIn, CartOut, CheckoutOut

app = FastAPI(title="shop-api")

# REMOVED  PRODUCTS, CARTS and ORDERS dicts: the data now lives in Postgres tables

@app.get("/")
def root():
    return {"message": "Hello from shop-api"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/version")
def version():
    return {"version": "0.3.0"}  # CHANGED  new version: the shop now stores data in Postgres 

@app.get("/products/{product_id}", response_model=Product)
def get_product(product_id: int, db: Session = Depends(get_db)):  
    product = db.get(models.Product, product_id)  
    if product is None:  
        raise HTTPException(
            status_code=404,
            detail=f"Product {product_id} not found",
        )
    return {"id": product.id, "name": product.name, "price": product.price}  # CHANGED  turn the table object into the API shape


@app.get("/products", response_model=list[Product])
def list_products(
    limit: int = Query(default=10, ge=1, le=100),
    max_price: int | None = Query(default=None, ge=0),
    sort: Literal["name", "price"] | None =None,
    order: Literal["asc", "desc"] = "asc",
    db: Session = Depends(get_db),  
):
    stmt = select(models.Product)  
    if max_price is not None:
        stmt = stmt.where(models.Product.price <= max_price)  

    if sort is not None:
        column = getattr(models.Product, sort)  
        stmt = stmt.order_by(column.desc() if order == "desc" else column.asc())  
    else:
        stmt = stmt.order_by(models.Product.id)  

    stmt = stmt.limit(limit)  
    return [{"id": p.id, "name": p.name, "price": p.price} for p in db.scalars(stmt)]  

def cart_key(user_id: int) -> str:
    return f"cart:{user_id}"

def build_cart(db: Session, r: redis.Redis, user_id: int) -> dict:
    raw = r.hgetall(cart_key(user_id))  # {"2": "3"} or {}
    qty_by_id = {int(pid): int(qty) for pid, qty in raw.items()}  # {2: 3}
    items = []
    if qty_by_id:
        stmt = select(models.Product).where(models.Product.id.in_(list(qty_by_id))).order_by(models.Product.id)
        for product in db.scalars(stmt):
            items.append({"product_id": product.id, "name": product.name,
                          "price": product.price, "qty": qty_by_id[product.id]})
    total = sum(item["price"] * item["qty"] for item in items)
    return {"user_id": user_id, "items": items, "total": total}

@app.post("/users/{user_id}/cart", response_model=CartOut)
def add_to_cart(user_id: int, item: CartItemIn, db: Session = Depends(get_db), r: redis.Redis = Depends(get_redis)):  
    if db.get(models.Product, item.product_id) is None:  
        raise HTTPException (status_code=404, detail=f"Product {item.product_id} not found")
    key = cart_key(user_id)
    pipe = r.pipeline()                              # send both commands together
    pipe.hincrby(key, item.product_id, item.qty)     # add qty to this product's line
    pipe.expire(key, CART_TTL_SECONDS)               # restart the 24 h expiry
    pipe.execute()
    return build_cart(db, r, user_id)  

@app.post(
    "/users/{user_id}/checkout",
    response_model=CheckoutOut,
    status_code=201,
)
def checkout(user_id: int, db: Session = Depends(get_db), r: redis.Redis = Depends(get_redis)): 
    key = cart_key(user_id)
    qty_by_id = {int(pid): int(qty) for pid, qty in r.hgetall(key).items()}
    products = []
    if qty_by_id:
        products = db.scalars(select(models.Product).where(models.Product.id.in_(list(qty_by_id)))).all()
    if not products:
        raise HTTPException(status_code=400, detail="Cart is empty")
    total = sum(p.price * qty_by_id[p.id] for p in products) 
    order = models.Order(user_id=user_id, total=total)  
    db.add(order)  
    db.flush() 
    for p in products:
          db.add(models.OrderItem(order_id=order.id, product_id=p.id, qty=qty_by_id[p.id], unit_price=p.price))  
    db.commit()
    r.delete(key)
    return {"order_id": order.id, "user_id": user_id, "total": total} 