from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Text, Integer, BigInteger, Enum
import enum

from src.common.models.uuid_mixin import UUIDMixin
from src.common.models.meta import Base


class UserStatus(enum.Enum):
    ACTIVE = 1
    NO_ACTIVE = 2

class User(Base, UUIDMixin):
    __tablename__ = 'user'

    full_name: Mapped[str] = mapped_column(Text)
    age: Mapped[int] = mapped_column(Integer)
    study_group: Mapped[str] = mapped_column(Text)
    room: Mapped[str] = mapped_column(Text)
    phone_number: Mapped[str] = mapped_column(Text)
    telegram_id = mapped_column(BigInteger)
    status = mapped_column(Enum(UserStatus))
