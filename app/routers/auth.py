from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timedelta, timezone
import uuid

from app.db.database import get_db
from app.models.user import User
from app.schemas.auth import (
    UserCreate,
    UserOut,
    Token,
    LoginRequest,
    ForgotPasswordRequest,
    VerifyOTPRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
    RefreshTokenRequest,
)
from app.services import auth_service
from app.services.email_service import (
    send_verification_email,
    send_otp_email,
    send_welcome_email,
)
from app.utils.response import send_response

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/refresh")
async def refresh_token(data: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    payload = auth_service.verify_token(data.refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    new_access_token = auth_service.create_access_token(data={"sub": str(user.id)})
    new_refresh_token = auth_service.create_refresh_token(data={"sub": str(user.id)})

    return send_response(
        data={
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
        },
        message="Token refreshed successfully.",
    )


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(
    user_in: UserCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )

    verification_token = auth_service.generate_otp()

    db_user = User(
        name=user_in.name,
        email=user_in.email,
        hashed_password=auth_service.get_password_hash(user_in.password),
        verification_token=verification_token,
        is_verified=False,
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    background_tasks.add_task(send_verification_email, db_user.email, verification_token)

    return send_response(
        data=UserOut.from_orm(db_user),
        message="User created successfully. Please verify your email.",
    )


@router.post("/verify-email")
async def verify_email(
    data: VerifyEmailRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or user.verification_token != data.verification_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification token",
        )

    user.is_verified = True
    user.verification_token = None
    await db.commit()

    background_tasks.add_task(send_welcome_email, user.email, user.name)

    return send_response(message="Email verified successfully.")


@router.post("/resend-verification")
async def resend_verification(
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or user.is_verified:
        return send_response(
            message="Verification email will be sent if account exists and is not verified."
        )

    new_token = auth_service.generate_otp()
    user.verification_token = new_token
    await db.commit()

    background_tasks.add_task(send_verification_email, user.email, new_token)

    return send_response(message="New verification token has been sent.")


@router.post("/login")
async def login(login_data: LoginRequest, db: AsyncSession = Depends(get_db)):
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
            detail="Please verify your email before logging in.",
        )

    access_token = auth_service.create_access_token(data={"sub": str(user.id)})
    refresh_token = auth_service.create_refresh_token(data={"sub": str(user.id)})

    return send_response(
        data={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        },
        message="Login successful.",
    )


@router.post("/forgot-password")
async def forgot_password(
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if user:
        otp_code = auth_service.generate_otp()
        user.otp_code = otp_code
        user.otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        await db.commit()

        background_tasks.add_task(send_otp_email, user.email, otp_code)

    return send_response(
        message="If an account exists with this email, an OTP has been sent."
    )


@router.post("/verify-otp")
async def verify_otp(data: VerifyOTPRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if (
        not user
        or user.otp_code != data.otp_code
        or user.otp_expires_at < datetime.now(timezone.utc)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP",
        )

    return send_response(message="OTP verified successfully.")


@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if (
        not user
        or user.otp_code != data.otp_code
        or user.otp_expires_at < datetime.now(timezone.utc)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP",
        )

    user.hashed_password = auth_service.get_password_hash(data.new_password)
    user.otp_code = None
    user.otp_expires_at = None
    await db.commit()

    return send_response(message="Password reset successfully.")