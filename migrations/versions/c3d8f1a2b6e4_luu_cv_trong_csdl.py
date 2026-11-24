"""luu noi dung CV PDF trong CSDL (CV_STORAGE=db)

Revision ID: c3d8f1a2b6e4
Revises: b7c1e2a4d9f0
Create Date: 2026-11-24 17:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'c3d8f1a2b6e4'
down_revision = 'b7c1e2a4d9f0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('student_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cv_data', sa.LargeBinary(), nullable=True))


def downgrade():
    with op.batch_alter_table('student_profiles', schema=None) as batch_op:
        batch_op.drop_column('cv_data')
