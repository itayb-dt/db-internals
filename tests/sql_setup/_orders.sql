-- shared sample data: customers and orders
CREATE TABLE customers (id bigint PRIMARY KEY, name text);
CREATE TABLE orders (
    id          bigint PRIMARY KEY,
    order_id    bigint,
    customer_id bigint,
    status      text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    total       numeric
);
INSERT INTO customers SELECT g, 'customer ' || g FROM generate_series(1, 1000) g;
INSERT INTO orders
SELECT g, g, g % 1000 + 1, (ARRAY['new', 'shipped', 'cancelled'])[1 + g % 3],
       now() - (g % 100) * interval '1 hour', g % 500
FROM generate_series(1, 20000) g;
ANALYZE customers;
ANALYZE orders;
