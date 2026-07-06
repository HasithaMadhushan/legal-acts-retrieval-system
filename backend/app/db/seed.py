from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.roles import UserRole
from app.core.security import hash_password
from app.models.user import User

logger = get_logger(__name__)

DEMO_USERS = [
    ("Admin User", "admin@example.com", "AdminPass123!", UserRole.ADMIN),
    ("Lawyer User", "lawyer@example.com", "LawyerPass123!", UserRole.LAWYER),
    ("General User", "user@example.com", "UserPass123!", UserRole.GENERAL_USER),
]


def seed_demo_users(db: Session) -> None:
    """Insert/refresh the demo accounts.

    Every Gunicorn worker runs this independently from its own `lifespan`
    startup, so two workers can race to insert the same not-yet-existing
    email at once. Since they'd insert identical data, it's safe to treat a
    unique-constraint violation here as "another worker already did this"
    and move on rather than crash the worker's startup.
    """
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
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.info("demo_user_seed_race_ignored")
