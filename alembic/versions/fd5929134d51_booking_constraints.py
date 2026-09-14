"""booking constraints

Revision ID: fd5929134d51
Revises: 1bf93eb04d91
Create Date: 2026-09-14 21:54:48.976242

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fd5929134d51'
down_revision: Union[str, Sequence[str], None] = '1bf93eb04d91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint("end_after_start", "Booking", "end_time > start_time")
    op.execute('CREATE EXTENSION IF NOT EXISTS btree_gist')
    op.execute('''
        ALTER TABLE "Booking"
        ADD CONSTRAINT no_overlapping_bookings
        EXCLUDE USING gist (
            facility_id WITH =,
            tstzrange(start_time, end_time) WITH &&
        ) WHERE (status = 'confirmed')
    ''')

def downgrade():
    op.drop_constraint("no_overlapping_bookings", "Booking", type_="exclude")
    op.drop_constraint("end_after_start", "Booking", type_="check") 