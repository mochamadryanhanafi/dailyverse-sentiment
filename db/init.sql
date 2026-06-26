CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS articles (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    year        SMALLINT        NOT NULL,
    month       SMALLINT        NOT NULL,
    date        DATE            NOT NULL,
    title       TEXT            NOT NULL,
    content     TEXT            NOT NULL,
    url         TEXT            NOT NULL,
    sentiment   VARCHAR(50),
    summary     TEXT,
    source_origin VARCHAR(100),
    source      VARCHAR(100),
    sequence    INTEGER,
    source_id   VARCHAR(100),
    preprocessed_content TEXT,
    is_preprocessed BOOLEAN NOT NULL DEFAULT FALSE,
    preprocessed_at TIMESTAMPTZ,
    scraped_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_articles_year_month ON articles (year, month);
CREATE INDEX IF NOT EXISTS idx_articles_date        ON articles (date);
CREATE INDEX IF NOT EXISTS idx_articles_scraped_at  ON articles (scraped_at);
CREATE INDEX IF NOT EXISTS idx_articles_is_preprocessed ON articles (is_preprocessed);

CREATE TABLE IF NOT EXISTS article_sentences (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id           UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    sentence_index       INTEGER NOT NULL DEFAULT 0,
    sentence_text        TEXT NOT NULL,
    sentiment            TEXT,
    initial_sentiment    TEXT,
    final_sentiment      TEXT,
    annotation_note      TEXT,
    is_manual_annotated  BOOLEAN NOT NULL DEFAULT FALSE,
    is_validated         BOOLEAN NOT NULL DEFAULT FALSE,
    validation_status    TEXT,
    annotator_id         UUID,
    dataset_version      TEXT,
    preprocessed_content TEXT,
    is_preprocessed      BOOLEAN NOT NULL DEFAULT FALSE,
    preprocessed_at      TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_article_sentences_article_id ON article_sentences (article_id);
CREATE INDEX IF NOT EXISTS idx_article_sentences_sentiment ON article_sentences (sentiment);
CREATE INDEX IF NOT EXISTS idx_article_sentences_is_preprocessed ON article_sentences (is_preprocessed);

CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255)    NOT NULL UNIQUE,
    username        VARCHAR(255)    NOT NULL,
    google_id       VARCHAR(255)    UNIQUE,
    picture         TEXT,
    role            VARCHAR(20)     DEFAULT 'user',
    hashed_password TEXT,
    is_active       BOOLEAN         DEFAULT TRUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

CREATE TABLE IF NOT EXISTS audit_logs (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID,
    action      TEXT NOT NULL,
    entity_id   TEXT,
    details     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs (created_at);
