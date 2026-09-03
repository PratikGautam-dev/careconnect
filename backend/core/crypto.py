# core/crypto.py
"""Symmetric encryption-at-rest for secrets that must be stored in the DB in
DECRYPTABLE form (not hashed) -- e.g. Google Calendar OAuth tokens
(db/repositories/google_calendar.py), which have to be read back and sent to
Google's API, unlike a password hash. First user of this helper; the
functions themselves are key-agnostic (caller passes the key in) so a future
second caller wouldn't need a second copy of this logic, but
CALENDAR_TOKEN_ENCRYPTION_KEY (core/config.py) is the only key in use so far.

Missing/invalid-key handling follows the same "boots cleanly, degrades at the
point of use" discipline as DOCTOR_SECRET etc. -- encrypt_secret()/
decrypt_secret() raise CryptoNotConfiguredError rather than letting Fernet's
own ValueError (malformed key) or InvalidToken (wrong key / corrupted data)
propagate as an unhandled 500. Route handlers catch this one exception type
and return a clean 4xx/503 instead."""
from cryptography.fernet import Fernet, InvalidToken


class CryptoNotConfiguredError(Exception):
    """The caller-supplied key is empty, malformed, or doesn't match the data
    it's being asked to decrypt."""


def encrypt_secret(plaintext: str, key: str) -> str:
    if not key:
        raise CryptoNotConfiguredError("Encryption key is not configured.")
    try:
        fernet = Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise CryptoNotConfiguredError("Encryption key is malformed.") from exc
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str, key: str) -> str:
    if not key:
        raise CryptoNotConfiguredError("Encryption key is not configured.")
    try:
        fernet = Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise CryptoNotConfiguredError("Encryption key is malformed.") from exc
    try:
        return fernet.decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise CryptoNotConfiguredError("Encryption key does not match the stored data.") from exc
