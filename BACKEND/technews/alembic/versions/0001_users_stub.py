"""Dev-only: create a minimal users table if (and only if) none exists. Delete if you already have one.

Revision ID: 0001
"""
import sqlalchemy as sa
from alembic import op

revision, down_revision = "0001", None


def upgrade():
    if not sa.inspect(op.get_bind()).has_table("users"):
        op.create_table("users", sa.Column("id", sa.Integer, primary_key=True), sa.Column("email", sa.String(255), unique=True, nullable=False),
                        sa.Column("display_name", sa.String(80)), sa.Column("role", sa.String(20), nullable=False, server_default="user"),
                        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()))


def downgrade():
    pass
