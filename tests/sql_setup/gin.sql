CREATE TABLE articles (id serial PRIMARY KEY, body text);
INSERT INTO articles (body) SELECT 'index scan notes ' || g FROM generate_series(1, 500) g;
CREATE INDEX articles_fts_gin ON articles USING gin (to_tsvector('english', body));
CREATE TABLE tickets (id bigint PRIMARY KEY, tags text[], payload jsonb);
INSERT INTO tickets SELECT g, ARRAY['urgent', 'bug'], '{"status": "open"}' FROM generate_series(1, 200) g;
CREATE INDEX tickets_tags_gin ON tickets USING gin (tags);
CREATE INDEX tickets_payload_gin ON tickets USING gin (payload);
