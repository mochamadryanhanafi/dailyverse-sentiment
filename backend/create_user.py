import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal
from app.infrastructure.repositories.user_model import UserModel

async def add_user(username: str, email: str, raw_password: str):
    hashed_pwd = raw_password  

    async with AsyncSessionLocal() as session:
        new_user = UserModel(
            username=username,
            email=email,
            hashed_password=hashed_pwd
        )
        session.add(new_user)
        await session.commit()
        print(f"User '{username}' berhasil ditambahkan ke database!")

if __name__ == "__main__":
    # Ganti dengan data user yang Anda inginkan
    asyncio.run(add_user(
        username="admin", 
        email="admin@dailyverse.com", 
        raw_password="password123"
    ))

    
