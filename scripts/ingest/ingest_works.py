"""Ingestion asynchrone des articles OpenAlex (sous-domaine IA)."""
import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ["OPENALEX_API_KEY"]

BASE_URL = "https://api.openalex.org/works"
RAW_DIR = Path("data/raw")
CKPT_DIR = RAW_DIR / "checkpoints"
DEFAULT_YEARS = range(2020, 2026)
MAX_CONCURRENT = 3
MAX_RETRIES = 6
PER_PAGE = 100
RETRY_STATUS = {429, 500, 502, 503, 504}
SELECT = ",".join([
    "id", "doi", "title", "publication_date", "publication_year", "type",
    "language", "cited_by_count", "referenced_works_count",
    "abstract_inverted_index", "authorships", "primary_topic", "open_access",
])


async def fetch_page(session, params):
    """GET avec nouvelles tentatives et attente exponentielle."""
    for attempt in range(MAX_RETRIES):
        try:
            async with session.get(BASE_URL, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                if resp.status in RETRY_STATUS:
                    raise aiohttp.ClientResponseError(
                        resp.request_info, resp.history, status=resp.status)
                raise RuntimeError(f"HTTP {resp.status}: {(await resp.text())[:200]}")
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            if attempt == MAX_RETRIES - 1:
                raise
            delay = min(2 ** attempt, 60) + random.random()
            print(f"  nouvelle tentative {attempt + 1} dans {delay:.1f}s ({exc!r})")
            await asyncio.sleep(delay)


def load_state(path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"cursor": "*", "page": 0, "records": 0, "done": False}


def write_atomic(path, text):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


async def ingest_year(session, sem, year):
    async with sem:
        ckpt_path = CKPT_DIR / f"works_{year}.json"
        state = load_state(ckpt_path)
        if state["done"]:
            print(f"[{year}] deja termine, on saute")
            return
        print(f"[{year}] demarrage (page {state['page']}, {state['records']} enregistrements)")
        while True:
            params = {
                "filter": f"primary_topic.subfield.id:1702,type:article,"
                          f"has_abstract:true,publication_year:{year}",
                "per_page": PER_PAGE,
                "cursor": state["cursor"],
                "select": SELECT,
            }
            data = await fetch_page(session, params)
            results = data["results"]
            next_cursor = data["meta"].get("next_cursor")

            if results:
                page = state["page"] + 1
                lines = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in results)
                write_atomic(RAW_DIR / f"works_{year}_page_{page:05d}.jsonl", lines)
                state["page"] = page
                state["records"] += len(results)

            state["cursor"] = next_cursor
            state["done"] = (not results) or (next_cursor is None)
            write_atomic(ckpt_path, json.dumps(state))

            if state["page"] % 10 == 0:
                print(f"[{year}] page {state['page']}, {state['records']} enregistrements")
            if state["done"]:
                print(f"[{year}] termine : {state['records']} enregistrements")
                return


async def main(years):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CKPT_DIR.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    timeout = aiohttp.ClientTimeout(total=60, connect=10)
    headers = {"Authorization": f"Bearer {API_KEY}"}
    start = time.perf_counter()
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        await asyncio.gather(*(ingest_year(session, sem, y) for y in years))
    print(f"Duree totale : {time.perf_counter() - start:.1f}s")


if __name__ == "__main__":
    years = [int(a) for a in sys.argv[1:]] or list(DEFAULT_YEARS)
    asyncio.run(main(years))