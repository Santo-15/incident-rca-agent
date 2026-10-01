from fastapi import FastAPI

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