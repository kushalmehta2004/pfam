"""Automation rules engine models: AutomationRule and RuleExecution."""
import enum

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RuleScope(str, enum.Enum):
    """The ad hierarchy level this rule acts on."""
    ACCOUNT = "account"
    CAMPAIGN = "campaign"
    AD_SET = "adset"
    AD = "ad"


class RuleActionType(str, enum.Enum):
    """The action the rule will execute when conditions are met."""
    PAUSE = "pause"
    REDUCE_BUDGET = "reduce_budget"
    INCREASE_BUDGET = "increase_budget"
    ALERT_ONLY = "alert_only"


class AutomationRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user-defined automation rule for profit-based campaign actions.

    Rules are created in draft state (is_active=False) and must be explicitly
    activated by the user. All rules are platform-specific per the SRS.
    """

    __tablename__ = "automation_rules"
    __table_args__ = (
        # Pre-filter index for rule evaluation loop (SRS Section 8)
        Index("ix_automation_rules_org_active_platform", "org_id", "is_active", "platform"),
    )

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Platform this rule targets: "meta", "google", "tiktok"
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    scope: Mapped[RuleScope] = mapped_column(
        SAEnum(RuleScope, name="rule_scope"),
        nullable=False,
        default=RuleScope.AD_SET,
    )

    # Conditions stored as JSON array:
    # [{"metric": "rolling_net_profit", "operator": "<", "value": 0, "window_days": 7}]
    conditions_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    action_type: Mapped[RuleActionType] = mapped_column(
        SAEnum(RuleActionType, name="rule_action_type"),
        nullable=False,
    )
    # Action parameters e.g. {"budget_reduction_pct": 20}
    action_params_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Guardrails stored as JSON:
    # {"min_orders": 10, "min_spend_cents": 5000, "max_actions_per_day": 10}
    guardrails_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # New rules are always created in draft state (OFF)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


class RuleExecution(UUIDPrimaryKeyMixin, Base):
    """Record of each rule evaluation run (one row per rule per sync cycle).

    Append-only — not updated after creation. Used for audit and debugging.
    """

    __tablename__ = "rule_executions"
    __table_args__ = (
        Index("ix_rule_executions_rule_evaluated_at", "rule_id", "evaluated_at"),
    )

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[str] = mapped_column(
        ForeignKey("automation_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    evaluated_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)

    # How many entities (campaigns / ad sets) were evaluated
    entities_evaluated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # How many passed the condition threshold
    entities_triggered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # How many were blocked by guardrails (min orders, min spend, etc.)
    entities_blocked_by_guardrail: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Whether an action was actually queued for execution
    action_queued: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Idempotency key: rule cannot fire on the same entity within 24h
    # Stored as JSON {"entity_id": "last_fired_at_iso"}
    idempotency_state_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
