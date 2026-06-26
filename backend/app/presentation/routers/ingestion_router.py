import io
import uuid
import pandas as pd
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy import delete
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
        
        now = datetime.now(timezone.utc)
        await db.execute(delete(ArticleModel))

        articles_to_insert = []

        def clean_value(row, column, default=""):
            value = row.get(column, default)
            if pd.isna(value):
                return default
            text = str(value).strip()
            return default if text.lower() == "nan" else text

        def clean_int(row, column, default):
            try:
                value = row.get(column, default)
                if pd.isna(value):
                    return default
                return int(value)
            except Exception:
                return default
        
        for idx, row in df.iterrows():
            row_number = idx + 1
            year = clean_int(row, 'Year', now.year)
            month = max(1, min(12, clean_int(row, 'Month', now.month)))

            # Parse Date
            dt_date = datetime(year=year, month=month, day=1).date()
            date_str = clean_value(row, 'Date', '')
            if date_str:
                try:
                    if '/' in date_str and len(date_str) > 2:
                        dt_date = datetime.strptime(date_str, "%d/%m/%Y").date()
                    else:
                        dt_date = datetime(year=year, month=month, day=int(date_str)).date()
                except Exception:
                    pass

            source_id = clean_value(row, 'ID_Artikel', f"CSV-{row_number:06d}")
            url = clean_value(row, 'URL', f"csv-ingestion://{source_id}/{row_number}")
            title = clean_value(row, 'Title', f"Artikel CSV {source_id}")
            content = clean_value(row, 'Content', title)
                
            article_data = {
                'id': uuid.uuid4(),
                'year': year,
                'month': month,
                'date': dt_date,
                'title': title,
                'content': content,
                'url': url,
            }

            # Map source using ID_Artikel as the primary indicator
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
                raw_src = clean_value(row, 'src', clean_value(row, 'Source', 'UNKNOWN'))
                mapped_src = raw_src

            article_data.update({
                'source': mapped_src,
                'source_origin': clean_value(row, 'src_origin', None),
                'sentiment': clean_value(row, 'sentimen', None),
                'summary': clean_value(row, 'rangkuman', None),
                'sequence': clean_int(row, 'urutan', row_number),
                'source_id': source_id,
                'scraped_at': now
            })
            
            articles_to_insert.append(article_data)
            
        if articles_to_insert:
            # Gunakan bulk insert biasa karena kita sudah menghapus semua data dan tidak mempedulikan duplikasi
            db.add_all([ArticleModel(**data) for data in articles_to_insert])
        
        # Add Audit Log
        audit = AuditLogModel(
            action="upload_csv",
            details=(
                f"Mode=replace_all. Uploaded {file.filename}; "
                f"inserted={len(articles_to_insert)}, skipped=0."
            ),
            created_at=now
        )
        db.add(audit)
        
        await db.commit()
        
        return {
            "message": "Upload successful.",
            "mode": "replace_all",
            "articles_inserted": len(articles_to_insert),
            "skipped_invalid": 0,
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
