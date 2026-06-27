from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import Base, engine
from app.presentation.routers.health_router import router as health_router
from app.presentation.routers.scraper_router import router as scraper_router
from app.presentation.routers.auth_router import router as auth_router
from app.presentation.routers.nlp_router import router as nlp_router
from app.presentation.routers.preprocessing_router import router as preprocessing_router
from app.presentation.routers.ingestion_router import router as ingestion_router
from app.presentation.routers.annotation_router import router as annotation_router
from app.infrastructure.repositories.ml_model_model import MlModelModel

from app.presentation.routers.evaluation_router import router as evaluation_router
from app.presentation.routers.training_router import router as training_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE articles DROP CONSTRAINT IF EXISTS articles_url_key"))
        await conn.execute(text("ALTER TABLE article_sentences ADD COLUMN IF NOT EXISTS is_validated BOOLEAN NOT NULL DEFAULT FALSE"))
        await conn.execute(text("ALTER TABLE article_sentences ADD COLUMN IF NOT EXISTS validation_status TEXT"))
        await conn.execute(text("ALTER TABLE article_sentences ADD COLUMN IF NOT EXISTS initial_sentiment TEXT"))
        await conn.execute(text("ALTER TABLE article_sentences ADD COLUMN IF NOT EXISTS final_sentiment TEXT"))
        await conn.execute(text("ALTER TABLE article_sentences ADD COLUMN IF NOT EXISTS annotation_note TEXT"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_article_sentences_is_validated ON article_sentences (is_validated)"))
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://frontend:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(scraper_router)
app.include_router(auth_router)
app.include_router(nlp_router)
app.include_router(preprocessing_router)
app.include_router(ingestion_router)
app.include_router(annotation_router)
app.include_router(evaluation_router)
app.include_router(training_router)

# Safe inclusion of chatbot router
try:
    from app.presentation.routers.chatbot_router import router as chatbot_router
    app.include_router(chatbot_router)
except Exception as e:
    import logging
    logging.error(f"Failed to load chatbot_router: {e}")

@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.app_title}", "version": settings.app_version}
