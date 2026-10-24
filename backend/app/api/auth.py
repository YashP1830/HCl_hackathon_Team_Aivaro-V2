"""Auth routes. Users can self-register as role 'user' only. Admin is
provisioned by the server on startup (never settable by a client)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.models import User
from app.repositories import repositories as repo
from app.schemas.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if repo.get_user_by_email(db, body.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = repo.create_user(
        db,
        name=body.name,
        email=body.email,
        password_hash=hash_password(body.password),
        role="user",  # never trust a client-supplied role
    )
    token = create_access_token(user.id, user.role)
    return TokenResponse(access_token=token, role=user.role, name=user.name, email=user.email)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = repo.get_user_by_email(db, body.email)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    token = create_access_token(user.id, user.role)
    return TokenResponse(access_token=token, role=user.role, name=user.name, email=user.email)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
