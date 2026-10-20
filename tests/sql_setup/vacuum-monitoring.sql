CREATE TABLE jobs (id int PRIMARY KEY, state text);
INSERT INTO jobs SELECT g, 'new' FROM generate_series(1, 20000) g;
UPDATE jobs SET state = 'done' WHERE id <= 5000;
ANALYZE jobs;
