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
import json
import logging
import re
import string
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi.responses import StreamingResponse, Response
from fpdf import FPDF
from pydantic import BaseModel
from sqlalchemy import func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, get_db
from app.infrastructure.repositories.article_model import ArticleModel, ArticleSentenceModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/preprocessing", tags=["Preprocessing"])

# ---------------------------------------------------------------------------
# Indonesian stopwords (compact built-in list – no external file required)
# ---------------------------------------------------------------------------
STOPWORDS_ID: set[str] = {
    "yang", "dan", "di", "ke", "dari", "ini", "itu", "dengan", "untuk",
    "pada", "adalah", "dalam", "tidak", "akan", "juga", "ada", "atau",
    "sudah", "oleh", "karena", "bisa", "saat", "lebih", "namun", "tetapi",
    "sehingga", "agar", "jika", "maka", "bahwa", "setelah", "sebelum",
    "antara", "ia", "mereka", "kami", "kita", "saya", "kamu", "dia",
    "anda", "kita", "para", "pun", "nya", "lain", "hal", "menjadi",
    "bagi", "telah", "dapat", "tersebut", "harus", "serta", "maupun",
    "namun", "hingga", "lalu", "kemudian", "sangat", "sangatlah",
    "seperti", "juga", "begitu", "menurut", "pernah", "baik", "atas",
    "bawah", "saja", "sedang", "sejak", "masih", "sebagai", "belum",
    "ketika", "secara", "tanpa", "selama", "semua", "berbagai", "beberapa",
    "demikian", "dimana", "melalui", "selain", "setiap", "tapi",
    "walaupun", "meski", "ialah", "yakni", "yaitu", "terus", "kini",
    "baru", "banyak", "satu", "dua", "tiga", "empat", "lima",
    "enam", "tujuh", "delapan", "sembilan", "sepuluh", "tahun",
    "bulan", "hari", "juta", "miliar", "triliun", "persen",
    "nomor", "no", "dan", "atau", "maupun", "jokowi", "rp"
}

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
    'pertumbuhan', 'pdb', 'inflasi', 'deflasi', 'kontraksi', 'pemulihan', 'stabilisasi', 'cadangan',
    'devisa', 'defisit', 'surplus', 'neraca', 'anggaran', 'utang', 'fiskal', 'moneter', 'ekspansi',
    'resesi', 'stagflasi', 'stagnan', 'deregulasi', 'regulasi', 'stimulus', 'subsidi', 'pajak',
    'tarif', 'kebijakan', 'reformasi', 'liberalisasi', 'privatisasi', 'nasionalisasi', 'intervensi',
    'moratorium', 'amnesty', 'insentif', 'disinsentif', 'proteksi', 'restrukturisasi', 'konsolidasi',
    'sinkronisasi', 'investasi', 'modal', 'ekspor', 'impor', 'perdagangan', 'komoditas', 'hilirisasi',
    'diversifikasi', 'realisasi', 'devaluasi', 'revaluasi', 'transaksi', 'proteksionisme', 'embargo',
    'dumping', 'kuota', 'bea', 'infrastruktur', 'konektivitas', 'elektrifikasi', 'irigasi', 'bendungan',
    'jembatan', 'pelabuhan', 'bandara', 'tol', 'kereta', 'jalan', 'kawasan', 'smelter', 'kilang',
    'jaringan', 'industri', 'manufaktur', 'produksi', 'kapasitas', 'produktivitas', 'industrialisasi',
    'reindustrialisasi', 'modernisasi', 'otomasi', 'digitalisasi', 'transformasi', 'inovasi', 'teknologi',
    'umkm', 'koperasi', 'wirausaha', 'mikro', 'kecil', 'menengah', 'kredit', 'pembiayaan', 'inkubasi',
    'pemberdayaan', 'kerakyatan', 'mandiri', 'bantuan', 'digital', 'fintech', 'e-commerce', 'startup',
    'unicorn', 'platform', 'dompet', 'neobank', 'pinjol', 'qris', 'gpn', 'marketplace', 'aplikasi',
    'ekosistem', 'kemiskinan', 'ketimpangan', 'gini', 'kesetaraan', 'inklusi', 'distribusi',
    'kesejahteraan', 'pengentasan', 'miskin', 'rentan', 'eksklusif', 'marjinal', 'bansos', 'santunan',
    'perlindungan', 'pengangguran', 'upah', 'gaji', 'phk', 'vokasi', 'pelatihan', 'rekrutmen',
    'outsourcing', 'kontrak', 'serikat', 'buruh', 'pekerja', 'informal', 'formal', 'energi', 'listrik',
    'bbm', 'migas', 'nikel', 'batu bara', 'sawit', 'tembaga', 'emas', 'mineral', 'tambang',
    'pertambangan', 'ebt', 'pangan', 'pertanian', 'beras', 'gabah', 'pupuk', 'sawah', 'swasembada',
    'ketahanan', 'panen', 'agribisnis', 'hortikultura', 'ternak', 'nelayan', 'pkh', 'kis', 'kip',
    'jkn', 'bpjs', 'blt', 'raskin', 'sembako', 'jaminan', 'sosial', 'bank', 'perbankan', 'bunga',
    'likuiditas', 'solvabilitas', 'npl', 'ldr', 'car', 'saham', 'obligasi', 'reksa dana', 'ojk',
    'ipm', 'literasi', 'sanitasi', 'gizi', 'stunting'
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


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class PreprocessStatsResponse(BaseModel):
    total: int
    preprocessed: int
    pending: int
    stemmer: str


class PreprocessBatchResponse(BaseModel):
    processed: int
    skipped: int
    total_preprocessed: int


class ResetResponse(BaseModel):
    reset: int


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
    return PreprocessStatsResponse(
        total=total,
        preprocessed=preprocessed,
        pending=total - preprocessed,
        stemmer=STEMMER_MODE,
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

    async def generate():
        # ── 1. Parse PDF ────────────────────────────────────────────────────
        rows_data = []
        try:
            with pdfplumber.open(io.BytesIO(contents)) as pdf:
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

                        def find_col(keywords):
                            for ki, k in enumerate(header):
                                if any(kw in k for kw in keywords):
                                    return ki
                            return None

                        col_id   = find_col(['id artikel', 'id_artikel', 'id'])
                        col_text = find_col(['kalimat', 'asli', 'teks', 'text'])
                        col_sent = find_col(['sentimen', 'sentiment', 'label'])
                        col_valid= find_col(['validasi', 'valid'])

                        if col_id is None or col_text is None:
                            continue

                        for row in table[header_row_idx + 1:]:
                            if not row or all(c is None or str(c).strip() == '' for c in row):
                                continue

                            def get_cell(idx):
                                if idx is None or idx >= len(row):
                                    return ''
                                return str(row[idx]).strip() if row[idx] else ''

                            id_artikel = get_cell(col_id)
                            kalimat    = get_cell(col_text)
                            sentimen   = get_cell(col_sent)  if col_sent  is not None else ''
                            validasi   = get_cell(col_valid) if col_valid is not None else ''

                            if not id_artikel or not kalimat:
                                continue

                            rows_data.append({
                                'id_artikel': id_artikel,
                                'kalimat_asli': kalimat,
                                'sentimen': sentimen,
                                'validasi': validasi,
                            })

        except Exception as exc:
            logger.error(f"[UPLOAD-PDF] ❌ GAGAL parsing PDF: {exc}", exc_info=True)
            yield _sse("error", {"detail": f"Gagal memproses PDF: {str(exc)}"})
            return

        logger.info(f"[UPLOAD-PDF] Parsing selesai: {len(rows_data)} baris ditemukan")

        if not rows_data:
            logger.warning("[UPLOAD-PDF] ⚠️ Tidak ada tabel valid di PDF")
            yield _sse("error", {"detail": "Tidak ada data tabel di PDF. Pastikan kolom: ID Artikel | Kalimat Asli | Sentimen | Validasi."})
            return

        yield _sse("parsed", {"total_parsed": len(rows_data)})
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

                if not kalimat:
                    skipped += 1
                    continue

                sentiment_norm = sent_map.get(sentimen_raw, None)

                # Article lookup
                parts = id_art.split('-')
                article_id = None

                if len(parts) >= 3:
                    lookup_key = f"{parts[0]}-{parts[1]}-{parts[2]}"
                    if lookup_key in article_lookup:
                        article_id = article_lookup[lookup_key][0]

                if article_id is None and id_art in source_id_lookup:
                    article_id = source_id_lookup[id_art]

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

                db.add(ArticleSentenceModel(
                    article_id=article_id,
                    sentence_index=article_sentence_counter[article_id],
                    sentence_text=kalimat,
                    sentiment=sentiment_norm,
                    is_manual_annotated=bool(sentiment_norm),
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
        src = (row.source or "UNK")[:3].upper()
        # Creates ID like: DET-2024-05-01
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
        "Kalimat_Asli", "Kalimat_Stemmed", "Label_Sentimen"
    ])
    
    for row in rows:
        src = (row.source or "UNK")[:3].upper()
        id_txt = f"{src}-{row.year}-{row.month:02d}-{row.sentence_index:02d}"
        
        writer.writerow([
            id_txt,
            row.source,
            row.year,
            row.month,
            row.sentence_text,
            row.preprocessed_content or "",
            row.sentiment or ""
        ])
        
    csv_bytes = output.getvalue().encode("utf-8")
    return Response(
        content=csv_bytes, 
        media_type="text/csv", 
        headers={"Content-Disposition": "attachment; filename=dataset_sentimen_training.csv"}
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
    ).join(ArticleModel, ArticleSentenceModel.article_id == ArticleModel.id)
    
    if status == "done":
        stmt = stmt.where(ArticleSentenceModel.is_preprocessed.is_(True))
    elif status == "pending":
        stmt = stmt.where(ArticleSentenceModel.is_preprocessed.is_(False))
        
    stmt = stmt.order_by(ArticleSentenceModel.created_at.asc()).limit(limit).offset(offset)

    result = await db.execute(stmt)
    rows = result.all()

    count_stmt = select(func.count()).select_from(ArticleSentenceModel)
    if status == "done":
        count_stmt = count_stmt.where(ArticleSentenceModel.is_preprocessed.is_(True))
    elif status == "pending":
        count_stmt = count_stmt.where(ArticleSentenceModel.is_preprocessed.is_(False))
        
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
            "steps": steps
        })

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }
