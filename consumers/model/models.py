from uuid import UUID, uuid4
from typing import List
from sqlalchemy import  String, Text, BigInteger, Date, Time, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from consumers.model.meta import Base
from datetime import date, time
import enum


class User(Base):
    __tablename__ = 'user'

    __table_args__ = (
        UniqueConstraint('telegram_user_id', name='user_unique_telegram_user_id'),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    telegram_user_id: Mapped[int] = mapped_column(BigInteger)
    full_name: Mapped[str] = mapped_column(Text, index=True)
    phone_number: Mapped[str] = mapped_column(String)

    roles: Mapped[List['UserRole']] = relationship(back_populates='user')
    resident_additional_data: Mapped['ResidentAdditionalData'] = relationship(back_populates='user')
    application_forms: Mapped['ApplicationForm'] = relationship(back_populates='user')


class Role(Base):
    __tablename__ = 'role'

    __table_args__ = (
        UniqueConstraint('title', name='role_unique_title'),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    title: Mapped[str] = mapped_column(String)

    users: Mapped[List['UserRole']] = relationship(back_populates='role')


class UserRole(Base):
    __tablename__ = 'user_role'

    __table_args__ = (
        UniqueConstraint('user_id', 'role_id', name='role_role_user_id_unique_combined_role_id'),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    user_id: Mapped[UUID] = mapped_column(ForeignKey('user.id'))
    role_id: Mapped[UUID] = mapped_column(ForeignKey('role.id'))

    user: Mapped['User'] = relationship(back_populates='roles')
    role: Mapped['Role'] = relationship(back_populates='users')


class ResidentAdditionalData(Base):
    __tablename__ = 'resident_additional_data'

    __table_args__ = (
        UniqueConstraint('id', 'user_id', name='resident_additional_data_id_unique_combined_user_id'),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    room: Mapped[str] = mapped_column(String)

    user_id: Mapped[UUID] = mapped_column(ForeignKey('user.id'))
    user: Mapped['User'] = relationship(back_populates='resident_additional_data')


class ApplicationFormStatus(enum.Enum):
    NOT_COMPLETED = 1
    IN_PROGRESS = 2
    COMPLETED = 3


class ApplicationForm(Base):
    __tablename__ = 'application_form'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    text: Mapped[str] = mapped_column(Text)
    description: Mapped[int] = mapped_column(Text)
    photo: Mapped[str] = mapped_column(Text)
    date: Mapped[date] = mapped_column(Date)
    time: Mapped[time] = mapped_column(Time)
    status: Mapped['ApplicationFormStatus'] = mapped_column(Enum(ApplicationFormStatus))

    user_id: Mapped[UUID] = mapped_column(ForeignKey('user.id'))
    user: Mapped['User'] = relationship(back_populates='application_forms')
