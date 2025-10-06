from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict

JobType = Literal["setup-bootstrap","setup-data-pipeline","full-pipeline","train-kepler-strict","benchmarks-compare","hardening-suite-strict","multi-sector"]
JobState = Literal["queued","running","succeeded","failed"]

class StartJobRequest(BaseModel):
    job_type: JobType
    params: Dict[str, str] = Field(default_factory=dict)

class JobInfo(BaseModel):
    job_id: str
    job_type: JobType
    state: JobState
    created_at: float
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    params: Dict[str,str] = Field(default_factory=dict)
    artifacts_dir: str
    note: Optional[str] = None
    attempts: int = 0
    max_retries: int = 1
    log_path: Optional[str] = None
    pid: Optional[int] = None
    error: Optional[str] = None

class JobList(BaseModel):
    jobs: List[JobInfo]

