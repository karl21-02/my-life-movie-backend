from argon2 import PasswordHasher as Argon2PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


class PasswordHasher:
    def __init__(self) -> None:
        self._hasher = Argon2PasswordHasher()

    def hash_password(self, plain_password: str) -> str:
        return self._hasher.hash(plain_password)

    def verify_password(self, plain_password: str, password_hash: str) -> bool:
        try:
            return self._hasher.verify(password_hash, plain_password)
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            return False


def normalize_email(email: str) -> str:
    return email.strip().lower()
