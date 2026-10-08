"""create_normalization_and_classification_tables

Revision ID: 9fd95c3b7d85
Revises: ea57c8cf5fc2
Create Date: 2026-10-07 15:02:29.727911

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '9fd95c3b7d85'
down_revision: Union[str, None] = 'ea57c8cf5fc2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('dim_product_alias',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('alias', sa.String(length=150), nullable=False),
    sa.Column('locale', sa.String(length=20), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['product_id'], ['dim_product.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dim_product_alias_alias'), 'dim_product_alias', ['alias'], unique=True)
    op.create_index(op.f('ix_dim_product_alias_id'), 'dim_product_alias', ['id'], unique=False)
    op.create_index(op.f('ix_dim_product_alias_product_id'), 'dim_product_alias', ['product_id'], unique=False)

    op.create_table('fact_normalized_comment',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('raw_comment_id', sa.Integer(), nullable=False),
    sa.Column('classification', sa.String(length=50), nullable=False),
    sa.Column('extracted_price', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('currency', sa.String(length=20), nullable=True),
    sa.Column('ai_confidence', sa.Float(), nullable=True),
    sa.Column('normalized_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['raw_comment_id'], ['fact_raw_comment.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fact_normalized_comment_id'), 'fact_normalized_comment', ['id'], unique=False)
    op.create_index(op.f('ix_fact_normalized_comment_raw_comment_id'), 'fact_normalized_comment', ['raw_comment_id'], unique=True)

    op.create_table('fact_normalized_listing',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('raw_listing_id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=True),
    sa.Column('variant_id', sa.Integer(), nullable=True),
    sa.Column('condition_id', sa.Integer(), nullable=True),
    sa.Column('market_segment_id', sa.Integer(), nullable=True),
    sa.Column('normalized_price', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('currency', sa.String(length=20), nullable=True),
    sa.Column('price_valid', sa.Boolean(), nullable=True),
    sa.Column('price_validity_reason', sa.String(length=100), nullable=True),
    sa.Column('normalized_attributes', sa.JSON(), nullable=True),
    sa.Column('classification', sa.String(length=50), nullable=False),
    sa.Column('ai_confidence', sa.Float(), nullable=True),
    sa.Column('pipeline_stage', sa.String(length=50), nullable=True),
    sa.Column('normalization_version', sa.String(length=50), nullable=True),
    sa.Column('normalized_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('manual_review_required', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['condition_id'], ['dim_condition.id'], ),
    sa.ForeignKeyConstraint(['market_segment_id'], ['dim_market_segment.id'], ),
    sa.ForeignKeyConstraint(['product_id'], ['dim_product.id'], ),
    sa.ForeignKeyConstraint(['raw_listing_id'], ['fact_raw_listing.id'], ),
    sa.ForeignKeyConstraint(['variant_id'], ['dim_variant.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fact_normalized_listing_condition_id'), 'fact_normalized_listing', ['condition_id'], unique=False)
    op.create_index(op.f('ix_fact_normalized_listing_id'), 'fact_normalized_listing', ['id'], unique=False)
    op.create_index(op.f('ix_fact_normalized_listing_manual_review_required'), 'fact_normalized_listing', ['manual_review_required'], unique=False)
    op.create_index(op.f('ix_fact_normalized_listing_market_segment_id'), 'fact_normalized_listing', ['market_segment_id'], unique=False)
    op.create_index(op.f('ix_fact_normalized_listing_product_id'), 'fact_normalized_listing', ['product_id'], unique=False)
    op.create_index(op.f('ix_fact_normalized_listing_raw_listing_id'), 'fact_normalized_listing', ['raw_listing_id'], unique=True)
    op.create_index(op.f('ix_fact_normalized_listing_variant_id'), 'fact_normalized_listing', ['variant_id'], unique=False)

    op.create_table('normalization_audit_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('normalized_listing_id', sa.Integer(), nullable=False),
    sa.Column('field_name', sa.String(length=100), nullable=False),
    sa.Column('old_value', sa.Text(), nullable=True),
    sa.Column('new_value', sa.Text(), nullable=True),
    sa.Column('corrected_by', sa.String(length=100), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['normalized_listing_id'], ['fact_normalized_listing.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_normalization_audit_log_id'), 'normalization_audit_log', ['id'], unique=False)
    op.create_index(op.f('ix_normalization_audit_log_normalized_listing_id'), 'normalization_audit_log', ['normalized_listing_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_normalization_audit_log_normalized_listing_id'), table_name='normalization_audit_log')
    op.drop_index(op.f('ix_normalization_audit_log_id'), table_name='normalization_audit_log')
    op.drop_table('normalization_audit_log')

    op.drop_index(op.f('ix_fact_normalized_listing_variant_id'), table_name='fact_normalized_listing')
    op.drop_index(op.f('ix_fact_normalized_listing_raw_listing_id'), table_name='fact_normalized_listing')
    op.drop_index(op.f('ix_fact_normalized_listing_product_id'), table_name='fact_normalized_listing')
    op.drop_index(op.f('ix_fact_normalized_listing_market_segment_id'), table_name='fact_normalized_listing')
    op.drop_index(op.f('ix_fact_normalized_listing_manual_review_required'), table_name='fact_normalized_listing')
    op.drop_index(op.f('ix_fact_normalized_listing_id'), table_name='fact_normalized_listing')
    op.drop_index(op.f('ix_fact_normalized_listing_condition_id'), table_name='fact_normalized_listing')
    op.drop_table('fact_normalized_listing')

    op.drop_index(op.f('ix_fact_normalized_comment_raw_comment_id'), table_name='fact_normalized_comment')
    op.drop_index(op.f('ix_fact_normalized_comment_id'), table_name='fact_normalized_comment')
    op.drop_table('fact_normalized_comment')

    op.drop_index(op.f('ix_dim_product_alias_product_id'), table_name='dim_product_alias')
    op.drop_index(op.f('ix_dim_product_alias_id'), table_name='dim_product_alias')
    op.drop_index(op.f('ix_dim_product_alias_alias'), table_name='dim_product_alias')
    op.drop_table('dim_product_alias')

