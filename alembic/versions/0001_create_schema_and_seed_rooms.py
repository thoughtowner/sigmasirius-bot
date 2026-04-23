"""create schema and seed rooms

Revision ID: 0001_create_schema_and_seed_rooms
Revises: 
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa
import os
import sys
import uuid

# allow importing project modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.model import meta

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    # create tables from metadata
    meta.metadata.create_all(bind=bind)

    # seed rooms using ROOM_NUMBERS from scripts/add_rooms.py
    try:
        from scripts.add_rooms import ROOM_NUMBERS
    except Exception:
        ROOM_NUMBERS = {}

    insert_stmt = sa.text(
        """
        INSERT INTO public.rooms (id, building, entrance, flour, room_number, full_room_number, room_class, people_quantity)
        VALUES (:id, :building, :entrance, :flour, :room_number, :full_room_number, :room_class, :people_quantity)
        ON CONFLICT (full_room_number) DO NOTHING
        """
    )

    for building, entrances in ROOM_NUMBERS.items():
        for entrance, floors in entrances.items():
            for floor, rooms_list in floors.items():
                for room_info in rooms_list:
                    room_number = int(room_info['room'])
                    full_room_number = f"{building}-{entrance}-{room_number}"
                    params = {
                        'id': str(uuid.uuid4()),
                        'building': int(building),
                        'entrance': int(entrance),
                        'flour': int(floor),
                        'room_number': room_number,
                        'full_room_number': full_room_number,
                        'room_class': room_info['room_class'],
                        'people_quantity': int(room_info.get('people_quantity', 1)),
                    }
                    bind.execute(insert_stmt, params)


def downgrade():
    bind = op.get_bind()
    # drop all tables created by metadata
    meta.metadata.drop_all(bind=bind)
