from abc import ABC, abstractmethod


class UnitOfWork(ABC):
    @abstractmethod
    def commit(self) -> None: ...
