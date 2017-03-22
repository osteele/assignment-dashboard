"""add assignment.due_date

Revision ID: 2d0ed25dcf60
Revises: be985ed5f992
Create Date: 2017-03-04 12:56:01.491002

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '2d0ed25dcf60'
down_revision = 'be985ed5f992'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('assignment', sa.Column('due_date', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('assignment', 'due_date')
