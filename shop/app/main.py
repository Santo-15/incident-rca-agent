from fastapi import FastAPI

app = FastAPI(title="shop-api")

@app.get("/")
def root():
    return {"message": "Hello from shop-api"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/version")
def version():
    return {"version": "0.1.0"}