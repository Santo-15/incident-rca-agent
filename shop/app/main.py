import logging
import os
import re
import time
import uuid
from typing import Literal
import redis
from fastapi import Depends, FastAPI, Query, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select  
from sqlalchemy.orm import Session  
from app.db import get_db 
from app.cache import get_redis, CART_TTL_SECONDS
from app import models 
from app.schemas import Product, CartItemIn, CartOut, CheckoutOut
from app.logging_setup import setup_logging, request_id_var

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
setup_logging(LOG_LEVEL)
logger = logging.getLogger("shop")

app = FastAPI(title="shop-api")

REQUEST_ID_RE = re.compile(r"[A-Za-z0-9-]{1,64}")

@app.middleware("http")                               
async def request_context(request: Request, call_next):  
    incoming = request.headers.get("X-Request-ID", "")   
    request_id = incoming if REQUEST_ID_RE.fullmatch(incoming) else uuid.uuid4().hex  
    token = request_id_var.set(request_id)           
    start = time.perf_counter()                       
    fields = {"method": request.method, "path": request.url.path}  
    try:                                              
        response = await call_next(request)           
    except Exception as exc:                         
        fields.update(status=500, duration_ms=round((time.perf_counter() - start) * 1000, 1), error=f"{type(exc).__name__}: {exc}")  
        logger.error("request failed", exc_info=True, extra=fields)  
        response = JSONResponse(status_code=500, content={"detail": "Internal Server Error"})  
    else:                                             
        fields.update(status=response.status_code, duration_ms=round((time.perf_counter() - start) * 1000, 1))  
        level = logging.DEBUG if request.url.path == "/health" else logging.INFO  
        logger.log(level, "request done", extra=fields)  
    finally:                                          
        request_id_var.reset(token)                   
    response.headers["X-Request-ID"] = request_id     
    return response                                   

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
        logger.info("product not found", extra={"product_id": product_id}) 
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
        logger.info("product not found", extra={"product_id": item.product_id, "user_id": user_id})  
        raise HTTPException (status_code=404, detail=f"Product {item.product_id} not found")
    key = cart_key(user_id)
    pipe = r.pipeline()                              # send both commands together
    pipe.hincrby(key, item.product_id, item.qty)     # add qty to this product's line
    pipe.expire(key, CART_TTL_SECONDS)               # restart the 24 h expiry
    pipe.execute()
    logger.debug("cart updated", extra={"redis_key": key, "product_id": item.product_id, "qty_added": item.qty})
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
        logger.info("checkout rejected cart empty", extra={"user_id": user_id})  
        raise HTTPException(status_code=400, detail="Cart is empty")
    total = sum(p.price * qty_by_id[p.id] for p in products) 
    order = models.Order(user_id=user_id, total=total)  
    db.add(order)  
    db.flush() 
    for p in products:
          db.add(models.OrderItem(order_id=order.id, product_id=p.id, qty=qty_by_id[p.id], unit_price=p.price))  
    db.commit()
    r.delete(key)
    logger.info("order created", extra={"order_id": order.id, "user_id": user_id, "total": total})   
    return {"order_id": order.id, "user_id": user_id, "total": total} 