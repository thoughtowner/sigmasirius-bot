from abc import ABC, abstractmethod
from aiogram.types import Message


class BaseTgValidator:
    def validate(self, message: Message) -> str:
        message_text = message.text
        self._do_validate(message_text)
        return message_text

    @abstractmethod
    def _do_validate(self, message: str) -> None:
        pass
