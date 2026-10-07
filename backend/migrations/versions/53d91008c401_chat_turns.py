"""Private Ask LifeLens history."""
from alembic import op
import sqlalchemy as sa
revision = '53d91008c401'
down_revision = '42c80907b301'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('chat_turns',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question', sa.String(1000), nullable=False),
        sa.Column('answer', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index('ix_chat_turns_user_id', 'chat_turns', ['user_id'])

def downgrade():
    op.drop_table('chat_turns')
