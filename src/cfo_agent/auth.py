from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Any, Dict, Tuple


DEFAULT_USERS: Dict[str, Dict[str, str]] = {
    "admin": {
        "display_name": "Platform Admin",
        "role": "admin",
        "password": {
            "scheme": "pbkdf2_sha256",
            "salt": "bootstrap",
            "iterations": 1,
            "hash": hashlib.sha256("admin123!bootstrap".encode("utf-8")).hexdigest(),
        },
    },
    "finance": {
        "display_name": "Finance Manager",
        "role": "finance_manager",
        "password": {
            "scheme": "pbkdf2_sha256",
            "salt": "bootstrap",
            "iterations": 1,
            "hash": hashlib.sha256("finance123!bootstrap".encode("utf-8")).hexdigest(),
        },
    },
    "board": {
        "display_name": "Board Viewer",
        "role": "board_viewer",
        "password": {
            "scheme": "pbkdf2_sha256",
            "salt": "bootstrap",
            "iterations": 1,
            "hash": hashlib.sha256("board123!bootstrap".encode("utf-8")).hexdigest(),
        },
    },
}


def create_password_record(password: str, iterations: int = 200_000) -> Dict[str, Any]:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return {
        "scheme": "pbkdf2_sha256",
        "salt": salt,
        "iterations": iterations,
        "hash": digest,
    }


def _verify_password_record(password: str, record: Dict[str, Any]) -> bool:
    scheme = record.get("scheme")
    salt = str(record.get("salt", ""))
    iterations = int(record.get("iterations", 0))
    stored_hash = str(record.get("hash", ""))

    if not salt or not iterations or not stored_hash:
        return False

    if scheme == "pbkdf2_sha256" and iterations > 1:
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        ).hex()
        return hmac.compare_digest(candidate, stored_hash)

    # Supports bootstrap records and old plaintext-hash migration path.
    candidate = hashlib.sha256(f"{password}{salt}".encode("utf-8")).hexdigest()
    return hmac.compare_digest(candidate, stored_hash)


def verify_credentials(
    username: str,
    password: str,
    users_config: Dict[str, Any] | None = None,
) -> Tuple[bool, Dict[str, str] | None]:
    users = users_config or DEFAULT_USERS
    profile = users.get(username)
    if not profile:
        return False, None

    password_record = profile.get("password")
    if isinstance(password_record, dict):
        if not _verify_password_record(password, password_record):
            return False, None
    else:
        legacy_hash = str(profile.get("password_hash", ""))
        provided_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(provided_hash, legacy_hash):
            return False, None

    return True, {
        "username": username,
        "display_name": profile.get("display_name", username),
        "role": profile.get("role", "board_viewer"),
    }
