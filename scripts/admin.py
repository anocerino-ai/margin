"""Configure the sole administrator interactively; never print passwords."""

from getpass import getpass

from dotenv import set_key

from margin.config import ROOT
from margin.security import password_hash

email = input("Admin email: ").strip()
password = getpass("Password (at least 12 characters): ")
if "@" not in email or len(password) < 12:
    raise SystemExit("Valid email and at least 12 password characters required")
if password != getpass("Repeat password: "):
    raise SystemExit("Passwords differ")
set_key(ROOT / ".env", "MARGIN_ADMIN_EMAIL", email)
set_key(ROOT / ".env", "MARGIN_ADMIN_PASSWORD_HASH", password_hash(password))
(ROOT / ".env").chmod(0o600)
print("Admin configured. Restart the API.")
