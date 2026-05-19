CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS articles (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    year        SMALLINT        NOT NULL,
    month       SMALLINT        NOT NULL,
    date        DATE            NOT NULL,
    title       TEXT            NOT NULL,
    content     TEXT            NOT NULL,
    url         TEXT            NOT NULL UNIQUE,
    sentiment   VARCHAR(50),
    summary     TEXT,
    source_origin VARCHAR(100),
    source      VARCHAR(100),
    sequence    INTEGER,
    source_id   VARCHAR(100),
    scraped_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_articles_year_month ON articles (year, month);
CREATE INDEX IF NOT EXISTS idx_articles_date        ON articles (date);
CREATE INDEX IF NOT EXISTS idx_articles_scraped_at  ON articles (scraped_at);

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
