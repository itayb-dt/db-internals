CREATE TABLE articles (id serial PRIMARY KEY, body text);
INSERT INTO articles (body) SELECT 'index scan notes ' || g FROM generate_series(1, 500) g;
