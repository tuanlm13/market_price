"""create_deal_appraisal_table

Revision ID: 44142d43fd19
Revises: 9fd95c3b7d85
Create Date: 2026-10-07 15:28:49.764736

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '44142d43fd19'
down_revision: Union[str, None] = '9fd95c3b7d85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('fact_deal_appraisal',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('normalized_listing_id', sa.Integer(), nullable=False),
    sa.Column('decision', sa.String(length=20), nullable=False),
    sa.Column('market_confidence', sa.Integer(), nullable=True),
    sa.Column('liquidity', sa.Integer(), nullable=True),
    sa.Column('asking_price', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('acquisition_cost', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('quick_sell_price', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('expected_profit', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('roi', sa.Float(), nullable=True),
    sa.Column('discount_vs_median', sa.Float(), nullable=True),
    sa.Column('discount_vs_p25', sa.Float(), nullable=True),
    sa.Column('discount_vs_quick_sell', sa.Float(), nullable=True),
    sa.Column('market_position', sa.String(length=50), nullable=True),
    sa.Column('risks', sa.JSON(), nullable=True),
    sa.Column('ai_reasoning', sa.Text(), nullable=True),
    sa.Column('ai_confidence', sa.Float(), nullable=True),
    sa.Column('alert_sent', sa.Boolean(), nullable=True),
    sa.Column('alert_sent_at', sa.DateTime(), nullable=True),
    sa.Column('effective_price_source', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['normalized_listing_id'], ['fact_normalized_listing.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fact_deal_appraisal_alert_sent'), 'fact_deal_appraisal', ['alert_sent'], unique=False)
    op.create_index(op.f('ix_fact_deal_appraisal_decision'), 'fact_deal_appraisal', ['decision'], unique=False)
    op.create_index(op.f('ix_fact_deal_appraisal_id'), 'fact_deal_appraisal', ['id'], unique=False)
    op.create_index(op.f('ix_fact_deal_appraisal_normalized_listing_id'), 'fact_deal_appraisal', ['normalized_listing_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_fact_deal_appraisal_normalized_listing_id'), table_name='fact_deal_appraisal')
    op.drop_index(op.f('ix_fact_deal_appraisal_id'), table_name='fact_deal_appraisal')
    op.drop_index(op.f('ix_fact_deal_appraisal_decision'), table_name='fact_deal_appraisal')
    op.drop_index(op.f('ix_fact_deal_appraisal_alert_sent'), table_name='fact_deal_appraisal')
    op.drop_table('fact_deal_appraisal')
    # ### end Alembic commands ###
