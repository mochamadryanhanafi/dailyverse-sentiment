import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ArticleResponse(BaseModel):
    id: uuid.UUID
    year: int
    month: int
    date: date
    title: str
    content: str
    url: str
    source: str | None = None
    sentiment: str | None = None
    scraped_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ArticleListResponse(BaseModel):
    items: list[ArticleResponse]
    total: int
    limit: int
    offset: int


class ScrapeRequest(BaseModel):
    start_year: int = 2015
    end_year: int = 2024
    total_target: int = 600


class ScrapeResponse(BaseModel):
    scraped: int
    saved: int
    total_in_db: int
