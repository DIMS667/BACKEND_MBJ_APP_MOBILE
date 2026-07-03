from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token
)
from .models import User, RefreshToken
from .schemas import RegisterRequest, LoginRequest


async def register_user(db: AsyncSession, data: RegisterRequest) -> User:
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un compte avec cet email existe déjà.",
        )
    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        role=data.role,
    )
    db.add(user)
    await db.flush()
    return user


async def login_user(db: AsyncSession, data: LoginRequest) -> dict:
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte désactivé.",
        )
    access_token = create_access_token({"sub": str(user.id), "role": user.role})
    refresh_token_str = create_refresh_token()
    refresh_token = RefreshToken(token=refresh_token_str, user_id=user.id)
    db.add(refresh_token)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token_str,
        "token_type": "bearer",
    }


async def refresh_token(db: AsyncSession, token: str) -> dict:
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token == token,
            RefreshToken.is_revoked == False
        )
    )
    refresh = result.scalar_one_or_none()
    if not refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalide ou expiré."
        )
    user_result = await db.execute(select(User).where(User.id == refresh.user_id))
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable."
        )
    # Révoquer l'ancien token
    refresh.is_revoked = True
    # Créer un nouveau pair de tokens
    new_access = create_access_token({"sub": str(user.id), "role": user.role})
    new_refresh_str = create_refresh_token()
    db.add(RefreshToken(token=new_refresh_str, user_id=user.id))
    return {
        "access_token": new_access,
        "refresh_token": new_refresh_str,
        "token_type": "bearer",
    }


async def logout_user(db: AsyncSession, token: str) -> None:
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token == token)
    )
    refresh = result.scalar_one_or_none()
    if refresh:
        refresh.is_revoked = True