from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.domain.entities.article import Article


class AbstractArticleRepository(ABC):
    @abstractmethod
    async def save(self, article: Article) -> Article:
        raise NotImplementedError

    @abstractmethod
    async def save_many(self, articles: Sequence[Article]) -> int:
        raise NotImplementedError

    @abstractmethod
    async def find_by_url(self, url: str) -> Article | None:
        raise NotImplementedError

    @abstractmethod
    async def find_all(self, limit: int = 100, offset: int = 0, source: str | None = None, start_date: str | None = None, end_date: str | None = None, sort_order: str = "desc") -> Sequence[Article]:
        raise NotImplementedError

    @abstractmethod
    async def count(self, source: str | None = None, start_date: str | None = None, end_date: str | None = None) -> int:
        raise NotImplementedError
