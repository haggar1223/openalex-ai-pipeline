"""Publie les fichiers Parquet sur le Hugging Face Hub (depot prive)."""
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import HfApi

REPO_ID = "Lassko/openalex-ai-articles"
DATA_DIR = Path("data/processed")


def main():
    load_dotenv()
    token = os.environ.get("HF_TOKEN")
    if not token:
        sys.exit("HF_TOKEN absent de .env")

    api = HfApi(token=token)
    print("Connecte en tant que :", api.whoami()["name"])

    api.create_repo(REPO_ID, repo_type="dataset", private=True, exist_ok=True)
    print("Depot pret :", REPO_ID, "(prive)")

    fichiers = list(DATA_DIR.rglob("*.parquet"))
    taille_mo = sum(f.stat().st_size for f in fichiers) / 1024**2
    print(f"A envoyer : {len(fichiers)} fichiers, {taille_mo:.1f} Mo")

    t0 = time.perf_counter()
    api.upload_folder(
        repo_id=REPO_ID,
        repo_type="dataset",
        folder_path=str(DATA_DIR),
        path_in_repo="data",
        allow_patterns="*.parquet",
        commit_message="Ajout des donnees Parquet",
    )
    print(f"Envoi termine en {time.perf_counter() - t0:.1f} s")


if __name__ == "__main__":
    main()