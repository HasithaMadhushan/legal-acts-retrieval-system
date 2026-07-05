from sqlalchemy.orm import Session

from app.core.roles import UserRole
from app.core.security import hash_password
from app.models.user import User

DEMO_USERS = [
    ("Admin User", "admin@example.com", "AdminPass123!", UserRole.ADMIN),
    ("Lawyer User", "lawyer@example.com", "LawyerPass123!", UserRole.LAWYER),
    ("General User", "user@example.com", "UserPass123!", UserRole.GENERAL_USER),
]


def seed_demo_users(db: Session) -> None:
    for full_name, email, password, role in DEMO_USERS:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            existing.full_name = full_name
            existing.hashed_password = hash_password(password)
            existing.role = role
            existing.is_active = True
            continue
        db.add(
            User(
                full_name=full_name,
                email=email,
                hashed_password=hash_password(password),
                role=role,
                is_active=True,
            )
        )
    db.commit()
