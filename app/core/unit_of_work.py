from abc import ABC, abstractmethod


class UnitOfWork(ABC):
    """Batas transaksi. Use case memanggil commit(); kalau tidak, perubahan di-rollback saat session ditutup."""

    @abstractmethod
    def commit(self) -> None: ...
