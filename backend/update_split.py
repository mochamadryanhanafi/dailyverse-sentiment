import asyncio
from sqlalchemy import text
from app.core.database import AsyncSessionLocal

async def test_update():
    async with AsyncSessionLocal() as db:
        try:
            update_pos = text("""
                WITH unannotated AS (
                    SELECT id FROM article_sentences WHERE sentiment IS NULL
                ),
                half AS (
                    SELECT id FROM unannotated ORDER BY RANDOM() LIMIT (SELECT count(*)/2 FROM unannotated)
                )
                UPDATE article_sentences SET sentiment = 'Positif', is_manual_annotated = false 
                WHERE id IN (SELECT id FROM half);
            """)
            await db.execute(update_pos)
            
            update_neg = text("""
                UPDATE article_sentences SET sentiment = 'Negatif', is_manual_annotated = false 
                WHERE sentiment IS NULL;
            """)
            await db.execute(update_neg)
            
            await db.commit()
            print("Success")
        except Exception as e:
            print(f"Error: {e}")

asyncio.run(test_update())
