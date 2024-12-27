from uuid import UUID, uuid4
from typing import List
from sqlalchemy import  String, Text, BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..model.meta import Base


class User(Base):
    __tablename__ = 'users'

    __table_args__ = (
        UniqueConstraint('telegram_id', name='users_unique_telegram_id'),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    telegram_id: Mapped[int] = mapped_column(BigInteger)

    roles: Mapped[List['UserRole']] = relationship(back_populates='user')
    resident_additional_data: Mapped['ResidentAdditionalData'] = relationship(back_populates='user')
    admin_additional_data: Mapped['AdminAdditionalData'] = relationship(back_populates='user')
    application_forms: Mapped['ApplicationForm'] = relationship(back_populates='user')


class Role(Base):
    __tablename__ = 'roles'

    __table_args__ = (
        UniqueConstraint('title', name='roles_unique_title'),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    title: Mapped[str] = mapped_column(String)

    users: Mapped[List['UserRole']] = relationship(back_populates='role')


class UserRole(Base):
    __tablename__ = 'user_to_role'

    __table_args__ = (
        UniqueConstraint('user_id', 'role_id', name='user_to_role_user_id_unique_combined_role_id'),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    role_id: Mapped[UUID] = mapped_column(ForeignKey('roles.id'))

    user: Mapped['User'] = relationship(back_populates='roles')
    role: Mapped['Role'] = relationship(back_populates='users')


class ResidentAdditionalData(Base):
    __tablename__ = 'resident_additional_data'

    __table_args__ = (
        UniqueConstraint('id', 'user_id', name='resident_additional_data_id_unique_combined_user_id'),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    full_name: Mapped[str] = mapped_column(Text, index=True)
    phone_number: Mapped[str] = mapped_column(String)
    room: Mapped[str] = mapped_column(String)

    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    user: Mapped['User'] = relationship(back_populates='resident_additional_data')


class AdminAdditionalData(Base):
    __tablename__ = 'admin_additional_data'

    __table_args__ = (
        UniqueConstraint('id', 'user_id', name='admin_additional_data_id_unique_combined_user_id'),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    full_name: Mapped[str] = mapped_column(Text, index=True)
    phone_number: Mapped[str] = mapped_column(String)

    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    user: Mapped['User'] = relationship(back_populates='admin_additional_data')


class ApplicationForm(Base):
    __tablename__ = 'application_forms'

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)

    status_id: Mapped[UUID] = mapped_column(ForeignKey('application_form_statuses.id'))
    status: Mapped['ApplicationFormStatus'] = relationship(back_populates='application_form')

    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    user: Mapped['User'] = relationship(back_populates='application_forms')


class ApplicationFormStatus(Base):
    __tablename__ = 'application_form_statuses'

    __table_args__ = (
        UniqueConstraint('title', name='application_form_statuses_unique_title'),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    title: Mapped[str] = mapped_column(String)

    application_form: Mapped['ApplicationForm'] = relationship(back_populates='status')
