"""baseline schema

Revision ID: 1bf93eb04d91
Revises: 
Create Date: 2026-09-14 21:53:00.752277

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1bf93eb04d91'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "Users",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("roll_number", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="student"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_Users_email", "Users", ["email"], unique=True)
    op.create_index("ix_Users_roll_number", "Users", ["roll_number"], unique=True)

    op.create_table(
        "Facility",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("location", sa.String(), nullable=False),
        sa.Column("slot_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("opens_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("closes_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("max_advance_days", sa.Integer(), nullable=False),
        sa.Column("max_active_bookings_per_user", sa.Integer(), nullable=False),
        sa.Column("min_cancellation_notice_hours", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_Facility_name", "Facility", ["name"], unique=True)

    op.create_table(
        "Closure",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("facility_id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("end_time", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["facility_id"], ["Facility.id"]),
    )

    op.create_table(
        "Booking",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("facility_id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("end_time", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="confirmed"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("cancelled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["Users.id"]),
        sa.ForeignKeyConstraint(["facility_id"], ["Facility.id"]),
    )

    op.create_table(
        "RefreshToken",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["Users.id"]),
    )
    op.create_index("ix_RefreshToken_token", "RefreshToken", ["token"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("RefreshToken")
    op.drop_table("Booking")
    op.drop_table("Closure")
    op.drop_table("Facility")
    op.drop_table("Users")
