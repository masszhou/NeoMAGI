"""Add principal_id + visibility to memory tables (P2-M3b).

Adds principal_id and visibility columns to memory_source_ledger and
memory_entries tables for identity-aware visibility policy.

Revision ID: a1c2d3e4f5g6
Revises: f3a4b5c6d7e8
Create Date: 2026-04-12
"""

import sqlalchemy as sa

from alembic import op
from src.constants import DB_SCHEMA

revision = "a1c2d3e4f5g6"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- memory_source_ledger: add principal_id + visibility ---
    op.add_column(
        "memory_source_ledger",
        sa.Column("principal_id", sa.String(36), nullable=True),
        schema=DB_SCHEMA,
    )
    op.add_column(
        "memory_source_ledger",
        sa.Column(
            "visibility",
            sa.String(32),
            nullable=False,
            server_default="private_to_principal",
        ),
        schema=DB_SCHEMA,
    )
    # CHECK constraint on visibility values
    op.execute(
        f"ALTER TABLE {DB_SCHEMA}.memory_source_ledger "
        f"ADD CONSTRAINT ck_memory_source_ledger_visibility "
        f"CHECK (visibility IN ('private_to_principal', 'shareable_summary', 'shared_in_space'))"
    )
    op.create_index(
        "idx_memory_source_ledger_principal",
        "memory_source_ledger",
        ["principal_id"],
        schema=DB_SCHEMA,
    )

    # --- memory_entries: add principal_id + visibility ---
    op.add_column(
        "memory_entries",
        sa.Column("principal_id", sa.String(36), nullable=True),
        schema=DB_SCHEMA,
    )
    op.add_column(
        "memory_entries",
        sa.Column(
            "visibility",
            sa.String(32),
            nullable=False,
            server_default="private_to_principal",
        ),
        schema=DB_SCHEMA,
    )
    op.create_index(
        "idx_memory_entries_principal",
        "memory_entries",
        ["principal_id"],
        schema=DB_SCHEMA,
    )
    op.create_index(
        "idx_memory_entries_visibility",
        "memory_entries",
        ["visibility"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    # memory_entries
    op.drop_index("idx_memory_entries_visibility", "memory_entries", schema=DB_SCHEMA)
    op.drop_index("idx_memory_entries_principal", "memory_entries", schema=DB_SCHEMA)
    op.drop_column("memory_entries", "visibility", schema=DB_SCHEMA)
    op.drop_column("memory_entries", "principal_id", schema=DB_SCHEMA)

    # memory_source_ledger
    op.execute(
        f"ALTER TABLE {DB_SCHEMA}.memory_source_ledger "
        f"DROP CONSTRAINT IF EXISTS ck_memory_source_ledger_visibility"
    )
    op.drop_index(
        "idx_memory_source_ledger_principal", "memory_source_ledger", schema=DB_SCHEMA,
    )
    op.drop_column("memory_source_ledger", "visibility", schema=DB_SCHEMA)
    op.drop_column("memory_source_ledger", "principal_id", schema=DB_SCHEMA)
