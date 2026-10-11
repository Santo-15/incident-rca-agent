-- shop/playground/explain_lab.sql: Phase 3 Step 6 practice. Run against the explain_lab database only.

-- a products table shaped like ours; SERIAL = Postgres auto-numbers id
CREATE TABLE products (id SERIAL PRIMARY KEY, name TEXT NOT NULL, price INTEGER NOT NULL);

-- 200,000 fake products: names Item 1..Item 200000, random prices 0..5000
INSERT INTO products (name, price)
SELECT 'Item ' || n, (random() * 5000)::int FROM generate_series(1, 200000) AS n;

-- refresh Postgres's statistics about the table so its plans are realistic
ANALYZE products;

-- 1. GET /products?max_price=1000&sort=price&limit=10 WITHOUT an index on price
EXPLAIN ANALYZE SELECT * FROM products WHERE price <= 1000 ORDER BY price LIMIT 10;

-- add the index (same name SQLAlchemy will use in our app)
CREATE INDEX ix_products_price ON products (price);

-- 2. the same query WITH the index
EXPLAIN ANALYZE SELECT * FROM products WHERE price <= 1000 ORDER BY price LIMIT 10;

-- 3. GET /products/150000: uses the primary key's automatic index
EXPLAIN ANALYZE SELECT * FROM products WHERE id = 150000;

-- 4. search by name: no index on name, so a full scan
EXPLAIN ANALYZE SELECT * FROM products WHERE name = 'Item 150000';

-- show the table with its indexes
\d products

-- 5. preview of the slow_query chaos scenario: drop the index, run query 1 again
DROP INDEX ix_products_price;
EXPLAIN ANALYZE SELECT * FROM products WHERE price <= 1000 ORDER BY price LIMIT 10;