import csv
import io
import re
import os
import joblib
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.infrastructure.repositories.article_model import ArticleModel

router = APIRouter(prefix="/nlp", tags=["NLP"])

# Load models
try:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    tfidf_vectorizer = joblib.load(os.path.join(BASE_DIR, "tfidf.pkl"))
    logreg_model = joblib.load(os.path.join(BASE_DIR, "logreg.pkl"))
except Exception as e:
    import logging
    logging.getLogger(__name__).error(f"Error loading models: {e}")
    tfidf_vectorizer = None
    logreg_model = None

class AnalyzeRequest(BaseModel):
    text: str

class AnalyzeResponse(BaseModel):
    sentiment: str
    confidence: float
    tfidf_features: list[dict] = []

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_sentiment(req: AnalyzeRequest):
    if not tfidf_vectorizer or not logreg_model:
        return {"sentiment": "Error (Model not loaded)", "confidence": 0.0}
    
    vec = tfidf_vectorizer.transform([req.text])
    pred = logreg_model.predict(vec)[0]
    
    # Extract top TF-IDF features for visualization
    tfidf_features = []
    if hasattr(tfidf_vectorizer, "get_feature_names_out"):
        feature_names = tfidf_vectorizer.get_feature_names_out()
        coo = vec.tocoo()
        for idx, value in zip(coo.col, coo.data):
            tfidf_features.append({
                "word": str(feature_names[idx]),
                "score": float(value)
            })
        # Sort by score descending and take top 15
        tfidf_features.sort(key=lambda x: x["score"], reverse=True)
        tfidf_features = tfidf_features[:15]
    
    if hasattr(logreg_model, "predict_proba"):
        probs = logreg_model.predict_proba(vec)[0]
        conf = float(max(probs))
    else:
        conf = 1.0
        
    # Standardize output string format
    sentiment_str = str(pred).capitalize()
    return {
        "sentiment": sentiment_str, 
        "confidence": round(conf, 4),
        "tfidf_features": tfidf_features
    }

def tokenize(text: str) -> set[str]:
    return set(re.findall(r'\w+', text.lower()))

def jaccard(s1: set[str], s2: set[str]) -> float:
    u = len(s1 | s2)
    return len(s1 & s2) / u if u else 0.0

def split_into_sentences(text: str) -> list[str]:
    text = re.sub(r'\s+', ' ', text)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if len(s.strip()) > 10]

@router.get("/export-sentences")
async def export_sentences(
    threshold: float = 0.8,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(ArticleModel.id, ArticleModel.date, ArticleModel.content).order_by(ArticleModel.date))
    articles = result.all()
    
    accepted_sentences = []
    
    for row in articles:
        sentences = split_into_sentences(row.content)
        for s in sentences:
            toks = tokenize(s)
            if len(toks) < 3:
                continue
                
            is_dup = False
            for acc in accepted_sentences:
                if jaccard(toks, acc[3]) >= threshold:
                    is_dup = True
                    break
            
            if not is_dup:
                accepted_sentences.append((str(row.id), row.date.strftime("%Y-%m-%d"), s, toks))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["article_id", "date", "sentence"])
    
    for acc in accepted_sentences:
        writer.writerow([acc[0], acc[1], acc[2]])
        
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=kalimat_unik_jaccard_{threshold}.csv"}
    )
