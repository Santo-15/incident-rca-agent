from pydantic import BaseModel, Field

class Product(BaseModel):
    id: int
    name: str
    price: int

class CartItemIn(BaseModel):
    product_id: int
    qty: int = Field(gt=0)

class CartItem(BaseModel):
    product_id: int
    name: str
    price: int
    qty: int

class CartOut(BaseModel):
    user_id:int
    items: list[CartItem]
    total: int

class CheckoutOut(BaseModel):
    order_id: int
    user_id: int
    total: int

