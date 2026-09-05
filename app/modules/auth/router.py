from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db, get_current_user
from app.core.rate_limit import limiter
from .schemas import (
    RegisterRequest, LoginRequest,
    TokenResponse, UserResponse, RefreshRequest,
    ForgotPasswordRequest, ResetPasswordRequest,
    ConfirmAccountDeletionRequest,
)
from . import service

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit("10/hour")
async def register(request: Request, data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    return await service.register_user(db, data)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute;20/hour")
async def login(request: Request, data: LoginRequest, db: AsyncSession = Depends(get_db)):
    return await service.login_user(db, data)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    return await service.refresh_token(db, data.refresh_token)


@router.post("/logout", status_code=204)
async def logout(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    await service.logout_user(db, data.refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(current_user=Depends(get_current_user)):
    return current_user


@router.post("/forgot-password", status_code=204)
@limiter.limit("5/hour")
async def forgot_password(
    request: Request, data: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)
):
    await service.request_password_reset(db, data.email)


@router.post("/reset-password", status_code=204)
@limiter.limit("10/hour")
async def reset_password(
    request: Request, data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)
):
    await service.reset_password(db, data.email, data.code, data.new_password)


@router.post("/delete-account/request", status_code=204)
@limiter.limit("5/hour")
async def request_account_deletion(
    request: Request,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await service.request_account_deletion(db, current_user)


@router.post("/delete-account/confirm", status_code=204)
@limiter.limit("10/hour")
async def confirm_account_deletion(
    request: Request,
    data: ConfirmAccountDeletionRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await service.confirm_account_deletion(db, current_user, data.code)