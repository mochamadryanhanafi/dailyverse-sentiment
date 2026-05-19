import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.infrastructure.repositories.article_model import ArticleModel

async def fix_sources():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ArticleModel))
        articles = result.scalars().all()
        
        updated_count = 0
        for article in articles:
            if not article.source_id:
                continue
                
            source_id_lower = str(article.source_id).lower()
            mapped_src = None
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
                
            if mapped_src and article.source != mapped_src:
                article.source = mapped_src
                updated_count += 1
                
        if updated_count > 0:
            await db.commit()
        print(f"Updated {updated_count} articles based on source_id.")

if __name__ == "__main__":
    asyncio.run(fix_sources())
