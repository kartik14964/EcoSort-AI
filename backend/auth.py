from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from backend.schemas import UserCreate, UserLogin, UserInDB, Token
from backend.database import Repository
from backend.utils import settings
from backend.utils import setup_logger

logger = setup_logger("auth_service")

router = APIRouter()
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return username
    except Exception as exc:
        logger.warning(f"Invalid auth token: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/register", response_model=Token)
async def register(user: UserCreate):
    try:
        existing_user = Repository.get_user_by_username(user.username)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    hashed_password = hash_password(user.password)
    user_db = UserInDB(username=user.username, hashed_password=hashed_password)

    try:
        Repository.create_user(user_db.dict())
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(user.username, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", response_model=Token)
async def login(user: UserLogin):
    try:
        user_data = Repository.get_user_by_username(user.username)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    if not user_data:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    if not verify_password(user.password, user_data.get("hashed_password")):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(user.username, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}


import jwt
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import bcrypt

from backend.utils import settings
from backend.utils import setup_logger

logger = setup_logger("passport_auth")

def hash_password(password: str) -> str:
    # bcrypt requires bytes
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except ValueError:
        return False


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    now = datetime.utcnow()
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {"sub": subject, "iat": int(now.timestamp()), "exp": int(expire.timestamp())}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
