from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyUoW:
    """Thin Unit of Work wrapper around SQLAlchemy AsyncSession.

    Exists solely to satisfy ``IUnitOfWork`` without a fragile ``cast``.
    All business logic still calls ``await uow.commit()`` / ``await uow.rollback()``
    through the protocol — the session never leaks into the application layer.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
