from transform_works import flatten_work, reconstruct_abstract, short_id, type_works

import pandas as pd


def test_short_id():
    assert short_id("https://openalex.org/W123") == "W123"
    assert short_id(None) is None


def test_reconstruct_abstract_orders_words_by_position():
    inverted = {"world": [1, 2], "Hello": [0]}
    assert reconstruct_abstract(inverted) == "Hello world world"


def test_reconstruct_abstract_empty():
    assert reconstruct_abstract(None) is None
    assert reconstruct_abstract({}) is None


def test_flatten_work_skips_authors_without_id_but_counts_them():
    rec = {
        "id": "https://openalex.org/W1",
        "title": "Un titre",
        "abstract_inverted_index": {"Bonjour": [0]},
        "primary_topic": {"id": "https://openalex.org/T9", "display_name": "IA"},
        "open_access": {"is_oa": True, "oa_status": "green"},
        "authorships": [
            {"author": {"id": None, "display_name": "Anonyme"}, "institutions": []},
            {
                "author": {"id": "https://openalex.org/A1", "display_name": "Ada"},
                "author_position": "first",
                "is_corresponding": True,
                "institutions": [
                    {"id": "https://openalex.org/I1", "display_name": "Univ A", "country_code": "FR", "type": "education"},
                    {"id": "https://openalex.org/I2", "display_name": "Univ B", "country_code": "DE", "type": "education"},
                ],
            },
        ],
    }
    work, links, authors, institutions = flatten_work(rec)
    assert work["work_id"] == "W1"
    assert work["abstract"] == "Bonjour"
    assert work["topic_id"] == "T9"
    assert work["n_authors"] == 2  # le compte inclut l'auteur sans identifiant
    assert [a["author_id"] for a in authors] == ["A1"]
    assert len(links) == 2  # une ligne par institution
    assert {i["institution_id"] for i in institutions} == {"I1", "I2"}


def test_flatten_work_author_without_institution_keeps_one_link():
    rec = {
        "id": "https://openalex.org/W2",
        "authorships": [{"author": {"id": "https://openalex.org/A2"}, "institutions": []}],
    }
    _, links, _, institutions = flatten_work(rec)
    assert len(links) == 1
    assert links[0]["institution_id"] is None
    assert institutions == []


def test_flatten_work_handles_empty_record():
    work, links, authors, institutions = flatten_work({})
    assert work["work_id"] is None
    assert work["abstract"] is None
    assert work["n_authors"] == 0
    assert links == [] and authors == [] and institutions == []


def test_type_works_converts_types():
    df = pd.DataFrame([{
        "publication_date": "2024-05-03",
        "publication_year": 2024,
        "cited_by_count": 5,
        "referenced_works_count": None,
        "n_authors": 2,
        "is_oa": True,
    }])
    df = type_works(df)
    assert str(df["cited_by_count"].dtype) == "Int32"
    assert pd.isna(df["referenced_works_count"].iloc[0])
    assert df["publication_date"].iloc[0].year == 2024