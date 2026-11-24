"""them CV PDF cho sinh vien

Revision ID: b7c1e2a4d9f0
Revises: 9f6d62bc3224
Create Date: 2026-11-24 10:30:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'b7c1e2a4d9f0'
down_revision = '9f6d62bc3224'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('student_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cv_filename', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('cv_original_name', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('cv_uploaded_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('student_profiles', schema=None) as batch_op:
        batch_op.drop_column('cv_uploaded_at')
        batch_op.drop_column('cv_original_name')
        batch_op.drop_column('cv_filename')
