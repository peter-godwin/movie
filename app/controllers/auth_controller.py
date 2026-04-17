import uuid
from datetime import datetime, timedelta
from fastapi import HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.user import User
from app.schemas.auth import UserCreate, UserOut, Token, LoginRequest, RefreshRequest, MessageResponse
from app.services import auth_service
from app.services.email_service import (
    send_verification_email,
    send_welcome_email,
)
from app.config import settings


async def signup(user_in: UserCreate, background_tasks: BackgroundTasks, db: AsyncSession) -> UserOut:
    result = await db.execute(select(User).where(User.email == user_in.email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )

    verification_token = str(uuid.uuid4())

    db_user = User(
        name=user_in.name,
        email=user_in.email,
        hashed_password=auth_service.get_password_hash(user_in.password),
        verification_token=verification_token
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    background_tasks.add_task(send_verification_email, db_user.email, verification_token)

    return db_user


async def login(login_data: LoginRequest, db: AsyncSession) -> Token:
    result = await db.execute(select(User).where(User.email == login_data.email))
    user = result.scalar_one_or_none()

    if not user or not auth_service.verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in."
        )

    access_token = auth_service.create_access_token(data={"sub": str(user.id)})
    refresh_token = auth_service.create_refresh_token(data={"sub": str(user.id)})

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


async def refresh_token(request: RefreshRequest, db: AsyncSession) -> Token:
    if await auth_service.is_token_blocked(db, request.refresh_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = auth_service.verify_token(request.refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    access_token = auth_service.create_access_token(data={"sub": str(user.id)})
    refresh_token = auth_service.create_refresh_token(data={"sub": str(user.id)})

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


async def logout(refresh_token: str, db: AsyncSession) -> MessageResponse:
    try:
        payload = auth_service.verify_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token type"
            )

        exp = payload.get("exp")
        if exp:
            expires_at = datetime.fromtimestamp(exp)
        else:
            expires_at = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)

        await auth_service.add_to_blocklist(db, refresh_token, "refresh", expires_at)

    except Exception:
        pass

    return MessageResponse(message="Logged out successfully")


async def verify_email(token: str, background_tasks: BackgroundTasks, db: AsyncSession) -> MessageResponse:
    result = await db.execute(select(User).where(User.verification_token == token))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification token"
        )

    user.is_verified = True
    user.verification_token = None
    await db.commit()

    background_tasks.add_task(send_welcome_email, user.email, user.name)

    return MessageResponse(message="Email verified successfully")


async def resend_verification(email: str, background_tasks: BackgroundTasks, db: AsyncSession) -> MessageResponse:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or user.is_verified:
        return MessageResponse(message="Verification email will be sent if account exists and is not verified.")

    verification_token = str(uuid.uuid4())
    user.verification_token = verification_token
    await db.commit()

    background_tasks.add_task(send_verification_email, user.email, verification_token)

    return MessageResponse(message="Verification email will be sent if account exists and is not verified.")