ALTER TABLE article_sentences ADD COLUMN IF NOT EXISTS is_validated BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE article_sentences ADD COLUMN IF NOT EXISTS validation_status TEXT;

CREATE INDEX IF NOT EXISTS idx_article_sentences_is_validated ON article_sentences (is_validated);
