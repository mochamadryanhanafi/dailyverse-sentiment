from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.core.database import get_db

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/")
async def server_status():
    return {"status": "ok", "service": "dailyverse-sentiment-api"}


@router.get("/db")
async def database_status(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        return {"status": "error", "database": "disconnected", "detail": str(exc)}
