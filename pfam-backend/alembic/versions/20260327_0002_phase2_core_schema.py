"""phase 2 core schema — all PFAM business domain tables

Revision ID: 20260327_0002
Revises: 20260324_0001
Create Date: 2026-03-27 00:00:02.000000

Tables created:
  organisations     — extended with billing/Stripe/attribution fields
  stores            — Shopify store connector
  ad_accounts       — Meta / Google / TikTok ad account connector
  campaigns         — Ad platform campaign hierarchy
  ad_sets           — Ad set / ad group hierarchy
  ad_insights       — Daily spend + impression metrics per ad set
  ads               — Individual ad creative entity
  orders            — Shopify orders
  line_items        — Order line items with COGS
  returns           — Shopify refunds (line-item granularity)
  attributed_orders — Attribution engine output (order → ad set)
  sku_return_rates  — Trailing SKU-level return rates
  profit_metrics    — Immutable profit snapshots per ad set per window
  automation_rules  — User-defined profit automation rules
  rule_executions   — Append-only rule evaluation records
  audit_log         — Extended with automation action fields
  cogs_settings     — COGS configuration entries
  notifications     — Multi-channel notification delivery records
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260327_0002"
down_revision: Union[str, None] = "20260324_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── 0. Define ENUM names for dropping ────────────────────────────────────────
ENUM_NAMES = [
    "billing_plan", "sync_status", "ad_platform", "ad_status",
    "cogs_source", "return_reason_category", "attribution_method",
    "window_type", "rule_scope", "rule_action_type", "actor_type",
    "cogs_scope", "cogs_type", "cogs_data_source",
    "notification_channel", "delivery_status",
]

# ── 1. Helper: Safe Type Creation ──────────────────────────────────────────
def _create_enum(name: str, *values: str) -> None:
    # We use CASCADE drop at the start of upgrade to ensure these are clean
    op.execute(sa.text(f"CREATE TYPE {name} AS ENUM ({', '.join(f'\'{v}\'' for v in values)})"))


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------
def upgrade() -> None:
    # ── 1. Clean Slate for Types ─────────────────────────────────────────────
    # Force drop existing types to prevent 'DuplicateObject' errors from failed runs
    for name in ENUM_NAMES:
        op.execute(sa.text(f"DROP TYPE IF EXISTS {name} CASCADE"))

    # ── 2. Recreate all ENUM types ───────────────────────────────────────────
    _create_enum("billing_plan", "starter", "growth", "pro", "scale", "enterprise")
    _create_enum("sync_status", "pending", "running", "success", "failed", "disconnected")
    _create_enum("ad_platform", "meta", "google", "tiktok")
    _create_enum("ad_status", "active", "paused", "archived", "deleted", "unknown")
    _create_enum("cogs_source", "shopify", "csv", "manual", "estimated")
    _create_enum("return_reason_category", "defective", "wrong_item", "changed_mind", "sizing", "other")
    _create_enum("attribution_method", "fbclid", "gclid", "ttclid", "conversion_event", "sku_weighted", "blended_spend", "ml_xgboost")
    _create_enum("window_type", "daily", "7d", "14d", "30d")
    _create_enum("rule_scope", "account", "campaign", "adset", "ad")
    _create_enum("rule_action_type", "pause", "reduce_budget", "increase_budget", "alert_only")
    _create_enum("actor_type", "user", "system")
    _create_enum("cogs_scope", "sku", "category", "global")
    _create_enum("cogs_type", "absolute", "percentage")
    _create_enum("cogs_data_source", "shopify", "csv", "manual", "estimated")
    _create_enum("notification_channel", "email", "slack", "webhook", "in_app")
    _create_enum("delivery_status", "pending", "delivered", "failed", "retrying")

    # Now define Enum types for use in tables (create_type=False is CRITICAL here)
    def _enum_type(name: str):
        return postgresql.ENUM(name=name, create_type=False)

    # ── 3. Extend organizations table ─────────────────────────────────────────
    op.add_column("organizations", sa.Column("billing_plan", _enum_type("billing_plan"), nullable=False, server_default="starter"))
    op.add_column("organizations", sa.Column("stripe_customer_id", sa.String(128), nullable=True))
    op.add_column("organizations", sa.Column("base_currency", sa.String(3), nullable=False, server_default="USD"))
    op.add_column("organizations", sa.Column("data_region", sa.String(32), nullable=False, server_default="us-east-1"))
    op.add_column("organizations", sa.Column("attribution_window_days", sa.Integer(), nullable=False, server_default="7"))
    op.add_column("organizations", sa.Column("platform_fee_bps", sa.BigInteger(), nullable=False, server_default="290"))
    op.add_column("organizations", sa.Column("platform_fee_fixed_cents", sa.BigInteger(), nullable=False, server_default="30"))
    op.create_unique_constraint("uq_organizations_stripe_customer_id", "organizations", ["stripe_customer_id"])

    # ── 4. Extend audit_log table ─────────────────────────────────────────────
    op.add_column("audit_log", sa.Column("actor_type", _enum_type("actor_type"), nullable=True))
    op.add_column("audit_log", sa.Column("action_type", sa.String(120), nullable=True))
    op.add_column("audit_log", sa.Column("entity_type", sa.String(80), nullable=True))
    op.add_column("audit_log", sa.Column("entity_id", sa.String(128), nullable=True))
    op.add_column("audit_log", sa.Column("platform", sa.String(32), nullable=True))
    op.add_column("audit_log", sa.Column("rule_id", sa.Uuid(as_uuid=False), nullable=True))
    op.add_column("audit_log", sa.Column("metric_snapshot_json", sa.JSON(), nullable=True))
    op.add_column("audit_log", sa.Column("api_request_json", sa.JSON(), nullable=True))
    op.add_column("audit_log", sa.Column("api_response_code", sa.Integer(), nullable=True))
    op.add_column("audit_log", sa.Column("api_response_json", sa.JSON(), nullable=True))

    op.execute(sa.text("UPDATE audit_log SET action_type = event_type WHERE action_type IS NULL"))
    op.execute(sa.text("UPDATE audit_log SET actor_type = 'user' WHERE actor_type IS NULL"))
    op.alter_column("audit_log", "action_type", nullable=False)
    op.alter_column("audit_log", "actor_type", nullable=False)

    # ── 5. stores ─────────────────────────────────────────────────────────────
    op.create_table(
        "stores",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("org_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("shopify_store_id", sa.String(255), nullable=False),
        sa.Column("access_token_enc", sa.Text(), nullable=False),
        sa.Column("access_token_iv", sa.String(64), nullable=False),
        sa.Column("region", sa.String(32), nullable=True),
        sa.Column("plan", sa.String(128), nullable=True),
        sa.Column("sync_status", _enum_type("sync_status"), nullable=False, server_default="pending"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("initial_sync_days", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "shopify_store_id", name="uq_stores_org_shopify_id"),
    )

    # ── 6. ad_accounts ────────────────────────────────────────────────────────
    op.create_table(
        "ad_accounts",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("org_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("platform", _enum_type("ad_platform"), nullable=False),
        sa.Column("account_id", sa.String(128), nullable=False),
        sa.Column("account_name", sa.String(255), nullable=True),
        sa.Column("access_token_enc", sa.Text(), nullable=False),
        sa.Column("access_token_iv", sa.String(64), nullable=False),
        sa.Column("refresh_token_enc", sa.Text(), nullable=True),
        sa.Column("refresh_token_iv", sa.String(64), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("sync_status", _enum_type("sync_status"), nullable=False, server_default="pending"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "platform", "account_id", name="uq_ad_accounts_org_platform_account"),
    )

    # ── 7. campaigns ──────────────────────────────────────────────────────────
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("org_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("ad_account_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("platform_campaign_id", sa.String(128), nullable=False),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("status", _enum_type("ad_status"), nullable=False, server_default="unknown"),
        sa.Column("objective", sa.String(128), nullable=True),
        sa.Column("daily_budget_cents", sa.BigInteger(), nullable=True),
        sa.Column("lifetime_budget_cents", sa.BigInteger(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["ad_account_id"], ["ad_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ad_account_id", "platform_campaign_id", name="uq_campaigns_account_platform_id"),
    )

    # ── 8. ad_sets ────────────────────────────────────────────────────────────
    op.create_table(
        "ad_sets",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("org_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("campaign_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("platform_adset_id", sa.String(128), nullable=False),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("status", _enum_type("ad_status"), nullable=False, server_default="unknown"),
        sa.Column("daily_budget_cents", sa.BigInteger(), nullable=True),
        sa.Column("targeting_summary_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "platform_adset_id", name="uq_adsets_campaign_platform_id"),
    )

    # ── 9. ad_insights ────────────────────────────────────────────────────────
    op.create_table(
        "ad_insights",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("org_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("adset_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("spend_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("conversion_value_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("impressions", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("clicks", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("reach", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("conversions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cpm", sa.Numeric(18, 6), nullable=True),
        sa.Column("cpc", sa.Numeric(18, 6), nullable=True),
        sa.Column("ctr", sa.Numeric(10, 6), nullable=True),
        sa.ForeignKeyConstraint(["adset_id"], ["ad_sets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("adset_id", "date", name="uq_ad_insights_adset_date"),
    )

    # ── 10. ads ───────────────────────────────────────────────────────────────
    op.create_table(
        "ads",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("org_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("adset_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("platform_ad_id", sa.String(128), nullable=False),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("status", _enum_type("ad_status"), nullable=False, server_default="unknown"),
        sa.Column("creative_thumbnail_url", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["adset_id"], ["ad_sets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("adset_id", "platform_ad_id", name="uq_ads_adset_platform_id"),
    )

    # ── 11. orders ────────────────────────────────────────────────────────────
    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("org_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("store_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("shopify_order_id", sa.String(64), nullable=False),
        sa.Column("shopify_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("total_discounts_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("customer_id", sa.String(64), nullable=True),
        sa.Column("financial_status", sa.String(64), nullable=True),
        sa.Column("fulfillment_status", sa.String(64), nullable=True),
        sa.Column("utm_source", sa.String(128), nullable=True),
        sa.Column("utm_medium", sa.String(128), nullable=True),
        sa.Column("utm_campaign", sa.String(255), nullable=True),
        sa.Column("fbclid", sa.String(255), nullable=True),
        sa.Column("gclid", sa.String(255), nullable=True),
        sa.Column("ttclid", sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("store_id", "shopify_order_id", name="uq_orders_store_shopify_id"),
    )

    # ── 12. line_items ───────────────────────────────────────────────────────
    op.create_table(
        "line_items",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("org_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("order_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("shopify_line_item_id", sa.String(64), nullable=False),
        sa.Column("product_id", sa.String(64), nullable=True),
        sa.Column("variant_id", sa.String(64), nullable=True),
        sa.Column("sku", sa.String(255), nullable=True),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price_cents", sa.BigInteger(), nullable=False),
        sa.Column("unit_discount_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("unit_cogs_cents", sa.BigInteger(), nullable=True),
        sa.Column("unit_cogs_source", _enum_type("cogs_source"), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", "shopify_line_item_id", name="uq_line_items_order_shopify_id"),
    )

    # ── 13. returns ──────────────────────────────────────────────────────────
    op.create_table(
        "returns",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("org_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("order_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("line_item_id", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("shopify_refund_id", sa.String(64), nullable=False),
        sa.Column("refund_amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("quantity_returned", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("reason_category", _enum_type("return_reason_category"), nullable=True),
        sa.Column("is_fulfillment_fault", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(["line_item_id"], ["line_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", "shopify_refund_id", name="uq_returns_order_shopify_id"),
    )

    # ── 14. automation_rules ─────────────────────────────────────────────────
    op.create_table(
        "automation_rules",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("org_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("scope", _enum_type("rule_scope"), nullable=False, server_default="adset"),
        sa.Column("conditions_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("action_type", _enum_type("rule_action_type"), nullable=False),
        sa.Column("action_params_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("guardrails_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_by", sa.Uuid(as_uuid=False), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 15. rule_executions ──────────────────────────────────────────────────
    op.create_table(
        "rule_executions",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("org_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("rule_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entities_evaluated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("entities_triggered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("entities_blocked_by_guardrail", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("action_queued", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("idempotency_state_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rule_id"], ["automation_rules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 16. attributed_orders ────────────────────────────────────────────────
    op.create_table(
        "attributed_orders",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("org_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("order_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("adset_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("attribution_tier", sa.Integer(), nullable=False),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("attribution_method", _enum_type("attribution_method"), nullable=False),
        sa.Column("matched_click_id", sa.String(512), nullable=True),
        sa.Column("attributed_revenue_cents", sa.BigInteger(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["adset_id"], ["ad_sets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", "adset_id", name="uq_attributed_orders_order_adset"),
    )

    # ── 17. sku_return_rates ─────────────────────────────────────────────────
    op.create_table(
        "sku_return_rates",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("org_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("sku", sa.String(255), nullable=False),
        sa.Column("trailing_90d_rate", sa.Numeric(6, 5), nullable=True),
        sa.Column("trailing_180d_rate", sa.Numeric(6, 5), nullable=True),
        sa.Column("manual_override_rate", sa.Numeric(6, 5), nullable=True),
        sa.Column("last_computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "sku", name="uq_sku_return_rates_org_sku"),
    )

    # ── 18. profit_metrics ───────────────────────────────────────────────────
    op.create_table(
        "profit_metrics",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("org_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("adset_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("window_type", _enum_type("window_type"), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("spend_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("attributed_revenue_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("attributed_cogs_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("estimated_returns_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("platform_fees_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("net_profit_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("net_profit_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("true_roas", sa.Numeric(10, 4), nullable=True),
        sa.Column("order_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attribution_coverage_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["adset_id"], ["ad_sets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("adset_id", "window_type", "window_start", "window_end", name="uq_profit_metrics_adset_window"),
    )

    # ── 19. cogs_settings ────────────────────────────────────────────────────
    op.create_table(
        "cogs_settings",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("org_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("scope", _enum_type("cogs_scope"), nullable=False),
        sa.Column("scope_value", sa.String(255), nullable=False),
        sa.Column("cogs_type", _enum_type("cogs_type"), nullable=False),
        sa.Column("cogs_value_cents", sa.BigInteger(), nullable=True),
        sa.Column("cogs_value_pct", sa.Numeric(6, 5), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("source", _enum_type("cogs_data_source"), nullable=False, server_default="manual"),
        sa.Column("updated_by", sa.Uuid(as_uuid=False), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "scope", "scope_value", name="uq_cogs_settings_org_scope_value"),
    )

    # ── 20. notifications ────────────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("org_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("trigger_type", sa.String(120), nullable=False),
        sa.Column("channel", _enum_type("notification_channel"), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_status", _enum_type("delivery_status"), nullable=False, server_default="pending"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
        sa.Column("source_rule_id", sa.Uuid(as_uuid=False), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_rule_id"], ["automation_rules.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_notifications_idempotency_key"),
    )

    # ── 21. Indexes ──────────────────────────────────────────────────────────
    op.create_index("ix_audit_log_rule_id", "audit_log", ["rule_id"])
    op.create_index("ix_stores_org_id", "stores", ["org_id"])
    op.create_index("ix_ad_accounts_org_id", "ad_accounts", ["org_id"])
    op.create_index("ix_ad_accounts_platform", "ad_accounts", ["platform"])
    op.create_index("ix_campaigns_org_id", "campaigns", ["org_id"])
    op.create_index("ix_campaigns_ad_account_id", "campaigns", ["ad_account_id"])
    op.create_index("ix_ad_sets_org_id", "ad_sets", ["org_id"])
    op.create_index("ix_ad_sets_campaign_id", "ad_sets", ["campaign_id"])
    op.create_index("ix_ad_insights_org_id", "ad_insights", ["org_id"])
    op.create_index("ix_ad_insights_adset_date", "ad_insights", ["adset_id", "date"])
    op.create_index("ix_ads_org_id", "ads", ["org_id"])
    op.create_index("ix_ads_adset_id", "ads", ["adset_id"])
    op.create_index("ix_orders_org_id", "orders", ["org_id"])
    op.create_index("ix_orders_store_id", "orders", ["store_id"])
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"])
    op.create_index("ix_orders_shopify_created_at", "orders", ["shopify_created_at"])
    op.create_index("ix_orders_fbclid", "orders", ["fbclid"])
    op.create_index("ix_orders_gclid", "orders", ["gclid"])
    op.create_index("ix_orders_ttclid", "orders", ["ttclid"])
    op.create_index("ix_orders_store_created_at", "orders", ["store_id", "shopify_created_at"])
    op.create_index("ix_line_items_org_id", "line_items", ["org_id"])
    op.create_index("ix_line_items_order_id", "line_items", ["order_id"])
    op.create_index("ix_line_items_product_id", "line_items", ["product_id"])
    op.create_index("ix_line_items_sku", "line_items", ["sku"])
    op.create_index("ix_returns_org_id", "returns", ["org_id"])
    op.create_index("ix_returns_order_id", "returns", ["order_id"])
    op.create_index("ix_returns_line_item_id", "returns", ["line_item_id"])
    op.create_index("ix_automation_rules_org_id", "automation_rules", ["org_id"])
    op.create_index("ix_automation_rules_created_by", "automation_rules", ["created_by"])
    op.create_index("ix_automation_rules_org_active_platform", "automation_rules", ["org_id", "is_active", "platform"])
    op.create_index("ix_rule_executions_org_id", "rule_executions", ["org_id"])
    op.create_index("ix_rule_executions_rule_id", "rule_executions", ["rule_id"])
    op.create_index("ix_rule_executions_rule_evaluated_at", "rule_executions", ["rule_id", "evaluated_at"])
    op.create_index("ix_attributed_orders_org_id", "attributed_orders", ["org_id"])
    op.create_index("ix_attributed_orders_order_id", "attributed_orders", ["order_id"])
    op.create_index("ix_attributed_orders_adset_id", "attributed_orders", ["adset_id"])
    op.create_index("ix_attributed_orders_adset_window", "attributed_orders", ["adset_id", "window_start", "window_end"])
    op.create_index("ix_sku_return_rates_org_id", "sku_return_rates", ["org_id"])
    op.create_index("ix_sku_return_rates_sku", "sku_return_rates", ["sku"])
    op.create_index("ix_profit_metrics_org_id", "profit_metrics", ["org_id"])
    op.create_index("ix_profit_metrics_adset_id", "profit_metrics", ["adset_id"])
    op.create_index("ix_profit_metrics_adset_window", "profit_metrics", ["adset_id", "window_type", "window_start", "window_end"])
    op.create_index("ix_cogs_settings_org_id", "cogs_settings", ["org_id"])
    op.create_index("ix_cogs_settings_org_scope", "cogs_settings", ["org_id", "scope"])
    op.create_index("ix_notifications_org_id", "notifications", ["org_id"])
    op.create_index("ix_notifications_trigger_type", "notifications", ["trigger_type"])
    op.create_index("ix_notifications_channel", "notifications", ["channel"])
    op.create_index("ix_notifications_delivery_status", "notifications", ["delivery_status"])
    op.create_index("ix_notifications_source_rule_id", "notifications", ["source_rule_id"])
    op.create_index("ix_notifications_idempotency_key", "notifications", ["idempotency_key"])

    # Final Audit Log re-link
    op.create_foreign_key(
        "fk_audit_log_rule_id",
        "audit_log",
        "automation_rules",
        ["rule_id"],
        ["id"],
        ondelete="SET NULL",
    )


# ---------------------------------------------------------------------------
# downgrade
# ---------------------------------------------------------------------------
def downgrade() -> None:
    # Drop all tables and then types
    tables = [
        "notifications", "cogs_settings", "profit_metrics", "sku_return_rates",
        "attributed_orders", "rule_executions", "automation_rules", "returns",
        "line_items", "orders", "ads", "ad_insights", "ad_sets", "campaigns",
        "ad_accounts", "stores"
    ]
    for t in tables:
        op.drop_table(t)

    for name in ENUM_NAMES:
        op.execute(sa.text(f"DROP TYPE IF EXISTS {name} CASCADE"))
