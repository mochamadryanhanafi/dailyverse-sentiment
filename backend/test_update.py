import asyncio
from sqlalchemy import text
from app.core.database import AsyncSessionLocal

async def test_update():
    async with AsyncSessionLocal() as db:
        try:
            update_stmt = text("""
                WITH counts AS (
                    SELECT article_id, sentiment, count(*) as cnt 
                    FROM article_sentences 
                    WHERE sentiment IS NOT NULL 
                    GROUP BY article_id, sentiment
                ),
                ranked AS (
                    SELECT article_id, sentiment, row_number() OVER (PARTITION BY article_id ORDER BY cnt DESC) as rn 
                    FROM counts
                )
                UPDATE articles 
                SET sentiment = ranked.sentiment 
                FROM ranked 
                WHERE articles.id = ranked.article_id AND ranked.rn = 1;
            """)
            await db.execute(update_stmt)
            await db.commit()
            print("Success")
        except Exception as e:
            print(f"Error: {e}")

asyncio.run(test_update())
