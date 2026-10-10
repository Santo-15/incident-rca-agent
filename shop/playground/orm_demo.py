from sqlalchemy import select
from app.db import Base, SessionLocal, engine
from app.models import CartItem, Order, OrderItem, Product

Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)

with SessionLocal() as session:
    session.add_all([
        Product(id=1, name="T-shirt", price=499),
        Product(id=2, name="Jeans", price=1299),
        Product(id=3, name="Cap", price=299),
    ])
    session.commit()
    session.add_all([CartItem(user_id=7, product_id=2, qty=3), CartItem(user_id=7, product_id=3, qty=1)])
    session.commit()
    print("\n## 1. GET /products?max_price=1000&sort=price&order=asc")
    stmt = select(Product).where(Product.price <= 1000).order_by(Product.price.asc()).limit(10)  # same SQL as Step 1, built in Python
    for p in session.scalars(stmt):  # scalars = give back Product objects (not raw rows)
        print("  ", p.id, p.name, p.price)  # attributes instead of row["name"]

    print("\n## 2. GET /products/2 and /products/99")
    print("  ", session.get(Product, 2).name)  # get = look up by primary key -> Product object
    print("  ", session.get(Product, 99))  # no row -> None (Step 5 turns this into 404)

    print("\n## 3. user 7's cart joined with products")
    stmt = (
        select(CartItem, Product)  # want both objects per row
        .join(Product, Product.id == CartItem.product_id)  # JOIN products ON products.id = cart_items.product_id
        .where(CartItem.user_id == 7)  # only user 7
    )
    lines = session.execute(stmt).all()  # execute = rows of (CartItem, Product) pairs
    for item, product in lines:  # unpack each pair
        print("  ", product.name, product.price, "x", item.qty)

    print("\n## 4. checkout for user 7")
    total = sum(product.price * item.qty for item, product in lines)  # 4196, from OUR prices
    order = Order(user_id=7, total=total)  # new order object, no id yet
    session.add(order)  # stage the INSERT
    session.flush()  # send the INSERT now (not saved yet) so Postgres gives order.id
    for item, product in lines:  # one order line per cart line
        session.add(OrderItem(order_id=order.id, product_id=product.id, qty=item.qty, unit_price=product.price))
        session.delete(item)  # stage DELETE of this cart line
    session.commit()  # order + order lines + cart deletes saved together, or none of them
    print("   order", order.id, "total", order.total)
    print("   cart lines left:", len(session.scalars(select(CartItem).where(CartItem.user_id == 7)).all()))