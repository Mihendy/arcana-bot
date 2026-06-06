"""VK admin commands (test_story, etc.)."""

from __future__ import annotations

import logging
from io import BytesIO
from urllib.parse import urlencode

from dishka import AsyncContainer
from vkbottle import API
from vkbottle.bot import BotLabeler, Message

from app.application.use_cases.get_daily_card import GetDailyCardUseCase
from app.core.config import Settings
from app.infrastructure.vk.photo_uploader import VKPhotoUploader
from app.presentation.telegram.formatters.daily_card import build_caption
from app.presentation.vk.formatters.keyboards import build_story_keyboard

logger = logging.getLogger(__name__)


def register(
    labeler: BotLabeler,
    container: AsyncContainer,
    api: API,
    settings: Settings,
) -> None:
    """Register admin-only VK handlers."""

    @labeler.message(text=["/test_story", "test_story"])
    async def handle_test_story(message: Message) -> None:
        if not settings.admin_vk_id or message.from_id != settings.admin_vk_id:
            return

        await message.answer("Генерирую карту дня для теста…")

        try:
            async with container() as di:
                use_case: GetDailyCardUseCase = await di.get(GetDailyCardUseCase)
                result = await use_case.execute()
        except Exception:
            logger.exception("vk test_story: daily card generation failed")
            await message.answer("Ошибка при генерации карты дня.")
            return

        uploader = VKPhotoUploader(api, settings.vk_group_id)
        attachment: str | None = None
        if result.image_bytes:
            try:
                attachment = await uploader.upload_message_photo(
                    BytesIO(result.image_bytes), "test_story.png"
                )
            except Exception:
                logger.exception("vk test_story: photo upload failed")

        caption = build_caption(result)
        story_url = result.story_image_url or result.image_url

        info_lines = [
            caption,
            "",
            f"Story image URL: {story_url}",
        ]

        keyboard: str | None = None
        if settings.vk_app_id:
            app_url = f"https://vk.ru/app{settings.vk_app_id}"
            hash_params = f"image_url={story_url}&app_url={app_url}"
            keyboard = build_story_keyboard(
                app_id=settings.vk_app_id,
                group_id=settings.vk_group_id,
                hash_params=hash_params,
            )

        kwargs: dict = {
            "message": "\n".join(info_lines),
            "attachment": attachment or "",
            "random_id": 0,
        }
        if keyboard:
            kwargs["keyboard"] = keyboard

        await api.messages.send(user_id=message.from_id, **kwargs)
