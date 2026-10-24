"""Password hashing, JWT handling and token encryption."""

from datetime import timedelta

import pytest

from app.core import security
from app.core.security import (
    KmsTokenEncryptor,
    TokenEncryptor,
    create_access_token,
    decode_access_token,
    generate_secure_token,
    get_password_hash,
    verify_password,
)


def test_password_hash_round_trip():
    hashed = get_password_hash("s3cret-pass")
    assert hashed != "s3cret-pass"
    assert verify_password("s3cret-pass", hashed)
    assert not verify_password("wrong-pass", hashed)


def test_access_token_round_trip_keeps_claims():
    token = create_access_token({"sub": "user-123", "role": "user"})
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "user"
    assert "exp" in payload


def test_expired_token_decodes_to_none():
    token = create_access_token({"sub": "user-123"}, expires_delta=timedelta(seconds=-5))
    assert decode_access_token(token) is None


def test_token_signed_with_another_key_is_rejected(monkeypatch):
    token = create_access_token({"sub": "user-123"})
    monkeypatch.setattr(
        security.settings, "JWT_SECRET_KEY", "a-different-secret-key-value-of-32-bytes"
    )
    assert decode_access_token(token) is None


def test_garbage_token_decodes_to_none():
    assert decode_access_token("not.a.jwt") is None


def test_tampered_token_is_rejected():
    token = create_access_token({"sub": "user-123"})
    header, payload, signature = token.split(".")
    flipped = signature[:-2] + ("AA" if signature[-2:] != "AA" else "BB")
    assert decode_access_token(f"{header}.{payload}.{flipped}") is None


def test_fernet_encryptor_round_trip():
    encryptor = TokenEncryptor("unit-test-key")
    ciphertext = encryptor.encrypt("gho_example")
    assert ciphertext != "gho_example"
    assert encryptor.decrypt(ciphertext) == "gho_example"


class FakeKms:
    def encrypt(self, KeyId, Plaintext):
        return {"CiphertextBlob": b"wrapped:" + Plaintext}

    def decrypt(self, CiphertextBlob):
        assert CiphertextBlob.startswith(b"wrapped:")
        return {"Plaintext": CiphertextBlob[len(b"wrapped:") :]}


@pytest.fixture
def kms_encryptor():
    encryptor = KmsTokenEncryptor()
    encryptor._kms = FakeKms()
    return encryptor


def test_kms_encryptor_prefixes_and_round_trips(kms_encryptor):
    ciphertext = kms_encryptor.encrypt("gho_example")
    assert ciphertext.startswith("KMS:")
    assert kms_encryptor.decrypt(ciphertext) == "gho_example"


def test_kms_encryptor_falls_back_to_legacy_fernet(kms_encryptor):
    legacy = TokenEncryptor().encrypt("old-token")
    assert kms_encryptor.decrypt(legacy) == "old-token"


def test_kms_encryptor_rejects_unknown_ciphertext(kms_encryptor):
    with pytest.raises(ValueError, match="Unable to decrypt token"):
        kms_encryptor.decrypt("neither-kms-nor-fernet")


def test_generate_secure_token_is_random_and_url_safe():
    first, second = generate_secure_token(), generate_secure_token()
    assert first != second
    assert all(c.isalnum() or c in "-_" for c in first)
