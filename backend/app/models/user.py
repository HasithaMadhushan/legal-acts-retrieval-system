from sqlalchemy import Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.roles import UserRole
from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

LAWYER_REQUEST_NONE = "none"
LAWYER_REQUEST_PENDING = "pending"
LAWYER_REQUEST_APPROVED = "approved"
LAWYER_REQUEST_REJECTED = "rejected"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), default=UserRole.GENERAL_USER, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lawyer_request_status: Mapped[str] = mapped_column(
        String(32), default=LAWYER_REQUEST_NONE, nullable=False, index=True
    )
    enrollment_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    enrollment_proof_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    uploaded_acts = relationship("LegalAct", back_populates="uploaded_by")
    saved_items = relationship("SavedItem", back_populates="user", cascade="all, delete-orphan")
    password_reset_tokens = relationship(
        "PasswordResetToken", back_populates="user", cascade="all, delete-orphan"
    )
