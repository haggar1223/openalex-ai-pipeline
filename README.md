# Pipeline de données OpenAlex : articles d'intelligence artificielle (2020-2025)

Pipeline complet, de l'API OpenAlex jusqu'à la publication d'un jeu de données : ingestion asynchrone, transformation par lots en Parquet, chargement dans PostgreSQL, analyses SQL avec un index justifié par `EXPLAIN ANALYZE`, puis publication sur le Hugging Face Hub.

- Jeu de données publié : https://huggingface.co/datasets/Lassko/openalex-ai-articles (version `v1.0.0`)
- Source : [OpenAlex](https://openalex.org), données sous licence CC0

## Architecture

    API OpenAlex
        |  ingestion asynchrone (aiohttp), JSON Lines, reprise sur checkpoints
        v
    data/raw/*.jsonl
        |  transformation par lots (pandas / pyarrow)
        v
    data/processed/{works,authorships,authors,institutions}/*.parquet
        |  chargement (staging + COPY + ON CONFLICT DO NOTHING)
        v
    PostgreSQL (5 tables, clés étrangères, contraintes CHECK)
        |  requêtes d'analyse + index
        v
    Hugging Face Hub (dépôt de données + Dataset Card, tag v1.0.0)

## Résultats mesurés

| Étape | Mesure |
|---|---|
| Ingestion | environ 57 min, 2 166 Mo de JSON Lines, années 2020 à 2025 |
| Transformation | 341 418 œuvres en 71,5 s, RAM max 147 Mo |
| Compression | 2 166 Mo (JSON Lines) vers 342,8 Mo (Parquet), soit un facteur 6,3 |
| Base PostgreSQL | 341 418 articles, 605 635 auteurs, 25 450 institutions, 1 323 793 signatures, 72 thématiques |
| Rechargement idempotent | 105,1 s, 0 ligne insérée, réconciliation Parquet = base = 341 418 |
| Index `authorships(author_id)` | 99,0 ms vers 7,1 ms (facteur 14, cache chaud) ; 150,3 ms vers 9,7 ms (cache froid) |
| Publication Hub | 692 fichiers, 342,8 Mo, 806 s |
| Tests | 7 tests pytest |

La durée d'ingestion est estimée à partir des dates d'écriture du premier et du dernier fichier. La durée du chargement initial n'a pas été mesurée : seul le rechargement (idempotent) l'a été.

## Choix techniques

- **Ingestion** : `aiohttp` avec un `Semaphore` (3 requêtes simultanées), pagination par curseur, un flux par année, délais d'expiration, nouvelles tentatives avec attente exponentielle et jitter, écritures atomiques, reprise grâce à des checkpoints.
- **Filtres OpenAlex** : sous-domaine « Artificial Intelligence » (`primary_topic.subfield.id:1702`), type `article`, présence d'un résumé, une requête par année.
- **Transformation** : traitement par lots pour borner la mémoire ; les résumés sont reconstruits à partir de `abstract_inverted_index` ; les identifiants sont raccourcis ; les signatures sans identifiant d'auteur sont ignorées (leur nombre reste compté dans `n_authors`).
- **Chargement** : tables de staging temporaires, `COPY`, puis `INSERT ... SELECT DISTINCT ON ... ON CONFLICT DO NOTHING` dans l'ordre des clés étrangères. Le script est relançable sans doublons. 85 doublons exacts de `authorships` ont été écartés.
- **Schéma** : `topics`, `works`, `authors`, `institutions`, `authorships` ; clés primaires et étrangères, contraintes `CHECK`, `UNIQUE NULLS NOT DISTINCT` sur `authorships` (PostgreSQL 15 ou plus).

## Analyses SQL et index

`sql/02_analyse.sql` contient 6 requêtes : jointures, agrégations `GROUP BY`, CTE et fonctions de fenêtrage.

`sql/03_index.sql` crée l'index `idx_authorships_author` sur `authorships(author_id)` et compare les plans `EXPLAIN (ANALYZE, BUFFERS)` avant et après, sur la recherche des articles de l'auteur le plus prolifique (444 articles) :

- avant : `Parallel Seq Scan on authorships`, coût estimé 20 121 ;
- après : `Bitmap Index Scan` puis `Bitmap Heap Scan`, coût estimé 950 ;
- gain mesuré : facteur 14 en cache chaud.

## Arborescence

    scripts/ingest/ingest_works.py        ingestion asynchrone
    scripts/transform/transform_works.py  JSON Lines vers Parquet
    scripts/load/load_postgres.py         chargement dans PostgreSQL
    scripts/publish/publish_hf.py         envoi des Parquet sur le Hub
    scripts/publish/publish_card.py       Dataset Card et tag v1.0.0
    sql/01_schema.sql                     schéma
    sql/02_analyse.sql                    requêtes d'analyse
    sql/03_index.sql                      index et comparaison EXPLAIN ANALYZE
    tests/test_transform.py               tests pytest
    docs/DATASET_CARD.md                  carte du jeu de données

## Reproduire le projet

Prérequis : Python 3.11 ou plus, PostgreSQL 15 ou plus, une clé API OpenAlex, un compte Hugging Face.

Créer un fichier `.env` à la racine (jamais versionné) avec : `OPENALEX_API_KEY`, `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `HF_TOKEN`.

    python -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install -r requirements.txt

    python scripts/ingest/ingest_works.py
    python scripts/transform/transform_works.py
    psql -f sql/01_schema.sql
    python scripts/load/load_postgres.py
    psql -f sql/02_analyse.sql
    psql -f sql/03_index.sql
    python scripts/publish/publish_hf.py
    python scripts/publish/publish_card.py

Tests : `python -m pytest -v`.

## Sécurité

Les secrets (clé OpenAlex, mot de passe PostgreSQL, token Hugging Face) ne sont que dans `.env` et dans des variables d'environnement. `.env` et `data/` sont dans `.gitignore`.

## Limites

- Le jeu de données couvre un seul sous-domaine et uniquement des articles avec résumé.
- Les métadonnées d'OpenAlex peuvent contenir des erreurs (affiliations manquantes, auteurs mal désambiguïsés).
- Les tables `authors` et `institutions` des fichiers Parquet contiennent des doublons entre lots, éliminés au chargement dans PostgreSQL.
- Instantané de novembre 2026 : les compteurs de citations évoluent.
