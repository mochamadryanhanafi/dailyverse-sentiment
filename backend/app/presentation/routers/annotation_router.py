from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
import uuid
from datetime import datetime, timezone

from app.core.database import get_db
from app.infrastructure.repositories.article_model import ArticleSentenceModel, AuditLogModel, ArticleModel

router = APIRouter(prefix="/annotation", tags=["Annotation"])

class AnnotationRequest(BaseModel):
    sentiment: str  # e.g., 'POS', 'NEG', 'NET'
    annotator_id: str | None = None

@router.get("/sentences")
async def get_unannotated_sentences(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0)
):
    """Fetch sentences that have not been manually annotated yet."""
    stmt = select(
        ArticleSentenceModel.id,
        ArticleSentenceModel.sentence_text,
        ArticleSentenceModel.sentence_index,
        ArticleModel.source,
        ArticleModel.year,
        ArticleModel.month
    ).join(
        ArticleModel, ArticleSentenceModel.article_id == ArticleModel.id
    ).where(
        ArticleSentenceModel.is_manual_annotated.is_(False)
    ).order_by(
        ArticleModel.date.asc(), ArticleSentenceModel.sentence_index.asc()
    ).limit(limit).offset(offset)
    
    result = await db.execute(stmt)
    rows = result.all()
    
    return [
        {
            "id": str(r.id),
            "text": r.sentence_text,
            "article_ref": f"{(r.source or 'UNK')[:3].upper()}-{r.year}-{r.month:02d}-{r.sentence_index:02d}"
        } for r in rows
    ]


@router.post("/sentences/{sentence_id}")
async def annotate_sentence(
    sentence_id: uuid.UUID,
    payload: AnnotationRequest,
    db: AsyncSession = Depends(get_db)
):
    """Submit a manual annotation for a specific sentence."""
    stmt = select(ArticleSentenceModel).where(ArticleSentenceModel.id == sentence_id)
    result = await db.execute(stmt)
    sentence = result.scalar_one_or_none()
    
    if not sentence:
        raise HTTPException(status_code=404, detail="Sentence not found")
        
    sentence.sentiment = payload.sentiment
    sentence.is_manual_annotated = True
    
    if payload.annotator_id:
        try:
            sentence.annotator_id = uuid.UUID(payload.annotator_id)
        except ValueError:
            pass
            
    now = datetime.now(timezone.utc)
            
    # Add Audit Log
    audit = AuditLogModel(
        action="annotate_sentence",
        entity_id=str(sentence.id),
        details=f"Annotated as {payload.sentiment}",
        created_at=now
    )
    db.add(audit)
    
    await db.commit()
    
    return {"message": "Annotation saved", "id": str(sentence_id), "sentiment": payload.sentiment}
