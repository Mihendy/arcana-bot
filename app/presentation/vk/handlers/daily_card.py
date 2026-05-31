"""VK daily card broadcaster."""

from __future__ import annotations

import asyncio
import logging
from io import BytesIO

from dishka import AsyncContainer
from vkbottle import API, VKAPIError

from app.application.use_cases.get_daily_card import GetDailyCardUseCase
from app.core.config import Settings
from app.domain.ports.unit_of_work import IUnitOfWork
from app.domain.ports.user_repo import IUserRepository
from app.infrastructure.vk.photo_uploader import VKPhotoUploader
from app.presentation.telegram.formatters.daily_card import build_caption

logger = logging.getLogger(__name__)

_SEND_CONCURRENCY = 25

# VK error code when user has privacy settings blocking community messages.
_VK_CANT_SEND_TO_USER = 901


class VKDailyCardBroadcaster:
    """Sends the daily card to all VK users via the group API."""

    def __init__(self, container: AsyncContainer, api: API, settings: Settings) -> None:
        self._container = container
        self._api = api
        self._settings = settings

    async def broadcast(self) -> None:
        """Generate and send the daily card to all active VK users."""
        async with self._container() as di:
            use_case: GetDailyCardUseCase = await di.get(GetDailyCardUseCase)
            result = await use_case.execute()
            user_repo: IUserRepository = await di.get(IUserRepository)
            identities = await user_repo.list_platform_identities("vk")

        if not identities:
            logger.info("vk daily_card broadcast skipped: no recipients")
            return

        uploader = VKPhotoUploader(self._api, self._settings.vk_group_id)

        attachment: str | None = None
        if result.image_bytes:
            try:
                buf = BytesIO(result.image_bytes)
                attachment = await uploader.upload_message_photo(buf, "daily_card.png")
            except Exception:
                logger.exception("vk daily_card photo upload failed")

        caption = build_caption(result)
        logger.info(
            "vk daily_card broadcasting card=%s to %d users",
            result.card_name, len(identities),
        )

        semaphore = asyncio.Semaphore(_SEND_CONCURRENCY)
        blocked: list[str] = []

        async def _send_one(external_id: str) -> None:
            async with semaphore:
                try:
                    await self._api.messages.send(
                        user_id=int(external_id),
                        message=caption,
                        attachment=attachment or "",
                        random_id=0,
                    )
                except VKAPIError as exc:
                    if exc.code == _VK_CANT_SEND_TO_USER:
                        logger.warning(
                            "vk daily_card: user restricted messages, "
                            "will be excluded external_id=%s",
                            external_id,
                        )
                        blocked.append(external_id)
                    else:
                        logger.exception(
                            "vk daily_card send failed external_id=%s", external_id
                        )
                except Exception:
                    logger.exception(
                        "vk daily_card send failed external_id=%s", external_id
                    )

        await asyncio.gather(*[_send_one(i.external_id) for i in identities])

        if blocked:
            async with self._container() as di:
                user_repo = await di.get(IUserRepository)
                uow: IUnitOfWork = await di.get(IUnitOfWork)
                await user_repo.mark_blocked_many(blocked)
                await uow.commit()
            logger.info("vk daily_card: marked %d users as blocked", len(blocked))
