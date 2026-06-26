ALTER TABLE article_sentences ADD COLUMN IF NOT EXISTS initial_sentiment TEXT;
ALTER TABLE article_sentences ADD COLUMN IF NOT EXISTS final_sentiment TEXT;
ALTER TABLE article_sentences ADD COLUMN IF NOT EXISTS annotation_note TEXT;
