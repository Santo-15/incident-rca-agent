import pytest
from fastapi.testclient import TestClient

from app.main import app, CARTS, ORDERS

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_store():
    CARTS.clear()
    ORDERS.clear()

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
    r = client.post("/users/7/cart", json={"product_id": 2, "qty": 3})   # NEW  json= sends the body + Content-Type header
    assert r.status_code == 200                          # NEW  cart changed, nothing created -> 200
    assert CARTS[7] == {2: 3}   
    
def test_missing_product_gives_404():
    r = client.get("/products/99")
    assert r.status_code == 404                          # NEW  Step 6 fix: not 200 + null any more
    assert r.json() == {"detail": "Product 99 not found"}                           # NEW  user 7's cart now holds 3 Jeans

def test_add_unknown_product_gives_404():
    r = client.post("/users/7/cart", json={"product_id": 99, "qty": 1})
    assert r.status_code == 404                          # NEW  we don't sell product 99
    assert CARTS == {}     

def test_add_qty_zero_gives_422():
    r = client.post("/users/7/cart", json={"product_id": 2, "qty": 0})
    assert r.status_code == 422 

def test_checkout_creates_order():
    client.post("/users/7/cart", json={"product_id": 2, "qty": 3})       # NEW  setup: put 3 Jeans in the cart
    r = client.post("/users/7/checkout")
    assert r.status_code == 201                          # NEW  new order created -> 201
    assert r.json() == {"order_id": 1, "user_id": 7, "total": 3897}       # NEW  1299 * 3, id 1 thanks to the fixture
    assert CARTS[7] == {}  

def test_checkout_empty_cart_gives_400():
    r = client.post("/users/8/checkout")                 # NEW  user 8 never added anything
    assert r.status_code == 400                          # NEW  Step 6 fix: not a 201 ₹0 order
    assert ORDERS == {}  
