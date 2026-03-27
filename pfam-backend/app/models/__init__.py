"""Database models package — exports all SQLAlchemy models.

Import order matters: tables with foreign keys must be defined after their
referenced tables. Alembic autogenerate reads Base.metadata, so every model
module must be imported here before migrations are generated.
"""

# Phase 1: Auth, Tenancy, RBAC
from app.models.organization import Organization, BillingPlan  # noqa: F401
from app.models.user import User, UserRole  # noqa: F401

# Phase 2: Connectors
from app.models.connectors import Store, AdAccount, Platform, SyncStatus  # noqa: F401

# Phase 2: Ad Hierarchy
from app.models.ads import Campaign, AdSet, Ad, AdInsight, AdStatus  # noqa: F401


# Phase 2: Commerce
from app.models.commerce import Order, LineItem, Return, CogsSource, ReturnReasonCategory  # noqa: F401

# Phase 2: Attribution
from app.models.attribution import AttributedOrder, SkuReturnRate, AttributionTier, AttributionMethod  # noqa: F401

# Phase 2: Profit
from app.models.profit import ProfitMetric, WindowType  # noqa: F401

# Phase 2: Automation (must be before AuditLog due to FK from audit_log → automation_rules)
from app.models.automation import AutomationRule, RuleExecution, RuleScope, RuleActionType  # noqa: F401

# Phase 2: Audit Log (extended — references automation_rules)
from app.models.audit_log import AuditLog, ActorType  # noqa: F401

# Phase 2: Settings
from app.models.settings import CogsSetting, CogsScope, CogsType, CogsDataSource  # noqa: F401

# Phase 2: Notifications
from app.models.notifications import Notification, NotificationChannel, DeliveryStatus  # noqa: F401


__all__ = [
    # Organizations & Users
    "Organization", "BillingPlan",
    "User", "UserRole",
    # Connectors
    "Store", "AdAccount", "Platform", "SyncStatus",
    # Ad Hierarchy
    "Campaign", "AdSet", "AdInsight", "AdStatus",
    # Commerce
    "Order", "LineItem", "Return", "CogsSource", "ReturnReasonCategory",
    # Attribution
    "AttributedOrder", "SkuReturnRate", "AttributionTier", "AttributionMethod",
    # Profit
    "ProfitMetric", "WindowType",
    # Automation
    "AutomationRule", "RuleExecution", "RuleScope", "RuleActionType",
    # Audit
    "AuditLog", "ActorType",
    # Settings
    "CogsSetting", "CogsScope", "CogsType", "CogsDataSource",
    # Notifications
    "Notification", "NotificationChannel", "DeliveryStatus",
]
