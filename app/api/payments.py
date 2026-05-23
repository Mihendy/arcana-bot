"""YooKassa webhook endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.application.use_cases.confirm_subscription_payment import (
    ConfirmSubscriptionPaymentUseCase,
    PaymentNotFoundError,
)
from app.domain.ports.payment_repo import IPaymentRepository
from app.domain.ports.unit_of_work import IUnitOfWork
from app.domain.ports.user_repo import IUserRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])

_ACTIVATED_MSG = (
    "💳 Оплата картой прошла успешно!\n\n"
    "Ваша Премиум-подписка активирована на 30 дней. Лимиты полностью отключены! 🌟"
)


@router.post("/yookassa/webhook")
async def yookassa_webhook(request: Request) -> JSONResponse:
    """Receive payment.succeeded events from YooKassa and activate premium."""
    body = await request.json()

    if body.get("event") != "payment.succeeded":
        return JSONResponse({"status": "ok"})

    obj = body.get("object", {})
    raw_payment_id = obj.get("metadata", {}).get("payment_id")
    yookassa_payment_id: str = obj.get("id", "")

    if raw_payment_id is None:
        logger.error("yookassa webhook: missing metadata.payment_id body=%s", body)
        return JSONResponse({"status": "ok"})

    try:
        payment_db_id = int(raw_payment_id)
    except (ValueError, TypeError):
        logger.error("yookassa webhook: invalid payment_id=%r", raw_payment_id)
        return JSONResponse({"status": "ok"})

    container = request.app.state.container
    async with container() as di:
        payment_repo: IPaymentRepository = await di.get(IPaymentRepository)
        user_repo: IUserRepository = await di.get(IUserRepository)
        uow: IUnitOfWork = await di.get(IUnitOfWork)

        try:
            use_case = ConfirmSubscriptionPaymentUseCase(payment_repo, user_repo, uow)
            user_id = await use_case.execute(
                payment_db_id=payment_db_id,
                provider_charge_id=yookassa_payment_id,
            )
        except PaymentNotFoundError:
            logger.error("yookassa webhook: payment not found id=%d", payment_db_id)
            return JSONResponse({"status": "ok"})
        except Exception:
            logger.exception(
                "yookassa webhook: confirm failed payment_id=%d", payment_db_id
            )
            return JSONResponse({"status": "ok"})

        identity = await user_repo.get_identity_by_user_id(user_id, "telegram")

    if identity is not None:
        bot = request.app.state.telegram_service.app.bot
        try:
            await bot.send_message(chat_id=int(identity.external_id), text=_ACTIVATED_MSG)
        except Exception:
            logger.exception(
                "yookassa webhook: telegram notify failed user_id=%d tg=%s",
                user_id,
                identity.external_id,
            )

    return JSONResponse({"status": "ok"})
