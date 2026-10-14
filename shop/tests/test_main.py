import pytest
import redis
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select  
from sqlalchemy.orm import sessionmaker  
from app.db import Base, get_db
from app.cache import get_redis
from app.main import app
from app import models  

TEST_DB_URL = "postgresql+psycopg://shop:shop@localhost:5432/shop_test"  
test_engine = create_engine(TEST_DB_URL)  
TestSession = sessionmaker(bind=test_engine) 

TEST_REDIS_URL = "redis://localhost:6379/15"
test_redis = redis.Redis.from_url(TEST_REDIS_URL, decode_responses=True)

def override_get_db():  
    with TestSession() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db 
app.dependency_overrides[get_redis] = lambda: test_redis
client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_store():
    test_redis.flushdb()  
    Base.metadata.drop_all(test_engine)  
    Base.metadata.create_all(test_engine)  
    with TestSession() as s: 
        s.add_all([
            models.Product(id=1, name="T-shirt", price=499),
            models.Product(id=2, name="Jeans", price=1299),
            models.Product(id=3, name="Cap", price=299),
        ])
        s.commit()


def cart_rows(user_id):  
    raw = test_redis.hgetall(f"cart:{user_id}")  
    return {int(k): int(v) for k, v in raw.items()}


def order_count(): 
    with TestSession() as s:
        return len(s.scalars(select(models.Order)).all())


def test_list_products():
    r = client.get("/products")
    assert r.status_code == 200
    assert len(r.json()) == 3

def test_filter_max_price():
    r = client.get("/products", params={"max_price": 500})
    ids = [p["id"] for p in r.json()]
    assert ids == [1,3]

def test_sort_by_price_desc():
    r = client.get("/products", params={"sort": "price", "order": "desc"})
    assert r.json()[0]["id"] == 2

def test_bad_sort_gives_422():
    r = client.get("/products", params={"sort": "colour"})
    assert r.status_code == 422

def test_add_to_cart():
    r = client.post("/users/7/cart", json={"product_id": 2, "qty": 3})
    assert r.status_code == 200
    assert cart_rows(7) == {2: 3}  

def test_missing_product_gives_404():
    r = client.get("/products/99")
    assert r.status_code == 404
    assert r.json() == {"detail": "Product 99 not found"}

def test_add_unknown_product_gives_404():
    r = client.post("/users/7/cart", json={"product_id": 99, "qty": 1})
    assert r.status_code == 404
    assert cart_rows(7) == {} 

def test_add_qty_zero_gives_422():
    r = client.post("/users/7/cart", json={"product_id": 2, "qty": 0})
    assert r.status_code == 422

def test_checkout_creates_order():
    client.post("/users/7/cart", json={"product_id": 2, "qty": 3})
    r = client.post("/users/7/checkout")
    assert r.status_code == 201
    assert r.json() == {"order_id": 1, "user_id": 7, "total": 3897}
    assert cart_rows(7) == {}  

def test_checkout_empty_cart_gives_400():
    r = client.post("/users/8/checkout")
    assert r.status_code == 400
    assert order_count() == 0  

def test_cart_has_ttl():  
    client.post("/users/7/cart", json={"product_id": 2, "qty": 1})  
    assert 0 < test_redis.ttl("cart:7") <= 86400