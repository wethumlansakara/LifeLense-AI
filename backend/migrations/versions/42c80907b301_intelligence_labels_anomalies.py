"""Private category labels and unusual spending records."""
from alembic import op
import sqlalchemy as sa

revision = '42c80907b301'
down_revision = '31b70406a201'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('category_labels', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False), sa.Column('transaction_id', sa.Integer(), sa.ForeignKey('transactions.id', ondelete='CASCADE'), nullable=False, unique=True), sa.Column('category_id', sa.Integer(), sa.ForeignKey('categories.id'), nullable=False), sa.Column('description', sa.String(500), nullable=False), sa.Column('merchant', sa.String(200), nullable=False), sa.Column('normalized_merchant', sa.String(200), nullable=False), sa.Column('text', sa.String(800), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index('ix_category_labels_user_id', 'category_labels', ['user_id'])
    op.create_index('ix_category_labels_normalized_merchant', 'category_labels', ['normalized_merchant'])
    op.create_table('spending_anomalies', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False), sa.Column('transaction_id', sa.Integer(), sa.ForeignKey('transactions.id', ondelete='CASCADE'), nullable=False, unique=True), sa.Column('score', sa.Float(), nullable=False), sa.Column('explanation', sa.String(1000), nullable=False), sa.Column('baseline', sa.Numeric(14, 2), nullable=False), sa.Column('method', sa.String(50), nullable=False), sa.Column('marked_normal', sa.Boolean(), server_default=sa.false(), nullable=False), sa.Column('active', sa.Boolean(), server_default=sa.true(), nullable=False), sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.CheckConstraint('score >= 0 AND score <= 1'))
    op.create_index('ix_spending_anomalies_user_id', 'spending_anomalies', ['user_id'])

def downgrade():
    op.drop_table('spending_anomalies')
    op.drop_table('category_labels')
