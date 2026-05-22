from sqlmodel import SQLModel

from app import models  # noqa: F401

# Import models here so Alembic can discover them.
metadata = SQLModel.metadata
