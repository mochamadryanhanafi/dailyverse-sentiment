import asyncio
import logging
from collections.abc import AsyncGenerator

from app.domain.entities.article import Article
from app.domain.repositories.article_repository import AbstractArticleRepository
from app.infrastructure.scraper.detik_scraper import ScraperProgressCallback, scrape_detik

logger = logging.getLogger(__name__)


class ScrapeAndPersistUseCase:
    def __init__(
        self,
        repository: AbstractArticleRepository,
        start_year: int,
        end_year: int,
        total_target: int,
        parallelism: int = 2,
        delay: float = 2.0,
    ) -> None:
        self._repo = repository
        self._start_year = start_year
        self._end_year = end_year
        self._total_target = total_target
        self._parallelism = parallelism
        self._delay = delay

    async def execute(
        self, on_progress: ScraperProgressCallback | None = None
    ) -> dict:
        articles = await scrape_detik(
            start_year=self._start_year,
            end_year=self._end_year,
            total_target=self._total_target,
            parallelism=self._parallelism,
            delay=self._delay,
            on_progress=on_progress,
        )

        saved = await self._repo.save_many(articles)
        total = await self._repo.count()

        return {
            "scraped": len(articles),
            "saved": saved,
            "total_in_db": total,
        }


class GetArticlesUseCase:
    def __init__(self, repository: AbstractArticleRepository) -> None:
        self._repo = repository

    async def execute(self, limit: int = 100, offset: int = 0, source: str | None = None, start_date: str | None = None, end_date: str | None = None, sort_order: str = "desc", sentiment: str | None = None) -> tuple[list[Article], int]:
        articles = await self._repo.find_all(limit=limit, offset=offset, source=source, start_date=start_date, end_date=end_date, sort_order=sort_order, sentiment=sentiment)
        total = await self._repo.count(source=source, start_date=start_date, end_date=end_date, sentiment=sentiment)
        return list(articles), total
