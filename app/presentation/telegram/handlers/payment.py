"""Payment handlers: buy buttons, pre-checkout approval, successful payment."""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    BaseHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

from app.application.use_cases.confirm_subscription_payment import (
    ConfirmSubscriptionPaymentUseCase,
    PaymentNotFoundError,
)
from app.application.use_cases.create_subscription_payment import (
    CreateSubscriptionPaymentUseCase,
)
from app.core.config import settings as _settings
from app.domain.ports.payment_repo import IPaymentRepository
from app.domain.ports.unit_of_work import IUnitOfWork
from app.domain.ports.user_repo import IUserRepository
from app.infrastructure.payment.tg_stars import TelegramStarsPaymentGateway
from app.infrastructure.payment.yookassa import YookassaPaymentGateway
from app.presentation.telegram.di import get_container

logger = logging.getLogger(__name__)

_PLATFORM = "telegram"
_PROVIDER_STARS = "tg_stars"

_PAYMENT_ERROR = "Не удалось создать платёж. Попробуй позже."
_CONFIRM_ERROR = "Платёж получен, но активация задержалась. Обратись в поддержку."
_INVOICE_PROMPT = (
    "Нажми кнопку ниже, чтобы оплатить подписку через Telegram Stars ⭐\n\n"
    "После оплаты подписка активируется мгновенно."
)
_ACTIVATED = (
    "🎉 Подписка активирована!\n\n"
    "Тебе доступны безлимитные расклады на 30 дней. "
    "Статус можно проверить в меню 👤 Профиль."
)


async def buy_stars_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 'buy:tg_stars' callback — create invoice and send the link."""
    query = update.callback_query
    tg_user = update.effective_user
    if query is None or tg_user is None:
        return
    await query.answer()

    gateway = TelegramStarsPaymentGateway(context.bot)
    try:
        async with get_container(context)() as di:
            user_repo: IUserRepository = await di.get(IUserRepository)
            payment_repo: IPaymentRepository = await di.get(IPaymentRepository)
            uow: IUnitOfWork = await di.get(IUnitOfWork)

            user = await user_repo.get_by_platform_id(_PLATFORM, str(tg_user.id))
            if user is None:
                await query.message.reply_text("Пожалуйста, начни с /start.")  # type: ignore[union-attr]
                return

            use_case = CreateSubscriptionPaymentUseCase(gateway, payment_repo, uow, _settings)
            invoice_url = await use_case.execute(
                user_id=user.id,
                provider_name=_PROVIDER_STARS,
            )
    except Exception:
        logger.exception("buy_stars failed tg_id=%s", tg_user.id)
        if query.message:
            await query.message.reply_text(_PAYMENT_ERROR)
        return

    await query.message.reply_text(  # type: ignore[union-attr]
        _INVOICE_PROMPT,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(f"⭐ Оплатить {_settings.premium_price_stars} Stars", url=invoice_url)]]
        ),
    )


async def buy_yookassa_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 'buy:yookassa' callback — create YooKassa invoice and send the link."""
    query = update.callback_query
    tg_user = update.effective_user
    if query is None or tg_user is None:
        return
    await query.answer()

    gateway = YookassaPaymentGateway(_settings)
    try:
        async with get_container(context)() as di:
            user_repo: IUserRepository = await di.get(IUserRepository)
            payment_repo: IPaymentRepository = await di.get(IPaymentRepository)
            uow: IUnitOfWork = await di.get(IUnitOfWork)

            user = await user_repo.get_by_platform_id(_PLATFORM, str(tg_user.id))
            if user is None:
                await query.message.reply_text("Пожалуйста, начни с /start.")  # type: ignore[union-attr]
                return

            use_case = CreateSubscriptionPaymentUseCase(gateway, payment_repo, uow, _settings)
            payment_url = await use_case.execute(
                user_id=user.id,
                provider_name="yookassa",
            )
    except Exception:
        logger.exception("buy_yookassa failed tg_id=%s", tg_user.id)
        if query.message:
            await query.message.reply_text(_PAYMENT_ERROR)
        return

    await query.message.reply_text(  # type: ignore[union-attr]
        "Нажми кнопку ниже, чтобы перейти на страницу оплаты.\n\n"
        "После успешной оплаты подписка активируется автоматически.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(
                f"🔗 Перейти к оплате ({_settings.premium_price_rub} ₽)",
                url=payment_url,
            )]]
        ),
    )


async def pre_checkout_query_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Auto-approve all Telegram Stars pre-checkout queries."""
    query = update.pre_checkout_query
    if query is None:
        return
    await query.answer(ok=True)


async def successful_payment_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Confirm the payment in DB and activate the user's premium subscription."""
    message = update.effective_message
    if message is None or message.successful_payment is None:
        return

    sp = message.successful_payment
    try:
        payment_db_id = int(sp.invoice_payload)
    except ValueError:
        logger.error("invalid invoice_payload: %r", sp.invoice_payload)
        return

    charge_id = sp.telegram_payment_charge_id

    try:
        async with get_container(context)() as di:
            payment_repo: IPaymentRepository = await di.get(IPaymentRepository)
            user_repo: IUserRepository = await di.get(IUserRepository)
            uow: IUnitOfWork = await di.get(IUnitOfWork)

            use_case = ConfirmSubscriptionPaymentUseCase(payment_repo, user_repo, uow)
            await use_case.execute(
                payment_db_id=payment_db_id,
                provider_charge_id=charge_id,
            )
    except PaymentNotFoundError:
        logger.error("payment not found payload=%d charge=%s", payment_db_id, charge_id)
        await message.reply_text(_CONFIRM_ERROR)
        return
    except Exception:
        logger.exception("confirm_payment failed payload=%d charge=%s", payment_db_id, charge_id)
        await message.reply_text(_CONFIRM_ERROR)
        return

    await message.reply_text(_ACTIVATED)


def get_payment_handlers() -> list[BaseHandler]:
    """Return payment-related handlers in priority order."""
    return [
        CallbackQueryHandler(buy_stars_callback, pattern=r"^buy:tg_stars$"),
        CallbackQueryHandler(buy_yookassa_callback, pattern=r"^buy:yookassa$"),
        PreCheckoutQueryHandler(pre_checkout_query_handler),
        MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler),
    ]
