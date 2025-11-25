from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.auth import get_current_user, require_admin


def get_db_dep() -> Session:
    return next(get_db())


def get_current_user_dep(user: models.User = Depends(get_current_user)) -> models.User:
    return user


def get_admin_user_dep(user: models.User = Depends(require_admin)) -> models.User:
    return user
