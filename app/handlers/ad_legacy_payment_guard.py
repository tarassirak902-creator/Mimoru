from __future__ import annotations

from aiogram import F, Router
from aiogram.types import PreCheckoutQuery


router = Router(name=__name__)


@router.pre_checkout_query(F.invoice_payload.regexp(r"^(reqad|postad|adorder):"))
async def reject_legacy_ad_invoice(query: PreCheckoutQuery) -> None:
    await query.answer(
        ok=False,
        error_message="Этот рекламный счёт создан по старой схеме. Вернитесь в раздел «Реклама» и создайте новую заявку.",
    )
