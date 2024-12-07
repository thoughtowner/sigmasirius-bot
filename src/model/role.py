from uuid import UUID, uuid4
from typing import List
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .user import User

from src.model.meta import Base


class Role(Base):
    __tablename__ = 'role'

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    title: Mapped[str] = mapped_column(String)

    users: Mapped[List['User']] = relationship(back_populates='roles')
