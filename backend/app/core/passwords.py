import re

PASSWORD_REQUIREMENT = "Use at least 8 characters with letters and numbers."
_PASSWORD_PATTERN = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$")
_NAME_SPLIT = re.compile(r"[._+\-]+")


def password_meets_policy(password: str) -> bool:
    return bool(_PASSWORD_PATTERN.search(password))


def full_name_from_email(email: str) -> str:
    local = email.split("@", 1)[0]
    cleaned = " ".join(part for part in _NAME_SPLIT.split(local) if part)
    name = " ".join(part.capitalize() for part in cleaned.split())
    return name if len(name) >= 2 else "Registered User"
