"""
Evaluation Router
=================
Membandingkan prediksi model otomatis (TF-IDF + Logistic Regression) 
dengan anotasi manual yang tersimpan di tabel article_sentences.

Mengembalikan:
- Confusion Matrix (3x3: Positif / Negatif / Netral)
- Precision, Recall, F1-score per kelas
- Accuracy, Macro avg, Weighted avg
- Per-sample mismatch list (opsional, top-100)
"""

from __future__ import annotations

import json
import logging
import os
from typing import AsyncGenerator

import joblib
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.infrastructure.repositories.article_model import ArticleSentenceModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/evaluation", tags=["Evaluation"])

# ---------------------------------------------------------------------------
# Load ML models (same path as nlp_router)
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    tfidf_vectorizer = joblib.load(os.path.join(BASE_DIR, "tfidf.pkl"))
    logreg_model = joblib.load(os.path.join(BASE_DIR, "logreg.pkl"))
    logger.info("[EVAL] Model TF-IDF + LogReg berhasil dimuat")
except Exception as exc:
    logger.error(f"[EVAL] Gagal memuat model: {exc}")
    tfidf_vectorizer = None
    logreg_model = None

LABELS = ["Positif", "Negatif", "Netral"]


def _normalize_sentiment(s: str | None) -> str | None:
    """Normalize raw DB value to one of LABELS."""
    if not s:
        return None
    mapping = {
        "positif": "Positif",
        "positive": "Positif",
        "pos": "Positif",
        "negatif": "Negatif",
        "negative": "Negatif",
        "neg": "Negatif",
        "netral": "Netral",
        "neutral": "Netral",
        "net": "Netral",
    }
    return mapping.get(s.strip().lower(), s.strip().capitalize())


def _compute_metrics(y_true: list[str], y_pred: list[str]) -> dict:
    """Compute confusion matrix and per-class + aggregate metrics."""
    labels = LABELS
    n = len(labels)
    idx = {lbl: i for i, lbl in enumerate(labels)}

    # Build confusion matrix
    cm = [[0] * n for _ in range(n)]
    for t, p in zip(y_true, y_pred):
        ti = idx.get(t, -1)
        pi = idx.get(p, -1)
        if ti >= 0 and pi >= 0:
            cm[ti][pi] += 1

    # Per-class metrics
    per_class = []
    total = len(y_true)
    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    accuracy = correct / total if total else 0.0

    for i, lbl in enumerate(labels):
        tp = cm[i][i]
        fp = sum(cm[r][i] for r in range(n)) - tp
        fn = sum(cm[i][c] for c in range(n)) - tp

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        support = sum(cm[i])

        per_class.append({
            "label": lbl,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": support,
            "tp": tp,
            "fp": fp,
            "fn": fn,
        })

    # Macro avg
    macro_p = sum(c["precision"] for c in per_class) / n
    macro_r = sum(c["recall"] for c in per_class) / n
    macro_f1 = sum(c["f1"] for c in per_class) / n

    # Weighted avg
    w_p = sum(c["precision"] * c["support"] for c in per_class) / total if total else 0
    w_r = sum(c["recall"] * c["support"] for c in per_class) / total if total else 0
    w_f1 = sum(c["f1"] * c["support"] for c in per_class) / total if total else 0

    return {
        "labels": labels,
        "confusion_matrix": cm,
        "per_class": per_class,
        "accuracy": round(accuracy, 4),
        "total": total,
        "correct": correct,
        "macro_avg": {
            "precision": round(macro_p, 4),
            "recall": round(macro_r, 4),
            "f1": round(macro_f1, 4),
        },
        "weighted_avg": {
            "precision": round(w_p, 4),
            "recall": round(w_r, 4),
            "f1": round(w_f1, 4),
        },
    }


# ---------------------------------------------------------------------------
# SSE Progress helper
# ---------------------------------------------------------------------------
def _sse(event: str, data: dict) -> str:
    return f"data: {json.dumps({'event': event, **data})}\n\n"


# ---------------------------------------------------------------------------
# Main evaluation endpoint — SSE streaming
# ---------------------------------------------------------------------------
@router.get("/run/stream")
async def evaluate_stream(
    limit: int = Query(default=0, ge=0, description="Max kalimat dievaluasi; 0 = semua"),
    include_mismatches: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
):
    """
    Evaluasi model otomatis (LogReg) vs anotasi manual menggunakan SSE.
    Streaming progress setiap 50 kalimat.

    Event types:
      - progress   : { processed, total, current_text }
      - done       : { metrics, mismatches }
      - error      : { detail }
    """
    async def generate() -> AsyncGenerator[str, None]:
        if not tfidf_vectorizer or not logreg_model:
            yield _sse("error", {"detail": "Model belum dimuat. Pastikan tfidf.pkl dan logreg.pkl tersedia."})
            return

        # Fetch annotated sentences
        stmt = (
            select(
                ArticleSentenceModel.id,
                ArticleSentenceModel.sentence_text,
                ArticleSentenceModel.preprocessed_content,
                ArticleSentenceModel.sentiment,
            )
            .where(
                ArticleSentenceModel.sentiment.isnot(None),
                ArticleSentenceModel.sentence_text.isnot(None),
            )
        )
        if limit > 0:
            stmt = stmt.limit(limit)

        result = await db.execute(stmt)
        rows = result.all()
        total = len(rows)

        if total == 0:
            yield _sse("error", {"detail": "Tidak ada kalimat dengan anotasi manual. Harap upload PDF anotasi terlebih dahulu."})
            return

        logger.info(f"[EVAL] Mulai evaluasi {total} kalimat ternotasi...")
        yield _sse("progress", {"processed": 0, "total": total, "current_text": "Memulai evaluasi..."})

        y_true: list[str] = []
        y_pred: list[str] = []
        mismatches: list[dict] = []

        for i, row in enumerate(rows):
            # Use preprocessed content if available, else raw text
            text = (row.preprocessed_content or row.sentence_text or "").strip()
            true_label = _normalize_sentiment(row.sentiment)

            if not text or not true_label or true_label not in LABELS:
                continue

            try:
                vec = tfidf_vectorizer.transform([text])
                pred_raw = logreg_model.predict(vec)[0]
                pred_label = _normalize_sentiment(str(pred_raw))

                if pred_label not in LABELS:
                    pred_label = "Netral"

                # Confidence
                conf = 1.0
                if hasattr(logreg_model, "predict_proba"):
                    probs = logreg_model.predict_proba(vec)[0]
                    conf = float(max(probs))

                y_true.append(true_label)
                y_pred.append(pred_label)

                if pred_label != true_label and include_mismatches and len(mismatches) < 100:
                    mismatches.append({
                        "id": str(row.id),
                        "text": text[:120],
                        "true": true_label,
                        "pred": pred_label,
                        "confidence": round(conf, 3),
                    })

            except Exception as exc:
                logger.warning(f"[EVAL] Skip kalimat {row.id}: {exc}")
                continue

            if (i + 1) % 50 == 0:
                yield _sse("progress", {
                    "processed": i + 1,
                    "total": total,
                    "current_text": text[:60],
                })
                await __import__("asyncio").sleep(0)

        if not y_true:
            yield _sse("error", {"detail": "Tidak cukup data valid untuk evaluasi."})
            return

        metrics = _compute_metrics(y_true, y_pred)
        logger.info(f"[EVAL] Selesai. Accuracy={metrics['accuracy']:.4f}, Total={metrics['total']}")

        yield _sse("done", {
            "metrics": metrics,
            "mismatches": mismatches if include_mismatches else [],
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
