from sqlalchemy.orm import Mapped, mapped_column

from src.model.meta import Base


class User(Base):
    __tablename__ = 'user'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    username: Mapped[str] = mapped_column(index=True)
    password: Mapped[str] = mapped_column()
