import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path

from pydantic import SecretStr

FIELDS = {"openrouter_api_key", "firecrawl_api_key", "resend_api_key", "email_from", "email_recipient"}


def password_hash(password):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return salt + ":" + digest


def verify_password(password, encoded):
    try:
        salt, expected = encoded.split(":")
        actual = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def load_credentials(settings):
    path = Path(settings.credentials_path)
    if path.exists():
        for key, value in json.loads(path.read_text()).items():
            if key in FIELDS:
                setattr(settings, key, SecretStr(value) if key.endswith("api_key") else value)
    return settings


def save_credentials(settings, values):
    path = Path(settings.credentials_path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    current = json.loads(path.read_text()) if path.exists() else {}
    current.update({k: v for k, v in values.items() if k in FIELDS and v})
    temporary = path.with_suffix(".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(current, stream)
    os.replace(temporary, path)
    load_credentials(settings)
