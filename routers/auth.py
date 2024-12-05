from datetime import datetime, timedelta, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
import logging

from models import BasicResponse, User, TwoFactorSetupResponse
from dependencies import (
    SessionDep, get_current_active_user, authenticate_user, 
    create_access_token
)
from services.two_factor import TwoFactorService
from services.email import generate_verification_code, send_verification_email
from core.config import get_settings

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

@router.post("/token", response_model=BasicResponse)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
):
    """Login endpoint to obtain access token"""
    user = authenticate_user(form_data.username, form_data.password, session)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, 
        expires_delta=access_token_expires
    )
    
    response = JSONResponse({"message": "Login successful"})
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        secure=True,
        samesite="Lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return response

@router.post("/logout", response_model=BasicResponse)
async def logout():
    """Logout endpoint that clears the authentication cookie"""
    response = JSONResponse({"message": "Logged out"})
    response.delete_cookie("access_token")
    return response

@router.post("/2fa/enable", response_model=TwoFactorSetupResponse)
async def enable_2fa(
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Enable 2FA for the current user"""
    if current_user.two_factor_enabled:
        raise HTTPException(status_code=400, detail="2FA already enabled")

    secret = TwoFactorService.generate_secret()
    current_user.two_factor_secret = secret
    session.add(current_user)
    session.commit()

    qr_uri = TwoFactorService.get_totp_uri(current_user)
    return {"secret": secret, "qr_uri": qr_uri}

@router.post("/2fa/verify", response_model=BasicResponse)
async def verify_2fa(
    code: str,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Verify and enable 2FA with provided code"""
    if not current_user.two_factor_secret:
        raise HTTPException(status_code=400, detail="2FA not set up")

    if TwoFactorService.verify_code(current_user.two_factor_secret, code):
        current_user.two_factor_enabled = True
        session.add(current_user)
        session.commit()
        return {"message": "2FA enabled successfully"}

    raise HTTPException(status_code=400, detail="Invalid verification code") 

@router.post("/verify-email", response_model=BasicResponse)
async def verify_email(
    verification_code: str,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> JSONResponse:
    """Verify user's email with the provided code"""
    if current_user.email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")

    if not current_user.verification_code:
        raise HTTPException(status_code=400, detail="No verification pending")

    if current_user.verification_code_expires.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Verification code expired")

    if current_user.verification_code != verification_code:
        raise HTTPException(status_code=400, detail="Invalid verification code")

    current_user.email_verified = True
    current_user.verification_code = None
    current_user.verification_code_expires = None

    session.add(current_user)
    session.commit()

    return JSONResponse({"message": "Email verified successfully"})

@router.post("/resend-verification", response_model=BasicResponse)
async def resend_verification(
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> JSONResponse:
    """Resend verification email"""
    if current_user.email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")

    verification_code = generate_verification_code()
    current_user.verification_code = verification_code
    current_user.verification_code_expires = datetime.now(timezone.utc) + timedelta(
        minutes=settings.VERIFICATION_CODE_EXPIRE_MINUTES
    )

    if send_verification_email(current_user.email, verification_code):
        session.add(current_user)
        session.commit()
        return JSONResponse({"message": "Verification email sent"})
    else:
        raise HTTPException(status_code=500, detail="Failed to send verification email") 