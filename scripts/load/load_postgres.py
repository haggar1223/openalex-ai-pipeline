"""Chargement des Parquet (data/processed) dans PostgreSQL.

Relancable sans doublons : chaque lot passe par des tables de staging temporaires,
puis INSERT ... ON CONFLICT DO NOTHING vers les tables finales.
La connexion lit PGHOST, PGPORT, PGDATABASE, PGUSER et PGPASSWORD dans le .env.
"""
import io
import time
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv()

PROCESSED = Path("data/processed")

COLS = {
    "stg_topics": ["topic_id", "topic_name", "subfield_name", "field_name", "domain_name"],
    "stg_institutions": ["institution_id", "display_name", "country_code", "type"],
    "stg_authors": ["author_id", "display_name", "orcid"],
    "stg_works": [
        "work_id", "doi", "title", "abstract", "publication_date", "publication_year",
        "type", "language", "cited_by_count", "referenced_works_count", "n_authors",
        "topic_id", "is_oa", "oa_status", "oa_url",
    ],
    "stg_authorships": [
        "work_id", "author_id", "institution_id", "author_position", "is_corresponding",
    ],
}

STAGING_DDL = {
    "stg_topics": "topic_id text, topic_name text, subfield_name text, field_name text, domain_name text",
    "stg_institutions": "institution_id text, display_name text, country_code text, type text",
    "stg_authors": "author_id text, display_name text, orcid text",
    "stg_works": (
        "work_id text, doi text, title text, abstract text, publication_date date, "
        "publication_year smallint, type text, language text, cited_by_count integer, "
        "referenced_works_count integer, n_authors integer, topic_id text, is_oa boolean, "
        "oa_status text, oa_url text"
    ),
    "stg_authorships": (
        "work_id text, author_id text, institution_id text, "
        "author_position text, is_corresponding boolean"
    ),
}

INSERTS = {
    "topics": """
        INSERT INTO topics (topic_id, topic_name, subfield_name, field_name, domain_name)
        SELECT DISTINCT ON (topic_id)
               topic_id, COALESCE(topic_name, '(inconnu)'), subfield_name, field_name, domain_name
        FROM stg_topics WHERE topic_id IS NOT NULL
        ORDER BY topic_id
        ON CONFLICT (topic_id) DO NOTHING""",
    "institutions": """
        INSERT INTO institutions (institution_id, display_name, country_code, type)
        SELECT DISTINCT ON (institution_id) institution_id, display_name, country_code, type
        FROM stg_institutions WHERE institution_id IS NOT NULL
        ORDER BY institution_id
        ON CONFLICT (institution_id) DO NOTHING""",
    "authors": """
        INSERT INTO authors (author_id, display_name, orcid)
        SELECT DISTINCT ON (author_id) author_id, display_name, orcid
        FROM stg_authors WHERE author_id IS NOT NULL
        ORDER BY author_id
        ON CONFLICT (author_id) DO NOTHING""",
    "works": """
        INSERT INTO works (work_id, doi, title, abstract, publication_date, publication_year,
                           type, language, cited_by_count, referenced_works_count, n_authors,
                           topic_id, is_oa, oa_status, oa_url)
        SELECT DISTINCT ON (work_id)
               work_id, doi, title, abstract, publication_date, publication_year,
               type, language, COALESCE(cited_by_count, 0), referenced_works_count, n_authors,
               topic_id, is_oa, oa_status, oa_url
        FROM stg_works WHERE work_id IS NOT NULL
        ORDER BY work_id
        ON CONFLICT (work_id) DO NOTHING""",
    "authorships": """
        INSERT INTO authorships (work_id, author_id, institution_id, author_position, is_corresponding)
        SELECT work_id, author_id, institution_id, author_position, is_corresponding
        FROM stg_authorships
        ON CONFLICT DO NOTHING""",
}


def copy_df(cur, staging, df):
    cols = COLS[staging]
    buf = io.StringIO()
    df[cols].to_csv(buf, index=False, header=False)
    with cur.copy(f"COPY {staging} ({', '.join(cols)}) FROM STDIN WITH (FORMAT csv)") as copy:
        copy.write(buf.getvalue())


def read_part(table, suffix):
    return pd.read_parquet(PROCESSED / table / f"{table}_{suffix}")


def main():
    work_files = sorted((PROCESSED / "works").glob("works_*_part_*.parquet"))
    if not work_files:
        raise SystemExit("Aucun fichier Parquet trouve dans data/processed/works")

    start = time.perf_counter()
    inserted = {t: 0 for t in INSERTS}
    parquet_works = 0

    with psycopg.connect() as conn:
        with conn.cursor() as cur:
            for name, ddl in STAGING_DDL.items():
                cur.execute(f"CREATE TEMP TABLE {name} ({ddl}) ON COMMIT DELETE ROWS")
        conn.commit()

        for i, wf in enumerate(work_files, start=1):
            suffix = wf.name[len("works_"):]
            works = pd.read_parquet(wf)
            parquet_works += len(works)
            topics = works[["topic_id", "topic_name", "subfield_name", "field_name", "domain_name"]]
            with conn.cursor() as cur:
                copy_df(cur, "stg_topics", topics.drop_duplicates("topic_id"))
                copy_df(cur, "stg_institutions", read_part("institutions", suffix))
                copy_df(cur, "stg_authors", read_part("authors", suffix))
                copy_df(cur, "stg_works", works)
                copy_df(cur, "stg_authorships", read_part("authorships", suffix))
                # ordre impose par les cles etrangeres
                for table in ("topics", "institutions", "authors", "works", "authorships"):
                    cur.execute(INSERTS[table])
                    inserted[table] += cur.rowcount
            conn.commit()
            if i % 20 == 0 or i == len(work_files):
                print(f"{i}/{len(work_files)} lots traites ({inserted['works']} oeuvres inserees)")

        with conn.cursor() as cur:
            totals = {}
            for table in INSERTS:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                totals[table] = cur.fetchone()[0]

    print(f"\nDuree : {time.perf_counter() - start:.1f}s")
    print("Lignes inserees pendant ce run :", inserted)
    print("Lignes presentes dans la base  :", totals)
    print(f"Reconciliation works : Parquet = {parquet_works}, base = {totals['works']}")


if __name__ == "__main__":
    main()