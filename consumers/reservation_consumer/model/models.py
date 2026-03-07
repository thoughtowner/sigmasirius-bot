from uuid import UUID, uuid4
from typing import List
from sqlalchemy import  String, Text, BigInteger, Boolean, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from ..model.meta import Base


class Status(enum.Enum):
    NOT_COMPLETED = "not_completed"
    IN_PROCESSING = "in_processing"
    COMPLETED = "completed"
    CANCELELLED = "cancelled"


class User(Base):
    __tablename__ = 'users'

    # __table_args__ = (
    #     UniqueConstraint('telegram_id', name='users_unique_telegram_id'),
    # )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    phone_number: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    is_repairman: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    residents: Mapped['Resident'] = relationship(back_populates='user')
    application_forms: Mapped['ApplicationForm'] = relationship(back_populates='user')


class Resident(Base):
    __tablename__ = "residents"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    room: Mapped[str] = mapped_column(String, nullable=False)

    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    user: Mapped['User'] = relationship(back_populates='residents')


class ApplicationForm(Base):
    __tablename__ = 'application_forms'

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[Status] = mapped_column(Enum(Status), nullable=False, default=Status.NOT_COMPLETED)

    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    user: Mapped['User'] = relationship(back_populates='application_forms')

    telegram_ids_and_message_ids: Mapped[List['TelegramIdAndMessageId']] = relationship(back_populates='application_form')


class TelegramIdAndMessageId(Base):
    __tablename__ = 'telegram_ids_and_message_ids'

    __table_args__ = (
        UniqueConstraint('id', 'application_form_id',  name='telegram_ids_and_message_ids_id_unique_combined_app_form_id'),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    application_form_id: Mapped[UUID] = mapped_column(ForeignKey('application_forms.id'))
    application_form: Mapped['ApplicationForm'] = relationship(back_populates='telegram_ids_and_message_ids')
