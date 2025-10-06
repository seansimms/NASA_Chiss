from __future__ import annotations
import os, hmac, json, base64, secrets, hashlib
from typing import Optional, Tuple
from .db import api_keys_all_material

ROLES = {"viewer":0, "operator":1, "admin":2}
PUBLIC_READ = os.getenv("CHISS_API_PUBLIC_READ","true").lower() in ("1","true","yes","on")
PEPPER = os.getenv("CHISS_API_SECRET","")

def _pbkdf2(password: bytes, salt: bytes)->bytes:
    # 200k iters PBKDF2-HMAC-SHA256 (fast enough for API keys, slow for attackers)
    return hashlib.pbkdf2_hmac("sha256", password, salt+PEPPER.encode("utf-8"), 200_000, dklen=32)

def hash_key(plaintext_key: str, salt_b: bytes)->str:
    digest = _pbkdf2(plaintext_key.encode("utf-8"), salt_b)
    return base64.b64encode(digest).decode("utf-8")

def verify_key(presented_key: str)->Optional[Tuple[int,str]]:
    """Return (role_level, role_name) if valid and not revoked, else None."""
    mats = api_keys_all_material()
    for row in mats:
        if row["revoked"]:
            continue
        try:
            salt_b = base64.b64decode(row["salt"].encode("utf-8"))
            want = row["hash"]
            got = hash_key(presented_key, salt_b)
            if hmac.compare_digest(got, want):
                role = row["role"]
                return (ROLES.get(role,0), role)
        except Exception:
            continue
    return None

def role_at_least(current:str, required:str)->bool:
    return ROLES.get(current,0) >= ROLES.get(required,0)

