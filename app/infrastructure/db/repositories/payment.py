from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.payment import Payment
from app.infrastructure.db.models.payment import PaymentORM


class PostgresPaymentRepository:
    """Implements IPaymentRepository against PostgreSQL via SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: int,
        amount: Decimal,
        currency: str,
        provider: str,
    ) -> Payment:
        """Insert a pending payment row and flush to obtain the assigned id."""
        orm = PaymentORM(
            user_id=user_id,
            amount=amount,
            currency=currency,
            provider=provider,
        )
        self._session.add(orm)
        await self._session.flush()  # populates orm.id without committing
        return _to_entity(orm)

    async def get_by_id(self, payment_id: int) -> Payment | None:
        result = await self._session.get(PaymentORM, payment_id)
        return _to_entity(result) if result else None

    async def get_by_provider_id(self, provider_payment_id: str) -> Payment | None:
        result = await self._session.execute(
            select(PaymentORM).where(PaymentORM.provider_payment_id == provider_payment_id)
        )
        row = result.scalar_one_or_none()
        return _to_entity(row) if row else None

    async def set_provider_id(self, payment_id: int, provider_payment_id: str) -> None:
        await self._session.execute(
            update(PaymentORM)
            .where(PaymentORM.id == payment_id)
            .values(provider_payment_id=provider_payment_id)
        )

    async def confirm(self, payment_id: int, provider_payment_id: str) -> None:
        await self._session.execute(
            update(PaymentORM)
            .where(PaymentORM.id == payment_id)
            .values(status="confirmed", provider_payment_id=provider_payment_id)
        )


def _to_entity(row: PaymentORM) -> Payment:
    now = datetime.now(timezone.utc)
    return Payment(
        id=row.id,
        user_id=row.user_id,
        amount=Decimal(str(row.amount)),
        currency=row.currency,
        provider=row.provider,
        status=row.status,
        provider_payment_id=row.provider_payment_id,
        created_at=row.created_at or now,
        updated_at=row.updated_at or now,
    )
