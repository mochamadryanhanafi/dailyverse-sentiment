import io
import csv
from collections import Counter
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.infrastructure.repositories.article_model import ArticleModel

router = APIRouter()

@router.get("/scraper/articles/export")
async def export_articles(db: AsyncSession = Depends(get_db)):
    stmt = select(ArticleModel).options(selectinload(ArticleModel.sentences)).order_by(ArticleModel.date)
    result = await db.execute(stmt)
    articles = result.scalars().all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(["ID_Artikel", "Title", "Content", "URL", "Year", "Month", "Date", "Source", "Sentiment_Artikel", "Sentiment_Kalimat"])
    
    for a in articles:
        # Menyesuaikan sentimen menurut kalimat
        kalimat_sentiments = [s.sentiment for s in a.sentences if s.sentiment]
        calculated_sentiment = ""
        if kalimat_sentiments:
            calculated_sentiment = Counter(kalimat_sentiments).most_common(1)[0][0]
            
        final_sentiment = calculated_sentiment if calculated_sentiment else (a.sentiment or "")
        
        writer.writerow([
            a.source_id or str(a.id),
            a.title,
            a.content,
            a.url,
            a.year,
            a.month,
            a.date.strftime("%Y-%m-%d") if a.date else "",
            a.source,
            a.sentiment or "",
            final_sentiment
        ])
        
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=articles_export.csv"}
    )
