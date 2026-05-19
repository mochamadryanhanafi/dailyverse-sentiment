import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.article_use_cases import GetArticlesUseCase, ScrapeAndPersistUseCase
from app.core.config import get_settings
from app.core.database import get_db
from app.infrastructure.repositories.article_model import ArticleModel
from app.infrastructure.repositories.article_repository_impl import PostgresArticleRepository
from app.presentation.schemas.article_schema import (
    ArticleListResponse,
    ArticleResponse,
    ScrapeRequest,
    ScrapeResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scraper", tags=["Scraper"])


@router.get("/articles/stats")
async def article_stats(
    source: str | None = Query(default=None),
    sentiment: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db)
):
    by_year_stmt = select(ArticleModel.year, func.count(ArticleModel.id).label("count"))
    if source:
        by_year_stmt = by_year_stmt.where(ArticleModel.source.ilike(f"%{source}%"))
    if sentiment:
        if sentiment.lower() == 'belum dianotasi':
            by_year_stmt = by_year_stmt.where(ArticleModel.sentiment.is_(None))
        else:
            by_year_stmt = by_year_stmt.where(ArticleModel.sentiment.ilike(sentiment))
    by_year_stmt = by_year_stmt.group_by(ArticleModel.year).order_by(ArticleModel.year)

    by_month_stmt = (
        select(ArticleModel.year, ArticleModel.month, func.count(ArticleModel.id).label("count"))
        .group_by(ArticleModel.year, ArticleModel.month)
        .order_by(ArticleModel.year, ArticleModel.month)
    )
    by_source_stmt = (
        select(ArticleModel.source, func.count(ArticleModel.id).label("count"))
        .group_by(ArticleModel.source)
        .order_by(func.count(ArticleModel.id).desc())
    )
    by_sentiment_stmt = (
        select(ArticleModel.sentiment, func.count(ArticleModel.id).label("count"))
        .group_by(ArticleModel.sentiment)
    )
    by_year_source_stmt = (
        select(ArticleModel.year, ArticleModel.source, func.count(ArticleModel.id).label("count"))
        .group_by(ArticleModel.year, ArticleModel.source)
        .order_by(ArticleModel.year)
    )
    by_year_sentiment_stmt = (
        select(ArticleModel.year, ArticleModel.sentiment, func.count(ArticleModel.id).label("count"))
        .group_by(ArticleModel.year, ArticleModel.sentiment)
        .order_by(ArticleModel.year)
    )
    
    year_result = await db.execute(by_year_stmt)
    month_result = await db.execute(by_month_stmt)
    source_result = await db.execute(by_source_stmt)
    sentiment_result = await db.execute(by_sentiment_stmt)
    year_source_result = await db.execute(by_year_source_stmt)
    year_sentiment_result = await db.execute(by_year_sentiment_stmt)
    
    return {
        "by_year": [{"year": r.year, "count": r.count} for r in year_result.all()],
        "by_month": [{"year": r.year, "month": r.month, "count": r.count} for r in month_result.all()],
        "by_source": [{"source": r.source, "count": r.count} for r in source_result.all()],
        "by_sentiment": [{"sentiment": r.sentiment or "Belum Dianotasi", "count": r.count} for r in sentiment_result.all()],
        "by_year_source": [{"year": r.year, "source": r.source, "count": r.count} for r in year_source_result.all()],
        "by_year_sentiment": [{"year": r.year, "sentiment": r.sentiment or "Belum Dianotasi", "count": r.count} for r in year_sentiment_result.all()],
    }


@router.get("/articles", response_model=ArticleListResponse)
async def list_articles(
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    source: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    sort_order: str = Query(default="desc"),
    sentiment: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    repo = PostgresArticleRepository(db)
    use_case = GetArticlesUseCase(repo)
    articles, total = await use_case.execute(
        limit=limit, offset=offset, source=source, start_date=start_date, end_date=end_date, sort_order=sort_order, sentiment=sentiment
    )
    return ArticleListResponse(
        items=[
            ArticleResponse(
                id=a.id.value,
                year=a.year,
                month=a.month,
                date=a.date,
                title=a.title,
                content=a.content,
                url=a.url,
                source=a.source,
                sentiment=a.sentiment,
                scraped_at=a.scraped_at,
            )
            for a in articles
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/run", response_model=ScrapeResponse)
async def run_scraper(
    payload: ScrapeRequest,
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    repo = PostgresArticleRepository(db)
    use_case = ScrapeAndPersistUseCase(
        repository=repo,
        start_year=payload.start_year,
        end_year=payload.end_year,
        total_target=payload.total_target,
        parallelism=settings.scraper_parallelism,
        delay=settings.scraper_delay_seconds,
    )
    result = await use_case.execute()
    return ScrapeResponse(**result)


import csv
import io
from datetime import datetime
from fastapi import APIRouter, Depends, Query, UploadFile, File
from pydantic import BaseModel

class UploadResponse(BaseModel):
    imported: int
    skipped: int
    errors: int

@router.post("/upload", response_model=UploadResponse)
async def upload_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    
    # Get existing articles to prevent (title, date) and url duplicates
    result = await db.execute(select(ArticleModel.title, ArticleModel.date, ArticleModel.url))
    rows = result.all()
    existing_set = {(r.title, r.date) for r in rows}
    existing_urls = {r.url for r in rows if r.url}
    
    imported = 0
    skipped = 0
    errors = 0
    
    new_articles = []
    
    for row in reader:
        try:
            row_title = row.get("Title", "")
            if not row_title:
                errors += 1
                continue
                
            raw_date = row.get("Date", "")
            try:
                dt = datetime.strptime(raw_date, "%d/%m/%Y").date()
            except ValueError:
                try:
                    dt = datetime.strptime(raw_date, "%Y-%m-%d").date()
                except ValueError:
                    errors += 1
                    continue
            
            # Determine URL first
            url = row.get("URL", f"csv-import-{row.get('ID_Artikel')}-{imported}")
            
            # Duplicate check
            if (row_title, dt) in existing_set or url in existing_urls:
                skipped += 1
                continue
                
            try:
                seq = int(row.get("urutan", 0))
            except:
                seq = None
                
            year = int(row.get("Year", dt.year))
            month = int(row.get("Month", dt.month))

            source_id = str(row.get("ID_Artikel", "")).strip()
            source_id_lower = source_id.lower()
            if "lip" in source_id_lower:
                mapped_src = "Liputan6"
            elif "rep" in source_id_lower:
                mapped_src = "Republika"
            elif "det" in source_id_lower:
                mapped_src = "Detik"
            elif "kom" in source_id_lower:
                mapped_src = "Kompas"
            elif "tem" in source_id_lower:
                mapped_src = "Tempo"
            elif "sua" in source_id_lower:
                mapped_src = "Suara"
            else:
                mapped_src = str(row.get("src", "")).strip() or "UNKNOWN"

            new_article = ArticleModel(
                title=row_title,
                content=row.get("Content", ""),
                url=url,
                year=year,
                month=month,
                date=dt,
                sentiment=row.get("sentimen"),
                summary=row.get("rangkuman"),
                source_origin=row.get("src_ori gin", row.get("src_origin")),
                source=mapped_src,
                sequence=seq,
                source_id=source_id if source_id else None
            )
            new_articles.append(new_article)
            existing_set.add((row_title, dt))
            existing_urls.add(url)
            imported += 1
        except Exception as e:
            errors += 1
            
    if new_articles:
        db.add_all(new_articles)
        await db.commit()
        
    return UploadResponse(imported=imported, skipped=skipped, errors=errors)

@router.get("/run/stream")
async def run_scraper_stream(payload: ScrapeRequest = Depends()):
    settings = get_settings()
    events: asyncio.Queue[str | None] = asyncio.Queue()

    def on_progress(event: str, data: dict) -> None:
        events.put_nowait(f"data: {json.dumps({'event': event, **data})}\n\n")

    async def generator() -> AsyncGenerator[str, None]:
        from app.core.database import AsyncSessionLocal
        from app.infrastructure.repositories.article_repository_impl import PostgresArticleRepository

        async def run_task():
            async with AsyncSessionLocal() as session:
                try:
                    repo = PostgresArticleRepository(session)
                    use_case = ScrapeAndPersistUseCase(
                        repository=repo,
                        start_year=payload.start_year,
                        end_year=payload.end_year,
                        total_target=payload.total_target,
                        parallelism=settings.scraper_parallelism,
                        delay=settings.scraper_delay_seconds,
                    )
                    result = await use_case.execute(on_progress=on_progress)
                    await session.commit()
                    events.put_nowait(
                        f"data: {json.dumps({'event': 'done', **result})}\n\n"
                    )
                except Exception as exc:
                    await session.rollback()
                    events.put_nowait(
                        f"data: {json.dumps({'event': 'error', 'detail': str(exc)})}\n\n"
                    )
                finally:
                    events.put_nowait(None)

        asyncio.create_task(run_task())

        while True:
            item = await events.get()
            if item is None:
                break
            yield item

    return StreamingResponse(generator(), media_type="text/event-stream")
