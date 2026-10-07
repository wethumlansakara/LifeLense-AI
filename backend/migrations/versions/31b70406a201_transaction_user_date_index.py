"""Index user-owned transaction date queries."""
from alembic import op

revision = '31b70406a201'
down_revision = '1e6308cf4a67'
branch_labels = None
depends_on = None

def upgrade():
    op.create_index('ix_transactions_user_date', 'transactions', ['user_id', 'transaction_date'])

def downgrade():
    op.drop_index('ix_transactions_user_date', table_name='transactions')
