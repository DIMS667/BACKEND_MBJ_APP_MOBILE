import random
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from fastapi import HTTPException, status
from app.core.email import send_email
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token
)
from .models import User, RefreshToken, PasswordResetCode, AccountDeletionCode
from .schemas import RegisterRequest, LoginRequest

# Durée de validité du code de réinitialisation envoyé par email.
_RESET_CODE_TTL_MINUTES = 15

# Durée de validité du code de confirmation de suppression de compte.
_DELETION_CODE_TTL_MINUTES = 15


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


async def request_password_reset(db: AsyncSession, email: str) -> None:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        # Ne révèle jamais si l'email est enregistré ou non (anti-énumération
        # de comptes) : on répond succès dans tous les cas côté route.
        return

    code = f"{random.randint(0, 999999):06d}"
    db.add(PasswordResetCode(
        code=code,
        user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(minutes=_RESET_CODE_TTL_MINUTES),
    ))
    await send_email(
        user.email,
        "Réinitialisation de votre mot de passe",
        f"""
        <p>Bonjour {user.first_name},</p>
        <p>Voici votre code de réinitialisation, valable {_RESET_CODE_TTL_MINUTES} minutes :</p>
        <p style="font-size:28px;font-weight:bold;letter-spacing:6px;">{code}</p>
        <p>Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet email.</p>
        <p>— L'équipe de La Maison Bleue de Julien</p>
        """,
    )


async def reset_password(
    db: AsyncSession, email: str, code: str, new_password: str
) -> None:
    invalid = HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Code invalide ou expiré.",
    )

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise invalid

    result = await db.execute(
        select(PasswordResetCode)
        .where(
            PasswordResetCode.user_id == user.id,
            PasswordResetCode.code == code,
            PasswordResetCode.used == False,  # noqa: E712
        )
        .order_by(PasswordResetCode.created_at.desc())
    )
    reset_code = result.scalar_one_or_none()
    if not reset_code or reset_code.expires_at < datetime.utcnow():
        raise invalid

    reset_code.used = True
    user.hashed_password = hash_password(new_password)
    # Sécurité : une fois le mot de passe changé, toute session déjà ouverte
    # (sur cet appareil ou un autre) doit être forcée à se reconnecter.
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id)
        .values(is_revoked=True)
    )


async def request_account_deletion(db: AsyncSession, user: User) -> None:
    code = f"{random.randint(0, 999999):06d}"
    db.add(AccountDeletionCode(
        code=code,
        user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(minutes=_DELETION_CODE_TTL_MINUTES),
    ))
    await send_email(
        user.email,
        "Confirmez la suppression de votre compte",
        f"""
        <p>Bonjour {user.first_name},</p>
        <p>Vous avez demandé la suppression définitive de votre compte Maison Bleue Kids.</p>
        <p><strong>Cette action supprime pour toujours votre compte, les profils de vos
        enfants ainsi que toutes leurs données (progression, dessins, histoires,
        réglages).</strong> Elle est irréversible.</p>
        <p>Voici votre code de confirmation, valable {_DELETION_CODE_TTL_MINUTES} minutes :</p>
        <p style="font-size:28px;font-weight:bold;letter-spacing:6px;">{code}</p>
        <p>Si vous n'êtes pas à l'origine de cette demande, ignorez cet email : votre
        compte restera intact.</p>
        <p>— L'équipe de La Maison Bleue de Julien</p>
        """,
    )


async def confirm_account_deletion(db: AsyncSession, user: User, code: str) -> None:
    invalid = HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Code invalide ou expiré.",
    )

    result = await db.execute(
        select(AccountDeletionCode)
        .where(
            AccountDeletionCode.user_id == user.id,
            AccountDeletionCode.code == code,
            AccountDeletionCode.used == False,  # noqa: E712
        )
        .order_by(AccountDeletionCode.created_at.desc())
    )
    deletion_code = result.scalar_one_or_none()
    if not deletion_code or deletion_code.expires_at < datetime.utcnow():
        raise invalid

    deletion_code.used = True
    await db.delete(user)