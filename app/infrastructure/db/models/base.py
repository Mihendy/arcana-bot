from sqlalchemy.orm import DeclarativeBase


class InfraBase(DeclarativeBase):
    """Declarative base for all infrastructure ORM models.

    Kept separate from the legacy ``app.models.base.Base`` so both can
    coexist during incremental migration. Alembic will be pointed at this
    metadata once the old models are retired.
    """
