import io
import uuid
import pandas as pd
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.infrastructure.repositories.article_model import ArticleModel, AuditLogModel

router = APIRouter(prefix="/ingestion", tags=["Data Ingestion"])

@router.post("/upload-csv")
async def upload_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
    # Ideally inject current_user here: current_user = Depends(get_current_user)
):
    """
    Upload a CSV file containing scraped news articles.
    Expected columns: Title, Content, URL, Year, Month, Source (or src_origin)
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed.")
        
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        
        # Required column mapping
        col_mapping = {
            'Title': 'title',
            'Content': 'content',
            'URL': 'url',
            'Year': 'year',
            'Month': 'month',
        }
        
        # Check if basic columns exist
        missing = [c for c in col_mapping.keys() if c not in df.columns]
        if missing:
            raise HTTPException(status_code=400, detail=f"Missing required columns: {missing}")
            
        now = datetime.now(timezone.utc)
        articles_to_insert = {}
        
        for idx, row in df.iterrows():
            url = str(row.get('URL', '')).strip()
            if not url or url == 'nan' or pd.isna(row.get('Content')):
                continue
                
            # Parse Date
            dt_date = now.date()
            if 'Date' in df.columns and not pd.isna(row['Date']):
                date_str = str(row['Date']).strip()
                try:
                    if '/' in date_str and len(date_str) > 2:
                        dt_date = datetime.strptime(date_str, "%d/%m/%Y").date()
                    else:
                        dt_date = datetime(year=int(row['Year']), month=int(row['Month']), day=int(date_str)).date()
                except Exception:
                    pass
                
            articles_to_insert[url] = {
                'id': uuid.uuid4(),
                'year': int(row['Year']) if 'Year' in df.columns and not pd.isna(row['Year']) else now.year,
                'month': int(row['Month']) if 'Month' in df.columns and not pd.isna(row['Month']) else now.month,
                'date': dt_date,
                'title': str(row['Title']).strip(),
                'content': str(row['Content']).strip(),
                'url': url,
            }
            
            # Map source using ID_Artikel as the primary indicator
            source_id = str(row['ID_Artikel']).strip() if 'ID_Artikel' in df.columns and not pd.isna(row['ID_Artikel']) else "UNKNOWN"
            source_id_lower = source_id.lower()
            if "lip" in source_id_lower:
                mapped_src = "Liputan6"
            elif "rep" in source_id_lower:
                mapped_src = "Republika"
            elif "det" in source_id_lower:
                mapped_src = "Detik"
            elif "kom" in source_id_lower:
                mapped_src = "Kompas"
            elif "tem" in source_id_lower:
                mapped_src = "Tempo"
            elif "sua" in source_id_lower:
                mapped_src = "Suara"
            else:
                raw_src = str(row['src']).strip() if 'src' in df.columns and not pd.isna(row['src']) else "UNKNOWN"
                mapped_src = raw_src

            articles_to_insert[url].update({
                'source': mapped_src,
                'source_origin': str(row['src_origin']).strip() if 'src_origin' in df.columns and not pd.isna(row['src_origin']) else None,
                'sentiment': str(row['sentimen']).strip() if 'sentimen' in df.columns and not pd.isna(row['sentimen']) else None,
                'summary': str(row['rangkuman']).strip() if 'rangkuman' in df.columns and not pd.isna(row['rangkuman']) else None,
                'sequence': int(row['urutan']) if 'urutan' in df.columns and not pd.isna(row['urutan']) else None,
                'source_id': source_id if source_id != "UNKNOWN" else None,
                'scraped_at': now
            })
            
        final_inserts = list(articles_to_insert.values())
        
        if final_inserts:
            from sqlalchemy.dialects.postgresql import insert
            stmt = insert(ArticleModel).values(final_inserts)
            stmt = stmt.on_conflict_do_update(
                index_elements=['url'],
                set_={
                    'title': stmt.excluded.title,
                    'content': stmt.excluded.content,
                    'sentiment': stmt.excluded.sentiment,
                    'summary': stmt.excluded.summary,
                    'source': stmt.excluded.source,
                    'source_origin': stmt.excluded.source_origin,
                    'sequence': stmt.excluded.sequence,
                    'source_id': stmt.excluded.source_id,
                }
            )
            await db.execute(stmt)
        
        # Add Audit Log
        audit = AuditLogModel(
            action="upload_csv",
            details=f"Uploaded {file.filename} containing {len(final_inserts)} valid/updated articles.",
            created_at=now
        )
        db.add(audit)
        
        await db.commit()
        
        return {"message": "Upload successful", "articles_inserted": len(final_inserts)}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
