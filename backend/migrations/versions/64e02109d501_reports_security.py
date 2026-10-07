"""Private report snapshots and shared rate limiting."""
from alembic import op
import sqlalchemy as sa
revision = '64e02109d501'
down_revision = '53d91008c401'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('financial_reports',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('month',sa.Date(),nullable=False),
        sa.Column('data',sa.JSON(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index('ix_financial_reports_user_id','financial_reports',['user_id'])
    op.create_table('rate_limit_buckets',sa.Column('key',sa.String(64),primary_key=True),
        sa.Column('count',sa.Integer(),nullable=False),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_rate_limit_buckets_expires_at','rate_limit_buckets',['expires_at'])

def downgrade():
    op.drop_table('rate_limit_buckets')
    op.drop_table('financial_reports')
