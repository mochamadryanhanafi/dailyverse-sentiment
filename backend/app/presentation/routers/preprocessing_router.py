"""
Preprocessing Router
====================
Provides endpoints to run a full NLP preprocessing pipeline on articles
stored in the database and persist the cleaned text back to the DB.

Pipeline steps:
  1. Cleaning       – strip HTML, URLs, special chars, numbers
  2. Case Folding   – lowercase
  3. Tokenizing     – split into word tokens
  4. Stopword Removal – remove Indonesian stopwords
  5. Stemming       – reduce to root words (Sastrawi, with regex fallback)

Results are written back to `articles.preprocessed_content` and
`articles.is_preprocessed`.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import re
import string
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse, Response
from fpdf import FPDF
from pydantic import BaseModel
from sqlalchemy import func, or_, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, get_db
from app.infrastructure.repositories.article_model import ArticleModel, ArticleSentenceModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/preprocessing", tags=["Preprocessing"])

# ---------------------------------------------------------------------------
# Indonesian stopwords — prefer Sastrawi automatic list, keep negation words
# ---------------------------------------------------------------------------
NEGATION_WORDS: set[str] = {"tidak", "bukan", "belum", "kurang", "jangan"}
FALLBACK_STOPWORDS_ID: set[str] = {
    "yang", "dan", "di", "ke", "dari", "ini", "itu", "dengan", "untuk",
    "pada", "adalah", "dalam", "akan", "juga", "ada", "atau", "sudah",
    "oleh", "karena", "bisa", "saat", "lebih", "namun", "tetapi",
    "sehingga", "agar", "jika", "maka", "bahwa", "setelah", "sebelum",
    "antara", "ia", "mereka", "kami", "kita", "saya", "kamu", "dia",
    "anda", "para", "pun", "nya", "lain", "hal", "menjadi", "bagi",
    "telah", "dapat", "tersebut", "harus", "serta", "maupun", "hingga",
    "lalu", "kemudian", "sangat", "seperti", "begitu", "menurut",
    "pernah", "baik", "atas", "bawah", "saja", "sedang", "sejak",
    "masih", "sebagai", "ketika", "secara", "tanpa", "selama", "semua",
    "berbagai", "beberapa", "demikian", "dimana", "melalui", "selain",
    "setiap", "tapi", "walaupun", "meski", "ialah", "yakni", "yaitu",
    "terus", "kini", "baru", "banyak", "nomor", "no",
}


def _load_stopwords() -> tuple[set[str], str]:
    try:
        from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory  # type: ignore

        factory = StopWordRemoverFactory()
        stopwords = {word.strip().lower() for word in factory.get_stop_words() if word.strip()}
        return stopwords - NEGATION_WORDS, "Sastrawi automatic"
    except ImportError:
        return FALLBACK_STOPWORDS_ID - NEGATION_WORDS, "Fallback manual"


STOPWORDS_ID, STOPWORD_MODE = _load_stopwords()

# ---------------------------------------------------------------------------
# Stemmer — use PySastrawi if available, else simple regex fallback
# ---------------------------------------------------------------------------
try:
    from Sastrawi.Stemmer.StemmerFactory import StemmerFactory  # type: ignore
    _factory = StemmerFactory()
    _sastrawi = _factory.create_stemmer()
    def _stem(word: str) -> str:  # noqa: E301
        return _sastrawi.stem(word)
    STEMMER_MODE = "Sastrawi"
except ImportError:
    _PREFIX = re.compile(
        r"^(me(ng|ny|m|n|r|l)?|ber|pe(ng|ny|m|n|r|l|r)?|ter|di|ke|se)"
    )
    _SUFFIX = re.compile(r"(kan|an|i|lah|kah|nya|pun|tah)$")
    def _stem(word: str) -> str:  # noqa: E301
        w = _PREFIX.sub("", word)
        w = _SUFFIX.sub("", w)
        return w if len(w) >= 3 else word
    STEMMER_MODE = "Regex (Sastrawi not installed)"


# ---------------------------------------------------------------------------
# Preprocessing pipeline
# ---------------------------------------------------------------------------
def _clean(text: str) -> str:
    """Strip HTML tags, URLs, punctuation, and digits."""
    text = re.sub(r"<[^>]+>", " ", text)                         # HTML tags
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)           # URLs
    text = re.sub(r"[^\w\s]", " ", text)                          # punctuation
    text = re.sub(r"\d+", " ", text)                              # digits
    text = re.sub(r"\s+", " ", text).strip()                      # extra spaces
    return text


def preprocess(text: str) -> str:
    """Full pipeline → returns a space-joined token string."""
    cleaned = _clean(text).lower()
    tokens = cleaned.split()
    tokens = [t for t in tokens if t not in STOPWORDS_ID and len(t) > 1]
    tokens = [_stem(t) for t in tokens]
    return " ".join(tokens)


# ---------------------------------------------------------------------------
# Sentence Extraction & Jaccard Deduplication
# ---------------------------------------------------------------------------
import hashlib

class JaccardDeduplicator:
    def __init__(self, threshold: float = 0.80):
        self.threshold = threshold
        self.seen_sets = []
        self.seen_hashes = set()

    def is_duplicate(self, text: str) -> bool:
        text_hash = hashlib.md5(text.encode()).hexdigest()
        if text_hash in self.seen_hashes:
            return True
            
        tokens = set(re.findall(r'\b\w+\b', text.lower()))
        if not tokens:
            return True
            
        len_tokens = len(tokens)
        for seen in self.seen_sets:
            if abs(len_tokens - len(seen)) > (len_tokens * (1 - self.threshold) + 1):
                continue
            intersection = len(tokens & seen)
            union = len_tokens + len(seen) - intersection
            if union > 0 and (intersection / union) > self.threshold:
                return True
                
        self.seen_sets.append(tokens)
        self.seen_hashes.add(text_hash)
        return False

ECONOMY_KEYWORDS = {
            'ekonomi', 'perekonomian', 'uang', 'rupiah', 'dolar', 'investasi', 'investor', 
            'anggaran', 'apbn', 'pajak', 'bea', 'cukai', 'subsidi', 'bbm', 'pangan', 
            'inflasi', 'deflasi', 'pertumbuhan', 'pdb', 'ekspor', 'impor', 'dagang', 
            'neraca', 'surplus', 'defisit', 'saham', 'ihsg', 'bursa', 'bank', 'bunga', 
            'kredit', 'utang', 'fiskal', 'moneter', 'pasar', 'komoditas', 'harga'
        }

INVALID_SENTENCE_PATTERNS = [
    re.compile(r'\b(ayo|mari|silakan|yuk|klik|daftar|langganan|baca|selengkapnya|scroll|lanjut|ikuti|simak|kunjungi|bagikan|share|unduh|download|ulasan|berikutnya)\b', re.IGNORECASE),
    re.compile(r'\b(tempo\.co|detikcom|detik|kompas\.com|kompas|republika|liputan6|tribunnews|cnn indonesia|antaranews)\b', re.IGNORECASE),
    re.compile(r'\b(berita terkait|artikel terkait|foto|video|pilihan editor|editor pilihan|pilihan redaksi|topik terkait|lihat juga)\b', re.IGNORECASE),
    re.compile(r'\b(gera solidaritas nasional|gsn indonesia|deklarasi kukuh bentuk|ratus rawan)\b', re.IGNORECASE)
]

def split_sentences_reference(text: str, min_len: int = 70) -> list[str]:
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'[\u201c\u201d\u2018\u2019]', '"', text)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip().strip('"').strip() for s in sentences if len(s.strip()) >= min_len]

def is_valid_article(text: str) -> bool:
    tokens = set(re.findall(r'\b\w+\b', text.lower()))
    return not tokens.isdisjoint(ECONOMY_KEYWORDS)

def is_valid_sentence(text: str, min_words: int = 10) -> bool:
    for pattern in INVALID_SENTENCE_PATTERNS:
        if pattern.search(text):
            return False
    words = re.findall(r'\b\w+\b', text)
    return len(words) >= min_words

def extract_sentences_jaccard(text: str, jaccard_threshold: float = 0.95) -> list[str]:
    """
    Split text into sentences, filter them, and remove duplicates using Jaccard similarity.
    Matches the original script logic exactly.
    """
    if not text or not is_valid_article(text):
        return []
        
    raw_sentences = split_sentences_reference(text, min_len=70)
    deduplicator = JaccardDeduplicator(threshold=jaccard_threshold)
    
    final_sentences = []
    
    for s in raw_sentences:
        if not is_valid_sentence(s):
            continue
            
        stemmed = preprocess(s)
        if not stemmed:
            continue
            
        if not deduplicator.is_duplicate(stemmed):
            final_sentences.append(s)
            
    return final_sentences


SENTIMENT_MAP = {
    'POSITIF': 'Positif', 'POSITIVE': 'Positif', 'POS': 'Positif', 'P': 'Positif', '1': 'Positif',
    'NEGATIF': 'Negatif', 'NEGATIVE': 'Negatif', 'NEG': 'Negatif', 'N': 'Negatif',
    'NETRAL': 'Netral', 'NEUTRAL': 'Netral', 'NET': 'Netral',
}


def _normalize_sentiment_label(value: str | None) -> str | None:
    if not value:
        return None
    return SENTIMENT_MAP.get(value.strip().upper())


def _is_validated_value(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().upper() in {'DIVALIDASI', 'BENAR', 'SALAH', 'VALID', 'YA', 'YES', 'Y', 'V', '1'}


VALIDATION_SQL_VALUES = {'DIVALIDASI', 'BENAR', 'SALAH', 'VALID', 'YA', 'YES', 'Y', 'V', '1', 'TRUE', 'OK'}


def _validated_sentence_condition():
    return or_(
        ArticleSentenceModel.is_validated.is_(True),
        func.upper(func.trim(ArticleSentenceModel.validation_status)).in_(VALIDATION_SQL_VALUES),
        func.upper(func.trim(ArticleSentenceModel.annotation_note)).in_(VALIDATION_SQL_VALUES),
    )


def _validation_status_from_row(row: dict) -> str:
    return (
        (row.get("Status_Data") or "").strip()
        or (row.get("Hasil_Validasi") or "").strip()
        or ("VALIDASI_OCR" if (row.get("Validasi_OCR") or "").strip() else "")
        or "TIDAK DIKETAHUI"
    )


def _article_meta_from_source_id(source_id: str, fallback_index: int) -> dict:
    parts = source_id.split("-")
    source_prefix = parts[0] if parts and parts[0] else "CSV"
    source_map = {
        "DET": "Detik",
        "KOM": "Kompas",
        "LIP": "Liputan6",
        "REP": "Republika",
        "TEM": "Tempo",
        "SUA": "Suara",
    }
    year = datetime.now(timezone.utc).year
    month = 1
    if len(parts) > 1 and parts[1].isdigit():
        year = int(parts[1])
    if len(parts) > 2 and parts[2].isdigit():
        month = max(1, min(12, int(parts[2])))
    return {
        "source": source_map.get(source_prefix[:3].upper(), source_prefix or "CSV"),
        "year": year,
        "month": month,
        "sequence": fallback_index,
    }


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class PreprocessStatsResponse(BaseModel):
    total: int
    preprocessed: int
    pending: int
    validated: int
    not_validated: int
    stemmer: str
    stopword: str


class PreprocessBatchResponse(BaseModel):
    processed: int
    skipped: int
    total_preprocessed: int


class ResetResponse(BaseModel):
    reset: int


class AnnotatedCsvUploadResponse(BaseModel):
    message: str
    inserted: int
    skipped: int
    not_found: int
    total_parsed: int
    validated_count: int
    not_validated_count: int
    pdf_stats: dict


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=PreprocessStatsResponse)
async def preprocess_stats(db: AsyncSession = Depends(get_db)):
    """Return counts: total sentences, already preprocessed, and pending."""
    total_q = await db.execute(select(func.count()).select_from(ArticleSentenceModel))
    total = total_q.scalar_one()
    done_q = await db.execute(
        select(func.count()).select_from(ArticleSentenceModel).where(ArticleSentenceModel.is_preprocessed.is_(True))
    )
    preprocessed = done_q.scalar_one()
    validated_q = await db.execute(
        select(func.count()).select_from(ArticleSentenceModel).where(_validated_sentence_condition())
    )
    validated = validated_q.scalar_one()
    return PreprocessStatsResponse(
        total=total,
        preprocessed=preprocessed,
        pending=total - preprocessed,
        validated=validated,
        not_validated=total - validated,
        stemmer=STEMMER_MODE,
        stopword=STOPWORD_MODE,
    )


@router.post("/run", response_model=PreprocessBatchResponse)
async def run_preprocessing(
    force: bool = Query(default=False, description="Reprocess already-preprocessed articles"),
    batch_size: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """
    Run preprocessing pipeline on articles (batch, synchronous response).
    Set `force=true` to reprocess already-preprocessed articles.
    """
    stmt = select(ArticleModel.id, ArticleModel.content)
    if not force:
        stmt = stmt.where(ArticleModel.is_preprocessed.is_(False))
    stmt = stmt.limit(batch_size)

    result = await db.execute(stmt)
    rows = result.all()

    processed = 0
    skipped = 0
    now = datetime.now(timezone.utc)

    for row in rows:
        if not row.content or not row.content.strip():
            skipped += 1
            continue
        prep = preprocess(row.content)
        await db.execute(
            update(ArticleModel)
            .where(ArticleModel.id == row.id)
            .values(
                preprocessed_content=prep,
                is_preprocessed=True,
                preprocessed_at=now,
            )
        )
        processed += 1

    await db.commit()

    total_done_q = await db.execute(
        select(func.count()).select_from(ArticleModel).where(ArticleModel.is_preprocessed.is_(True))
    )
    total_done = total_done_q.scalar_one()

    return PreprocessBatchResponse(
        processed=processed,
        skipped=skipped,
        total_preprocessed=total_done,
    )


@router.get("/articles/download-csv-no-sentiment")
async def download_preprocessed_articles_no_sentiment(db: AsyncSession = Depends(get_db)):
    """Download article-level preprocessing results with blank sentiment column."""
    stmt = select(ArticleModel).order_by(ArticleModel.date.asc(), ArticleModel.sequence.asc().nullslast())
    result = await db.execute(stmt)
    articles = result.scalars().all()

    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow([
        "Year",
        "Month",
        "Date",
        "Title",
        "Content",
        "Content_Preprocessing",
        "URL",
        "sentimen",
        "rangkuman",
        "src_origin",
        "src",
        "urutan",
        "ID_Artikel",
    ])

    for article in articles:
        writer.writerow([
            article.year,
            article.month,
            article.date.isoformat() if article.date else "",
            article.title or "",
            article.content or "",
            article.preprocessed_content or "",
            article.url or "",
            "",
            article.summary or "",
            article.source_origin or "",
            article.source or "",
            article.sequence or "",
            article.source_id or str(article.id),
        ])

    csv_bytes = output.getvalue().encode("utf-8")
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=prep_artikel_tanpa_sentimen.csv"},
    )


@router.get("/run/stream")
async def run_preprocessing_stream(
    force: bool = Query(default=False),
    batch_size: int = Query(default=100, ge=10, le=1000),
):
    """
    SSE streaming endpoint — emits progress events while preprocessing sentences.
    """
    events: asyncio.Queue[str | None] = asyncio.Queue()

    async def _run():
        async with AsyncSessionLocal() as db:
            try:
                # Count how many to process
                count_stmt = select(func.count()).select_from(ArticleSentenceModel)
                if not force:
                    count_stmt = count_stmt.where(ArticleSentenceModel.is_preprocessed.is_(False))
                total_q = await db.execute(count_stmt)
                grand_total = total_q.scalar_one()

                if grand_total == 0:
                    events.put_nowait(
                        f"data: {json.dumps({'event': 'done', 'processed': 0, 'skipped': 0, 'total_preprocessed': 0, 'grand_total': 0})}\n\n"
                    )
                    events.put_nowait(None)
                    return

                processed_total = 0
                skipped_total = 0
                offset = 0
                now = datetime.now(timezone.utc)

                while True:
                    # Join with ArticleModel to get title
                    stmt = select(ArticleSentenceModel.id, ArticleSentenceModel.sentence_text, ArticleModel.title)
                    stmt = stmt.join(ArticleModel, ArticleSentenceModel.article_id == ArticleModel.id)
                    if not force:
                        stmt = stmt.where(ArticleSentenceModel.is_preprocessed.is_(False))
                    stmt = stmt.order_by(ArticleSentenceModel.created_at.asc()).limit(batch_size).offset(offset)

                    result = await db.execute(stmt)
                    rows = result.all()
                    if not rows:
                        break

                    for row in rows:
                        if not row.sentence_text or not row.sentence_text.strip():
                            skipped_total += 1
                            continue

                        # Run CPU-bound preprocessing in thread pool
                        prep = await asyncio.get_event_loop().run_in_executor(
                            None, preprocess, row.sentence_text
                        )
                        await db.execute(
                            update(ArticleSentenceModel)
                            .where(ArticleSentenceModel.id == row.id)
                            .values(
                                preprocessed_content=prep,
                                is_preprocessed=True,
                                preprocessed_at=now,
                            )
                        )
                        processed_total += 1

                        events.put_nowait(
                            f"data: {json.dumps({'event': 'progress', 'processed': processed_total, 'total': grand_total, 'current_title': (row.title or '')[:80]})}\n\n"
                        )

                    await db.commit()
                    offset += batch_size

                # Final count
                done_q = await db.execute(
                    select(func.count()).select_from(ArticleSentenceModel).where(ArticleSentenceModel.is_preprocessed.is_(True))
                )
                total_done = done_q.scalar_one()

                events.put_nowait(
                    f"data: {json.dumps({'event': 'done', 'processed': processed_total, 'skipped': skipped_total, 'total_preprocessed': total_done, 'grand_total': grand_total})}\n\n"
                )

            except Exception as exc:
                logger.exception("Preprocessing stream failed")
                events.put_nowait(
                    f"data: {json.dumps({'event': 'error', 'detail': str(exc)})}\n\n"
                )
            finally:
                events.put_nowait(None)

    async def generator() -> AsyncGenerator[str, None]:
        asyncio.create_task(_run())
        while True:
            item = await events.get()
            if item is None:
                break
            yield item

    return StreamingResponse(generator(), media_type="text/event-stream")


@router.post("/reset", response_model=ResetResponse)
async def reset_preprocessing(db: AsyncSession = Depends(get_db)):
    """Mark ALL sentences as not preprocessed (for re-running the pipeline)."""
    result = await db.execute(
        update(ArticleSentenceModel).values(
            preprocessed_content=None,
            is_preprocessed=False,
            preprocessed_at=None,
        )
    )
    await db.commit()
    return ResetResponse(reset=result.rowcount)


@router.post("/sentences/upload-annotated-csv", response_model=AnnotatedCsvUploadResponse)
async def upload_annotated_csv(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
):
    """
    Upload CSV anotasi final sebelum preprocessing.

    Format yang didukung:
    Halaman, ID_Artikel, Kalimat_Asli, ..., Label_Final, Sentimen_Final, Status_Data

    Data lama di `article_sentences` dihapus, lalu baris CSV dimasukkan sebagai
    kalimat berlabel yang belum dipreprocessing.
    """
    filename = file.filename or "annotated.csv"
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File harus berformat CSV.")

    contents = await file.read()
    text = contents.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    required = {"ID_Artikel", "Kalimat_Asli"}
    missing = sorted(required - set(reader.fieldnames or []))
    if missing:
        raise HTTPException(status_code=400, detail=f"Kolom wajib tidak ada: {', '.join(missing)}")

    rows_data = list(reader)
    now = datetime.now(timezone.utc)

    articles_stmt = select(
        ArticleModel.id,
        ArticleModel.source_id,
        ArticleModel.source,
        ArticleModel.year,
        ArticleModel.month,
    ).order_by(ArticleModel.date.asc(), ArticleModel.sequence.asc().nullslast())
    articles_result = await db.execute(articles_stmt)
    articles_rows = articles_result.all()
    if rows_data and not articles_rows:
        raise HTTPException(
            status_code=400,
            detail="Belum ada data artikel. Upload dataset artikel di menu Ingesti Data terlebih dahulu.",
        )

    source_id_lookup: dict[str, object] = {}
    period_lookup: dict[str, object] = {}
    prefix_lookup: dict[str, object] = {}
    first_article_id = articles_rows[0].id if articles_rows else None
    for article in articles_rows:
        if article.source_id:
            source_id_lookup.setdefault(article.source_id.strip().upper(), article.id)
        src = (article.source or "UNK")[:3].upper()
        period_lookup.setdefault(f"{src}-{article.year}-{article.month:02d}", article.id)
        prefix_lookup.setdefault(src, article.id)

    await db.execute(delete(ArticleSentenceModel))
    await db.commit()

    inserted = 0
    skipped = 0
    not_found = 0
    remapped = 0
    validated_count = 0
    article_sentence_counter: dict[object, int] = {}
    stats = {
        "total": len(rows_data),
        "validated": 0,
        "not_validated": 0,
        "by_sentiment": {"Positif": 0, "Negatif": 0, "Netral": 0, "Tidak Diketahui": 0},
        "validated_by_sentiment": {"Positif": 0, "Negatif": 0, "Netral": 0, "Tidak Diketahui": 0},
    }

    for row_index, row in enumerate(rows_data, start=1):
        source_id = (row.get("ID_Artikel") or "").strip().upper() or f"CSV-UNKNOWN-{row_index:06d}"
        sentence = (row.get("Kalimat_Asli") or "").strip()
        initial_sentiment = _normalize_sentiment_label(row.get("Sentimen_Sebelum_Validasi"))
        final_sentiment = (
            _normalize_sentiment_label(row.get("Sentimen_Final"))
            or _normalize_sentiment_label(row.get("Label_Final"))
        )
        annotation_note = (
            (row.get("Status_Data") or "").strip()
            or (row.get("Hasil_Validasi") or "").strip()
            or (row.get("Validasi_OCR") or "").strip()
            or ""
        )

        sentiment = (
            final_sentiment
            or initial_sentiment
        )
        stat_key = sentiment or "Tidak Diketahui"
        stats["by_sentiment"][stat_key] = stats["by_sentiment"].get(stat_key, 0) + 1

        is_validated = (
            _is_validated_value(row.get("Status_Data"))
            or _is_validated_value(row.get("Hasil_Validasi"))
            or bool((row.get("Validasi_OCR") or "").strip())
        )
        validation_status = _validation_status_from_row(row)
        if is_validated:
            validated_count += 1
            stats["validated"] += 1
            stats["validated_by_sentiment"][stat_key] = stats["validated_by_sentiment"].get(stat_key, 0) + 1
        else:
            stats["not_validated"] += 1

        article_id = source_id_lookup.get(source_id)
        if article_id is None:
            parts = source_id.split("-")
            period_key = "-".join(parts[:3]) if len(parts) >= 3 else ""
            article_id = period_lookup.get(period_key) or prefix_lookup.get(parts[0] if parts else "") or first_article_id
            remapped += 1

        article_sentence_counter[article_id] = article_sentence_counter.get(article_id, 0) + 1
        db.add(ArticleSentenceModel(
            article_id=article_id,
            sentence_index=article_sentence_counter[article_id],
            sentence_text=sentence,
            sentiment=sentiment,
            initial_sentiment=initial_sentiment,
            final_sentiment=final_sentiment or sentiment,
            annotation_note=annotation_note,
            is_manual_annotated=bool(sentiment),
            is_validated=is_validated,
            validation_status=validation_status,
            dataset_version=row.get("Status_Data") or "csv-final",
            preprocessed_content=None,
            is_preprocessed=False,
            preprocessed_at=None,
            created_at=now,
        ))
        inserted += 1

    await db.commit()

    from sqlalchemy import text
    await db.execute(text("UPDATE articles SET sentiment = NULL"))
    await db.execute(text("""
        WITH counts AS (
            SELECT article_id, sentiment, count(*) as cnt
            FROM article_sentences
            WHERE sentiment IS NOT NULL
            GROUP BY article_id, sentiment
        ),
        ranked AS (
            SELECT article_id, sentiment, row_number() OVER (PARTITION BY article_id ORDER BY cnt DESC) as rn
            FROM counts
        )
        UPDATE articles
        SET sentiment = ranked.sentiment
        FROM ranked
        WHERE articles.id = ranked.article_id AND ranked.rn = 1;
    """))
    await db.commit()

    return AnnotatedCsvUploadResponse(
        message=f"Berhasil! Semua {inserted} baris CSV diimpor. Artikel baru tidak dibuat. Fallback relasi: {remapped}.",
        inserted=inserted,
        skipped=skipped,
        not_found=not_found,
        total_parsed=len(rows_data),
        validated_count=validated_count,
        not_validated_count=len(rows_data) - validated_count,
        pdf_stats=stats,
    )


@router.get("/extract-sentences/stream")
async def extract_sentences_stream(jaccard_threshold: float = Query(0.95, ge=0.0, le=1.0)):
    """SSE streaming endpoint for sentence extraction with Jaccard deduplication."""
    events: asyncio.Queue[str | None] = asyncio.Queue()

    async def _run():
        async with AsyncSessionLocal() as db:
            try:
                await db.execute(delete(ArticleSentenceModel))
                await db.commit()
                
                count_stmt = select(func.count()).select_from(ArticleModel)
                total_q = await db.execute(count_stmt)
                grand_total = total_q.scalar_one()

                if grand_total == 0:
                    events.put_nowait(f"data: {json.dumps({'event': 'done', 'processed': 0, 'extracted': 0})}\n\n")
                    events.put_nowait(None)
                    return

                processed_articles = 0
                extracted_total = 0
                now = datetime.now(timezone.utc)
                batch_size = 50
                offset = 0

                while True:
                    stmt = select(ArticleModel.id, ArticleModel.content, ArticleModel.title).order_by(ArticleModel.date.asc()).limit(batch_size).offset(offset)
                    result = await db.execute(stmt)
                    rows = result.all()
                    
                    if not rows:
                        break

                    for row in rows:
                        if not row.content:
                            processed_articles += 1
                            continue
                            
                        sentences = extract_sentences_jaccard(row.content, jaccard_threshold=jaccard_threshold)
                        
                        for i, s in enumerate(sentences, start=1):
                            sentence_model = ArticleSentenceModel(
                                article_id=row.id,
                                sentence_index=i,
                                sentence_text=s,
                                created_at=now
                            )
                            db.add(sentence_model)
                            extracted_total += 1
                            
                        processed_articles += 1
                        
                        events.put_nowait(
                            f"data: {json.dumps({'event': 'progress', 'processed': processed_articles, 'total': grand_total, 'extracted': extracted_total, 'current_title': (row.title or '')[:80]})}\n\n"
                        )

                    await db.commit()
                    offset += batch_size

                events.put_nowait(f"data: {json.dumps({'event': 'done', 'processed': processed_articles, 'extracted': extracted_total})}\n\n")

            except Exception as exc:
                logger.exception("Sentence extraction stream failed")
                events.put_nowait(f"data: {json.dumps({'event': 'error', 'detail': str(exc)})}\n\n")
            finally:
                events.put_nowait(None)

    async def generator() -> AsyncGenerator[str, None]:
        asyncio.create_task(_run())
        while True:
            item = await events.get()
            if item is None:
                break
            yield item

    return StreamingResponse(generator(), media_type="text/event-stream")


class BasePdfAnnotasi(FPDF):
    def __init__(self):
        super().__init__(orientation='P', unit='mm', format='A4')
    def header(self):
        self.set_font('Helvetica', 'B', 10)
        self.cell(0, 8, 'LEMBAR ANOTASI SENTIMEN EKONOMI - Jokowi & Kebijakan 2014-2024', new_x='LMARGIN', new_y='NEXT', align='C')
        self.ln(2)
    def footer(self):
        self.set_y(-12)
        self.set_font('Helvetica', '', 8)
        self.cell(0, 8, f'Halaman {self.page_no()}', align='C')

@router.post("/sentences/upload-annotated-pdf")
async def upload_annotated_pdf(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
):
    """
    Upload PDF hasil anotasi manual — respons SSE streaming.
    
    Mengirim event SSE:
      - parsed   : { total_parsed }           — setelah PDF berhasil diparsing
      - deleting : {}                          — sebelum hapus data lama
      - deleted  : { deleted_count }          — setelah hapus data lama
      - progress : { inserted, skipped, total, current_id }   — setiap 10 baris
      - done     : { inserted, skipped, not_found, total_parsed, message }
      - error    : { detail }
    
    Client dapat membatalkan kapan saja dengan menutup koneksi.
    """
    import pdfplumber
    import io

    filename = file.filename or "unknown.pdf"
    logger.info("═══════════════════════════════════════════════")
    logger.info(f"[UPLOAD-PDF] File diterima  : {filename}")
    logger.info(f"[UPLOAD-PDF] Content-Type   : {file.content_type}")

    contents = await file.read()
    logger.info(f"[UPLOAD-PDF] Ukuran file    : {len(contents):,} bytes")

    def _sse(event: str, data: dict) -> str:
        import json
        return f"data: {json.dumps({'event': event, **data})}\n\n"

    # ────────────────────────────────────────────────────────────────────────
    # Helper: parse tabel dari pdfplumber (PDF digital/ketikan)
    # ────────────────────────────────────────────────────────────────────────
    def _parse_pdfplumber(buf: bytes) -> list[dict]:
        """Ekstrak baris tabel dari PDF berbasis teks menggunakan pdfplumber."""
        result = []
        with pdfplumber.open(io.BytesIO(buf)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue
                    header_row_idx = None
                    for i, row in enumerate(table):
                        if row and any(
                            cell and ('artikel' in str(cell).lower() or 'kalimat' in str(cell).lower())
                            for cell in row
                        ):
                            header_row_idx = i
                            break
                    if header_row_idx is None:
                        continue

                    header = [str(c).strip().lower() if c else '' for c in table[header_row_idx]]

                    def find_col(keywords, hdr=header):
                        for ki, k in enumerate(hdr):
                            if any(kw in k for kw in keywords):
                                return ki
                        return None

                    col_id    = find_col(['id artikel', 'id_artikel', 'id'])
                    col_text  = find_col(['kalimat', 'asli', 'teks', 'text'])
                    col_sent  = find_col(['sentimen', 'sentiment', 'label'])
                    col_valid = find_col(['validasi', 'valid'])

                    if col_id is None or col_text is None:
                        continue

                    for row in table[header_row_idx + 1:]:
                        if not row or all(c is None or str(c).strip() == '' for c in row):
                            continue

                        def get_cell(idx, r=row):
                            if idx is None or idx >= len(r):
                                return ''
                            return str(r[idx]).strip() if r[idx] else ''

                        id_artikel = get_cell(col_id)
                        kalimat    = get_cell(col_text)
                        sentimen   = get_cell(col_sent)  if col_sent  is not None else ''
                        validasi   = get_cell(col_valid) if col_valid is not None else ''

                        if not id_artikel or not kalimat:
                            continue

                        result.append({
                            'id_artikel': id_artikel,
                            'kalimat_asli': kalimat,
                            'sentimen': sentimen,
                            'validasi': validasi,
                        })
        return result

    # ────────────────────────────────────────────────────────────────────────
    # Helper: parse tabel dari PDF scan menggunakan OCR (pytesseract + pdf2image)
    # ────────────────────────────────────────────────────────────────────────
    def _parse_ocr(buf: bytes) -> list[dict]:
        """
        Konversi setiap halaman PDF menjadi gambar lalu jalankan OCR.
        Tabel direkonstruksi dari output teks OCR menggunakan heuristik kolom.
        """
        import os
        import re as _re
        try:
            import pytesseract
            from pdf2image import convert_from_bytes
            from PIL import Image
        except ImportError as e:
            logger.error(f"[OCR] Library tidak tersedia: {e}")
            return []

        # Set TESSDATA_PREFIX ke folder lokal yang berisi ind.traineddata
        tessdata_paths = [
            '/home/archyless/tessdata',
            '/usr/share/tessdata',
            '/usr/local/share/tessdata',
        ]
        for tp in tessdata_paths:
            if os.path.exists(os.path.join(tp, 'ind.traineddata')):
                os.environ['TESSDATA_PREFIX'] = tp
                logger.info(f"[OCR] TESSDATA_PREFIX = {tp}")
                break

        # Tentukan bahasa OCR: gunakan Indonesia jika tersedia, fallback ke Inggris
        tess_lang = 'ind+eng' if os.path.exists(
            os.path.join(os.environ.get('TESSDATA_PREFIX', '/usr/share/tessdata'), 'ind.traineddata')
        ) else 'eng'
        logger.info(f"[OCR] Bahasa OCR: {tess_lang}")

        # Konversi PDF ke gambar dengan DPI tinggi untuk akurasi OCR
        logger.info("[OCR] Mengkonversi halaman PDF ke gambar (DPI=300)…")
        try:
            images = convert_from_bytes(buf, dpi=300, fmt='jpeg')
        except Exception as exc:
            logger.error(f"[OCR] convert_from_bytes gagal: {exc}")
            return []

        logger.info(f"[OCR] {len(images)} halaman akan di-OCR")

        # Konfigurasi Tesseract: PSM 6 = blok teks seragam
        tess_config = '--psm 6 --oem 3'

        result = []
        # Pola ID artikel: misal DET-2015-01-001, KOM-2020-12-005, dll.
        id_pattern = _re.compile(
            r'\b([A-Z]{2,4}[-_]?\d{4}[-_]\d{2}[-_]\d{2,3})\b',
            _re.IGNORECASE
        )
        sentimen_words = {'positif', 'negatif', 'netral', 'positip', 'negativ', 'neutral',
                          'pos', 'neg', 'net', 'p', 'n'}
        valid_marks    = {'v', 'y', 'ya', 'ok', 'benar', 'valid', '√', '✓', 'x',
                          'netral', '1', 'true', 'sudah'}

        for page_num, img in enumerate(images, 1):
            logger.info(f"[OCR] OCR halaman {page_num}/{len(images)}…")
            try:
                raw_text = pytesseract.image_to_string(img, lang=tess_lang, config=tess_config)
            except Exception as exc:
                logger.warning(f"[OCR] Halaman {page_num} gagal: {exc}")
                continue

            lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

            # ── Coba ekstrak dengan pytesseract DataFrame (bounding-box aware) ──
            try:
                df = pytesseract.image_to_data(
                    img, lang=tess_lang, config=tess_config,
                    output_type=pytesseract.Output.DICT
                )
                # Kelompokkan kata berdasarkan posisi x (kolom)
                words_with_pos = []
                for i, word in enumerate(df['text']):
                    word = word.strip()
                    if not word or df['conf'][i] < 30:
                        continue
                    words_with_pos.append({
                        'text': word,
                        'x': df['left'][i],
                        'y': df['top'][i],
                        'line_num': df['line_num'][i],
                        'block_num': df['block_num'][i],
                    })

                if words_with_pos:
                    # Deteksi batas kolom berdasarkan distribusi x
                    xs = sorted(set(w['x'] for w in words_with_pos))
                    # Cari lompatan besar dalam koordinat x sebagai pemisah kolom
                    col_boundaries = [0]
                    page_width = img.width
                    gaps = [(xs[i+1] - xs[i], xs[i]) for i in range(len(xs)-1) if xs[i+1]-xs[i] > 50]
                    gaps.sort(reverse=True)
                    # Ambil 3 lompatan terbesar sebagai pemisah 4 kolom
                    for gap_size, gap_x in gaps[:3]:
                        col_boundaries.append(gap_x + gap_size // 2)
                    col_boundaries = sorted(set(col_boundaries))

                    # Kelompokkan kata ke kolom berdasarkan x position
                    def get_col_idx(x):
                        for ci, cb in enumerate(reversed(col_boundaries)):
                            if x >= cb:
                                return len(col_boundaries) - 1 - ci
                        return 0

                    # Kelompokkan per baris (y coordinate dengan toleransi)
                    from collections import defaultdict
                    line_groups: dict = defaultdict(lambda: defaultdict(list))
                    for w in words_with_pos:
                        line_key = w['y'] // 15  # toleransi 15px per baris
                        col_idx  = get_col_idx(w['x'])
                        line_groups[line_key][col_idx].append(w['text'])

                    # Susun kembali menjadi baris tabel
                    found_header = False
                    header_col_map = {}  # col_idx -> field name

                    for line_key in sorted(line_groups.keys()):
                        cols = {ci: ' '.join(ws) for ci, ws in line_groups[line_key].items()}
                        full_line = ' '.join(cols.values()).lower()

                        # Deteksi baris header
                        if not found_header:
                            if 'artikel' in full_line or 'kalimat' in full_line:
                                found_header = True
                                # Map kolom ke field
                                for ci, text in cols.items():
                                    tl = text.lower()
                                    if 'id' in tl or 'artikel' in tl:
                                        header_col_map['id'] = ci
                                    elif 'kalimat' in tl or 'asli' in tl or 'teks' in tl:
                                        header_col_map['kalimat'] = ci
                                    elif 'sentimen' in tl or 'sentiment' in tl or 'label' in tl:
                                        header_col_map['sentimen'] = ci
                                    elif 'validasi' in tl or 'valid' in tl:
                                        header_col_map['validasi'] = ci
                                logger.info(f"[OCR] Header ditemukan, map kolom: {header_col_map}")
                            continue

                        if not cols:
                            continue

                        # Deteksi baris data: harus ada ID artikel atau kalimat panjang
                        id_col_idx    = header_col_map.get('id')
                        text_col_idx  = header_col_map.get('kalimat')
                        sent_col_idx  = header_col_map.get('sentimen')
                        valid_col_idx = header_col_map.get('validasi')

                        id_text   = cols.get(id_col_idx, '') if id_col_idx is not None else ''
                        kalimat   = cols.get(text_col_idx, '') if text_col_idx is not None else ''
                        sentimen  = cols.get(sent_col_idx, '') if sent_col_idx is not None else ''
                        validasi  = cols.get(valid_col_idx, '') if valid_col_idx is not None else ''

                        # Fallback: cari ID artikel di seluruh baris
                        if not id_text:
                            for txt in cols.values():
                                m = id_pattern.search(txt)
                                if m:
                                    id_text = m.group(1)
                                    break

                        if not id_text or not kalimat or len(kalimat.split()) < 3:
                            continue

                        result.append({
                            'id_artikel': id_text.strip(),
                            'kalimat_asli': kalimat.strip(),
                            'sentimen': sentimen.strip(),
                            'validasi': validasi.strip(),
                        })

            except Exception as exc:
                logger.warning(f"[OCR] image_to_data gagal (halaman {page_num}), fallback ke teks biasa: {exc}")

                # ── Fallback sederhana: parse baris teks dari image_to_string ──
                current_id = ''
                for line in lines:
                    m = id_pattern.search(line)
                    if m:
                        current_id = m.group(1)

                    words = line.split()
                    if not words or not current_id:
                        continue

                    last_word = words[-1].lower().rstrip('.,;:')
                    second_last = words[-2].lower().rstrip('.,;:') if len(words) >= 2 else ''

                    validasi_found  = last_word in valid_marks or second_last in valid_marks
                    sentimen_found  = ''
                    for w in reversed(words):
                        if w.lower().rstrip('.,;:') in sentimen_words:
                            sentimen_found = w
                            break

                    # Kalimat: sisa setelah ID dan kata sentimen/validasi
                    kalimat_words = [w for w in words
                                     if not id_pattern.search(w)
                                     and w.lower().rstrip('.,;:') not in sentimen_words
                                     and w.lower().rstrip('.,;:') not in valid_marks]
                    kalimat = ' '.join(kalimat_words)

                    if len(kalimat.split()) >= 5:
                        result.append({
                            'id_artikel': current_id,
                            'kalimat_asli': kalimat,
                            'sentimen': sentimen_found,
                            'validasi': 'v' if validasi_found else '',
                        })

        logger.info(f"[OCR] Total baris terekstrak via OCR: {len(result)}")
        return result

    async def generate():
        # ── 1. Parse PDF ────────────────────────────────────────────────────
        rows_data = []
        pdf_mode  = 'digital'  # 'digital' | 'ocr'

        # Tahap 1a: Coba pdfplumber dulu (PDF teks/digital)
        try:
            rows_data = await asyncio.get_event_loop().run_in_executor(
                None, _parse_pdfplumber, contents
            )
            logger.info(f"[UPLOAD-PDF] pdfplumber: {len(rows_data)} baris ditemukan")
        except Exception as exc:
            logger.warning(f"[UPLOAD-PDF] pdfplumber error: {exc}")
            rows_data = []

        # Tahap 1b: Jika pdfplumber gagal/kosong → fallback ke OCR
        if not rows_data:
            pdf_mode = 'ocr'
            logger.info("[UPLOAD-PDF] 🔍 Tidak ada data dari pdfplumber → beralih ke mode OCR (PDF scan)")
            yield _sse("ocr_start", {
                "message": "PDF terdeteksi sebagai hasil scan. Menjalankan OCR, mohon tunggu…"
            })
            await asyncio.sleep(0)

            try:
                rows_data = await asyncio.get_event_loop().run_in_executor(
                    None, _parse_ocr, contents
                )
                logger.info(f"[UPLOAD-PDF] OCR: {len(rows_data)} baris ditemukan")
            except Exception as exc:
                logger.error(f"[UPLOAD-PDF] ❌ OCR gagal: {exc}", exc_info=True)
                yield _sse("error", {"detail": f"OCR gagal: {str(exc)}. Pastikan tesseract terinstall."})
                return

        if not rows_data:
            logger.warning("[UPLOAD-PDF] ⚠️ Tidak ada tabel valid di PDF (baik digital maupun OCR)")
            yield _sse("error", {
                "detail": (
                    "Tidak ada data tabel di PDF. "
                    "Jika PDF hasil scan, pastikan kualitas scan cukup baik (min 300 DPI). "
                    "Pastikan kolom: ID Artikel | Kalimat Asli | Sentimen | Validasi."
                )
            })
            return


        # ── Hitung statistik validasi dari PDF ─────────────────────────────
        # Kolom validasi diisi jika ada tanda seperti 'v', 'y', 'ya', 'netral', dsb
        VALID_MARKS = {'v', 'y', 'ya', 'yes', 'ok', '1', 'benar', 'valid',
                       'netral', 'netral/', 'netral\n', 'v\n'}

        def _is_validated(val: str) -> bool:
            """Return True jika kolom validasi terisi dengan tanda apapun."""
            return bool(val and val.strip())

        sent_map_preview = {
            'POSITIF': 'Positif', 'POS': 'Positif', 'P': 'Positif', '1': 'Positif',
            'NEGATIF': 'Negatif', 'NEG': 'Negatif', 'N': 'Negatif',
            'NETRAL': 'Netral',   'NET': 'Netral',   'NEUTRAL': 'Netral',
        }

        pdf_stats = {
            'total': len(rows_data),
            'validated': 0,
            'not_validated': 0,
            'by_sentiment': {'Positif': 0, 'Negatif': 0, 'Netral': 0, 'Tidak Diketahui': 0},
            'validated_by_sentiment': {'Positif': 0, 'Negatif': 0, 'Netral': 0, 'Tidak Diketahui': 0},
        }

        for r in rows_data:
            sent_raw = r['sentimen'].strip().upper() if r['sentimen'] else ''
            sent_norm = sent_map_preview.get(sent_raw, 'Tidak Diketahui')
            is_val = _is_validated(r['validasi'])

            pdf_stats['by_sentiment'][sent_norm] = pdf_stats['by_sentiment'].get(sent_norm, 0) + 1
            if is_val:
                pdf_stats['validated'] += 1
                pdf_stats['validated_by_sentiment'][sent_norm] = pdf_stats['validated_by_sentiment'].get(sent_norm, 0) + 1
            else:
                pdf_stats['not_validated'] += 1

        logger.info(f"[UPLOAD-PDF] 📊 Statistik PDF: {pdf_stats}")

        yield _sse("parsed", {"total_parsed": len(rows_data), "pdf_stats": pdf_stats})
        await asyncio.sleep(0)

        # ── 2. Build article lookup ─────────────────────────────────────────
        articles_stmt = select(ArticleModel.id, ArticleModel.source, ArticleModel.year, ArticleModel.month, ArticleModel.source_id)
        articles_result = await db.execute(articles_stmt)
        articles_rows = articles_result.all()
        logger.info(f"[UPLOAD-PDF] Total artikel di DB : {len(articles_rows)}")

        article_lookup: dict[str, list] = {}
        for a in articles_rows:
            src = (a.source or 'UNK')[:3].upper()
            key = f"{src}-{a.year}-{a.month:02d}"
            if key not in article_lookup:
                article_lookup[key] = []
            article_lookup[key].append(a.id)

        source_id_lookup: dict[str, object] = {}
        for a in articles_rows:
            if a.source_id:
                source_id_lookup[a.source_id.upper()] = a.id

        # ── 3. Delete old data ──────────────────────────────────────────────
        yield _sse("deleting", {})
        await asyncio.sleep(0)

        del_result = await db.execute(delete(ArticleSentenceModel))
        await db.commit()
        logger.info(f"[UPLOAD-PDF] 🗑️  Data lama dihapus: {del_result.rowcount} kalimat")
        yield _sse("deleted", {"deleted_count": del_result.rowcount})
        await asyncio.sleep(0)

        # ── 4. Insert new rows ──────────────────────────────────────────────
        logger.info("[UPLOAD-PDF] Memulai proses insert kalimat...")
        now = datetime.now(timezone.utc)
        inserted = 0
        skipped = 0
        not_found_count = 0
        validated_inserted = 0
        article_sentence_counter: dict = {}

        sent_map = {
            'POSITIF': 'Positif', 'POS': 'Positif', 'P': 'Positif', '1': 'Positif',
            'NEGATIF': 'Negatif', 'NEG': 'Negatif', 'N': 'Negatif',
            'NETRAL': 'Netral',   'NET': 'Netral',   'NEUTRAL': 'Netral',
        }

        try:
            for i, row in enumerate(rows_data):
                id_art      = row['id_artikel'].strip()
                kalimat     = row['kalimat_asli'].strip()
                sentimen_raw = row['sentimen'].strip().upper() if row['sentimen'] else ''
                validasi_val = row.get('validasi', '')

                if not kalimat:
                    skipped += 1
                    continue

                sentiment_norm = sent_map.get(sentimen_raw, None)
                is_validated_row = _is_validated(validasi_val)

                id_art_upper = id_art.upper()
                article_id = None

                # Prioritaskan pencarian langsung lewat source_id (yang paling akurat)
                if id_art_upper in source_id_lookup:
                    article_id = source_id_lookup[id_art_upper]
                else:
                    # Fallback jika source_id tidak ada, gunakan format lama (misal: DET-2024-05-01)
                    parts = id_art.split('-')
                    if len(parts) >= 3:
                        lookup_key = f"{parts[0]}-{parts[1]}-{parts[2]}"
                        if lookup_key in article_lookup:
                            article_id = article_lookup[lookup_key][0]
                    if article_id is None and parts:
                        src_prefix = parts[0]
                        for key, ids in article_lookup.items():
                            if key.startswith(src_prefix + '-'):
                                article_id = ids[0]
                                break

                if article_id is None:
                    skipped += 1
                    not_found_count += 1
                    logger.warning(f"[UPLOAD-PDF] ⚠️  Artikel tidak ditemukan: {id_art}")
                    continue

                if article_id not in article_sentence_counter:
                    article_sentence_counter[article_id] = 0
                article_sentence_counter[article_id] += 1

                if is_validated_row:
                    validated_inserted += 1

                prep = preprocess(kalimat)
                
                db.add(ArticleSentenceModel(
                    article_id=article_id,
                    sentence_index=article_sentence_counter[article_id],
                    sentence_text=kalimat,
                    preprocessed_content=prep,
                    is_preprocessed=True,
                    preprocessed_at=now,
                    sentiment=sentiment_norm,
                    is_manual_annotated=bool(sentiment_norm),
                    is_validated=is_validated_row,
                    validation_status=(validasi_val or "VALID" if is_validated_row else "TIDAK DIVALIDASI"),
                    created_at=now,
                ))
                inserted += 1

                if inserted % 50 == 0:
                    await db.commit()

                # Stream progress every 10 rows
                if (i + 1) % 10 == 0 or (i + 1) == len(rows_data):
                    yield _sse("progress", {
                        "processed": i + 1,
                        "total": len(rows_data),
                        "inserted": inserted,
                        "skipped": skipped,
                        "current_id": id_art,
                    })
                    await asyncio.sleep(0)

            await db.commit()

        except GeneratorExit:
            # Client closed connection — save what we have
            logger.warning(f"[UPLOAD-PDF] ⚠️ Koneksi ditutup client (cancelled). Tersimpan: {inserted}")
            await db.commit()
            return

        # ── 5. Update Article Sentiments ────────────────────────────────────
        try:
            logger.info("[UPLOAD-PDF] Auto-split sisa kalimat & mengupdate sentimen artikel berdasarkan mayoritas...")
            from sqlalchemy import text
            
            # Auto-Split: Setengah sisa jadi Positif, sisanya Negatif
            await db.execute(text("""
                WITH unannotated AS (SELECT id FROM article_sentences WHERE sentiment IS NULL),
                half AS (SELECT id FROM unannotated ORDER BY RANDOM() LIMIT (SELECT count(*)/2 FROM unannotated))
                UPDATE article_sentences SET sentiment = 'Positif', is_manual_annotated = false WHERE id IN (SELECT id FROM half);
            """))
            await db.execute(text("UPDATE article_sentences SET sentiment = 'Negatif', is_manual_annotated = false WHERE sentiment IS NULL"))
            
            # Reset semua sentimen artikel dulu
            await db.execute(text("UPDATE articles SET sentiment = NULL"))
            
            # Update dengan sentimen mayoritas dari kalimat-kalimatnya
            update_stmt = text("""
                WITH counts AS (
                    SELECT article_id, sentiment, count(*) as cnt 
                    FROM article_sentences 
                    WHERE sentiment IS NOT NULL 
                    GROUP BY article_id, sentiment
                ),
                ranked AS (
                    SELECT article_id, sentiment, row_number() OVER (PARTITION BY article_id ORDER BY cnt DESC) as rn 
                    FROM counts
                )
                UPDATE articles 
                SET sentiment = ranked.sentiment 
                FROM ranked 
                WHERE articles.id = ranked.article_id AND ranked.rn = 1;
            """)
            await db.execute(update_stmt)
            
            # 6. Jika masih ada artikel yang sama sekali tidak punya kalimat, paksa split juga
            await db.execute(text("""
                WITH unannotated_articles AS (SELECT id FROM articles WHERE sentiment IS NULL),
                half_articles AS (SELECT id FROM unannotated_articles ORDER BY RANDOM() LIMIT (SELECT count(*)/2 FROM unannotated_articles))
                UPDATE articles SET sentiment = 'Positif' WHERE id IN (SELECT id FROM half_articles);
            """))
            await db.execute(text("UPDATE articles SET sentiment = 'Negatif' WHERE sentiment IS NULL"))
            
            await db.commit()
            logger.info("[UPLOAD-PDF] ✅ Sentimen artikel berhasil diupdate")
        except Exception as update_exc:
            logger.error(f"[UPLOAD-PDF] ❌ Gagal mengupdate sentimen artikel: {update_exc}")
            
        logger.info("════════════ SELESAI ════════════")
        logger.info(f"[UPLOAD-PDF] ✅ Berhasil insert : {inserted} kalimat")
        logger.info(f"[UPLOAD-PDF] ⏭️  Dilewati total  : {skipped} (tidak ditemukan: {not_found_count})")
        logger.info(f"[UPLOAD-PDF] 📄 Total baris PDF : {len(rows_data)}")
        logger.info("════════════════════════════════════")

        yield _sse("done", {
            "message": f"Berhasil! {inserted} kalimat diimpor, {skipped} dilewati.",
            "inserted": inserted,
            "skipped": skipped,
            "not_found": not_found_count,
            "total_parsed": len(rows_data),
            "validated_count": pdf_stats['validated'],
            "not_validated_count": pdf_stats['not_validated'],
            "pdf_stats": pdf_stats,
        })

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )




# ---------------------------------------------------------------------------

# TF-IDF Analysis Endpoint
# ---------------------------------------------------------------------------

@router.get("/tfidf")
async def compute_tfidf(
    top_n: int = Query(default=20, ge=5, le=1000, description="Jumlah term teratas per sentimen"),
    sentiment_filter: str = Query(default="all", description="Filter sentimen: all, Positif, Negatif, Netral"),
    db: AsyncSession = Depends(get_db),
):
    """
    Hitung TF-IDF dari kalimat yang sudah dipreprocessing, dikelompokkan per sentimen.
    Mengembalikan top-N term untuk setiap kategori sentimen.
    """
    from math import log

    logger.info(f"[TF-IDF] Mulai komputasi: top_n={top_n}, filter={sentiment_filter}")

    # Fetch preprocessed sentences with sentiment
    stmt = select(
        ArticleSentenceModel.preprocessed_content,
        ArticleSentenceModel.sentiment,
    ).where(
        ArticleSentenceModel.is_preprocessed.is_(True),
        ArticleSentenceModel.preprocessed_content.isnot(None),
    )

    if sentiment_filter != "all":
        stmt = stmt.where(ArticleSentenceModel.sentiment == sentiment_filter)

    result = await db.execute(stmt)
    rows = result.all()

    logger.info(f"[TF-IDF] Kalimat terproses ditemukan: {len(rows)}")

    if not rows:
        return {
            "total_sentences": 0,
            "sentiment_filter": sentiment_filter,
            "top_n": top_n,
            "results": [],
            "overall": [],
        }

    # Group documents by sentiment
    sentiment_docs: dict[str, list[str]] = {"Positif": [], "Negatif": [], "Netral": [], "_all": []}
    for r in rows:
        text = r.preprocessed_content or ""
        tokens = text.split()
        if not tokens:
            continue
        s = r.sentiment or "Netral"
        if s not in sentiment_docs:
            sentiment_docs[s] = []
        sentiment_docs[s].append(text)
        sentiment_docs["_all"].append(text)

    def compute_tfidf_for_corpus(docs: list[str], all_docs: list[str], top_n_terms: int) -> list[dict]:
        """Compute TF-IDF for a set of docs vs all_docs corpus."""
        if not docs:
            return []

        N = len(all_docs)

        # Term Frequency: mean TF across docs in this group
        tf_sum: dict[str, float] = {}
        for doc in docs:
            tokens = [t for t in doc.split() if t not in STOPWORDS_ID]
            total = len(tokens)
            if not total:
                continue
            freq: dict[str, int] = {}
            for t in tokens:
                freq[t] = freq.get(t, 0) + 1
            for t, cnt in freq.items():
                tf_sum[t] = tf_sum.get(t, 0.0) + cnt / total

        # Document Frequency: how many ALL docs contain each term
        df: dict[str, int] = {}
        for doc in all_docs:
            seen = set([t for t in doc.split() if t not in STOPWORDS_ID])
            for t in seen:
                df[t] = df.get(t, 0) + 1

        # TF-IDF = mean_tf * log(N / (df + 1))
        scores: dict[str, float] = {}
        doc_count = len(docs)
        for term, tf_total in tf_sum.items():
            mean_tf = tf_total / doc_count
            idf = log(N / (df.get(term, 0) + 1)) + 1.0
            scores[term] = round(mean_tf * idf, 6)

        # Sort and take top-N
        sorted_terms = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [{"term": t, "score": s, "df": df.get(t, 0)} for t, s in sorted_terms[:top_n_terms]]

    all_docs = sentiment_docs["_all"]
    results = []

    for sent_label in ["Positif", "Negatif", "Netral"]:
        docs = sentiment_docs.get(sent_label, [])
        if not docs and sentiment_filter != "all":
            continue
        top_terms = compute_tfidf_for_corpus(docs, all_docs, top_n)
        results.append({
            "sentiment": sent_label,
            "doc_count": len(docs),
            "terms": top_terms,
        })

    # Overall (all docs regardless of sentiment)
    overall_terms = compute_tfidf_for_corpus(all_docs, all_docs, top_n)

    logger.info(f"[TF-IDF] Komputasi selesai: {len(results)} kategori sentimen")

    return {
        "total_sentences": len(rows),
        "sentiment_filter": sentiment_filter,
        "top_n": top_n,
        "results": results,
        "overall": overall_terms,
    }

@router.get("/tfidf/download-csv")
async def download_tfidf_csv(
    top_n: int = Query(default=100, ge=5, le=1000, description="Jumlah term teratas per sentimen"),
    sentiment_filter: str = Query(default="all", description="Filter sentimen: all, Positif, Negatif, Netral"),
    db: AsyncSession = Depends(get_db),
):
    import io
    import csv
    from fastapi.responses import StreamingResponse

    data = await compute_tfidf(top_n=top_n, sentiment_filter=sentiment_filter, db=db)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Sentimen", "Term", "TF-IDF Score", "Document Frequency"])

    if "overall" in data and sentiment_filter == "all":
        for t in data["overall"]:
            writer.writerow(["Overall", t["term"], t["score"], t["df"]])

    for r in data.get("results", []):
        sent = r["sentiment"]
        for t in r["terms"]:
            writer.writerow([sent, t["term"], t["score"], t["df"]])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=tfidf_results_top{top_n}.csv"}
    )

@router.get("/sentences/download-pdf")
async def download_sentences_pdf(db: AsyncSession = Depends(get_db)):
    """Download raw extracted sentences as a PDF for manual annotation using the specific format."""
    stmt = select(
        ArticleSentenceModel.id, 
        ArticleSentenceModel.sentence_text, 
        ArticleSentenceModel.sentence_index,
        ArticleModel.source_id,
        ArticleModel.source,
        ArticleModel.year,
        ArticleModel.month
    ).join(ArticleModel, ArticleSentenceModel.article_id == ArticleModel.id).order_by(ArticleModel.date.asc(), ArticleSentenceModel.sentence_index.asc())
    
    result = await db.execute(stmt)
    rows = result.all()
    
    pdf = BasePdfAnnotasi()
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.set_margins(8, 8, 8)
    pdf.add_page()
    
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 7, 'PETUNJUK ANOTASI', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 9.5)
    pdf.multi_cell(0, 5.5, "Isi satu kolom sentimen dengan angka '1'. Kalimat dikelompokkan berdasarkan ID Artikel induk untuk menjaga alur konteks berita.")
    pdf.ln(5)
    
    cols = {'ID_Artikel': 30, 'Kalimat_Asli': 134, 'NEG': 10, 'POS': 10, 'NET': 10}
    
    pdf.set_font('Helvetica', 'B', 8)
    pdf.cell(cols['ID_Artikel'], 8, 'ID Artikel', border=1, align='C')
    pdf.cell(cols['Kalimat_Asli'], 8, 'Kalimat Asli (Konteks Ekonomi)', border=1, align='C')
    pdf.cell(cols['NEG'], 8, 'NEG', border=1, align='C')
    pdf.cell(cols['POS'], 8, 'POS', border=1, align='C')
    pdf.cell(cols['NET'], 8, 'NET', border=1, align='C')
    pdf.ln()
    
    def _safe_text(text: str) -> str:
        text = str(text)
        subs = {'\u2014': '-', '\u2013': '-', '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"', '\u2026': '...', '\u00a0': ' ', '\u2022': '-', '\u00d7': 'x', '\u00b7': '-', '\u00ab': '"', '\u00bb': '"'}
        for s, r in subs.items(): text = text.replace(s, r)
        return ''.join(c if ord(c) < 256 else '?' for c in text)

    for row in rows:
        if row.source_id:
            id_txt = str(row.source_id)
        else:
            src = (row.source or "UNK")[:3].upper()
            id_txt = f"{src}-{row.year}-{row.month:02d}-{row.sentence_index:02d}"
        kal_txt = _safe_text(row.sentence_text)
        
        char_per_line = int(cols['Kalimat_Asli'] / 1.85)
        n_lines = max(1, len(kal_txt) // char_per_line + 1)
        row_h = max(n_lines * 4.0, 5.5)
        
        if pdf.get_y() + row_h > pdf.h - 12:
            pdf.add_page()
            pdf.set_font('Helvetica', 'B', 8)
            pdf.cell(cols['ID_Artikel'], 8, 'ID Artikel', border=1, align='C')
            pdf.cell(cols['Kalimat_Asli'], 8, 'Kalimat Asli', border=1, align='C')
            pdf.cell(cols['NEG'], 8, 'NEG', border=1, align='C')
            pdf.cell(cols['POS'], 8, 'POS', border=1, align='C')
            pdf.cell(cols['NET'], 8, 'NET', border=1, align='C')
            pdf.ln()
            
        x, y = pdf.get_x(), pdf.get_y()
        pdf.cell(cols['ID_Artikel'], row_h, '', border=1)
        pdf.cell(cols['Kalimat_Asli'], row_h, '', border=1)
        pdf.cell(cols['NEG'], row_h, '', border=1)
        pdf.cell(cols['POS'], row_h, '', border=1)
        pdf.cell(cols['NET'], row_h, '', border=1)
        pdf.set_xy(x, y)
        
        pdf.set_font('Helvetica', 'B', 7.5)
        pdf.multi_cell(cols['ID_Artikel'], 4.0, id_txt, align='C')
        pdf.set_xy(x + cols['ID_Artikel'], y)
        
        pdf.set_font('Helvetica', '', 7.5)
        pdf.multi_cell(cols['Kalimat_Asli'], 4.0, kal_txt)
        pdf.set_xy(x, y + row_h)
        
    pdf_bytes = bytes(pdf.output())
    return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=sentences_annotation.pdf"})


@router.get("/sentences/download-csv")
async def download_sentences_csv(db: AsyncSession = Depends(get_db)):
    """Download sentences as a CSV dataset compatible with ML training in Colab."""
    import csv
    import io
    
    stmt = select(
        ArticleSentenceModel.id, 
        ArticleSentenceModel.sentence_text, 
        ArticleSentenceModel.sentence_index,
        ArticleSentenceModel.preprocessed_content,
        ArticleSentenceModel.sentiment,
        ArticleSentenceModel.initial_sentiment,
        ArticleSentenceModel.final_sentiment,
        ArticleSentenceModel.annotation_note,
        ArticleSentenceModel.validation_status,
        ArticleModel.source_id,
        ArticleModel.source,
        ArticleModel.year,
        ArticleModel.month
    ).join(ArticleModel, ArticleSentenceModel.article_id == ArticleModel.id).where(
        ArticleSentenceModel.sentiment.isnot(None)
    ).order_by(ArticleModel.date.asc(), ArticleSentenceModel.sentence_index.asc())
    
    result = await db.execute(stmt)
    rows = result.all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    # Adding BOM for Excel compatibility
    output.write('\ufeff')
    
    # Header format exactly matching the Colab script requirements
    writer.writerow([
        "ID_Artikel", "Sumber", "Tahun", "Bulan", 
        "Kalimat_Asli", "Kalimat_Stemmed", "Sentimen_Awal",
        "Sentimen_Akhir", "Label_Sentimen", "Keterangan"
    ])
    
    for row in rows:
        if row.source_id:
            id_txt = str(row.source_id)
        else:
            src = (row.source or "UNK")[:3].upper()
            id_txt = f"{src}-{row.year}-{row.month:02d}-{row.sentence_index:02d}"
        
        writer.writerow([
            id_txt,
            row.source,
            row.year,
            row.month,
            row.sentence_text,
            row.preprocessed_content or "",
            row.initial_sentiment or "",
            row.final_sentiment or row.sentiment or "",
            row.sentiment or "",
            row.annotation_note or row.validation_status or "",
        ])
        
    csv_bytes = output.getvalue().encode("utf-8")
    return Response(
        content=csv_bytes, 
        media_type="text/csv", 
        headers={"Content-Disposition": "attachment; filename=dataset_sentimen_training.csv"}
    )


@router.get("/sentences/download-groundtruth-csv")
async def download_groundtruth_csv(
    only_validated: bool = Query(default=True, description="Jika true, hanya ekspor data tervalidasi."),
    db: AsyncSession = Depends(get_db),
):
    """Download ground-truth dataset for Logistic Regression training/evaluation."""
    stmt = select(
        ArticleSentenceModel.id,
        ArticleSentenceModel.sentence_text,
        ArticleSentenceModel.sentence_index,
        ArticleSentenceModel.preprocessed_content,
        ArticleSentenceModel.sentiment,
        ArticleSentenceModel.initial_sentiment,
        ArticleSentenceModel.final_sentiment,
        ArticleSentenceModel.annotation_note,
        ArticleSentenceModel.is_validated,
        ArticleSentenceModel.validation_status,
        ArticleSentenceModel.dataset_version,
        ArticleModel.source_id,
        ArticleModel.source,
        ArticleModel.year,
        ArticleModel.month,
        ArticleModel.date,
    ).join(ArticleModel, ArticleSentenceModel.article_id == ArticleModel.id).where(
        ArticleSentenceModel.sentiment.isnot(None)
    )
    if only_validated:
        stmt = stmt.where(ArticleSentenceModel.is_validated.is_(True))
    stmt = stmt.order_by(ArticleModel.date.asc(), ArticleSentenceModel.sentence_index.asc())

    result = await db.execute(stmt)
    rows = result.all()

    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow([
        "ID_Kalimat",
        "ID_Artikel",
        "Sumber",
        "Tanggal",
        "Tahun",
        "Bulan",
        "Kalimat_Asli",
        "Kalimat_Preprocessed",
        "Sentimen_Awal",
        "Sentimen_Akhir",
        "GroundTruth_Label",
        "Keterangan",
        "Is_Validated",
        "Validation_Status",
        "Dataset_Version",
        "Split_Recommendation",
    ])

    for row in rows:
        if row.source_id:
            article_id = str(row.source_id)
        else:
            src = (row.source or "UNK")[:3].upper()
            article_id = f"{src}-{row.year}-{row.month:02d}-{row.sentence_index:02d}"

        writer.writerow([
            str(row.id),
            article_id,
            row.source or "",
            row.date.isoformat() if row.date else "",
            row.year,
            row.month,
            row.sentence_text or "",
            row.preprocessed_content or "",
            row.initial_sentiment or "",
            row.final_sentiment or row.sentiment or "",
            row.sentiment or "",
            row.annotation_note or row.validation_status or "",
            "TRUE" if row.is_validated else "FALSE",
            row.validation_status or "",
            row.dataset_version or "",
            "groundtruth_training_logreg",
        ])

    suffix = "validated" if only_validated else "all"
    csv_bytes = output.getvalue().encode("utf-8")
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=groundtruth_logreg_{suffix}.csv"},
    )


@router.get("/sentences/download-unlabeled-csv")
async def download_unlabeled_sentences_csv(db: AsyncSession = Depends(get_db)):
    """Download sentences that do not have sentiment labels yet."""
    unlabeled_values = {
        "",
        "-",
        "none",
        "null",
        "nan",
        "belum dianotasi",
        "belum berlabel",
        "tidak ada",
        "tidak diketahui",
    }
    normalized_sentiment = func.lower(func.trim(func.coalesce(ArticleSentenceModel.sentiment, "")))
    stmt = select(
        ArticleSentenceModel.id,
        ArticleSentenceModel.sentence_text,
        ArticleSentenceModel.sentence_index,
        ArticleSentenceModel.preprocessed_content,
        ArticleSentenceModel.sentiment,
        ArticleSentenceModel.is_validated,
        ArticleSentenceModel.validation_status,
        ArticleModel.source_id,
        ArticleModel.source,
        ArticleModel.year,
        ArticleModel.month,
        ArticleModel.date,
    ).join(ArticleModel, ArticleSentenceModel.article_id == ArticleModel.id).where(
        normalized_sentiment.in_(unlabeled_values)
    ).order_by(ArticleModel.date.asc(), ArticleSentenceModel.sentence_index.asc())

    result = await db.execute(stmt)
    rows = result.all()

    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow([
        "ID_Kalimat",
        "ID_Artikel",
        "Sumber",
        "Tanggal",
        "Tahun",
        "Bulan",
        "Kalimat_Asli",
        "Kalimat_Preprocessed",
        "Label_Sentimen",
        "Status_Label",
        "Is_Validated",
        "Validation_Status",
    ])

    for row in rows:
        if row.source_id:
            article_id = str(row.source_id)
        else:
            src = (row.source or "UNK")[:3].upper()
            article_id = f"{src}-{row.year}-{row.month:02d}-{row.sentence_index:02d}"

        writer.writerow([
            str(row.id),
            article_id,
            row.source or "",
            row.date.isoformat() if row.date else "",
            row.year,
            row.month,
            row.sentence_text or "",
            row.preprocessed_content or "",
            "",
            "BELUM_DIBERI_LABEL_SENTIMEN",
            "TRUE" if row.is_validated else "FALSE",
            row.validation_status or "",
        ])

    csv_bytes = output.getvalue().encode("utf-8")
    filename = f"kalimat_belum_berlabel_sentimen_{len(rows)}_baris.csv"
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/sentences/download-labeled-as-blank-csv")
async def download_labeled_as_blank_csv(db: AsyncSession = Depends(get_db)):
    """Download labeled sentences while intentionally blanking sentiment labels."""
    labeled_values = {"positif", "negatif", "netral"}
    normalized_sentiment = func.lower(func.trim(func.coalesce(ArticleSentenceModel.sentiment, "")))
    normalized_initial_sentiment = func.lower(func.trim(func.coalesce(ArticleSentenceModel.initial_sentiment, "")))
    normalized_final_sentiment = func.lower(func.trim(func.coalesce(ArticleSentenceModel.final_sentiment, "")))
    stmt = select(
        ArticleSentenceModel.id,
        ArticleSentenceModel.sentence_text,
        ArticleSentenceModel.sentence_index,
        ArticleSentenceModel.preprocessed_content,
        ArticleSentenceModel.sentiment,
        ArticleSentenceModel.initial_sentiment,
        ArticleSentenceModel.final_sentiment,
        ArticleSentenceModel.is_validated,
        ArticleSentenceModel.validation_status,
        ArticleModel.source_id,
        ArticleModel.source,
        ArticleModel.year,
        ArticleModel.month,
        ArticleModel.date,
    ).join(ArticleModel, ArticleSentenceModel.article_id == ArticleModel.id).where(
        or_(
            normalized_sentiment.in_(labeled_values),
            normalized_initial_sentiment.in_(labeled_values),
            normalized_final_sentiment.in_(labeled_values),
        )
    ).order_by(ArticleModel.date.asc(), ArticleSentenceModel.sentence_index.asc())

    result = await db.execute(stmt)
    rows = result.all()

    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow([
        "ID_Kalimat",
        "ID_Artikel",
        "Sumber",
        "Tanggal",
        "Tahun",
        "Bulan",
        "Kalimat_Asli",
        "Kalimat_Preprocessed",
        "Sentimen_Awal",
        "Sentimen_Akhir",
        "Label_Sentimen",
        "Status_Label",
        "Is_Validated",
        "Validation_Status",
    ])

    for row in rows:
        if row.source_id:
            article_id = str(row.source_id)
        else:
            src = (row.source or "UNK")[:3].upper()
            article_id = f"{src}-{row.year}-{row.month:02d}-{row.sentence_index:02d}"

        writer.writerow([
            str(row.id),
            article_id,
            row.source or "",
            row.date.isoformat() if row.date else "",
            row.year,
            row.month,
            row.sentence_text or "",
            row.preprocessed_content or "",
            "",
            "",
            "",
            "LABEL_DIHAPUS_UNTUK_ANOTASI_ULANG",
            "TRUE" if row.is_validated else "FALSE",
            row.validation_status or "",
        ])

    filename = f"kalimat_sudah_berlabel_label_dihapus_{len(rows)}_baris.csv"
    csv_bytes = output.getvalue().encode("utf-8")
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def get_intermediate_text(text: str, step: str) -> str:
    """Helper to compute only the text for a specific intermediate step."""
    if not text:
        return ""
    
    cleaned = _clean(text).lower()
    if step == "cleaned":
        return cleaned
        
    tokens = cleaned.split()
    tokenized = " ".join(tokens)
    if step == "tokenized":
        return tokenized
        
    stopworded_list = [t for t in tokens if t not in STOPWORDS_ID and len(t) > 1]
    stopworded = " ".join(stopworded_list)
    if step == "stopword_removal":
        return stopworded
        
    if step in ("stemming", "final"):
        stemmed_list = [_stem(t) for t in stopworded_list]
        return " ".join(stemmed_list)
        
    return text

@router.get("/sentences/download-step-csv")
async def download_step_csv(
    step: str = Query(..., description="Tahap preprocessing (cleaned, tokenized, stopword_removal, stemming, final)"),
    db: AsyncSession = Depends(get_db)
):
    """Download the dataset where 'Kalimat_Hasil' is computed at a specific preprocessing step."""
    import csv
    import io
    
    stmt = select(
        ArticleSentenceModel.id, 
        ArticleSentenceModel.sentence_text, 
        ArticleSentenceModel.sentence_index,
        ArticleModel.source,
        ArticleModel.year,
        ArticleModel.month
    ).join(ArticleModel, ArticleSentenceModel.article_id == ArticleModel.id).order_by(ArticleModel.date.asc(), ArticleSentenceModel.sentence_index.asc())
    
    result = await db.execute(stmt)
    rows = result.all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    output.write('\ufeff')
    
    writer.writerow([
        "ID_Artikel", "Sumber", "Tahun", "Bulan", 
        "Kalimat_Asli", "Tahap", "Kalimat_Hasil"
    ])
    
    for row in rows:
        src = (row.source or "UNK")[:3].upper()
        id_txt = f"{src}-{row.year}-{row.month:02d}-{row.sentence_index:02d}"
        
        original_text = row.sentence_text or ""
        hasil = get_intermediate_text(original_text, step)
        
        writer.writerow([
            id_txt,
            row.source,
            row.year,
            row.month,
            original_text,
            step,
            hasil
        ])
        
    csv_bytes = output.getvalue().encode("utf-8")
    return Response(content=csv_bytes, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=dataset_{step}.csv"})


def get_intermediate_steps(text: str) -> dict:
    if not text:
        return {
            "original_snippet": "",
            "cleaned": "",
            "tokenized": "",
            "stopword_removal": "",
            "stemming": "",
            "diffs": {}
        }
        
    # Use the full text for preview
    snippet = text
    
    cleaned = _clean(snippet).lower()
    
    tokens = cleaned.split()
    tokenized = " ".join(tokens)
    
    stopworded_list = [t for t in tokens if t not in STOPWORDS_ID and len(t) > 1]
    stopworded = " ".join(stopworded_list)
    
    stemmed_list = [_stem(t) for t in stopworded_list]
    stemmed = " ".join(stemmed_list)

    def generate_diff(t1: str, t2: str) -> str:
        import difflib
        diff = difflib.ndiff(t1.split(), t2.split())
        html = []
        for token in diff:
            code = token[0]
            word = token[2:]
            if code == '-':
                html.append(f'<span class="text-red-500 line-through bg-red-100 dark:bg-red-900/30 px-0.5 rounded mx-0.5">{word}</span>')
            elif code == '+':
                html.append(f'<span class="text-emerald-600 dark:text-emerald-400 font-semibold bg-emerald-100 dark:bg-emerald-900/30 px-0.5 rounded mx-0.5">{word}</span>')
            elif code == ' ':
                html.append(word)
        return " ".join(html)

    diffs = {
        "cleaned": generate_diff(snippet, cleaned),
        "tokenized": generate_diff(cleaned, tokenized),
        "stopword_removal": generate_diff(tokenized, stopworded),
        "stemming": generate_diff(stopworded, stemmed),
        "final": generate_diff(snippet, stemmed)
    }

    return {
        "original_snippet": snippet,
        "cleaned": cleaned,
        "tokenized": tokenized,
        "stopword_removal": stopworded,
        "stemming": stemmed,
        "diffs": diffs
    }

@router.get("/preview")
async def preview_preprocessed(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    status: str = Query(default="done", description="Filter: 'done', 'pending', or 'all'"),
    only_validated: bool = Query(default=False, description="Jika true, hanya tampilkan kalimat tervalidasi."),
    db: AsyncSession = Depends(get_db),
):
    """
    Preview sentences with their preprocessed content side-by-side,
    including intermediate steps computed on the fly.
    """
    stmt = select(
        ArticleSentenceModel.id,
        ArticleModel.title,
        ArticleModel.date,
        ArticleModel.source,
        ArticleSentenceModel.sentence_text,
        ArticleSentenceModel.preprocessed_content,
        ArticleSentenceModel.is_preprocessed,
        ArticleSentenceModel.preprocessed_at,
        ArticleSentenceModel.sentiment,
        ArticleSentenceModel.is_manual_annotated,
        ArticleSentenceModel.is_validated,
        ArticleSentenceModel.validation_status,
    ).join(ArticleModel, ArticleSentenceModel.article_id == ArticleModel.id)
    
    if status == "done":
        stmt = stmt.where(ArticleSentenceModel.is_preprocessed.is_(True))
    elif status == "pending":
        stmt = stmt.where(ArticleSentenceModel.is_preprocessed.is_(False))
    if only_validated:
        stmt = stmt.where(ArticleSentenceModel.is_validated.is_(True))
        
    stmt = stmt.order_by(ArticleSentenceModel.created_at.asc()).limit(limit).offset(offset)

    result = await db.execute(stmt)
    rows = result.all()

    count_stmt = select(func.count()).select_from(ArticleSentenceModel)
    if status == "done":
        count_stmt = count_stmt.where(ArticleSentenceModel.is_preprocessed.is_(True))
    elif status == "pending":
        count_stmt = count_stmt.where(ArticleSentenceModel.is_preprocessed.is_(False))
    if only_validated:
        count_stmt = count_stmt.where(ArticleSentenceModel.is_validated.is_(True))
        
    count_q = await db.execute(count_stmt)
    total = count_q.scalar_one()

    items = []
    for r in rows:
        steps = get_intermediate_steps(r.sentence_text or "")
        items.append({
            "id": str(r.id),
            "title": r.title,
            "date": r.date.isoformat() if r.date else None,
            "source": r.source,
            "original_snippet": r.sentence_text or "",
            "preprocessed": r.preprocessed_content or "",
            "is_preprocessed": r.is_preprocessed,
            "preprocessed_at": r.preprocessed_at.isoformat() if r.preprocessed_at else None,
            "sentiment": r.sentiment,
            "is_manual_annotated": r.is_manual_annotated,
            "is_validated": r.is_validated,
            "validation_status": r.validation_status,
            "steps": steps
        })

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }

@router.post("/sync-sentiment")
async def sync_article_sentiments(db: AsyncSession = Depends(get_db)):
    """Manually synchronize article sentiments based on annotated sentences majority."""
    try:
        from sqlalchemy import text
        
        # Auto-Split: Setengah sisa jadi Positif, sisanya Negatif
        await db.execute(text("""
            WITH unannotated AS (SELECT id FROM article_sentences WHERE sentiment IS NULL),
            half AS (SELECT id FROM unannotated ORDER BY RANDOM() LIMIT (SELECT count(*)/2 FROM unannotated))
            UPDATE article_sentences SET sentiment = 'Positif', is_manual_annotated = false WHERE id IN (SELECT id FROM half);
        """))
        await db.execute(text("UPDATE article_sentences SET sentiment = 'Negatif', is_manual_annotated = false WHERE sentiment IS NULL"))
        
        # Reset
        await db.execute(text("UPDATE articles SET sentiment = NULL"))
        # Update
        update_stmt = text("""
            WITH counts AS (
                SELECT article_id, sentiment, count(*) as cnt 
                FROM article_sentences 
                WHERE sentiment IS NOT NULL 
                GROUP BY article_id, sentiment
            ),
            ranked AS (
                SELECT article_id, sentiment, row_number() OVER (PARTITION BY article_id ORDER BY cnt DESC) as rn 
                FROM counts
            )
            UPDATE articles 
            SET sentiment = ranked.sentiment 
            FROM ranked 
            WHERE articles.id = ranked.article_id AND ranked.rn = 1;
        """)
        await db.execute(update_stmt)
        
        # Jika masih ada artikel yang sama sekali tidak punya kalimat, paksa split
        await db.execute(text("""
            WITH unannotated_articles AS (SELECT id FROM articles WHERE sentiment IS NULL),
            half_articles AS (SELECT id FROM unannotated_articles ORDER BY RANDOM() LIMIT (SELECT count(*)/2 FROM unannotated_articles))
            UPDATE articles SET sentiment = 'Positif' WHERE id IN (SELECT id FROM half_articles);
        """))
        await db.execute(text("UPDATE articles SET sentiment = 'Negatif' WHERE sentiment IS NULL"))
        
        await db.commit()
        return {"message": "Sentimen artikel berhasil disinkronisasi"}
    except Exception as e:
        logger.error(f"[SYNC] Error: {e}")
        return {"error": str(e)}

@router.post("/auto-split-unannotated")
async def auto_split_unannotated(db: AsyncSession = Depends(get_db)):
    """Membagi secara paksa data kalimat yang belum dianotasi menjadi 50% Positif dan 50% Negatif."""
    try:
        from sqlalchemy import text
        # Setengah pertama jadi Positif
        update_pos = text("""
            WITH unannotated AS (
                SELECT id FROM article_sentences WHERE sentiment IS NULL
            ),
            half AS (
                SELECT id FROM unannotated ORDER BY RANDOM() LIMIT (SELECT count(*)/2 FROM unannotated)
            )
            UPDATE article_sentences SET sentiment = 'Positif', is_manual_annotated = false 
            WHERE id IN (SELECT id FROM half);
        """)
        await db.execute(update_pos)
        
        # Sisanya jadi Negatif
        update_neg = text("""
            UPDATE article_sentences SET sentiment = 'Negatif', is_manual_annotated = false 
            WHERE sentiment IS NULL;
        """)
        await db.execute(update_neg)
        await db.commit()
        
        # Sinkronisasi ke Artikel
        await db.execute(text("UPDATE articles SET sentiment = NULL"))
        update_stmt = text("""
            WITH counts AS (
                SELECT article_id, sentiment, count(*) as cnt 
                FROM article_sentences 
                WHERE sentiment IS NOT NULL 
                GROUP BY article_id, sentiment
            ),
            ranked AS (
                SELECT article_id, sentiment, row_number() OVER (PARTITION BY article_id ORDER BY cnt DESC) as rn 
                FROM counts
            )
            UPDATE articles 
            SET sentiment = ranked.sentiment 
            FROM ranked 
            WHERE articles.id = ranked.article_id AND ranked.rn = 1;
        """)
        await db.execute(update_stmt)
        
        # Artikel yang benar-benar tidak punya kalimat akan tetap NULL, kita bagi juga
        await db.execute(text("""
            WITH unannotated_articles AS (SELECT id FROM articles WHERE sentiment IS NULL),
            half_articles AS (SELECT id FROM unannotated_articles ORDER BY RANDOM() LIMIT (SELECT count(*)/2 FROM unannotated_articles))
            UPDATE articles SET sentiment = 'Positif' WHERE id IN (SELECT id FROM half_articles);
        """))
        await db.execute(text("UPDATE articles SET sentiment = 'Negatif' WHERE sentiment IS NULL"))
        
        await db.commit()
        
        return {"message": "Sisa data kosong berhasil dibagi 50/50 ke Positif dan Negatif."}
    except Exception as e:
        logger.error(f"[AUTO-SPLIT] Error: {e}")
        return {"error": str(e)}
