from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Text, String, Integer, BigInteger, Date, Time

from src.model.meta import Base
from datetime import date, time


class ApplicationForm(Base):
    __tablename__ = 'application_form'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    text: Mapped[str] = mapped_column(Text)
    description: Mapped[int] = mapped_column(Text)
    photo: Mapped[str] = mapped_column(Text)
    date: Mapped[date] = mapped_column(Date)
    time: Mapped[time] = mapped_column(Time)
    status: Mapped[str] = mapped_column(String)
