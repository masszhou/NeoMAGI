"""Create memory source ledger table (P2-M2d).

Adds append-only memory_source_ledger table for DB memory truth (ADR 0060).
Uses event_id (UUIDv7) as PK, entry_id references the memory entry.
Partial unique index ensures at most one 'append' event per entry_id.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-04-12
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op
from src.constants import DB_SCHEMA

revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memory_source_ledger",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("entry_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(16), nullable=False, server_default="append"),
        sa.Column("scope_key", sa.String(128), nullable=False, server_default="main"),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_session_id", sa.String(256), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=DB_SCHEMA,
    )

    op.create_index(
        "idx_memory_source_ledger_entry_id",
        "memory_source_ledger",
        ["entry_id"],
        schema=DB_SCHEMA,
    )
    op.create_index(
        "idx_memory_source_ledger_scope",
        "memory_source_ledger",
        ["scope_key"],
        schema=DB_SCHEMA,
    )
    op.create_index(
        "idx_memory_source_ledger_created_at",
        "memory_source_ledger",
        ["created_at"],
        schema=DB_SCHEMA,
    )
    # Partial unique index: at most one 'append' event per entry_id
    op.execute(
        f"CREATE UNIQUE INDEX uq_memory_source_ledger_entry_append "
        f"ON {DB_SCHEMA}.memory_source_ledger (entry_id) "
        f"WHERE event_type = 'append'"
    )


def downgrade() -> None:
    op.drop_table("memory_source_ledger", schema=DB_SCHEMA)
