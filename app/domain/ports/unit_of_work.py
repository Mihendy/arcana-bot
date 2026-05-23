from __future__ import annotations

from typing import Protocol


class IUnitOfWork(Protocol):
    """Minimal Unit of Work contract: owns commit and rollback.

    ``AsyncSession`` from SQLAlchemy satisfies this protocol structurally,
    so the application layer never imports SQLAlchemy directly — it only
    depends on this domain-level abstraction.
    """

    async def commit(self) -> None:
        """Persist all pending changes atomically."""
        ...

    async def rollback(self) -> None:
        """Discard all pending changes."""
        ...
