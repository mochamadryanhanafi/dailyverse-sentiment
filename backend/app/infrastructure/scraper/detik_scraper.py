import asyncio
import logging
import re
from datetime import date
from typing import Protocol

import httpx
from bs4 import BeautifulSoup

from app.domain.entities.article import Article

logger = logging.getLogger(__name__)

BASE_URL = "https://finance.detik.com/indeks"
PRIMARY_KEYWORD = "jokowi"
SECONDARY_KEYWORDS = [
    "ekonomi", "investasi", "infrastruktur", "hilirisasi", "apbn", "utang", "pajak",
    "subsidi", "defisit", "devisa", "bansos", "kur", "umkm", "bbm", "kartu prakerja",
    "bantuan", "cipta kerja", "omnibus law", "bumn", "perppu", "nikel", "smelter",
    "tambang", "ekspor", "impor", "sawit", "freeport", "ikn", "psn", "kereta cepat",
    "tol laut", "bendungan", "bandara", "inflasi", "pertumbuhan", "kemiskinan", "pengangguran",
]

_AUTHOR_CODE_RE = re.compile(r"\s*\([a-zA-Z]{2,5}/[a-zA-Z]{2,5}\)\s*$")
_LOCATION_PREFIX_RE = re.compile(r"^[\w\s.,]+-\s*")


class ScraperProgressCallback(Protocol):
    def __call__(self, event: str, data: dict) -> None: ...


def _build_index_url(day: int, month: int, year: int) -> str:
    return f"{BASE_URL}?date={day:02d}/{month:02d}/{year}"


def _matches_keywords(title: str) -> bool:
    lower = title.lower()
    if PRIMARY_KEYWORD not in lower:
        return False
    return any(kw in lower for kw in SECONDARY_KEYWORDS)


def _clean_content(soup: BeautifulSoup) -> str:
    body = soup.select_one("div.detail__body-text")
    if not body:
        return ""
    for tag in body.select("script, style, .sisip_embed_sosmed, .paradetail, .baca-juga, .lihat-juga"):
        tag.decompose()
    text = body.get_text(separator=" ")
    text = _AUTHOR_CODE_RE.sub("", text)
    text = _LOCATION_PREFIX_RE.sub("", text)
    text = text.replace("SCROLL TO CONTINUE WITH CONTENT", "")
    return " ".join(text.split())


async def _fetch_article(
    client: httpx.AsyncClient,
    link: str,
    year: int,
    month: int,
    article_date: date,
    semaphore: asyncio.Semaphore,
    delay: float,
) -> Article | None:
    async with semaphore:
        await asyncio.sleep(delay)
        try:
            resp = await client.get(link, follow_redirects=True, timeout=15)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("HTTP %s fetching article %s", exc.response.status_code, link)
            return None
        except httpx.RequestError as exc:
            logger.warning("Request error fetching article %s: %s", link, exc)
            return None

        soup = BeautifulSoup(resp.text, "lxml")
        title_tag = soup.select_one("h1.detail__title")
        title = title_tag.get_text(strip=True) if title_tag else ""
        content = _clean_content(soup)

        if not title or not content:
            return None

        return Article(
            title=title,
            content=content,
            url=str(resp.url),
            year=year,
            month=month,
            date=article_date,
        )


async def _fetch_index_links(
    client: httpx.AsyncClient,
    day: int,
    month: int,
    year: int,
    semaphore: asyncio.Semaphore,
    delay: float,
) -> list[str]:
    url = _build_index_url(day, month, year)
    async with semaphore:
        await asyncio.sleep(delay)
        try:
            resp = await client.get(url, follow_redirects=True, timeout=15)
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Error fetching index %s: %s", url, exc)
            return []

    soup = BeautifulSoup(resp.text, "lxml")
    links: list[str] = []
    for item in soup.select("article.list-content__item"):
        title_tag = item.select_one(".media__title")
        anchor = item.select_one("a[href]")
        if not title_tag or not anchor:
            continue
        title = title_tag.get_text(strip=True)
        if _matches_keywords(title):
            href = anchor.get("href", "")
            if href:
                links.append(href)
    return links


async def scrape_detik(
    start_year: int,
    end_year: int,
    total_target: int,
    parallelism: int = 2,
    delay: float = 2.0,
    on_progress: ScraperProgressCallback | None = None,
) -> list[Article]:
    semaphore = asyncio.Semaphore(parallelism)
    collected: list[Article] = []
    total_months = (end_year - start_year + 1) * 12
    months_processed = 0

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": "https://finance.detik.com/",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
    }

    async with httpx.AsyncClient(headers=headers, http2=True) as client:
        for year in range(start_year, end_year + 1):
            for month in range(1, 13):
                if len(collected) >= total_target:
                    break

                months_remaining = total_months - months_processed
                articles_needed = total_target - len(collected)
                quota = max(1, -(-articles_needed // months_remaining)) if months_remaining > 0 else 1

                if on_progress:
                    on_progress("month_start", {
                        "year": year, "month": month,
                        "found": len(collected), "quota": quota,
                    })

                month_links: list[str] = []
                for day in range(1, 29):
                    if len(month_links) >= quota:
                        break
                    article_date = date(year, month, day)
                    links = await _fetch_index_links(client, day, month, year, semaphore, delay)
                    for lnk in links:
                        if lnk not in month_links:
                            month_links.append(lnk)

                tasks = [
                    _fetch_article(client, lnk, year, month, date(year, month, 1), semaphore, delay)
                    for lnk in month_links[:quota]
                ]
                results = await asyncio.gather(*tasks)
                month_articles = [a for a in results if a is not None]

                for art in month_articles:
                    collected.append(art)
                    if on_progress:
                        on_progress("article_scraped", {"title": art.title, "url": art.url})

                months_processed += 1
                await asyncio.sleep(1.0)

            if len(collected) >= total_target:
                break

    return collected
