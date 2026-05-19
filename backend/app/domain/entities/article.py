import uuid
from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True)
class ArticleId:
    value: uuid.UUID = field(default_factory=uuid.uuid4)

    def __str__(self) -> str:
        return str(self.value)


@dataclass
class Article:
    title: str
    content: str
    url: str
    year: int
    month: int
    date: date
    source: str | None = None
    sentiment: str | None = None
    id: ArticleId = field(default_factory=ArticleId)
    scraped_at: datetime = field(default_factory=datetime.utcnow)

    def is_valid(self) -> bool:
        return bool(self.title and self.content and self.url)
