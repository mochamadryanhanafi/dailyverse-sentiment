import logging
import os
import joblib
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix

from app.core.database import get_db
from app.infrastructure.repositories.article_model import ArticleSentenceModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/training", tags=["Training"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

LABELS = ["Positif", "Negatif", "Netral"]

def _normalize_sentiment(s: str | None) -> str | None:
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

@router.post("/train")
async def train_model(
    test_size: float = 0.2,
    db: AsyncSession = Depends(get_db)
):
    # 1. Fetch data
    stmt = select(ArticleSentenceModel).where(
        ArticleSentenceModel.sentiment.isnot(None),
        ArticleSentenceModel.sentence_text.isnot(None)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    texts = []
    labels = []
    for row in rows:
        text = (row.preprocessed_content or row.sentence_text or "").strip()
        label = _normalize_sentiment(row.sentiment)
        if text and label in LABELS:
            texts.append(text)
            labels.append(label)

    if len(texts) < 10:
        raise HTTPException(status_code=400, detail="Not enough annotated data to train. Need at least 10 sentences.")

    # 2. Split data
    X_train, X_test, y_train, y_test = train_test_split(texts, labels, test_size=test_size, random_state=42)

    # 3. TF-IDF
    vectorizer = TfidfVectorizer()
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    # 4. Logistic Regression
    model = LogisticRegression(max_iter=1000)
    model.fit(X_train_vec, y_train)

    # 5. Evaluate
    y_pred = model.predict(X_test_vec)
    acc = accuracy_score(y_test, y_pred)
    prec, rec, f1, support = precision_recall_fscore_support(y_test, y_pred, labels=LABELS, zero_division=0)
    cm = confusion_matrix(y_test, y_pred, labels=LABELS)

    per_class = []
    for i, lbl in enumerate(LABELS):
        per_class.append({
            "label": lbl,
            "precision": float(prec[i]),
            "recall": float(rec[i]),
            "f1": float(f1[i]),
            "support": int(support[i])
        })

    # Save models
    try:
        joblib.dump(vectorizer, os.path.join(BASE_DIR, "tfidf.pkl"))
        joblib.dump(model, os.path.join(BASE_DIR, "logreg.pkl"))
    except Exception as e:
        logger.error(f"Failed to save models: {e}")

    formulas = {
        "tfidf": (
            "TF (Term Frequency): TF(t,d) = (Jumlah kemunculan term t dalam dokumen d) / (Total kata dalam dokumen d)\n"
            "IDF (Inverse Document Frequency): IDF(t) = log_e(Total dokumen n / Jumlah dokumen yang mengandung term t) + 1\n"
            "TF-IDF(t,d) = TF(t,d) * IDF(t)\n"
            "Normalisasi L2 diterapkan pada hasil TF-IDF sehingga jumlah kuadrat elemen vektor = 1."
        ),
        "logreg": (
            "Logistic Regression menggunakan fungsi sigmoid (untuk binary) atau softmax (untuk multiclass).\n"
            "P(y=k | x) = exp(w_k * x + b_k) / sum(exp(w_j * x + b_j))\n"
            "w_k = bobot (coefficients) untuk kelas k\n"
            "b_k = bias (intercept) untuk kelas k\n"
            "x = vektor fitur TF-IDF\n"
            "Model dilatih dengan meminimalkan fungsi loss (cross-entropy)."
        )
    }

    return {
        "message": "Model trained successfully",
        "samples": len(texts),
        "train_size": len(X_train),
        "test_size": len(X_test),
        "formulas": formulas,
        "metrics": {
            "accuracy": float(acc),
            "per_class": per_class,
            "confusion_matrix": cm.tolist(),
            "labels": LABELS
        }
    }
