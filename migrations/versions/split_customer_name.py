"""split customer full_name into first_name, middle_initial, last_name

Revision ID: split_customer_name
Revises: (set this to your current head revision)
Create Date: 2026-04-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# ── Set these before running ──────────────────────────────────────────────────
revision    = 'split_customer_name'
down_revision = None   # ← replace with your current alembic head revision ID
branch_labels = None
depends_on    = None
# ─────────────────────────────────────────────────────────────────────────────


def upgrade():
    # 1. Add the three new columns (nullable so existing rows don't fail)
    op.add_column('customers', sa.Column('first_name',     sa.String(100), nullable=True, server_default=''))
    op.add_column('customers', sa.Column('middle_initial', sa.String(10),  nullable=True))
    op.add_column('customers', sa.Column('last_name',      sa.String(100), nullable=True, server_default=''))

    # 2. Backfill: split the existing full_name value into the new columns.
    #    Strategy:
    #      • 1 word  → first_name only
    #      • 2 words → first_name + last_name
    #      • 3+ words → first_name + middle token as middle_initial + rest as last_name
    conn = op.get_bind()
    rows = conn.execute(text("SELECT customer_id, full_name FROM customers")).fetchall()
    for customer_id, full_name in rows:
        if not full_name:
            continue
        parts = full_name.strip().split()
        if len(parts) == 1:
            first, mi, last = parts[0], None, ''
        elif len(parts) == 2:
            first, mi, last = parts[0], None, parts[1]
        else:
            first = parts[0]
            mi    = parts[1]
            last  = ' '.join(parts[2:])
        conn.execute(
            text("""
                UPDATE customers
                SET first_name = :first,
                    middle_initial = :mi,
                    last_name = :last
                WHERE customer_id = :cid
            """),
            {'first': first, 'mi': mi, 'last': last, 'cid': customer_id}
        )

    # 3. Make first_name / last_name non-nullable now that data is backfilled
    op.alter_column('customers', 'first_name', nullable=False, server_default=None)
    op.alter_column('customers', 'last_name',  nullable=False, server_default=None)

    # 4. Drop the old full_name column
    op.drop_column('customers', 'full_name')


def downgrade():
    # Rebuild full_name from the three parts, then drop them
    op.add_column('customers', sa.Column('full_name', sa.String(200), nullable=True))

    conn = op.get_bind()
    conn.execute(text("""
        UPDATE customers
        SET full_name = TRIM(CONCAT(
            COALESCE(first_name, ''), ' ',
            CASE WHEN middle_initial IS NOT NULL AND middle_initial != ''
                 THEN CONCAT(TRIM(TRIM('.' FROM middle_initial)), '. ')
                 ELSE ''
            END,
            COALESCE(last_name, '')
        ))
    """))

    op.alter_column('customers', 'full_name', nullable=False)
    op.drop_column('customers', 'first_name')
    op.drop_column('customers', 'middle_initial')
    op.drop_column('customers', 'last_name')
