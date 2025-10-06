from __future__ import annotations
import json, os, time, uuid
from pathlib import Path
from typing import Dict, Optional, List
from .models import JobInfo, JobType
from .db import upsert_job

JOB_ROOT = Path(os.environ.get("JOB_ROOT","/tmp/jobdata"))
JOB_ROOT.mkdir(parents=True, exist_ok=True)

def _job_dir(job_id:str)->Path: return JOB_ROOT / job_id
def _job_json(job_id:str)->Path: return _job_dir(job_id)/"job.json"
def _job_log(job_id:str)->Path: return _job_dir(job_id)/"run.log"
def _job_cancel(job_id:str)->Path: return _job_dir(job_id)/"cancel.flag"

def create_job(job_type: JobType, params: Dict[str,str], artifacts_root: Path)->JobInfo:
    job_id = f"job-{int(time.time())}-{uuid.uuid4().hex[:12]}"
    d = _job_dir(job_id); d.mkdir(parents=True, exist_ok=True)
    info = JobInfo(
        job_id=job_id, job_type=job_type, state="queued",
        created_at=time.time(), artifacts_dir=str(artifacts_root / job_id),
        params=params, max_retries=int(os.environ.get("JOB_MAX_RETRIES","1")),
        log_path=str(_job_log(job_id))
    )
    (artifacts_root / job_id).mkdir(parents=True, exist_ok=True)
    _job_json(job_id).write_text(info.model_dump_json(indent=2), encoding="utf-8")
    return info

def save_job(info: JobInfo)->None:
    _job_json(info.job_id).write_text(info.model_dump_json(indent=2), encoding="utf-8")
    # persist in DB as well
    upsert_job(info.model_dump())

def load_job(job_id: str)->Optional[JobInfo]:
    p=_job_json(job_id)
    if not p.exists(): return None
    return JobInfo.model_validate_json(p.read_text(encoding="utf-8"))

def list_jobs()->List[JobInfo]:
    out=[]
    for p in JOB_ROOT.iterdir():
        if (p/_job_json(p.name).name).exists():
            out.append(load_job(p.name))
    out.sort(key=lambda j: j.created_at if j else 0, reverse=True)
    return [j for j in out if j]

def running_jobs()->List[JobInfo]:
    return [j for j in list_jobs() if j and j.state=="running"]

def has_duplicate_running(job_type: JobType, params: Dict[str,str])->Optional[JobInfo]:
    for j in running_jobs():
        if j.job_type==job_type and j.params==params:
            return j
    return None

def append_log(job_id: str, line: str)->None:
    lp = _job_log(job_id); lp.parent.mkdir(parents=True, exist_ok=True)
    with lp.open("a", encoding="utf-8") as f:
        f.write(line.rstrip()+"\n")

def mark_cancel(job_id: str)->None:
    _job_cancel(job_id).write_text("1", encoding="utf-8")

def is_cancelled(job_id: str)->bool:
    return _job_cancel(job_id).exists()
