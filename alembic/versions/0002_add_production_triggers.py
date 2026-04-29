"""add production reservation triggers

Revision ID: 0001_add_production_triggers
Revises: 77d16ce68149_initial_database
Create Date: 2026-04-23
"""
from alembic import op
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

revision = '0001'
down_revision = '77d16ce68149'
branch_labels = None
depends_on = None


def _read_sql(filename: str) -> str:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    path = os.path.join(base, 'sql', 'triggers', filename)
    with open(path, 'r') as f:
        return f.read()


def upgrade():
    bind = op.get_bind()
    sql = _read_sql('reservation_triggers.sql')
    # execute the whole SQL file using driver execution to preserve dollar-quoted blocks
    bind.exec_driver_sql(sql)


def downgrade():
    bind = op.get_bind()
    # remove triggers and functions created by reservation_triggers.sql
    cleanup = '''
    DROP TRIGGER IF EXISTS trg_schedule_reservation_jobs ON reservations;
    DROP FUNCTION IF EXISTS schedule_reservation_jobs() CASCADE;
    DROP FUNCTION IF EXISTS process_scheduled_reservation_jobs() CASCADE;
    DROP TABLE IF EXISTS scheduled_reservation_jobs;
    '''
    for stmt in [s.strip() for s in cleanup.split(';') if s.strip()]:
        bind.exec_driver_sql(stmt)
