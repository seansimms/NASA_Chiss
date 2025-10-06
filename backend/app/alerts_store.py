import os, json, threading, time, uuid, hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional

ALERTS_DIR = Path(os.environ.get("CHISS_ALERTS_DIR", "dashboard_state/alerts")).resolve()
EVENTS_FILE = ALERTS_DIR / "events.jsonl"
RULES_FILE  = ALERTS_DIR / "rules.json"
OUTBOX_DIR  = ALERTS_DIR / "outbox"
_lock = threading.Lock()

def _now_iso()->str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _ensure_dirs():
    ALERTS_DIR.mkdir(parents=True, exist_ok=True)
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    if not RULES_FILE.exists():
        RULES_FILE.write_text(json.dumps({"rules":[]}, indent=2))
    if not EVENTS_FILE.exists():
        EVENTS_FILE.write_text("")

def list_recent(limit:int=100, status:str="all")->List[Dict]:
    """Read last N events from JSONL (tail)."""
    _ensure_dirs()
    try:
        with EVENTS_FILE.open("r") as f:
            lines = f.readlines()[-max(1,limit):]
        items = [json.loads(l) for l in lines if l.strip()]
        if status in ("sent","failed"):
            items = [it for it in items if bool(it.get("sent")) == (status=="sent")]
        # newest first
        items.sort(key=lambda x: x.get("ts",""), reverse=True)
        return items
    except FileNotFoundError:
        return []

def append_event(ev:Dict)->Dict:
    _ensure_dirs()
    with _lock:
        ev = dict(ev)  # copy
        ev.setdefault("id", str(uuid.uuid4()))
        ev.setdefault("ts", _now_iso())
        line = json.dumps(ev, separators=(",",":")) + "\n"
        with EVENTS_FILE.open("a") as f:
            f.write(line)
    return ev

def rules_get()->List[Dict]:
    _ensure_dirs()
    j = json.loads(RULES_FILE.read_text() or '{"rules":[]}')
    return j.get("rules", [])

def rules_put(rules:List[Dict])->None:
    _ensure_dirs()
    tmp = RULES_FILE.with_suffix(".tmp.json")
    payload = {"updated_at": _now_iso(), "rules": rules}
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(RULES_FILE)

def upsert_rule(rule:Dict)->Dict:
    """Create or update a rule. Required fields: name, p_min, p_std_max. Optional: run_scope, channels, muted."""
    rules = rules_get()
    if not rule.get("id"):
        rule["id"] = str(uuid.uuid4())
        rule["created_at"] = _now_iso()
    rule["updated_at"] = _now_iso()
    # defaults
    rule.setdefault("run_scope","*")
    rule.setdefault("muted", False)
    rule.setdefault("channels", {})
    # replace if id matches else append
    out = []
    found = False
    for r in rules:
        if r.get("id")==rule["id"]:
            out.append(rule); found=True
        else:
            out.append(r)
    if not found: out.append(rule)
    rules_put(out)
    return rule

def delete_rule(rule_id:str)->bool:
    rules = rules_get()
    out = [r for r in rules if r.get("id")!=rule_id]
    if len(out)==len(rules): return False
    rules_put(out); return True

def set_rule_muted(rule_id:str, muted:bool)->bool:
    rules = rules_get()
    changed=False
    for r in rules:
        if r.get("id")==rule_id:
            r["muted"]=bool(muted)
            r["updated_at"]=_now_iso()
            changed=True
    if changed: rules_put(rules)
    return changed

def channel_health()->Dict:
    """Lightweight summary of available channels from rules."""
    rules = rules_get()
    slack = any(r.get("channels",{}).get("slack_webhook") for r in rules)
    hook  = any(r.get("channels",{}).get("webhook_url") for r in rules)
    return {"slack_webhook_configured": slack, "webhook_configured": hook}

def outbox_write(name:str, payload:Dict)->Path:
    _ensure_dirs()
    ts = _now_iso().replace(":","").replace("-","")
    p = OUTBOX_DIR / f"{ts}_{name}.json"
    p.write_text(json.dumps(payload, indent=2))
    return p
