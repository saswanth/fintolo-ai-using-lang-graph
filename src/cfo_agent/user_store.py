from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Dict

from cryptography.fernet import Fernet

from .auth import DEFAULT_USERS, create_password_record


SECURITY_DIR = Path("data/security")
USERS_FILE = SECURITY_DIR / "users.enc"
KEY_FILE = SECURITY_DIR / "users.key"


def _ensure_security_paths() -> None:
    SECURITY_DIR.mkdir(parents=True, exist_ok=True)


def _load_or_create_key() -> bytes:
    _ensure_security_paths()
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()

    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    return key


def _cipher() -> Fernet:
    key = _load_or_create_key()
    return Fernet(key)


def _seed_default_users() -> Dict[str, Any]:
    users: Dict[str, Any] = {}
    for username, profile in DEFAULT_USERS.items():
        users[username] = {
            "display_name": profile["display_name"],
            "role": profile["role"],
            "password": create_password_record(f"{username}123!"),
        }
    return users


def load_users() -> Dict[str, Any]:
    _ensure_security_paths()
    if not USERS_FILE.exists():
        users = _seed_default_users()
        save_users(users)
        return users

    encrypted = USERS_FILE.read_bytes()
    data = _cipher().decrypt(encrypted)
    users = json.loads(data.decode("utf-8"))
    return users


def save_users(users: Dict[str, Any]) -> None:
    serialized = json.dumps(users, indent=2).encode("utf-8")
    encrypted = _cipher().encrypt(serialized)
    USERS_FILE.write_bytes(encrypted)


def create_or_update_user(
    username: str,
    display_name: str,
    role: str,
    password: str | None = None,
) -> None:
    users = load_users()
    existing = users.get(username, {})

    users[username] = {
        "display_name": display_name,
        "role": role,
        "password": existing.get("password"),
    }
    if password:
        users[username]["password"] = create_password_record(password)

    save_users(users)


def delete_user(username: str) -> None:
    users = load_users()
    if username in users:
        del users[username]
    save_users(users)
