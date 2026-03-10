from cryptography.fernet import Fernet, InvalidToken
from backend.config import settings


def get_fernet() -> Fernet:
    key = settings.token_encryption_key
    return Fernet(key.encode())


def encrypt_token(token: str) -> str:
    return get_fernet().encrypt(token.encode()).decode()


def decrypt_token(token_encrypted: str) -> str:
    return get_fernet().decrypt(token_encrypted.encode()).decode()


def safe_decrypt(token_encrypted: str) -> str | None:
    try:
        return decrypt_token(token_encrypted)
    except InvalidToken:
        return None
