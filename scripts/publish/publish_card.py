"""Ecrit la Dataset Card, l'envoie sur le Hub et (re)pose le tag v1.0.0."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import HfApi
from huggingface_hub.errors import RevisionNotFoundError

REPO_ID = "Lassko/openalex-ai-articles"
TAG = "v1.0.0"
CARTE_FICHIER = Path("docs/DATASET_CARD.md")

CARTE = """---
license: cc0-1.0
pretty_name: "OpenAlex - Articles d'intelligence artificielle (2020-2025)"
size_categories:
- 100K<n<1M
tags:
- openalex
- bibliometrics
- scientometrics
- artificial-intelligence
configs:
- config_name: works
  data_files: "data/works/*.parquet"
  default: true
- config_name: authorships
  data_files: "data/authorships/*.parquet"
- config_name: authors
  data_files: "data/authors/*.parquet"
- config_name: institutions
  data_files: "data/institutions/*.parquet"
---

# OpenAlex - Articles d'intelligence artificielle (2020-2025)

Jeu de données de métadonnées d'articles scientifiques d'intelligence artificielle, extrait de l'API OpenAlex puis transformé en fichiers Parquet. Il a été produit dans le cadre d'un projet de pipeline de données : ingestion asynchrone, transformation par lots, chargement dans PostgreSQL, analyse SQL et publication.

## Contenu

Quatre tables, une par configuration :

- `works` : un article par ligne. Colonnes : `work_id`, `doi`, `title`, `abstract`, `publication_date`, `publication_year`, `type`, `language`, `cited_by_count`, `referenced_works_count`, `n_authors`, `topic_id`, `topic_name`, `subfield_name`, `field_name`, `domain_name`, `is_oa`, `oa_status`, `oa_url`.
- `authorships` : un lien article-auteur-institution par ligne. Colonnes : `work_id`, `author_id`, `author_position`, `is_corresponding`, `institution_id`.
- `authors` : `author_id`, `display_name`, `orcid`.
- `institutions` : `institution_id`, `display_name`, `country_code`, `type`.

Les fichiers Parquet sont découpés par année et par lot (`data/<table>/<table>_<annee>_part_<NNNN>.parquet`). Les tables `authors` et `institutions` peuvent contenir des doublons d'un fichier à l'autre : un même auteur ou une même institution apparaît dans chaque lot où il est cité. La déduplication est faite au chargement dans PostgreSQL.

## Volumes

Après chargement et déduplication dans PostgreSQL :

- 341 418 articles
- 605 635 auteurs
- 25 450 institutions
- 1 323 793 liens article-auteur (`authorships`)
- 72 thématiques

Les données brutes (JSON Lines) pèsent 2 166 Mo, contre 342,8 Mo en Parquet, soit un facteur de compression d'environ 6,3.

## Source et méthode

- Source : [OpenAlex](https://openalex.org), via son API.
- Filtres : sous-domaine « Artificial Intelligence » (`primary_topic.subfield.id:1702`), type `article`, présence d'un résumé, années de publication 2020 à 2025.
- Les résumés sont reconstruits à partir de l'index inversé fourni par OpenAlex (`abstract_inverted_index`).
- Les identifiants OpenAlex sont raccourcis (par exemple `W123...` au lieu de l'URL complète).
- Les signatures sans identifiant d'auteur sont ignorées. Au chargement, 85 doublons exacts de `authorships` ont été supprimés.

## Limites

- Jeu de données restreint à un seul sous-domaine et à des articles disposant d'un résumé : ce n'est pas un échantillon représentatif de toute la littérature.
- Les métadonnées d'OpenAlex peuvent contenir des erreurs (affiliations manquantes, auteurs mal désambiguïsés, thématique attribuée automatiquement).
- Les résumés restent la propriété de leurs auteurs et éditeurs. Ils sont fournis ici tels que les distribue OpenAlex.
- La langue (`language`) est détectée automatiquement et peut être inexacte.
- Instantané pris en novembre 2026 : les compteurs de citations évoluent avec le temps.

## Licence

Les données d'OpenAlex sont diffusées sous licence CC0 (domaine public). Ce jeu de données est publié sous la même licence. Merci de citer OpenAlex comme source.

## Utilisation

Chaque table se charge séparément avec la bibliothèque `datasets`, en précisant le nom de la configuration (`works`, `authorships`, `authors` ou `institutions`) et la version `v1.0.0`.

## Version

`v1.0.0` : première publication.
"""


def main():
    load_dotenv()
    token = os.environ.get("HF_TOKEN")
    if not token:
        sys.exit("HF_TOKEN absent de .env")

    # Ecriture du fichier de carte (versionne dans Git), en UTF-8 sans BOM.
    CARTE_FICHIER.parent.mkdir(exist_ok=True)
    CARTE_FICHIER.write_text(CARTE, encoding="utf-8", newline="\n")
    print("Carte ecrite :", CARTE_FICHIER, "-", len(CARTE.splitlines()), "lignes")

    api = HfApi(token=token)
    api.upload_file(
        path_or_fileobj=CARTE.encode("utf-8"),
        path_in_repo="README.md",
        repo_id=REPO_ID,
        repo_type="dataset",
        commit_message="Correction de la Dataset Card",
    )

    # Le tag existant pointe sur l'ancienne version : on le supprime et on le repose.
    try:
        api.delete_tag(REPO_ID, tag=TAG, repo_type="dataset")
    except RevisionNotFoundError:
        pass
    api.create_tag(
        REPO_ID,
        tag=TAG,
        tag_message="Version 1.0.0",
        repo_type="dataset",
    )
    refs = api.list_repo_refs(REPO_ID, repo_type="dataset")
    print("Carte envoyee. Tags du depot :", [t.name for t in refs.tags])


if __name__ == "__main__":
    main()