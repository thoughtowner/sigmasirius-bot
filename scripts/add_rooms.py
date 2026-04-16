import asyncio

from src.storage.db import async_session
from src.model.models import Room, RoomClass
from sqlalchemy import select

ROOM_NUMBERS = {
    "1": {
        "1": {
            "1": [
                {"room": 101, "people_quantity": 1, "room_class": "economy"},
                {"room": 102, "people_quantity": 4, "room_class": "economy"},
                {"room": 103, "people_quantity": 4, "room_class": "economy"},
                {"room": 104, "people_quantity": 1, "room_class": "economy"},
            ],
            "2": [
                {"room": 201, "people_quantity": 2, "room_class": "economy"},
                {"room": 202, "people_quantity": 3, "room_class": "economy"},
                {"room": 203, "people_quantity": 3, "room_class": "economy"},
                {"room": 204, "people_quantity": 2, "room_class": "economy"},
            ],
            "3": [
                {"room": 301, "people_quantity": 1, "room_class": "comfort"},
                {"room": 302, "people_quantity": 4, "room_class": "comfort"},
                {"room": 303, "people_quantity": 4, "room_class": "comfort"},
                {"room": 304, "people_quantity": 1, "room_class": "comfort"},
            ],
            "4": [
                {"room": 401, "people_quantity": 2, "room_class": "comfort"},
                {"room": 402, "people_quantity": 3, "room_class": "comfort"},
                {"room": 403, "people_quantity": 3, "room_class": "comfort"},
                {"room": 404, "people_quantity": 2, "room_class": "comfort"},
            ],
            "5": [
                {"room": 501, "people_quantity": 1, "room_class": "luxury"},
                {"room": 502, "people_quantity": 4, "room_class": "luxury"},
                {"room": 503, "people_quantity": 4, "room_class": "luxury"},
                {"room": 504, "people_quantity": 1, "room_class": "luxury"},
            ],
            "6": [
                {"room": 601, "people_quantity": 2, "room_class": "luxury"},
                {"room": 602, "people_quantity": 3, "room_class": "luxury"},
                {"room": 603, "people_quantity": 3, "room_class": "luxury"},
                {"room": 604, "people_quantity": 2, "room_class": "luxury"},
            ],
        },
        "2": {
            "1": [
                {"room": 101, "people_quantity": 1, "room_class": "economy"},
                {"room": 102, "people_quantity": 4, "room_class": "economy"},
                {"room": 103, "people_quantity": 4, "room_class": "economy"},
                {"room": 104, "people_quantity": 1, "room_class": "economy"},
            ],
            "2": [
                {"room": 201, "people_quantity": 2, "room_class": "economy"},
                {"room": 202, "people_quantity": 3, "room_class": "economy"},
                {"room": 203, "people_quantity": 3, "room_class": "economy"},
                {"room": 204, "people_quantity": 2, "room_class": "economy"},
            ],
            "3": [
                {"room": 301, "people_quantity": 1, "room_class": "comfort"},
                {"room": 302, "people_quantity": 4, "room_class": "comfort"},
                {"room": 303, "people_quantity": 4, "room_class": "comfort"},
                {"room": 304, "people_quantity": 1, "room_class": "comfort"},
            ],
            "4": [
                {"room": 401, "people_quantity": 2, "room_class": "comfort"},
                {"room": 402, "people_quantity": 3, "room_class": "comfort"},
                {"room": 403, "people_quantity": 3, "room_class": "comfort"},
                {"room": 404, "people_quantity": 2, "room_class": "comfort"},
            ],
            "5": [
                {"room": 501, "people_quantity": 1, "room_class": "luxury"},
                {"room": 502, "people_quantity": 4, "room_class": "luxury"},
                {"room": 503, "people_quantity": 4, "room_class": "luxury"},
                {"room": 504, "people_quantity": 1, "room_class": "luxury"},
            ],
            "6": [
                {"room": 601, "people_quantity": 2, "room_class": "luxury"},
                {"room": 602, "people_quantity": 3, "room_class": "luxury"},
                {"room": 603, "people_quantity": 3, "room_class": "luxury"},
                {"room": 604, "people_quantity": 2, "room_class": "luxury"},
            ],
        },
    },
    "2": {
        "1": {
            "1": [
                {"room": 101, "people_quantity": 1, "room_class": "economy"},
                {"room": 102, "people_quantity": 4, "room_class": "economy"},
                {"room": 103, "people_quantity": 4, "room_class": "economy"},
                {"room": 104, "people_quantity": 1, "room_class": "economy"},
            ],
            "2": [
                {"room": 201, "people_quantity": 2, "room_class": "economy"},
                {"room": 202, "people_quantity": 3, "room_class": "economy"},
                {"room": 203, "people_quantity": 3, "room_class": "economy"},
                {"room": 204, "people_quantity": 2, "room_class": "economy"},
            ],
            "3": [
                {"room": 301, "people_quantity": 1, "room_class": "comfort"},
                {"room": 302, "people_quantity": 4, "room_class": "comfort"},
                {"room": 303, "people_quantity": 4, "room_class": "comfort"},
                {"room": 304, "people_quantity": 1, "room_class": "comfort"},
            ],
            "4": [
                {"room": 401, "people_quantity": 2, "room_class": "comfort"},
                {"room": 402, "people_quantity": 3, "room_class": "comfort"},
                {"room": 403, "people_quantity": 3, "room_class": "comfort"},
                {"room": 404, "people_quantity": 2, "room_class": "comfort"},
            ],
            "5": [
                {"room": 501, "people_quantity": 1, "room_class": "luxury"},
                {"room": 502, "people_quantity": 4, "room_class": "luxury"},
                {"room": 503, "people_quantity": 4, "room_class": "luxury"},
                {"room": 504, "people_quantity": 1, "room_class": "luxury"},
            ],
            "6": [
                {"room": 601, "people_quantity": 2, "room_class": "luxury"},
                {"room": 602, "people_quantity": 3, "room_class": "luxury"},
                {"room": 603, "people_quantity": 3, "room_class": "luxury"},
                {"room": 604, "people_quantity": 2, "room_class": "luxury"},
            ],
        },
        "2": {
            "1": [
                {"room": 101, "people_quantity": 1, "room_class": "economy"},
                {"room": 102, "people_quantity": 4, "room_class": "economy"},
                {"room": 103, "people_quantity": 4, "room_class": "economy"},
                {"room": 104, "people_quantity": 1, "room_class": "economy"},
            ],
            "2": [
                {"room": 201, "people_quantity": 2, "room_class": "economy"},
                {"room": 202, "people_quantity": 3, "room_class": "economy"},
                {"room": 203, "people_quantity": 3, "room_class": "economy"},
                {"room": 204, "people_quantity": 2, "room_class": "economy"},
            ],
            "3": [
                {"room": 301, "people_quantity": 1, "room_class": "comfort"},
                {"room": 302, "people_quantity": 4, "room_class": "comfort"},
                {"room": 303, "people_quantity": 4, "room_class": "comfort"},
                {"room": 304, "people_quantity": 1, "room_class": "comfort"},
            ],
            "4": [
                {"room": 401, "people_quantity": 2, "room_class": "comfort"},
                {"room": 402, "people_quantity": 3, "room_class": "comfort"},
                {"room": 403, "people_quantity": 3, "room_class": "comfort"},
                {"room": 404, "people_quantity": 2, "room_class": "comfort"},
            ],
            "5": [
                {"room": 501, "people_quantity": 1, "room_class": "luxury"},
                {"room": 502, "people_quantity": 4, "room_class": "luxury"},
                {"room": 503, "people_quantity": 4, "room_class": "luxury"},
                {"room": 504, "people_quantity": 1, "room_class": "luxury"},
            ],
            "6": [
                {"room": 601, "people_quantity": 2, "room_class": "luxury"},
                {"room": 602, "people_quantity": 3, "room_class": "luxury"},
                {"room": 603, "people_quantity": 3, "room_class": "luxury"},
                {"room": 604, "people_quantity": 2, "room_class": "luxury"},
            ],
        },
    },
}


TEST_ROOM_NUMBERS = {
    "1": {
        "1": {
            "1": [
                {"room": 101, "people_quantity": 1, "room_class": "economy"},
                {"room": 102, "people_quantity": 4, "room_class": "economy"},
                {"room": 103, "people_quantity": 4, "room_class": "economy"},
                {"room": 104, "people_quantity": 1, "room_class": "economy"},
            ],
        }
    }
}


async def seed_rooms():
    async with async_session() as db:
        for building, entrances in TEST_ROOM_NUMBERS.items():
            for entrance, floors in entrances.items():
                for floor, rooms_list in floors.items():
                    for room_info in rooms_list:
                        room_number = int(room_info['room'])
                        full_room_number = f"{building}-{entrance}-{room_number}"

                        existing = await db.execute(select(Room).filter(Room.full_room_number == full_room_number))
                        existing_room = existing.scalar_one_or_none()
                        if existing_room:
                            continue

                        room = Room(
                            building=int(building),
                            entrance=int(entrance),
                            flour=int(floor),
                            room_number=room_number,
                            full_room_number=full_room_number,
                            room_class=RoomClass(room_info['room_class']),
                            people_quantity=int(room_info.get('people_quantity', 1)),
                        )
                        db.add(room)

        await db.commit()
        print('Seeding completed')


def main():
    asyncio.run(seed_rooms())


if __name__ == '__main__':
    main()
