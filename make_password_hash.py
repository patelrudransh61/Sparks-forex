import getpass
import hashlib
import secrets

password = getpass.getpass("Create bot access password: ")
confirm = getpass.getpass("Confirm password: ")

if not password:
    raise SystemExit("Password cannot be empty.")
if password != confirm:
    raise SystemExit("Passwords do not match.")

salt = secrets.token_bytes(16)
digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)

print("\nPut this value into BOT_PASSWORD_HASH in .env:\n")
print(f"{salt.hex()}:{digest.hex()}")
