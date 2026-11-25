import hashlib
import hmac
import secrets

ITERATIONS = 120_000


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return digest, salt


def verify_password(password, digest, salt):
    return hmac.compare_digest(hash_password(password, salt)[0], digest)


def new_token():
    return secrets.token_urlsafe(32)
