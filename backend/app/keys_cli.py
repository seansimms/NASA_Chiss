from __future__ import annotations
import sys, base64, secrets
from .db import init_db, api_keys_insert, api_keys_list, api_keys_revoke
from .security import hash_key

USAGE = """Usage:
  python -m app.keys_cli create <name> <role:viewer|operator|admin>
  python -m app.keys_cli list
  python -m app.keys_cli revoke <id>
"""

def create(name:str, role:str):
    if role not in ("viewer","operator","admin"):
        print("role must be viewer|operator|admin"); sys.exit(2)
    salt = secrets.token_bytes(16)
    token = "chiss_" + secrets.token_urlsafe(24)
    h = hash_key(token, salt)
    sid = api_keys_insert(name=name, role=role, salt=base64.b64encode(salt).decode("utf-8"), hash_=h)
    print(f"API key created id={sid} role={role} name={name}")
    print("---- COPY & STORE THIS TOKEN NOW (not shown again) ----")
    print(token)

def list_():
    rows = api_keys_list()
    for r in rows:
        print(f"id={r['id']} name={r['name']} role={r['role']} revoked={r['revoked']} created_at={r['created_at']}")

def revoke(id_:str):
    ok = api_keys_revoke(int(id_))
    print("revoked" if ok else "not found")

def main():
    init_db()
    if len(sys.argv) < 2:
        print(USAGE); sys.exit(2)
    cmd = sys.argv[1]
    if cmd == "create" and len(sys.argv)==4:
        create(sys.argv[2], sys.argv[3]); return
    if cmd == "list":
        list_(); return
    if cmd == "revoke" and len(sys.argv)==3:
        revoke(sys.argv[2]); return
    print(USAGE); sys.exit(2)

if __name__ == "__main__":
    main()

