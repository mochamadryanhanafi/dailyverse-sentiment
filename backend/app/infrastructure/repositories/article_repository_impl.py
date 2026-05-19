from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.article import Article, ArticleId
from app.domain.repositories.article_repository import AbstractArticleRepository
from app.infrastructure.repositories.article_model import ArticleModel


def _to_domain(model: ArticleModel) -> Article:
    return Article(
        id=ArticleId(value=model.id),
        year=model.year,
        month=model.month,
        date=model.date,
        title=model.title,
        content=model.content,
        url=model.url,
        source=model.source,
        sentiment=model.sentiment,
        scraped_at=model.scraped_at,
    )


def _to_model(article: Article) -> dict:
    return {
        "id": article.id.value,
        "year": article.year,
        "month": article.month,
        "date": article.date,
        "title": article.title,
        "content": article.content,
        "url": article.url,
        "source": article.source,
        "sentiment": article.sentiment,
        "scraped_at": article.scraped_at,
    }


class PostgresArticleRepository(AbstractArticleRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, article: Article) -> Article:
        stmt = (
            insert(ArticleModel)
            .values(**_to_model(article))
            .on_conflict_do_nothing(index_elements=["url"])
            .returning(ArticleModel)
        )
        result = await self._session.execute(stmt)
        row = result.scalars().first()
        return _to_domain(row) if row else article

    async def save_many(self, articles: Sequence[Article]) -> int:
        if not articles:
            return 0
        stmt = (
            insert(ArticleModel)
            .values([_to_model(a) for a in articles])
            .on_conflict_do_nothing(index_elements=["url"])
        )
        result = await self._session.execute(stmt)
        return result.rowcount

    async def find_by_url(self, url: str) -> Article | None:
        stmt = select(ArticleModel).where(ArticleModel.url == url)
        result = await self._session.execute(stmt)
        row = result.scalars().first()
        return _to_domain(row) if row else None

    async def find_all(self, limit: int = 100, offset: int = 0, source: str | None = None, start_date: str | None = None, end_date: str | None = None, sort_order: str = "desc", sentiment: str | None = None) -> Sequence[Article]:
        stmt = select(ArticleModel)
        
        if source:
            stmt = stmt.where(ArticleModel.source.ilike(f"%{source}%") | ArticleModel.url.ilike(f"%{source}%"))
        if start_date:
            stmt = stmt.where(ArticleModel.date >= start_date)
        if end_date:
            stmt = stmt.where(ArticleModel.date <= end_date)
        if sentiment:
            if sentiment.lower() == 'belum dianotasi':
                stmt = stmt.where(ArticleModel.sentiment.is_(None))
            else:
                stmt = stmt.where(ArticleModel.sentiment.ilike(sentiment))
            
        if sort_order.lower() == "asc":
            stmt = stmt.order_by(ArticleModel.date.asc())
        else:
            stmt = stmt.order_by(ArticleModel.date.desc())
            
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [_to_domain(row) for row in result.scalars().all()]

    async def count(self, source: str | None = None, start_date: str | None = None, end_date: str | None = None, sentiment: str | None = None) -> int:
        stmt = select(func.count()).select_from(ArticleModel)
        
        if source:
            stmt = stmt.where(ArticleModel.source.ilike(f"%{source}%") | ArticleModel.url.ilike(f"%{source}%"))
        if start_date:
            stmt = stmt.where(ArticleModel.date >= start_date)
        if end_date:
            stmt = stmt.where(ArticleModel.date <= end_date)
        if sentiment:
            if sentiment.lower() == 'belum dianotasi':
                stmt = stmt.where(ArticleModel.sentiment.is_(None))
            else:
                stmt = stmt.where(ArticleModel.sentiment.ilike(sentiment))
            
        result = await self._session.execute(stmt)
        return result.scalar_one()
