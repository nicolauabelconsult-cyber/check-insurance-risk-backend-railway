# seed_admin.py
from sqlalchemy.orm import Session

from auth import get_password_hash
from models import User, UserRole


def seed_default_admin(db: Session) -> None:
    """
    Garante que existe um utilizador admin por defeito.
    username: admin
    password: admin123
    """
    existing = db.query(User).filter(User.username == "admin").first()
    if existing:
        return

    admin = User(
        username="admin",
        email="admin@example.com",
        hashed_password=get_password_hash("admin123"),
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    db.add(admin)
    db.commit()
