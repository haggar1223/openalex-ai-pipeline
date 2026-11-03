"""Transformation par lots : JSON Lines (data/raw) -> Parquet (data/processed)."""
import json
import sys
import time
from pathlib import Path

import pandas as pd
import psutil

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/processed")
BATCH_FILES = 20  # 20 pages x 100 = 2000 enregistrements en memoire a la fois
DEFAULT_YEARS = range(2020, 2026)


def short_id(url):
    """'https://openalex.org/W123' -> 'W123'."""
    if not url:
        return None
    return url.rstrip("/").split("/")[-1]


def reconstruct_abstract(inverted):
    """Reconstruit le texte depuis l'index inverse {mot: [positions]}."""
    if not inverted:
        return None
    positions = [p for pos in inverted.values() for p in pos]
    if not positions:
        return None
    words = [""] * (max(positions) + 1)
    for word, pos in inverted.items():
        for p in pos:
            words[p] = word
    return " ".join(w for w in words if w)


def flatten_work(rec):
    """Un enregistrement brut -> (ligne works, liens, auteurs, institutions)."""
    work_id = short_id(rec.get("id"))
    topic = rec.get("primary_topic") or {}
    oa = rec.get("open_access") or {}
    authorships = rec.get("authorships") or []

    work = {
        "work_id": work_id,
        "doi": rec.get("doi"),
        "title": rec.get("title"),
        "abstract": reconstruct_abstract(rec.get("abstract_inverted_index")),
        "publication_date": rec.get("publication_date"),
        "publication_year": rec.get("publication_year"),
        "type": rec.get("type"),
        "language": rec.get("language"),
        "cited_by_count": rec.get("cited_by_count"),
        "referenced_works_count": rec.get("referenced_works_count"),
        "n_authors": len(authorships),
        "topic_id": short_id(topic.get("id")),
        "topic_name": topic.get("display_name"),
        "subfield_name": (topic.get("subfield") or {}).get("display_name"),
        "field_name": (topic.get("field") or {}).get("display_name"),
        "domain_name": (topic.get("domain") or {}).get("display_name"),
        "is_oa": oa.get("is_oa"),
        "oa_status": oa.get("oa_status"),
        "oa_url": oa.get("oa_url"),
    }

    links, authors, institutions = [], [], []
    for a in authorships:
        author = a.get("author") or {}
        author_id = short_id(author.get("id"))
        if not author_id:
            continue  # auteur non identifie : ligne ignoree
        authors.append({
            "author_id": author_id,
            "display_name": author.get("display_name"),
            "orcid": author.get("orcid"),
        })
        insts = a.get("institutions") or [None]  # une ligne meme sans institution
        for inst in insts:
            inst_id = short_id(inst.get("id")) if inst else None
            links.append({
                "work_id": work_id,
                "author_id": author_id,
                "author_position": a.get("author_position"),
                "is_corresponding": a.get("is_corresponding"),
                "institution_id": inst_id,
            })
            if inst_id:
                institutions.append({
                    "institution_id": inst_id,
                    "display_name": inst.get("display_name"),
                    "country_code": inst.get("country_code"),
                    "type": inst.get("type"),
                })
    return work, links, authors, institutions


def type_works(df):
    df["publication_date"] = pd.to_datetime(df["publication_date"], errors="coerce").dt.date
    for col in ("publication_year", "cited_by_count", "referenced_works_count", "n_authors"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int32")
    df["is_oa"] = df["is_oa"].astype("boolean")
    return df


def write_table(df, table, year, part):
    path = OUT_DIR / table / f"{table}_{year}_part_{part:04d}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False, compression="snappy")


def process_batch(files, year, part):
    works, links, authors, insts = [], [], [], []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                w, l, a, i = flatten_work(json.loads(line))
                works.append(w)
                links.extend(l)
                authors.extend(a)
                insts.extend(i)
    write_table(type_works(pd.DataFrame(works)), "works", year, part)
    write_table(pd.DataFrame(links).astype({"is_corresponding": "boolean"}), "authorships", year, part)
    write_table(pd.DataFrame(authors).drop_duplicates("author_id"), "authors", year, part)
    write_table(pd.DataFrame(insts).drop_duplicates("institution_id"), "institutions", year, part)
    return len(works)


def main(years):
    proc = psutil.Process()
    peak_mb, total = 0.0, 0
    start = time.perf_counter()
    for year in years:
        files = sorted(RAW_DIR.glob(f"works_{year}_page_*.jsonl"))
        for part, i in enumerate(range(0, len(files), BATCH_FILES), start=1):
            total += process_batch(files[i:i + BATCH_FILES], year, part)
            peak_mb = max(peak_mb, proc.memory_info().rss / 1024 ** 2)
        print(f"[{year}] termine, total cumule : {total}")
    print(f"{total} oeuvres, duree {time.perf_counter() - start:.1f}s, RAM max {peak_mb:.0f} Mo")


if __name__ == "__main__":
    main([int(a) for a in sys.argv[1:]] or list(DEFAULT_YEARS))