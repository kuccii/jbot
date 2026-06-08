import os
import sys

from cryptography.fernet import Fernet


def _get_key() -> bytes:
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        print("ENCRYPTION_KEY not set. Generating one-time key.", file=sys.stderr)
        key = Fernet.generate_key().decode()
    return key.encode() if isinstance(key, str) else key


_cipher: Fernet | None = None


def _get_cipher() -> Fernet:
    global _cipher
    if _cipher is None:
        _cipher = Fernet(_get_key())
    return _cipher


def encrypt(plaintext: str) -> str:
    return _get_cipher().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _get_cipher().decrypt(ciphertext.encode()).decode()
