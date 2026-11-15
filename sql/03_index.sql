\echo === Index sur authorships(author_id) ===

DROP INDEX IF EXISTS idx_authorships_author;
ANALYZE authorships;

-- Auteur avec le plus de publications : la requete test
SELECT author_id AS top_author
FROM authorships
GROUP BY author_id
ORDER BY COUNT(*) DESC
LIMIT 1
\gset

\echo === AVANT index : 1ere execution ===
EXPLAIN (ANALYZE, BUFFERS)
SELECT w.work_id, w.title, w.cited_by_count
FROM authorships a
JOIN works w ON w.work_id = a.work_id
WHERE a.author_id = :'top_author'
ORDER BY w.cited_by_count DESC;

\echo === AVANT index : 2eme execution (cache chaud) ===
EXPLAIN (ANALYZE, BUFFERS)
SELECT w.work_id, w.title, w.cited_by_count
FROM authorships a
JOIN works w ON w.work_id = a.work_id
WHERE a.author_id = :'top_author'
ORDER BY w.cited_by_count DESC;

CREATE INDEX idx_authorships_author ON authorships (author_id);
ANALYZE authorships;

\echo === APRES index : 1ere execution ===
EXPLAIN (ANALYZE, BUFFERS)
SELECT w.work_id, w.title, w.cited_by_count
FROM authorships a
JOIN works w ON w.work_id = a.work_id
WHERE a.author_id = :'top_author'
ORDER BY w.cited_by_count DESC;

\echo === APRES index : 2eme execution (cache chaud) ===
EXPLAIN (ANALYZE, BUFFERS)
SELECT w.work_id, w.title, w.cited_by_count
FROM authorships a
JOIN works w ON w.work_id = a.work_id
WHERE a.author_id = :'top_author'
ORDER BY w.cited_by_count DESC;