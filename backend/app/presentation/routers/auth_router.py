from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.core.config import get_settings
from app.core.database import get_db
from app.infrastructure.repositories.user_model import UserModel

settings = get_settings()
SECRET_KEY = settings.secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
GOOGLE_CLIENT_ID = settings.google_client_id

router = APIRouter(prefix="/auth", tags=["Auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/google")

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    picture: str | None
    role: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class GoogleAuthRequest(BaseModel):
    token: str

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
        
    return user

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: UserModel = Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "username": current_user.username,
        "email": current_user.email,
        "picture": current_user.picture,
        "role": current_user.role
    }

@router.post("/google", response_model=LoginResponse)
async def google_auth(request: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    try:
        # Verify Google Token
        idinfo = id_token.verify_oauth2_token(request.token, requests.Request(), GOOGLE_CLIENT_ID)
        
        email = idinfo['email']
        name = idinfo.get('name', '')
        google_id = idinfo['sub']
        picture = idinfo.get('picture', '')
        
        # Check if user exists
        result = await db.execute(select(UserModel).where(UserModel.email == email))
        user = result.scalars().first()
        
        if not user:
            # Check if this is the first user
            count_result = await db.execute(select(func.count(UserModel.id)))
            user_count = count_result.scalar_one()
            assigned_role = "superadmin" if user_count == 0 else "viewer"
            
            # Register new user
            user = UserModel(
                email=email,
                username=name,
                google_id=google_id,
                picture=picture,
                role=assigned_role,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        else:
            # Keep the existing application role; only refresh Google profile fields.
            if not user.google_id or user.picture != picture:
                user.google_id = google_id
                user.picture = picture
                await db.commit()
                
        # Generate JWT Token for our app
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id)}, expires_delta=access_token_expires
        )
        return {
            "access_token": access_token, 
            "token_type": "bearer",
            "user": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "picture": user.picture,
                "role": user.role
            }
        }
        
    except ValueError as e:
        # Invalid token
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid Google token: {str(e)}")
