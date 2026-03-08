from uuid import UUID, uuid4
from typing import List
from sqlalchemy import  String, Text, BigInteger, Boolean, Date, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from datetime import date

from ..model.meta import Base


class ApplicationFormStatus(enum.Enum):
    NOT_COMPLETED = "not_completed"
    IN_PROCESSING = "in_processing"
    COMPLETED = "completed"
    CANCELELLED = "cancelled"


class RoomClass(enum.Enum):
    ECONOMY = "economy"
    COMFORT = "comfort"
    LUXURY = "luxury"


class ReservationStatus(enum.Enum):
    AWAITING_EXECUTION = "awaiting_execution"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class User(Base):
    __tablename__ = 'users'

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    phone_number: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    is_repairman: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    application_forms: Mapped[List['ApplicationForm']] = relationship(back_populates='user')
    reservations: Mapped[List['Reservation']] = relationship(back_populates='user')


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    building: Mapped[int] = mapped_column(BigInteger, nullable=False)
    entrance: Mapped[int] = mapped_column(BigInteger, nullable=False)
    room_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    full_room_number: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    room_class: Mapped[RoomClass] = mapped_column(Enum(RoomClass), nullable=False)
    people_quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)

    reservations: Mapped[List["Reservation"]] = relationship(back_populates="room")


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    people_quantity: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    room_class: Mapped[RoomClass] = mapped_column(Enum(RoomClass), nullable=False)

    check_in_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    eviction_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)

    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus),
        nullable=False,
        default=ReservationStatus.AWAITING_EXECUTION
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    user: Mapped["User"] = relationship(back_populates="reservations")

    room_id: Mapped[UUID | None] = mapped_column(ForeignKey("rooms.id"), nullable=True)
    room: Mapped["Room | None"] = relationship(back_populates="reservations")


class ApplicationForm(Base):
    __tablename__ = 'application_forms'

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[ApplicationFormStatus] = mapped_column(Enum(ApplicationFormStatus), nullable=False, default=ApplicationFormStatus.NOT_COMPLETED)

    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    user: Mapped['User'] = relationship(back_populates='application_forms')

    telegram_ids_and_message_ids: Mapped[List['TelegramIdAndMessageId']] = relationship(back_populates='application_form')


class TelegramIdAndMessageId(Base):
    __tablename__ = 'telegram_ids_and_message_ids'

    __table_args__ = (
        UniqueConstraint('id', 'application_form_id', name='telegram_ids_and_message_ids_id_unique_combined_app_form_id'),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    application_form_id: Mapped[UUID] = mapped_column(ForeignKey('application_forms.id'))
    application_form: Mapped['ApplicationForm'] = relationship(back_populates='telegram_ids_and_message_ids')
