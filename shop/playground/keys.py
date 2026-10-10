import sqlite3

conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys = ON")

def show(title, sql, params=()):
    print(f"\n## {title}")  
    for row in conn.execute(sql, params):  
        print("  ", dict(row))

def try_sql(title, sql, params=()):  
    print(f"\n## {title}")  
    try:  
        conn.execute(sql, params)  
        print("   accepted (rule missing!)")  
    except sqlite3.IntegrityError as e:  
        print("   rejected ->", e)  

conn.execute("""
    CREATE TABLE products (
        id    INTEGER PRIMARY KEY,   
        name  TEXT    NOT NULL,      
        price INTEGER NOT NULL 
    )
""")

conn.execute("""
    CREATE TABLE cart_items (
        user_id    INTEGER NOT NULL,                          
        product_id INTEGER NOT NULL REFERENCES products(id),  
        qty        INTEGER NOT NULL,                          
        PRIMARY KEY (user_id, product_id)                    
    )
""")

conn.execute("""
    CREATE TABLE orders (
        id      INTEGER PRIMARY KEY,  
        user_id INTEGER NOT NULL,     
        total   INTEGER NOT NULL      
    )
""")

conn.execute("""
    CREATE TABLE order_items (
        order_id   INTEGER NOT NULL REFERENCES orders(id),    -- foreign key: which order this line belongs to
        product_id INTEGER NOT NULL REFERENCES products(id),  -- foreign key: which product was bought
        qty        INTEGER NOT NULL,                          -- how many were bought
        unit_price INTEGER NOT NULL,                          -- price AT ORDER TIME, so later price changes don't rewrite old orders
        PRIMARY KEY (order_id, product_id)                    -- one line per product per order
    )
""")

conn.executemany(  
    "INSERT INTO products (id, name, price) VALUES (?, ?, ?)",  
    [(1, "T-shirt", 499), (2, "Jeans", 1299), (3, "Cap", 299)],  
)
conn.executemany(  
    "INSERT INTO cart_items (user_id, product_id, qty) VALUES (?, ?, ?)",
    [(7, 2, 3), (7, 3, 1)],
)
conn.commit()

try_sql("1. cart add product 99 (doesn't exist)",  
        "INSERT INTO cart_items (user_id, product_id, qty) VALUES (?, ?, ?)", (7, 99, 1))
try_sql("2. same (user 7, Jeans) row twice", 
        "INSERT INTO cart_items (user_id, product_id, qty) VALUES (?, ?, ?)", (7, 2, 5))
try_sql("3. product with no name",  
        "INSERT INTO products (id, name, price) VALUES (?, ?, ?)", (4, None, 199))


show("4. user 7's cart joined with products",
     """SELECT c.product_id, p.name, p.price, c.qty, p.price * c.qty AS line_total  
        FROM cart_items AS c                         
        JOIN products   AS p ON p.id = c.product_id  
        WHERE c.user_id = ?""",                      
     (7,))

lines = conn.execute(  
    """SELECT c.product_id, c.qty, p.price
       FROM cart_items AS c JOIN products AS p ON p.id = c.product_id
       WHERE c.user_id = ?""", (7,)
).fetchall()  
total = sum(r["price"] * r["qty"] for r in lines)  # 1299*3 + 299*1 = 4196, priced from OUR products table

cur = conn.execute("INSERT INTO orders (user_id, total) VALUES (?, ?)", (7, total))  
order_id = cur.lastrowid  
conn.executemany(  
    "INSERT INTO order_items (order_id, product_id, qty, unit_price) VALUES (?, ?, ?, ?)",
    [(order_id, r["product_id"], r["qty"], r["price"]) for r in lines],  
)

conn.execute("DELETE FROM cart_items WHERE user_id = ?", (7,))
conn.commit() 

show("5. orders", "SELECT * FROM orders")  
show("6. order_items", "SELECT * FROM order_items")  #
show("7. cart after checkout", "SELECT COUNT(*) AS lines FROM cart_items WHERE user_id = ?", (7,))  

try_sql("8. delete Jeans while an order points to it",  # order_items still references product 2
        "DELETE FROM products WHERE id = ?", (2,))

conn.close()


