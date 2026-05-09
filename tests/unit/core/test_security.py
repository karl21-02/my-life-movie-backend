import pytest

from app.core.security import PasswordHasher, normalize_email


pytestmark = pytest.mark.unit


def test_password_hasher_hashes_and_verifies_password():
    hasher = PasswordHasher()

    password_hash = hasher.hash_password("password123")

    assert password_hash != "password123"
    assert password_hash.startswith("$argon2")
    assert hasher.verify_password("password123", password_hash) is True
    assert hasher.verify_password("wrong-password", password_hash) is False


def test_password_hasher_rejects_invalid_hash():
    hasher = PasswordHasher()

    assert hasher.verify_password("password123", "not-a-valid-hash") is False


def test_normalize_email_trims_and_lowercases_email():
    assert normalize_email("  USER@Example.COM  ") == "user@example.com"
