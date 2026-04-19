import bcrypt
from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from app.database import get_session
from app.models import User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def require_auth(request: Request, session: Session = Depends(get_session)) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401)
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401)
    return user
