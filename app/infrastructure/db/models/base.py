from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Explicit naming convention so Alembic generates deterministic, reproducible
# constraint names across all environments.  Without this, auto-generated names
# (e.g. PostgreSQL's "platform_identities_user_id_fkey") differ between DBs
# and make autogenerate migrations unreliable.
_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class InfraBase(DeclarativeBase):
    metadata = MetaData(naming_convention=_NAMING_CONVENTION)
