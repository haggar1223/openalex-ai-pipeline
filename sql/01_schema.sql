-- Schema OpenAlex (articles d'IA, 2020-2025)

CREATE TABLE topics (
    topic_id      TEXT PRIMARY KEY,
    topic_name    TEXT NOT NULL,
    subfield_name TEXT,
    field_name    TEXT,
    domain_name   TEXT
);

CREATE TABLE works (
    work_id                TEXT PRIMARY KEY,
    doi                    TEXT,
    title                  TEXT,
    abstract               TEXT,
    publication_date       DATE,
    publication_year       SMALLINT NOT NULL CHECK (publication_year BETWEEN 1900 AND 2100),
    type                   TEXT,
    language               TEXT,
    cited_by_count         INTEGER NOT NULL DEFAULT 0 CHECK (cited_by_count >= 0),
    referenced_works_count INTEGER CHECK (referenced_works_count >= 0),
    n_authors              INTEGER CHECK (n_authors >= 0),
    topic_id               TEXT REFERENCES topics (topic_id),
    is_oa                  BOOLEAN,
    oa_status              TEXT,
    oa_url                 TEXT
);

CREATE TABLE authors (
    author_id    TEXT PRIMARY KEY,
    display_name TEXT,
    orcid        TEXT
);

CREATE TABLE institutions (
    institution_id TEXT PRIMARY KEY,
    display_name   TEXT,
    country_code   TEXT,
    type           TEXT
);

CREATE TABLE authorships (
    authorship_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    work_id          TEXT NOT NULL REFERENCES works (work_id) ON DELETE CASCADE,
    author_id        TEXT NOT NULL REFERENCES authors (author_id),
    institution_id   TEXT REFERENCES institutions (institution_id),
    author_position  TEXT CHECK (author_position IN ('first', 'middle', 'last')),
    is_corresponding BOOLEAN,
    UNIQUE NULLS NOT DISTINCT (work_id, author_id, institution_id)
);
