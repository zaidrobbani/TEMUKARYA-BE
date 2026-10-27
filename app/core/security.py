import hashlib
import hmac
import secrets
from abc import ABC, abstractmethod


class PasswordHasher(ABC):
    @abstractmethod
    def hash(self, password: str) -> str: ...

    @abstractmethod
    def verify(self, password: str, hashed: str) -> bool: ...


class ScryptPasswordHasher(PasswordHasher):
    # Format: scrypt$n$r$p$salt_hex$digest_hex
    _N, _R, _P = 2**14, 8, 1

    def hash(self, password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.scrypt(password.encode(), salt=salt, n=self._N, r=self._R, p=self._P)
        return f"scrypt${self._N}${self._R}${self._P}${salt.hex()}${digest.hex()}"

    def verify(self, password: str, hashed: str) -> bool:
        try:
            _, n, r, p, salt, digest = hashed.split("$")
            candidate = hashlib.scrypt(
                password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p)
            )
        except ValueError:
            return False
        return hmac.compare_digest(candidate, bytes.fromhex(digest))
