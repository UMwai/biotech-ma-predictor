"""Initial schema with all tables

Revision ID: 001
Revises:
Create Date: 2025-12-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all initial tables."""

    # Create companies table
    op.create_table(
        'companies',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ticker', sa.String(length=10), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('market_cap_usd', sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column('cash_position_usd', sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column('quarterly_burn_rate_usd', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('total_debt_usd', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('runway_quarters', sa.Float(), nullable=True),
        sa.Column('enterprise_value_usd', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('therapeutic_areas', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('founded_year', sa.Integer(), nullable=True),
        sa.Column('employee_count', sa.Integer(), nullable=True),
        sa.Column('headquarters_location', sa.String(length=255), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=True),
        sa.Column('is_cash_constrained', sa.Boolean(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('last_data_refresh', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_companies_cash_constrained', 'companies', ['is_cash_constrained'])
    op.create_index('idx_companies_deleted', 'companies', ['deleted_at'])
    op.create_index('idx_companies_market_cap', 'companies', ['market_cap_usd'])
    op.create_index('idx_companies_therapeutic_areas', 'companies', ['therapeutic_areas'], postgresql_using='gin')
    op.create_index(op.f('ix_companies_ticker'), 'companies', ['ticker'], unique=True)

    # Create drug_candidates table
    op.create_table(
        'drug_candidates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('phase', sa.String(length=50), nullable=False),
        sa.Column('indication', sa.Text(), nullable=False),
        sa.Column('mechanism', sa.Text(), nullable=False),
        sa.Column('therapeutic_area', sa.String(length=50), nullable=False),
        sa.Column('patent_expiry', sa.DateTime(timezone=True), nullable=True),
        sa.Column('patent_years_remaining', sa.Float(), nullable=True),
        sa.Column('orphan_designation', sa.Boolean(), nullable=True),
        sa.Column('fast_track', sa.Boolean(), nullable=True),
        sa.Column('breakthrough_therapy', sa.Boolean(), nullable=True),
        sa.Column('next_milestone', sa.Text(), nullable=True),
        sa.Column('next_milestone_date', sa.String(length=50), nullable=True),
        sa.Column('phase_score', sa.Float(), nullable=True),
        sa.Column('competitive_landscape_score', sa.Float(), nullable=True),
        sa.Column('market_potential_usd', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('additional_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_drug_candidates_company_phase', 'drug_candidates', ['company_id', 'phase'])
    op.create_index('idx_drug_candidates_deleted', 'drug_candidates', ['deleted_at'])
    op.create_index('idx_drug_candidates_therapeutic_area', 'drug_candidates', ['therapeutic_area'])
    op.create_index(op.f('ix_drug_candidates_company_id'), 'drug_candidates', ['company_id'])
    op.create_index(op.f('ix_drug_candidates_phase'), 'drug_candidates', ['phase'])
    op.create_index(op.f('ix_drug_candidates_therapeutic_area'), 'drug_candidates', ['therapeutic_area'])

    # Create signals table
    op.create_table(
        'signals',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('signal_type', sa.String(length=50), nullable=False),
        sa.Column('event_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('signal_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ma_impact_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_signals_company_date', 'signals', ['company_id', 'event_date'])
    op.create_index('idx_signals_company_type', 'signals', ['company_id', 'signal_type'])
    op.create_index('idx_signals_data', 'signals', ['signal_data'], postgresql_using='gin')
    op.create_index('idx_signals_event_date', 'signals', ['event_date'])
    op.create_index('idx_signals_severity', 'signals', ['severity'])
    op.create_index(op.f('ix_signals_company_id'), 'signals', ['company_id'])
    op.create_index(op.f('ix_signals_event_date'), 'signals', ['event_date'])
    op.create_index(op.f('ix_signals_severity'), 'signals', ['severity'])
    op.create_index(op.f('ix_signals_signal_type'), 'signals', ['signal_type'])

    # Create ma_scores table
    op.create_table(
        'ma_scores',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('score_date', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('score_version', sa.String(length=20), nullable=True),
        sa.Column('total_score', sa.Float(), nullable=False),
        sa.Column('percentile_rank', sa.Float(), nullable=True),
        sa.Column('pipeline_score', sa.Float(), nullable=True),
        sa.Column('patent_score', sa.Float(), nullable=True),
        sa.Column('financial_score', sa.Float(), nullable=True),
        sa.Column('insider_score', sa.Float(), nullable=True),
        sa.Column('strategic_fit_score', sa.Float(), nullable=True),
        sa.Column('regulatory_score', sa.Float(), nullable=True),
        sa.Column('score_change_30d', sa.Float(), nullable=True),
        sa.Column('score_change_90d', sa.Float(), nullable=True),
        sa.Column('key_drivers', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('risk_factors', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'score_date', name='uq_company_score_date')
    )
    op.create_index('idx_ma_scores_company_date', 'ma_scores', ['company_id', 'score_date'])
    op.create_index('idx_ma_scores_date', 'ma_scores', ['score_date'])
    op.create_index('idx_ma_scores_total_score', 'ma_scores', ['total_score'])
    op.create_index(op.f('ix_ma_scores_company_id'), 'ma_scores', ['company_id'])
    op.create_index(op.f('ix_ma_scores_score_date'), 'ma_scores', ['score_date'])
    op.create_index(op.f('ix_ma_scores_total_score'), 'ma_scores', ['total_score'])

    # Create acquirer_matches table
    op.create_table(
        'acquirer_matches',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('acquirer_ticker', sa.String(length=10), nullable=False),
        sa.Column('acquirer_name', sa.String(length=255), nullable=False),
        sa.Column('match_date', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('strategic_fit_score', sa.Float(), nullable=False),
        sa.Column('therapeutic_overlap_score', sa.Float(), nullable=True),
        sa.Column('geographic_fit_score', sa.Float(), nullable=True),
        sa.Column('financial_capacity_score', sa.Float(), nullable=True),
        sa.Column('historical_ma_score', sa.Float(), nullable=True),
        sa.Column('synergy_rationale', sa.Text(), nullable=True),
        sa.Column('key_assets_of_interest', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('estimated_valuation_range_usd', sa.String(length=100), nullable=True),
        sa.Column('match_rank', sa.Integer(), nullable=True),
        sa.Column('is_top_match', sa.Boolean(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['target_company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_acquirer_matches_acquirer', 'acquirer_matches', ['acquirer_ticker'])
    op.create_index('idx_acquirer_matches_fit_score', 'acquirer_matches', ['strategic_fit_score'])
    op.create_index('idx_acquirer_matches_target', 'acquirer_matches', ['target_company_id'])
    op.create_index('idx_acquirer_matches_top', 'acquirer_matches', ['is_top_match'])
    op.create_index(op.f('ix_acquirer_matches_acquirer_ticker'), 'acquirer_matches', ['acquirer_ticker'])
    op.create_index(op.f('ix_acquirer_matches_target_company_id'), 'acquirer_matches', ['target_company_id'])

    # Create reports table
    op.create_table(
        'reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('report_type', sa.String(length=50), nullable=False),
        sa.Column('report_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('format', sa.String(length=20), nullable=True),
        sa.Column('s3_key', sa.String(length=500), nullable=True),
        sa.Column('s3_bucket', sa.String(length=255), nullable=True),
        sa.Column('local_path', sa.String(length=500), nullable=True),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('recipients', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivery_status', sa.String(length=20), nullable=True),
        sa.Column('companies_included', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('key_findings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_reports_date', 'reports', ['report_date'])
    op.create_index('idx_reports_deleted', 'reports', ['deleted_at'])
    op.create_index('idx_reports_type', 'reports', ['report_type'])
    op.create_index(op.f('ix_reports_report_date'), 'reports', ['report_date'])
    op.create_index(op.f('ix_reports_report_type'), 'reports', ['report_type'])

    # Create alerts table
    op.create_table(
        'alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('alert_type', sa.String(length=50), nullable=False),
        sa.Column('condition', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('threshold_value', sa.Float(), nullable=True),
        sa.Column('company_tickers', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('signal_types', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('last_triggered', sa.DateTime(timezone=True), nullable=True),
        sa.Column('trigger_count', sa.Integer(), nullable=True),
        sa.Column('notification_channels', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('recipients', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_alerts_active', 'alerts', ['is_active'])
    op.create_index('idx_alerts_deleted', 'alerts', ['deleted_at'])
    op.create_index('idx_alerts_type', 'alerts', ['alert_type'])
    op.create_index(op.f('ix_alerts_alert_type'), 'alerts', ['alert_type'])
    op.create_index(op.f('ix_alerts_is_active'), 'alerts', ['is_active'])

    # Create webhooks table
    op.create_table(
        'webhooks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('url', sa.String(length=2048), nullable=False),
        sa.Column('secret', sa.String(length=255), nullable=True),
        sa.Column('event_types', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('company_tickers', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('min_score', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('last_triggered', sa.DateTime(timezone=True), nullable=True),
        sa.Column('success_count', sa.Integer(), nullable=True),
        sa.Column('failure_count', sa.Integer(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('retry_policy', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('timeout_seconds', sa.Integer(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_webhooks_active', 'webhooks', ['is_active'])
    op.create_index('idx_webhooks_deleted', 'webhooks', ['deleted_at'])
    op.create_index(op.f('ix_webhooks_is_active'), 'webhooks', ['is_active'])

    # Create clients table
    op.create_table(
        'clients',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_name', sa.String(length=255), nullable=False),
        sa.Column('api_key', sa.String(length=255), nullable=False),
        sa.Column('client_type', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('allowed_endpoints', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('rate_limit_per_hour', sa.Integer(), nullable=True),
        sa.Column('watchlist_tickers', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('notification_preferences', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('custom_thresholds', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('last_access', sa.DateTime(timezone=True), nullable=True),
        sa.Column('request_count', sa.Integer(), nullable=True),
        sa.Column('contact_email', sa.String(length=255), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_clients_active', 'clients', ['is_active'])
    op.create_index('idx_clients_deleted', 'clients', ['deleted_at'])
    op.create_index(op.f('ix_clients_api_key'), 'clients', ['api_key'], unique=True)
    op.create_index(op.f('ix_clients_is_active'), 'clients', ['is_active'])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('clients')
    op.drop_table('webhooks')
    op.drop_table('alerts')
    op.drop_table('reports')
    op.drop_table('acquirer_matches')
    op.drop_table('ma_scores')
    op.drop_table('signals')
    op.drop_table('drug_candidates')
    op.drop_table('companies')
