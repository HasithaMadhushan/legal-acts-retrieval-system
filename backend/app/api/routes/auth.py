import hashlib
import secrets
from datetime import timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import LEGAL_DISCLAIMER, get_settings
from app.core.logging import get_logger
from app.core.passwords import full_name_from_email
from app.core.rate_limit import auth_rate_limit, limiter
from app.core.roles import UserRole
from app.core.security import create_access_token, hash_password, utc_now_naive, verify_password
from app.db.session import get_db
from app.models.password_reset_token import PasswordResetToken
from app.models.user import (
    LAWYER_REQUEST_NONE,
    LAWYER_REQUEST_PENDING,
    User,
)
from app.schemas.auth import (
    CurrentUserResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.schemas.user import UserRead
from app.services.storage import get_storage

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger(__name__)

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]

PROOF_PDF_SIGNATURE = b"%PDF"
PROOF_JPEG_SIGNATURE = b"\xff\xd8"
PROOF_PNG_SIGNATURE = b"\x89PNG"
PROOF_CONTENT_TYPES = {
    "application/pdf": (".pdf", PROOF_PDF_SIGNATURE),
    "image/jpeg": (".jpg", PROOF_JPEG_SIGNATURE),
    "image/png": (".png", PROOF_PNG_SIGNATURE),
}
RESET_MESSAGE = "If that email is registered, a password reset link will be issued."
READ_CHUNK_SIZE = 1024 * 64
LAWYER_VERIFY_RESPONSES = {
    400: {"description": "Invalid enrollment number, file type, or proof content."},
    413: {"description": "Proof file exceeds configured upload size limit."},
}
RESET_PASSWORD_RESPONSES = {
    400: {"description": "Reset token is invalid, expired, or already used."},
}


def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _read_upload_with_limit(upload: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = upload.file.read(READ_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail="Proof file exceeds configured upload size limit.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _current_user_payload(user: User) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        lawyer_request_status=user.lawyer_request_status,
        enrollment_number=user.enrollment_number,
        disclaimer=LEGAL_DISCLAIMER,
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit(auth_rate_limit)
def register(request: Request, payload: RegisterRequest, db: DbSession) -> User:
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email is already registered.")
    user = User(
        full_name=payload.full_name or full_name_from_email(str(payload.email)),
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=UserRole.GENERAL_USER,
        is_active=True,
        lawyer_request_status=LAWYER_REQUEST_NONE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit(auth_rate_limit)
def login(request: Request, payload: LoginRequest, db: DbSession) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive.")
    settings = get_settings()
    expires = timedelta(
        minutes=(
            settings.remember_me_expire_minutes
            if payload.remember_me
            else settings.access_token_expire_minutes
        )
    )
    return TokenResponse(
        access_token=create_access_token(
            user.id,
            user.role.value,
            token_version=user.token_version,
            expires_delta=expires,
        ),
        role=user.role,
        disclaimer=LEGAL_DISCLAIMER,
    )


@router.post("/logout")
def logout() -> dict[str, str]:
    return {"detail": "Discard the bearer token on the client."}


@router.get("/me", response_model=CurrentUserResponse)
def me(current_user: CurrentUser) -> CurrentUserResponse:
    return _current_user_payload(current_user)


@router.post(
    "/lawyer-verification",
    response_model=UserRead,
    responses=LAWYER_VERIFY_RESPONSES,
)
@limiter.limit(auth_rate_limit)
def submit_lawyer_verification(
    request: Request,
    enrollment_number: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    db: DbSession,
    current_user: CurrentUser,
) -> User:
    number = enrollment_number.strip()
    if not number:
        raise HTTPException(status_code=400, detail="Enrollment number is required.")
    if current_user.role != UserRole.GENERAL_USER:
        raise HTTPException(
            status_code=400,
            detail="Only General User accounts can submit attorney verification.",
        )

    original_name = file.filename or "proof.pdf"
    if "/" in original_name or "\\" in original_name:
        raise HTTPException(status_code=400, detail="File name must not contain path separators.")
    content_type = file.content_type or ""
    if content_type not in PROOF_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Proof must be a PDF, JPEG, or PNG file.")
    suffix, signature = PROOF_CONTENT_TYPES[content_type]
    settings = get_settings()
    content = _read_upload_with_limit(file, settings.max_upload_size_bytes)
    if not content.startswith(signature):
        raise HTTPException(status_code=400, detail="Uploaded proof file content is not valid.")

    stored_name = f"lawyer-proof-{current_user.id}-{uuid4()}{suffix}"
    stored_key = get_storage().save(stored_name, content)
    if current_user.enrollment_proof_path:
        get_storage().delete(current_user.enrollment_proof_path)

    current_user.enrollment_number = number
    current_user.enrollment_proof_path = stored_key
    current_user.lawyer_request_status = LAWYER_REQUEST_PENDING
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/forgot-password")
@limiter.limit(auth_rate_limit)
def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    db: DbSession,
) -> ForgotPasswordResponse:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not user.is_active:
        return ForgotPasswordResponse(detail=RESET_MESSAGE)

    now = utc_now_naive()
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).update({"used_at": now})

    settings = get_settings()
    raw_token = secrets.token_urlsafe(32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_reset_token(raw_token),
            expires_at=now + timedelta(minutes=settings.password_reset_expire_minutes),
        )
    )
    db.commit()

    # Never return the raw token in the HTTP body (email enumeration / token leak).
    # In development the reset URL is written to structured logs for local demos.
    logger.info("password_reset_requested", user_id=user.id)
    if settings.environment.strip().lower() == "development":
        reset_url = f"{settings.frontend_url.rstrip('/')}/reset-password?token={raw_token}"
        logger.info("password_reset_dev_url", reset_url=reset_url)
    return ForgotPasswordResponse(detail=RESET_MESSAGE)


@router.post("/reset-password", responses=RESET_PASSWORD_RESPONSES)
@limiter.limit(auth_rate_limit)
def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    db: DbSession,
) -> dict[str, str]:
    token_hash = _hash_reset_token(payload.token)
    record = (
        db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == token_hash).first()
    )
    now = utc_now_naive()
    if record is None or record.used_at is not None or record.expires_at < now:
        raise HTTPException(status_code=400, detail="Reset token is invalid or expired.")
    user = db.get(User, record.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="Reset token is invalid or expired.")
    user.hashed_password = hash_password(payload.password)
    user.token_version += 1
    record.used_at = now
    db.commit()
    return {"detail": "Password has been reset. You can sign in with the new password."}
