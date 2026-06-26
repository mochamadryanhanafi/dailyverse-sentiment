"""
Evaluation Router
=================
Membandingkan prediksi model otomatis TF-IDF + Logistic Regression
dengan label ground truth pada tabel article_sentences.

Output:
- Confusion Matrix 3x3
- Precision, Recall, F1-score per kelas
- Accuracy, Macro avg, Weighted avg
- Per-sample mismatch list
"""

from __future__ import annotations

import json
import logging
import os
from typing import AsyncGenerator

import joblib
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    confusion_matrix,
    classification_report,
)

from app.core.database import get_db
from app.infrastructure.repositories.article_model import ArticleSentenceModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/evaluation", tags=["Evaluation"])

# ============================================================
# PATH MODEL
# ============================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

TFIDF_PATH = os.path.join(BASE_DIR, "tfidf.pkl")
LOGREG_PATH = os.path.join(BASE_DIR, "logreg.pkl")
PIPELINE_PATH = os.path.join(BASE_DIR, "model_logreg_sentimen.pkl")

# Urutan label disamakan dengan evaluasi Colab:
# Negatif, Netral, Positif
LABELS = ["Negatif", "Netral", "Positif"]

tfidf_vectorizer = None
logreg_model = None
pipeline_model = None


def _is_pipeline_like(model) -> bool:
    return hasattr(model, "steps") or hasattr(model, "named_steps")


# ============================================================
# LOAD MODEL
# ============================================================

def _load_models() -> None:
    """
    Mendukung dua format model:

    1. Pipeline tunggal:
       model_logreg_sentimen.pkl
       Pipeline berisi TF-IDF + Logistic Regression.

    2. Model terpisah:
       tfidf.pkl + logreg.pkl
    """
    global tfidf_vectorizer, logreg_model, pipeline_model

    tfidf_vectorizer = None
    logreg_model = None
    pipeline_model = None

    try:
        if os.path.exists(PIPELINE_PATH):
            candidate = joblib.load(PIPELINE_PATH)

            if hasattr(candidate, "predict"):
                pipeline_model = candidate
                logger.info("[EVAL] Pipeline model berhasil dimuat: model_logreg_sentimen.pkl")
                return

        if os.path.exists(TFIDF_PATH) and os.path.exists(LOGREG_PATH):
            candidate_tfidf = joblib.load(TFIDF_PATH)
            candidate_logreg = joblib.load(LOGREG_PATH)

            if not hasattr(candidate_tfidf, "transform"):
                raise ValueError("tfidf.pkl tidak memiliki method transform().")

            if not hasattr(candidate_logreg, "predict"):
                raise ValueError("logreg.pkl tidak memiliki method predict().")

            if _is_pipeline_like(candidate_logreg):
                pipeline_model = candidate_logreg
                logger.info("[EVAL] logreg.pkl terdeteksi sebagai Pipeline. Evaluasi memakai input teks mentah.")
                return

            tfidf_vectorizer = candidate_tfidf
            logreg_model = candidate_logreg

            logger.info("[EVAL] TF-IDF dan LogReg berhasil dimuat.")
            return

        logger.error("[EVAL] File model tidak ditemukan.")

    except Exception as exc:
        logger.error(f"[EVAL] Gagal memuat model: {exc}")
        tfidf_vectorizer = None
        logreg_model = None
        pipeline_model = None


_load_models()


def _model_ready() -> bool:
    if pipeline_model is not None:
        return True

    if tfidf_vectorizer is not None and logreg_model is not None:
        return True

    return False


# ============================================================
# UPLOAD MODEL
# ============================================================

@router.post("/upload-model")
async def upload_model(
    tfidf_file: UploadFile = File(None),
    logreg_file: UploadFile = File(None),
    pipeline_file: UploadFile = File(None),
):
    """
    Upload model evaluasi.

    Opsi 1:
    - Upload pipeline_file = model_logreg_sentimen.pkl

    Opsi 2:
    - Upload tfidf_file = tfidf.pkl
    - Upload logreg_file = logreg.pkl
    """

    # --------------------------------------------------------
    # Opsi pipeline tunggal
    # --------------------------------------------------------
    if pipeline_file is not None:
        if not pipeline_file.filename.lower().endswith(".pkl"):
            raise HTTPException(status_code=400, detail="File pipeline harus berformat .pkl")

        pipeline_bytes = await pipeline_file.read()
        tmp_pipeline_path = f"{PIPELINE_PATH}.upload"

        try:
            with open(tmp_pipeline_path, "wb") as f:
                f.write(pipeline_bytes)

            candidate_pipeline = joblib.load(tmp_pipeline_path)

            if not hasattr(candidate_pipeline, "predict"):
                raise ValueError("Pipeline tidak memiliki method predict().")

            os.replace(tmp_pipeline_path, PIPELINE_PATH)
            _load_models()

        except Exception as exc:
            if os.path.exists(tmp_pipeline_path):
                os.remove(tmp_pipeline_path)

            raise HTTPException(status_code=400, detail=f"Pipeline model tidak valid: {exc}") from exc

        return {
            "message": "Pipeline model berhasil diupload dan dimuat ulang.",
            "pipeline_file": pipeline_file.filename,
            "model_type": "pipeline",
        }

    # --------------------------------------------------------
    # Opsi model terpisah
    # --------------------------------------------------------
    if tfidf_file is None or logreg_file is None:
        raise HTTPException(
            status_code=400,
            detail="Upload pipeline_file, atau upload tfidf_file dan logreg_file sekaligus."
        )

    if not tfidf_file.filename.lower().endswith(".pkl") or not logreg_file.filename.lower().endswith(".pkl"):
        raise HTTPException(status_code=400, detail="File model harus berformat .pkl")

    tfidf_bytes = await tfidf_file.read()
    logreg_bytes = await logreg_file.read()

    tmp_tfidf_path = f"{TFIDF_PATH}.upload"
    tmp_logreg_path = f"{LOGREG_PATH}.upload"

    try:
        with open(tmp_tfidf_path, "wb") as f:
            f.write(tfidf_bytes)

        with open(tmp_logreg_path, "wb") as f:
            f.write(logreg_bytes)

        candidate_tfidf = joblib.load(tmp_tfidf_path)
        candidate_logreg = joblib.load(tmp_logreg_path)

        if not hasattr(candidate_tfidf, "transform"):
            raise ValueError("TF-IDF file tidak memiliki method transform().")

        if not hasattr(candidate_logreg, "predict"):
            raise ValueError("LogReg file tidak memiliki method predict().")

        os.replace(tmp_tfidf_path, TFIDF_PATH)
        os.replace(tmp_logreg_path, LOGREG_PATH)
        if os.path.exists(PIPELINE_PATH):
            os.remove(PIPELINE_PATH)

        _load_models()

    except Exception as exc:
        for path in [tmp_tfidf_path, tmp_logreg_path]:
            if os.path.exists(path):
                os.remove(path)

        raise HTTPException(status_code=400, detail=f"Model tidak valid: {exc}") from exc

    return {
        "message": "TF-IDF dan Logistic Regression berhasil diupload dan dimuat ulang.",
        "tfidf_file": tfidf_file.filename,
        "logreg_file": logreg_file.filename,
        "model_type": "separate",
    }


# ============================================================
# NORMALISASI LABEL
# ============================================================

def _normalize_sentiment(value: str | None) -> str | None:
    """
    Menyamakan variasi label ke:
    - Negatif
    - Netral
    - Positif
    """
    if value is None:
        return None

    raw = str(value).strip()

    if raw == "":
        return None

    mapping = {
        "positif": "Positif",
        "positive": "Positif",
        "pos": "Positif",
        "1": "Positif",

        "negatif": "Negatif",
        "negative": "Negatif",
        "neg": "Negatif",
        "-1": "Negatif",

        "netral": "Netral",
        "neutral": "Netral",
        "net": "Netral",
        "0": "Netral",
    }

    normalized = mapping.get(raw.lower())

    if normalized in LABELS:
        return normalized

    raw_title = raw.capitalize()

    if raw_title in LABELS:
        return raw_title

    return None


def _get_ground_truth_label(row) -> str | None:
    """
    Mengambil label ground truth.

    Prioritas:
    1. validation_status, jika isinya memang label sentimen.
    2. sentiment, jika validation_status bukan label sentimen.

    Ini dibuat agar hasil evaluasi bisa mengikuti label validasi ahli
    jika label ahli disimpan pada validation_status.
    Jika validation_status hanya berisi status seperti 'DIVALIDASI',
    maka sistem otomatis fallback ke row.sentiment.
    """

    for attr in ("final_sentiment", "sentiment", "initial_sentiment", "validation_status"):
        label = _normalize_sentiment(getattr(row, attr, None))
        if label in LABELS:
            return label

    return None


VALIDATION_SQL_VALUES = {'DIVALIDASI', 'BENAR', 'SALAH', 'VALID', 'YA', 'YES', 'Y', 'V', '1', 'TRUE', 'OK'}


def _validated_sentence_condition():
    return or_(
        ArticleSentenceModel.is_validated.is_(True),
        func.upper(func.trim(ArticleSentenceModel.validation_status)).in_(VALIDATION_SQL_VALUES),
        func.upper(func.trim(ArticleSentenceModel.annotation_note)).in_(VALIDATION_SQL_VALUES),
    )


def _labeled_sentence_condition():
    label_values = {"positif", "negatif", "netral"}
    return or_(
        func.lower(func.trim(func.coalesce(ArticleSentenceModel.sentiment, ""))).in_(label_values),
        func.lower(func.trim(func.coalesce(ArticleSentenceModel.initial_sentiment, ""))).in_(label_values),
        func.lower(func.trim(func.coalesce(ArticleSentenceModel.final_sentiment, ""))).in_(label_values),
    )


# ============================================================
# PREDIKSI MODEL
# ============================================================

def _predict_one(text: str) -> tuple[str, float]:
    """
    Prediksi satu kalimat.

    Return:
    - pred_label
    - confidence
    """

    if pipeline_model is not None:
        pred_raw = pipeline_model.predict([text])[0]
        pred_label = _normalize_sentiment(str(pred_raw))

        confidence = 1.0

        if hasattr(pipeline_model, "predict_proba"):
            probs = pipeline_model.predict_proba([text])[0]
            confidence = float(np.max(probs))

        if pred_label not in LABELS:
            pred_label = "Netral"

        return pred_label, confidence

    try:
        vec = tfidf_vectorizer.transform([text])
        pred_raw = logreg_model.predict(vec)[0]
    except Exception as exc:
        if "lower" not in str(exc).lower() and "csr_matrix" not in str(exc):
            raise
        pred_raw = logreg_model.predict([text])[0]
        pred_label = _normalize_sentiment(str(pred_raw))

        confidence = 1.0

        if hasattr(logreg_model, "predict_proba"):
            probs = logreg_model.predict_proba([text])[0]
            confidence = float(np.max(probs))

        if pred_label not in LABELS:
            pred_label = "Netral"

        return pred_label, confidence

    pred_label = _normalize_sentiment(str(pred_raw))

    confidence = 1.0

    if hasattr(logreg_model, "predict_proba"):
        probs = logreg_model.predict_proba(vec)[0]
        confidence = float(np.max(probs))

    if pred_label not in LABELS:
        pred_label = "Netral"

    return pred_label, confidence


# ============================================================
# HITUNG METRIK SESUAI SKLEARN / COLAB
# ============================================================

def _compute_metrics(y_true: list[str], y_pred: list[str]) -> dict:
    """
    Menghitung metrik dengan sklearn agar hasilnya konsisten
    dengan classification_report di Colab.
    """

    total = len(y_true)

    if total == 0:
        return {
            "labels": LABELS,
            "confusion_matrix": [[0, 0, 0], [0, 0, 0], [0, 0, 0]],
            "per_class": [],
            "accuracy": 0.0,
            "accuracy_percent": 0.0,
            "total": 0,
            "correct": 0,
            "incorrect": 0,
            "macro_avg": {
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
            },
            "weighted_avg": {
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
            },
        }

    cm = confusion_matrix(y_true, y_pred, labels=LABELS)

    accuracy = accuracy_score(y_true, y_pred)
    correct = int(sum(1 for t, p in zip(y_true, y_pred) if t == p))
    incorrect = total - correct

    precision, recall, f1, support = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=LABELS,
        zero_division=0,
    )

    per_class = []

    for i, label in enumerate(LABELS):
        tp = int(cm[i][i])
        fp = int(cm[:, i].sum() - tp)
        fn = int(cm[i, :].sum() - tp)

        per_class.append({
            "label": label,
            "precision": round(float(precision[i]), 4),
            "recall": round(float(recall[i]), 4),
            "f1": round(float(f1[i]), 4),
            "support": int(support[i]),
            "tp": tp,
            "fp": fp,
            "fn": fn,
        })

    macro_precision, macro_recall, macro_f1, _ = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=LABELS,
        average="macro",
        zero_division=0,
    )

    weighted_precision, weighted_recall, weighted_f1, _ = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=LABELS,
        average="weighted",
        zero_division=0,
    )

    report = classification_report(
        y_true,
        y_pred,
        labels=LABELS,
        target_names=LABELS,
        output_dict=True,
        zero_division=0,
    )

    return {
        "labels": LABELS,
        "confusion_matrix": cm.astype(int).tolist(),
        "per_class": per_class,
        "accuracy": round(float(accuracy), 4),
        "accuracy_percent": round(float(accuracy) * 100, 2),
        "total": int(total),
        "correct": int(correct),
        "incorrect": int(incorrect),
        "macro_avg": {
            "precision": round(float(macro_precision), 4),
            "recall": round(float(macro_recall), 4),
            "f1": round(float(macro_f1), 4),
        },
        "weighted_avg": {
            "precision": round(float(weighted_precision), 4),
            "recall": round(float(weighted_recall), 4),
            "f1": round(float(weighted_f1), 4),
        },
        "classification_report": report,
    }


# ============================================================
# SSE HELPER
# ============================================================

def _sse(event: str, data: dict) -> str:
    return f"data: {json.dumps({'event': event, **data}, ensure_ascii=False)}\n\n"


# ============================================================
# ENDPOINT EVALUASI STREAM
# ============================================================

@router.get("/run/stream")
async def evaluate_stream(
    limit: int = Query(default=0, ge=0, description="Max kalimat dievaluasi; 0 = semua"),
    include_mismatches: bool = Query(default=True),
    only_validated: bool = Query(
        default=True,
        description="Gunakan hanya data ground truth yang sudah divalidasi ahli"
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Evaluasi model otomatis vs ground truth.

    Event SSE:
    - progress
    - done
    - error
    """

    async def generate() -> AsyncGenerator[str, None]:
        if not _model_ready():
            yield _sse("error", {
                "detail": (
                    "Model belum dimuat. Pastikan tersedia model_logreg_sentimen.pkl "
                    "atau pasangan tfidf.pkl dan logreg.pkl."
                )
            })
            return

        stmt = (
            select(
                ArticleSentenceModel.id,
                ArticleSentenceModel.sentence_text,
                ArticleSentenceModel.preprocessed_content,
                ArticleSentenceModel.sentiment,
                ArticleSentenceModel.initial_sentiment,
                ArticleSentenceModel.final_sentiment,
                ArticleSentenceModel.is_validated,
                ArticleSentenceModel.validation_status,
            )
            .where(
                _labeled_sentence_condition(),
                ArticleSentenceModel.sentence_text.isnot(None),
            )
        )

        if only_validated:
            stmt = stmt.where(_validated_sentence_condition())

        if limit > 0:
            stmt = stmt.limit(limit)

        result = await db.execute(stmt)
        rows = result.all()
        total_rows = len(rows)

        if total_rows == 0:
            detail = (
                "Tidak ada kalimat ground truth yang sudah divalidasi ahli."
                if only_validated
                else "Tidak ada kalimat dengan label sentimen."
            )

            yield _sse("error", {"detail": detail})
            return

        logger.info(f"[EVAL] Mulai evaluasi {total_rows} baris. only_validated={only_validated}")

        yield _sse("progress", {
            "processed": 0,
            "total": total_rows,
            "current_text": (
                "Memulai evaluasi data tervalidasi..."
                if only_validated
                else "Memulai evaluasi semua data berlabel..."
            ),
            "only_validated": only_validated,
        })

        y_true: list[str] = []
        y_pred: list[str] = []
        mismatches: list[dict] = []

        skipped = 0

        for i, row in enumerate(rows):
            text = (row.preprocessed_content or row.sentence_text or "").strip()
            true_label = _get_ground_truth_label(row)

            if not text or true_label not in LABELS:
                skipped += 1
                continue

            try:
                pred_label, confidence = _predict_one(text)

                if pred_label not in LABELS:
                    pred_label = "Netral"

                y_true.append(true_label)
                y_pred.append(pred_label)

                if pred_label != true_label and include_mismatches and len(mismatches) < 100:
                    mismatches.append({
                        "id": str(row.id),
                        "text": text[:180],
                        "true": true_label,
                        "pred": pred_label,
                        "confidence": round(float(confidence), 3),
                        "validated": bool(row.is_validated),
                        "validation_status": row.validation_status,
                    })

            except Exception as exc:
                skipped += 1
                logger.warning(f"[EVAL] Skip kalimat {row.id}: {exc}")
                continue

            if (i + 1) % 50 == 0:
                yield _sse("progress", {
                    "processed": i + 1,
                    "total": total_rows,
                    "valid_evaluated": len(y_true),
                    "skipped": skipped,
                    "current_text": text[:80],
                })

                await __import__("asyncio").sleep(0)

        if not y_true:
            yield _sse("error", {
                "detail": "Tidak cukup data valid untuk evaluasi. Cek label sentimen dan teks preprocessing."
            })
            return

        metrics = _compute_metrics(y_true, y_pred)

        logger.info(
            f"[EVAL] Selesai. "
            f"Accuracy={metrics['accuracy']:.4f}, "
            f"Total={metrics['total']}, "
            f"Skipped={skipped}"
        )

        yield _sse("done", {
            "metrics": metrics,
            "mismatches": mismatches if include_mismatches else [],
            "only_validated": only_validated,
            "skipped": skipped,
            "model_type": "pipeline" if pipeline_model is not None else "separate",
            "note": (
                "Accuracy dihitung sebagai jumlah prediksi benar dibagi total data valid yang dievaluasi. "
                "Urutan label confusion matrix: Negatif, Netral, Positif."
            ),
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
