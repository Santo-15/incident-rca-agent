from typing import Literal
from fastapi import Depends, FastAPI, Query, HTTPException  
from sqlalchemy import select  
from sqlalchemy.orm import Session  
from app.db import get_db 
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
    return {"version": "0.2.0"}  # CHANGED  new version: the shop now stores data in Postgres 

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

def build_cart(db: Session, user_id: int) -> dict: 
    stmt = (  
        select(models.CartItem, models.Product)  
        .join(models.Product, models.Product.id == models.CartItem.product_id)  
        .where(models.CartItem.user_id == user_id)  
        .order_by(models.CartItem.product_id)  
    )
    items = []
    for line, product in db.execute(stmt).all():  
        items.append({
            "product_id": product.id,
            "name": product.name,
            "price": product.price,
            "qty": line.qty,
        })
    total = sum(item["price"] * item["qty"] for item in items)
    return {"user_id": user_id, "items": items, "total": total}

@app.post("/users/{user_id}/cart", response_model=CartOut)
def add_to_cart(user_id: int, item: CartItemIn, db: Session = Depends(get_db)):  
    if db.get(models.Product, item.product_id) is None:  
        raise HTTPException (status_code=404, detail=f"Product {item.product_id} not found")
    line = db.get(models.CartItem, (user_id, item.product_id))  
    if line is None:  
        db.add(models.CartItem(user_id=user_id, product_id=item.product_id, qty=item.qty)) 
    else:  
        line.qty += item.qty 
    db.commit()  
    return build_cart(db, user_id)  

@app.post(
    "/users/{user_id}/checkout",
    response_model=CheckoutOut,
    status_code=201,
)
def checkout(user_id: int, db: Session = Depends(get_db)): 
    stmt = (  # NEW
        select(models.CartItem, models.Product)  
        .join(models.Product, models.Product.id == models.CartItem.product_id)  
        .where(models.CartItem.user_id == user_id)  
    )
    lines = db.execute(stmt).all()  
    if not lines:  
        raise HTTPException(
            status_code=400,
            detail="Cart is empty",
        )
    total = sum(product.price * line.qty for line, product in lines)  
    order = models.Order(user_id=user_id, total=total)  
    db.add(order)  
    db.flush() 
    for line, product in lines:  
        db.add(models.OrderItem(order_id=order.id, product_id=product.id, qty=line.qty, unit_price=product.price)) 
        db.delete(line)  
    db.commit()  
    return {"order_id": order.id, "user_id": user_id, "total": total} 