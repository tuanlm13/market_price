"""create_raw_market_collection_tables

Revision ID: ea57c8cf5fc2
Revises: 8a74f5fad03b
Create Date: 2026-10-07 14:45:22.636815

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ea57c8cf5fc2'
down_revision: Union[str, None] = '8a74f5fad03b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('collector_health',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_code', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('last_start', sa.DateTime(), nullable=True),
        sa.Column('last_success', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('items_scanned', sa.Integer(), nullable=True),
        sa.Column('items_new', sa.Integer(), nullable=True),
        sa.Column('auth_status', sa.String(length=50), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_collector_health_id'), 'collector_health', ['id'], unique=False)
    op.create_index(op.f('ix_collector_health_source_code'), 'collector_health', ['source_code'], unique=True)

    op.create_table('fact_raw_listing',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('source_listing_id', sa.String(length=255), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('raw_title', sa.Text(), nullable=False),
        sa.Column('raw_description', sa.Text(), nullable=True),
        sa.Column('raw_price_text', sa.String(length=100), nullable=True),
        sa.Column('raw_currency', sa.String(length=20), nullable=True),
        sa.Column('seller_name_raw', sa.String(length=255), nullable=True),
        sa.Column('seller_id_raw', sa.String(length=255), nullable=True),
        sa.Column('location_raw', sa.String(length=255), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('raw_metadata', sa.JSON(), nullable=True),
        sa.Column('crawl_status', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['source_id'], ['dim_source.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_id', 'source_listing_id', name='uq_fact_raw_listing_source_item')
    )
    op.create_index(op.f('ix_fact_raw_listing_id'), 'fact_raw_listing', ['id'], unique=False)
    op.create_index(op.f('ix_fact_raw_listing_source_id'), 'fact_raw_listing', ['source_id'], unique=False)
    op.create_index(op.f('ix_fact_raw_listing_source_listing_id'), 'fact_raw_listing', ['source_listing_id'], unique=False)

    op.create_table('fact_listing_price_snapshot',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('listing_id', sa.Integer(), nullable=False),
        sa.Column('price_raw', sa.String(length=100), nullable=False),
        sa.Column('currency', sa.String(length=20), nullable=True),
        sa.Column('captured_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['listing_id'], ['fact_raw_listing.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fact_listing_price_snapshot_captured_at'), 'fact_listing_price_snapshot', ['captured_at'], unique=False)
    op.create_index(op.f('ix_fact_listing_price_snapshot_id'), 'fact_listing_price_snapshot', ['id'], unique=False)
    op.create_index(op.f('ix_fact_listing_price_snapshot_listing_id'), 'fact_listing_price_snapshot', ['listing_id'], unique=False)

    op.create_table('fact_raw_comment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_comment_id', sa.String(length=255), nullable=False),
        sa.Column('listing_id', sa.Integer(), nullable=False),
        sa.Column('author', sa.String(length=255), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('created_at_source', sa.DateTime(), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['listing_id'], ['fact_raw_listing.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fact_raw_comment_id'), 'fact_raw_comment', ['id'], unique=False)
    op.create_index(op.f('ix_fact_raw_comment_listing_id'), 'fact_raw_comment', ['listing_id'], unique=False)
    op.create_index(op.f('ix_fact_raw_comment_source_comment_id'), 'fact_raw_comment', ['source_comment_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_fact_raw_comment_source_comment_id'), table_name='fact_raw_comment')
    op.drop_index(op.f('ix_fact_raw_comment_listing_id'), table_name='fact_raw_comment')
    op.drop_index(op.f('ix_fact_raw_comment_id'), table_name='fact_raw_comment')
    op.drop_table('fact_raw_comment')

    op.drop_index(op.f('ix_fact_listing_price_snapshot_listing_id'), table_name='fact_listing_price_snapshot')
    op.drop_index(op.f('ix_fact_listing_price_snapshot_id'), table_name='fact_listing_price_snapshot')
    op.drop_index(op.f('ix_fact_listing_price_snapshot_captured_at'), table_name='fact_listing_price_snapshot')
    op.drop_table('fact_listing_price_snapshot')

    op.drop_index(op.f('ix_fact_raw_listing_source_listing_id'), table_name='fact_raw_listing')
    op.drop_index(op.f('ix_fact_raw_listing_source_id'), table_name='fact_raw_listing')
    op.drop_index(op.f('ix_fact_raw_listing_id'), table_name='fact_raw_listing')
    op.drop_table('fact_raw_listing')

    op.drop_index(op.f('ix_collector_health_source_code'), table_name='collector_health')
    op.drop_index(op.f('ix_collector_health_id'), table_name='collector_health')
    op.drop_table('collector_health')
