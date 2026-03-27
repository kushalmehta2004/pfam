import enum

from sqlalchemy import BigInteger, Integer, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BillingPlan(str, enum.Enum):
    STARTER = "starter"
    GROWTH = "growth"
    PRO = "pro"
    SCALE = "scale"
    ENTERPRISE = "enterprise"


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    billing_plan: Mapped[BillingPlan] = mapped_column(
        SAEnum(BillingPlan, name="billing_plan", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=BillingPlan.STARTER,
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    # ISO 4217 currency code, e.g. "USD"
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    # AWS region for data residency, e.g. "us-east-1" or "eu-west-1"
    data_region: Mapped[str] = mapped_column(String(32), nullable=False, default="us-east-1")
    # Attribution click window in days: 1, 7, 14, or 30
    attribution_window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    # Platform fee percentage * 10000 stored as integer (e.g. 290 = 2.90%)
    # Default: 2.9% represented as 290 basis-points-like integer (/ 10000 to get fraction)
    platform_fee_bps: Mapped[int] = mapped_column(BigInteger, nullable=False, default=290)
    # Fixed per-transaction fee in cents (e.g. $0.30 = 30)
    platform_fee_fixed_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=30)

    users = relationship("User", back_populates="organization")
