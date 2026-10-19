CREATE TABLE documents (id serial PRIMARY KEY, body text, pdf bytea);
INSERT INTO documents (body, pdf)
SELECT (SELECT string_agg(md5(random()::text || g || i), '') FROM generate_series(1, 200) i),
       decode(repeat('ff', 3000), 'hex')
FROM generate_series(1, 200) g;
ANALYZE documents;
