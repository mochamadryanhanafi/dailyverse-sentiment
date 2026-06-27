import json
import logging
import os
import httpx
from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from collections.abc import AsyncGenerator

from app.core.database import get_db, AsyncSessionLocal
from app.infrastructure.repositories.article_model import ArticleModel, ArticleSentenceModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chatbot", tags=["chatbot"])

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")


def _sse(event: str, data: dict) -> str:
    return f"data: {json.dumps({'event': event, **data}, ensure_ascii=False)}\n\n"


async def get_rag_context(db: AsyncSession) -> str:
    try:
        # Get basic stats
        total_articles = await db.scalar(select(func.count(ArticleModel.id)))
        
        # Get sentiments stats (from validated or final sentiment)
        stmt_pos = select(func.count(ArticleSentenceModel.id)).where(ArticleSentenceModel.final_sentiment == "positif")
        stmt_neg = select(func.count(ArticleSentenceModel.id)).where(ArticleSentenceModel.final_sentiment == "negatif")
        stmt_neu = select(func.count(ArticleSentenceModel.id)).where(ArticleSentenceModel.final_sentiment == "netral")
        
        total_pos = await db.scalar(stmt_pos) or 0
        total_neg = await db.scalar(stmt_neg) or 0
        total_neu = await db.scalar(stmt_neu) or 0

        # Get recent 5 articles
        stmt_recent = select(ArticleModel.title).order_by(ArticleModel.date.desc()).limit(5)
        recent_result = await db.execute(stmt_recent)
        recent_titles = [r[0] for r in recent_result.all()]
        recent_titles_str = "\n".join([f"- {t}" for t in recent_titles])

        context = (
            f"Statistik Database Proyek Analisis Sentimen Berita:\n"
            f"- Total Artikel: {total_articles}\n"
            f"- Sentimen Positif: {total_pos} kalimat\n"
            f"- Sentimen Negatif: {total_neg} kalimat\n"
            f"- Sentimen Netral: {total_neu} kalimat\n\n"
            f"5 Berita Terbaru:\n{recent_titles_str}"
        )
        return context
    except Exception as e:
        logger.error(f"Error fetching RAG context: {e}")
        return "Gagal mengambil data dari database."


@router.post("/chat")
async def chat_stream(
    message: str = Body(..., embed=True)
):
    """
    Streaming chat response using Groq API.
    """
    async def generate() -> AsyncGenerator[str, None]:
        if not GROQ_API_KEY:
            yield _sse("error", {"detail": "GROQ_API_KEY tidak ditemukan di environment variables."})
            return

        # Fetch Context from Database in an isolated session
        async with AsyncSessionLocal() as db:
            context = await get_rag_context(db)
        
        system_prompt = (
            "Anda adalah AI Analis Data untuk proyek DailyVerse Sentiment API berbahasa Indonesia. "
            "Tugas Anda adalah menjawab pertanyaan pengguna berdasarkan data statistik yang diberikan. "
            "Berbicaralah dengan ramah, profesional, dan dalam bahasa Indonesia yang baik.\n\n"
            f"=== KONTEKS DATA ===\n{context}\n==================\n"
        )

        groq_payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            "stream": True,
            "temperature": 0.7
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                }
                async with client.stream("POST", url, json=groq_payload, headers=headers) as response:
                    
                    if response.status_code != 200:
                        error_msg = await response.aread()
                        yield _sse("error", {"detail": f"Groq error {response.status_code}: {error_msg.decode()}"})
                        return

                    async for line in response.aiter_lines():
                        if not line or line.strip() == "":
                            continue
                        
                        line = line.strip()
                        if line.startswith("data: "):
                            data_str = line[6:]
                            
                            if data_str == "[DONE]":
                                yield _sse("done", {"detail": "Selesai"})
                                break
                            
                            try:
                                data = json.loads(data_str)
                                choices = data.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    chunk = delta.get("content", "")
                                    if chunk:
                                        yield _sse("chunk", {"text": chunk})
                            except json.JSONDecodeError:
                                continue
                            
        except httpx.ConnectError:
            yield _sse("error", {"detail": "Gagal terhubung ke API Groq. Periksa koneksi internet server."})
        except Exception as e:
            logger.error(f"Groq stream error: {e}")
            yield _sse("error", {"detail": f"Terjadi kesalahan saat menghubungi Groq: {str(e)}"})

    headers = {
        "X-Accel-Buffering": "no",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }
    return StreamingResponse(generate(), media_type="text/event-stream", headers=headers)
