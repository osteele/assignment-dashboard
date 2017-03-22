"""add organization_users table

Revision ID: be985ed5f992
Revises:
Create Date: 2017-02-28 19:51:48.711414

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'be985ed5f992'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('organization_users',
                    sa.Column('organization_id', sa.Integer(), nullable=False),
                    sa.Column('user_id', sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(
                        ['organization_id'], ['user.id'], ),
                    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
                    sa.PrimaryKeyConstraint('organization_id', 'user_id')
                    )
    op.add_column('user', sa.Column('gh_type', sa.Enum(
        'Organization', 'User'), nullable=True))


def downgrade():
    op.drop_column('user', 'gh_type')
    op.drop_table('organization_users')
