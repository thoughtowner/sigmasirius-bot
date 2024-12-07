from uuid import UUID, uuid4
from typing import List
from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .role import Role

from consumers.model.meta import Base


class User(Base):
    __tablename__ = 'user'

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    telegram_id: Mapped[int] = mapped_column(BigInteger)
    full_name: Mapped[str] = mapped_column(Text, index=True)
    phone_number: Mapped[str] = mapped_column(String)

    roles: Mapped[List['Role']] = relationship(back_populates='users')
    resident_details: Mapped['ResidentDetails'] = relationship(back_populates='user')


class UserRole(Base):
    __tablename__ = 'user_role'

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    user_id: Mapped['User'] = mapped_column(ForeignKey('user.id'))
    role_id: Mapped['Role'] = mapped_column(ForeignKey('role.id'))

    user: Mapped['User'] = mapped_column(back_populates='roles')
    role: Mapped['Role'] = mapped_column(back_populates='users')


class ResidentDetails(Base):
    __tablename__ = 'resident_details'

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    room: Mapped[str] = mapped_column(String)

    user_id: Mapped[UUID] = mapped_column(ForeignKey('user.id'))
    user: Mapped['User'] = relationship(back_populates='resident_details')
