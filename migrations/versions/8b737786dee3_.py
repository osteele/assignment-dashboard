"""add repo.is_active

Revision ID: 8b737786dee3
Revises: 2d0ed25dcf60
Create Date: 2017-03-21 22:19:04.088104

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '8b737786dee3'
down_revision = '2d0ed25dcf60'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('repo', sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False))


def downgrade():
    op.drop_column('repo', 'is_active')
