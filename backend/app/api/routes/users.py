from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.roles import UserRole
from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import (
    LAWYER_REQUEST_APPROVED,
    LAWYER_REQUEST_PENDING,
    LAWYER_REQUEST_REJECTED,
    User,
)
from app.schemas.user import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[UserRead])
def list_users(
    lawyer_request_status: str | None = None,
    db: Session = Depends(get_db),
) -> list[User]:
    query = db.query(User)
    if lawyer_request_status:
        query = query.filter(User.lawyer_request_status == lawyer_request_status)
    return query.order_by(User.created_at.desc()).all()


@router.post("", response_model=UserRead, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email is already registered.")
    user = User(
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        is_active=payload.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(user_id: str, payload: UserUpdate, db: Session = Depends(get_db)) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    update_data = payload.model_dump(exclude_unset=True)
    password = update_data.pop("password", None)
    for key, value in update_data.items():
        setattr(user, key, value)
    if password:
        user.hashed_password = hash_password(password)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", response_model=UserRead)
def deactivate_user(user_id: str, db: Session = Depends(get_db)) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user


def _pending_lawyer_request(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.lawyer_request_status != LAWYER_REQUEST_PENDING:
        raise HTTPException(
            status_code=400,
            detail="User does not have a pending attorney request.",
        )
    return user


@router.post("/{user_id}/lawyer-requests/approve", response_model=UserRead)
def approve_lawyer_request(user_id: str, db: Session = Depends(get_db)) -> User:
    user = _pending_lawyer_request(db, user_id)
    user.role = UserRole.LAWYER
    user.lawyer_request_status = LAWYER_REQUEST_APPROVED
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/lawyer-requests/reject", response_model=UserRead)
def reject_lawyer_request(user_id: str, db: Session = Depends(get_db)) -> User:
    user = _pending_lawyer_request(db, user_id)
    user.role = UserRole.GENERAL_USER
    user.lawyer_request_status = LAWYER_REQUEST_REJECTED
    db.commit()
    db.refresh(user)
    return user
