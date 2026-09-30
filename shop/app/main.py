from fastapi import FastAPI

app = FastAPI(title="shop-api")

@app.get("/")
def root():
    return {"message": "Hello from shop-api"}

@app.get("/health")
def health():
    return {"status": "ok"}