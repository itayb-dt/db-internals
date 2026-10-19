\ir _orders.sql
CREATE TABLE addresses (id serial PRIMARY KEY, city text, zip text);
INSERT INTO addresses (city, zip) SELECT 'city ' || (g % 50), 'zip ' || (g % 50) FROM generate_series(1, 5000) g;
ANALYZE addresses;
