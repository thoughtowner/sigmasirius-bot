"""add test-only reservation triggers

Revision ID: 0003_add_test_triggers
Revises: 0002_add_production_triggers
Create Date: 2026-04-23
"""
from alembic import op
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

revision = '0003'
down_revision = '0001'
branch_labels = None
depends_on = None


def _read_sql(filename: str) -> str:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    path = os.path.join(base, 'sql', 'triggers', filename)
    with open(path, 'r') as f:
        return f.read()


def upgrade():
    bind = op.get_bind()
    sql = _read_sql('reservation_test_triggers.sql')
    bind.exec_driver_sql(sql)


def downgrade():
    bind = op.get_bind()
    cleanup = '''
    DROP TRIGGER IF EXISTS trg_schedule_reservation_test_jobs ON reservations;
    DROP FUNCTION IF EXISTS schedule_reservation_test_jobs() CASCADE;
    '''
    for stmt in [s.strip() for s in cleanup.split(';') if s.strip()]:
        bind.exec_driver_sql(stmt)
