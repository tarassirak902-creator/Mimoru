from __future__ import annotations

from app.db.ad_market_models import (
    DirectRequiredRule,
    GlobalPostDelivery,
    GlobalPostRequest,
    RequiredAdDealRequest,
    RequiredAdListing,
)
from app.db.payment_refund_models import GlobalPostDuplicateRefund, SubscriptionDuplicateRefund
from app.db.session import engine


_AD_MARKET_TABLES = [
    RequiredAdListing.__table__,
    RequiredAdDealRequest.__table__,
    GlobalPostRequest.__table__,
    GlobalPostDelivery.__table__,
    DirectRequiredRule.__table__,
    GlobalPostDuplicateRefund.__table__,
    SubscriptionDuplicateRefund.__table__,
]


async def ensure_ad_market_schema() -> None:
    """Create only tables used by the current advertising marketplace."""
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: [
                table.create(sync_connection, checkfirst=True)
                for table in _AD_MARKET_TABLES
            ]
        )
