from uuid import UUID, uuid4

from sqlalchemy.orm import Mapped, mapped_column


class UUIDMixin:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
