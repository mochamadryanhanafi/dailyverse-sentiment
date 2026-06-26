CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

ALTER TABLE articles ADD COLUMN IF NOT EXISTS preprocessed_content TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS is_preprocessed BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS preprocessed_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_articles_is_preprocessed ON articles (is_preprocessed);

CREATE TABLE IF NOT EXISTS article_sentences (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id           UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    sentence_index       INTEGER NOT NULL DEFAULT 0,
    sentence_text        TEXT NOT NULL,
    sentiment            TEXT,
    is_manual_annotated  BOOLEAN NOT NULL DEFAULT FALSE,
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
