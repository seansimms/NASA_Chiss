from __future__ import annotations
import os, sqlite3, json, time
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import pandas as pd

DB_PATH = Path(os.environ.get("DB_PATH", "/tmp/chiss.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def _conn():
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    return con

def init_db():
    con = _conn()
    with con:
        con.execute("""CREATE TABLE IF NOT EXISTS jobs(
            job_id TEXT PRIMARY KEY,
            job_type TEXT, state TEXT,
            created_at REAL, started_at REAL, finished_at REAL,
            params TEXT, artifacts_dir TEXT,
            attempts INTEGER, max_retries INTEGER,
            log_path TEXT, pid INTEGER,
            note TEXT, error TEXT
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS metrics(
            run_id TEXT PRIMARY KEY,
            n INTEGER, n_pos INTEGER,
            auprc REAL, brier REAL, ece REAL,
            recall_small_at_1pct REAL,
            source TEXT, created_at REAL
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS candidates(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT, star TEXT,
            label INTEGER, p_final REAL,
            created_at REAL,
            extra TEXT,
            UNIQUE(run_id, star)
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS artifacts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            star TEXT,
            kind TEXT,      -- lc_raw | phase | odd_even | centroid | dossier | fit | tls_result
            path TEXT,
            size INTEGER,
            mtime REAL,
            created_at REAL,
            UNIQUE(run_id, star, kind, path)
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS metrics_detail(
            run_id TEXT,
            key TEXT,
            value TEXT,
            PRIMARY KEY (run_id, key)
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS api_keys(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            role TEXT CHECK(role IN ('viewer','operator','admin')) NOT NULL,
            salt TEXT NOT NULL,
            hash TEXT NOT NULL,
            revoked INTEGER DEFAULT 0,
            created_at REAL
        )""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_star_kind ON artifacts(star, kind)")
    con.close()

def upsert_job(j: Dict):
    con = _conn()
    with con:
        con.execute("""INSERT INTO jobs(job_id,job_type,state,created_at,started_at,finished_at,params,artifacts_dir,attempts,max_retries,log_path,pid,note,error)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(job_id) DO UPDATE SET
                         job_type=excluded.job_type, state=excluded.state,
                         created_at=excluded.created_at, started_at=excluded.started_at, finished_at=excluded.finished_at,
                         params=excluded.params, artifacts_dir=excluded.artifacts_dir,
                         attempts=excluded.attempts, max_retries=excluded.max_retries,
                         log_path=excluded.log_path, pid=excluded.pid,
                         note=excluded.note, error=excluded.error
        """, (
            j["job_id"], j["job_type"], j["state"],
            j.get("created_at"), j.get("started_at"), j.get("finished_at"),
            json.dumps(j.get("params") or {}), j.get("artifacts_dir"),
            j.get("attempts",0), j.get("max_retries",1),
            j.get("log_path"), j.get("pid"),
            j.get("note"), j.get("error")
        ))
    con.close()

def list_incomplete_jobs()->List[str]:
    con=_conn()
    cur=con.execute("SELECT job_id FROM jobs WHERE state IN ('queued','running')")
    out=[r[0] for r in cur.fetchall()]
    con.close()
    return out

def ingest_metrics(run_id: str, summary: Dict):
    con=_conn()
    with con:
        con.execute("""INSERT INTO metrics(run_id,n,n_pos,auprc,brier,ece,recall_small_at_1pct,source,created_at)
                       VALUES(?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(run_id) DO UPDATE SET
                         n=excluded.n, n_pos=excluded.n_pos,
                         auprc=excluded.auprc, brier=excluded.brier, ece=excluded.ece,
                         recall_small_at_1pct=excluded.recall_small_at_1pct,
                         source=excluded.source, created_at=excluded.created_at
        """, (
            run_id,
            int(summary.get("n",0)), int(summary.get("n_pos",0)),
            float(summary.get("auprc",0.0)), float(summary.get("brier",0.0)),
            float(summary.get("ece",0.0)), summary.get("recall_small_at_1pct"),
            str(summary.get("source","")), time.time()
        ))
    con.close()

def latest_metrics()->Optional[Dict]:
    con=_conn()
    cur=con.execute("SELECT run_id,n,n_pos,auprc,brier,ece,recall_small_at_1pct,source,created_at FROM metrics ORDER BY created_at DESC LIMIT 1")
    row=cur.fetchone()
    con.close()
    if not row: return None
    keys=["run_id","n","n_pos","auprc","brier","ece","recall_small_at_1pct","source","created_at"]
    return dict(zip(keys,row))

def ingest_candidates(run_id: str, csv_path: Path):
    if not csv_path.exists():
        return 0
    df = pd.read_csv(csv_path)
    if "star" not in df.columns or "p_final" not in df.columns:
        return 0
    keep_extra = [c for c in df.columns if c not in ("star","label","p_final")]
    con=_conn()
    inserted=0
    with con:
        for _, row in df.iterrows():
            extra = {k: (None if pd.isna(row[k]) else row[k]) for k in keep_extra}
            con.execute("""INSERT OR IGNORE INTO candidates(run_id,star,label,p_final,created_at,extra)
                           VALUES(?,?,?,?,?,?)""",
                        (run_id, str(row["star"]),
                         (None if "label" not in df.columns or pd.isna(row["label"]) else int(row["label"])),
                         float(row["p_final"]), time.time(), json.dumps(extra)))
            inserted += 1
    con.close()
    return inserted

def query_candidates(limit:int=50, min_p:float=0.0, offset:int=0)->Tuple[int,List[Dict]]:
    con=_conn()
    total = con.execute("SELECT COUNT(*) FROM candidates WHERE p_final >= ?", (min_p,)).fetchone()[0]
    cur = con.execute("""SELECT star,label,p_final,extra FROM candidates
                         WHERE p_final >= ?
                         ORDER BY p_final DESC
                         LIMIT ? OFFSET ?""", (min_p, limit, offset))
    rows=[]
    for star,label,p_final,extra in cur.fetchall():
        rows.append({"star":star,"label":label,"p_final":p_final,"extra":json.loads(extra or "{}")})
    con.close()
    return total, rows

# ---------- Metrics History ----------
def upsert_metrics_detail(run_id: str, details: Dict):
    con=_conn()
    with con:
        for k,v in details.items():
            con.execute("""INSERT INTO metrics_detail(run_id,key,value)
                           VALUES(?,?,?)
                           ON CONFLICT(run_id,key) DO UPDATE SET value=excluded.value
                        """, (run_id, str(k), json.dumps(v)))
    con.close()

def get_metrics_detail(run_id: str)->Dict:
    con=_conn()
    cur=con.execute("SELECT key,value FROM metrics_detail WHERE run_id=?",(run_id,))
    out={}
    for k,v in cur.fetchall():
        try: out[k]=json.loads(v)
        except Exception: out[k]=v
    con.close()
    return out

def list_metrics(limit:int=100, offset:int=0)->List[Dict]:
    con=_conn()
    cur=con.execute("""SELECT run_id,n,n_pos,auprc,brier,ece,recall_small_at_1pct,source,created_at
                       FROM metrics ORDER BY created_at DESC LIMIT ? OFFSET ?""",(limit, offset))
    rows=[]
    cols=["run_id","n","n_pos","auprc","brier","ece","recall_small_at_1pct","source","created_at"]
    for r in cur.fetchall():
        rows.append(dict(zip(cols,r)))
    con.close()
    return rows

def count_metrics()->int:
    con=_conn()
    n = con.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
    con.close()
    return int(n)

def get_metrics_summary(run_id: str)->Dict|None:
    con=_conn()
    cur=con.execute("""SELECT run_id,n,n_pos,auprc,brier,ece,recall_small_at_1pct,source,created_at
                       FROM metrics WHERE run_id=?""",(run_id,))
    row=cur.fetchone()
    con.close()
    if not row: return None
    keys=["run_id","n","n_pos","auprc","brier","ece","recall_small_at_1pct","source","created_at"]
    return dict(zip(keys,row))

def count_candidates_by_run(run_id: str)->int:
    con=_conn()
    n = con.execute("SELECT COUNT(*) FROM candidates WHERE run_id=?",(run_id,)).fetchone()[0]
    con.close()
    return int(n)

# ---------- Artifact Index ----------
import re, os, time
STAR_PAT = re.compile(r'\b((?:TIC|KIC|EPIC)\d{3,})\b', re.IGNORECASE)

def _guess_star_from_path(p: str)->str|None:
    m = STAR_PAT.search(os.path.basename(p))
    return (m.group(1).upper() if m else None)

def _guess_kind(p: str)->str|None:
    name = os.path.basename(p).lower()
    if "odd" in name and "even" in name: return "odd_even"
    if "centroid" in name: return "centroid"
    if "phase" in name: return "phase"
    if "tls" in name and "result" in name: return "tls_result"
    if name.endswith(".html") and "dossier" in name: return "dossier"
    if "fit" in name and (name.endswith(".json") or name.endswith(".csv")): return "fit"
    if ("lc" in name or "lightcurve" in name or "flux" in name) and (name.endswith(".csv") or name.endswith(".json")): return "lc_raw"
    return None

def upsert_artifact(run_id: str, star: str, kind: str, path: str, size:int, mtime:float):
    con=_conn()
    with con:
        con.execute("""INSERT INTO artifacts(run_id,star,kind,path,size,mtime,created_at)
                       VALUES(?,?,?,?,?,?,?)
                       ON CONFLICT(run_id,star,kind,path) DO UPDATE SET
                         size=excluded.size, mtime=excluded.mtime""",
                    (run_id, star, kind, path, size, mtime, time.time()))
    con.close()

from pathlib import Path
def bulk_index_dir(run_id: str, root: Path, star_hint: str|None=None)->int:
    if not root.exists(): return 0
    cnt=0
    for p in root.rglob("*"):
        if not p.is_file(): continue
        kind = _guess_kind(p.name)
        if not kind: continue
        star = (star_hint or _guess_star_from_path(str(p)))
        if not star: continue
        try:
            st = p.stat()
            upsert_artifact(run_id, star, kind, str(p), st.st_size, st.st_mtime)
            cnt += 1
        except Exception:
            pass
    return cnt

def list_artifacts_for_star(star: str)->List[Dict]:
    con=_conn()
    cur=con.execute("""SELECT run_id, kind, path, size, mtime
                       FROM artifacts WHERE star = ? ORDER BY mtime DESC""",(star.upper(),))
    rows=[{"run_id":r[0], "star":star.upper(), "kind":r[1], "path":r[2], "size":r[3], "mtime":r[4]} for r in cur.fetchall()]
    con.close()
    return rows

# ---------- API Keys ----------
def api_keys_insert(name:str, role:str, salt:str, hash_:str)->int:
    con=_conn()
    with con:
        cur = con.execute("""INSERT INTO api_keys(name,role,salt,hash,revoked,created_at)
                             VALUES(?,?,?,?,0,?)""",(name,role,salt,hash_,time.time()))
        key_id = cur.lastrowid
    con.close()
    return int(key_id)

def api_keys_list()->List[Dict]:
    con=_conn()
    cur = con.execute("SELECT id,name,role,revoked,created_at FROM api_keys ORDER BY id DESC")
    rows=[{"id":r[0],"name":r[1],"role":r[2],"revoked":int(r[3]),"created_at":r[4]} for r in cur.fetchall()]
    con.close(); return rows

def api_keys_get_by_id(key_id:int)->Optional[Dict]:
    con=_conn()
    cur=con.execute("SELECT id,name,role,salt,hash,revoked,created_at FROM api_keys WHERE id=?",(key_id,))
    r=cur.fetchone(); con.close()
    if not r: return None
    return {"id":r[0],"name":r[1],"role":r[2],"salt":r[3],"hash":r[4],"revoked":int(r[5]),"created_at":r[6]}

def api_keys_all_material()->List[Dict]:
    con=_conn()
    cur=con.execute("SELECT id,role,salt,hash,revoked FROM api_keys")
    rows=[{"id":r[0],"role":r[1],"salt":r[2],"hash":r[3],"revoked":int(r[4])} for r in cur.fetchall()]
    con.close(); return rows

def api_keys_revoke(key_id:int)->bool:
    con=_conn()
    with con:
        cur = con.execute("UPDATE api_keys SET revoked=1 WHERE id=?",(key_id,))
    con.close()
    return cur.rowcount>0
