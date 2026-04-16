"""Repository for user persistence."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """CRUD operations for User model."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_tg_id(self, tg_id: int) -> User | None:
        """Find user by Telegram ID."""
        result = await self.session.execute(select(User).where(User.tg_id == tg_id))
        return result.scalar_one_or_none()

    async def create(self, tg_id: int, username: str | None, full_name: str) -> User:
        """Create and persist new user."""
        user = User(tg_id=tg_id, username=username, full_name=full_name)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def get_or_create(
        self,
        tg_id: int,
        username: str | None,
        full_name: str,
    ) -> tuple[User, bool]:
        """Return existing user or create one."""
        user = await self.get_by_tg_id(tg_id=tg_id)
        if user is not None:
            return user, False
        return await self.create(tg_id=tg_id, username=username, full_name=full_name), True
