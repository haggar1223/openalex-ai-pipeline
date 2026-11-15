-- Requetes d'analyse OpenAlex (articles d'IA, 2020-2025)

\echo '=== 1. Institutions les plus productives (jointure + GROUP BY)'
SELECT i.display_name,
       i.country_code,
       COUNT(DISTINCT a.work_id) AS nb_articles
FROM authorships a
JOIN institutions i ON i.institution_id = a.institution_id
GROUP BY i.institution_id, i.display_name, i.country_code
ORDER BY nb_articles DESC
LIMIT 10;

\echo '=== 2. Citations et acces ouvert par annee (GROUP BY + FILTER)'
SELECT publication_year,
       COUNT(*) AS nb_articles,
       ROUND(AVG(cited_by_count), 2) AS citations_moyennes,
       ROUND(100.0 * COUNT(*) FILTER (WHERE is_oa)
             / NULLIF(COUNT(*) FILTER (WHERE is_oa IS NOT NULL), 0), 1) AS pct_open_access
FROM works
GROUP BY publication_year
ORDER BY publication_year;

\echo '=== 3. Les 3 sujets les plus frequents par annee (CTE + ROW_NUMBER)'
WITH par_topic AS (
  SELECT w.publication_year, t.topic_name, COUNT(*) AS nb_articles
  FROM works w
  JOIN topics t ON t.topic_id = w.topic_id
  GROUP BY w.publication_year, t.topic_name
),
classement AS (
  SELECT publication_year, topic_name, nb_articles,
         ROW_NUMBER() OVER (
           PARTITION BY publication_year
           ORDER BY nb_articles DESC, topic_name
         ) AS rang
  FROM par_topic
)
SELECT publication_year, rang, topic_name, nb_articles
FROM classement
WHERE rang <= 3
ORDER BY publication_year, rang;

\echo '=== 4. Croissance annuelle du nombre d''articles (CTE + LAG)'
WITH par_annee AS (
  SELECT publication_year, COUNT(*) AS nb_articles
  FROM works
  GROUP BY publication_year
)
SELECT publication_year,
       nb_articles,
       LAG(nb_articles) OVER w AS annee_precedente,
       ROUND(100.0 * (nb_articles - LAG(nb_articles) OVER w)
             / NULLIF(LAG(nb_articles) OVER w, 0), 1) AS croissance_pct
FROM par_annee
WINDOW w AS (ORDER BY publication_year)
ORDER BY publication_year;

\echo '=== 5. Pays les plus presents (CTE + SUM OVER + RANK)'
WITH par_pays AS (
  SELECT i.country_code, COUNT(DISTINCT a.work_id) AS nb_articles
  FROM authorships a
  JOIN institutions i ON i.institution_id = a.institution_id
  WHERE i.country_code IS NOT NULL
  GROUP BY i.country_code
)
SELECT country_code,
       nb_articles,
       ROUND(100.0 * nb_articles / SUM(nb_articles) OVER (), 1) AS part_pct,
       RANK() OVER (ORDER BY nb_articles DESC) AS rang
FROM par_pays
ORDER BY rang
LIMIT 10;

\echo '=== 6. Article le plus cite de chaque sujet (CTE + ROW_NUMBER)'
WITH classement AS (
  SELECT t.topic_name, w.title, w.publication_year, w.cited_by_count,
         ROW_NUMBER() OVER (
           PARTITION BY w.topic_id
           ORDER BY w.cited_by_count DESC, w.work_id
         ) AS rang
  FROM works w
  JOIN topics t ON t.topic_id = w.topic_id
)
SELECT topic_name, title, publication_year, cited_by_count
FROM classement
WHERE rang = 1
ORDER BY cited_by_count DESC
LIMIT 10;