from __future__ import annotations
import asyncio, os, signal, time
from typing import Dict, Optional
from pathlib import Path
from .models import JobInfo, JobType
from .storage import save_job, append_log, is_cancelled, list_jobs
from .jobs import exec_process, ARTIFACTS_ROOT

MAX_CONCURRENCY = int(os.environ.get("JOB_MAX_CONCURRENCY","2"))
BACKOFF_BASE = int(os.environ.get("JOB_BACKOFF_BASE_SEC","2"))
TERM_GRACE = int(os.environ.get("JOB_TERM_GRACE_SEC","20"))

class Orchestrator:
    def __init__(self):
        self.q: asyncio.Queue[JobInfo] = asyncio.Queue()
        self.workers: list[asyncio.Task] = []
        self.running: Dict[str, JobInfo] = {}
        self._shutdown = asyncio.Event()

    async def start(self):
        for _ in range(MAX_CONCURRENCY):
            self.workers.append(asyncio.create_task(self._worker()))

    async def stop(self):
        self._shutdown.set()
        for _ in self.workers:
            await self.q.put(None)  # poison pills
        await asyncio.gather(*self.workers, return_exceptions=True)

    async def enqueue(self, info: JobInfo):
        await self.q.put(info)

    async def _worker(self):
        while not self._shutdown.is_set():
            info = await self.q.get()
            if info is None: break
            self.running[info.job_id] = info
            try:
                await self._run_with_retries(info)
            finally:
                self.running.pop(info.job_id, None)
                self.q.task_done()

    async def _run_with_retries(self, info: JobInfo):
        attempt = 0
        while attempt <= info.max_retries:
            attempt += 1
            info.attempts = attempt - 1
            save_job(info)
            rc, err = await exec_process(info, term_grace=TERM_GRACE)
            if rc == 0:
                return
            # failure
            if is_cancelled(info.job_id):
                append_log(info.job_id, f"INFO Job {info.job_id} cancelled during attempt {attempt}.")
                return
            if attempt > info.max_retries:
                append_log(info.job_id, f"ERROR Job {info.job_id} failed after {attempt} attempt(s). Last error: {err or ''}")
                return
            backoff = min(BACKOFF_BASE ** (attempt-1), 60)
            append_log(info.job_id, f"WARN Job {info.job_id} failed (attempt {attempt}); retrying in {backoff}s.")
            await asyncio.sleep(backoff)

    def stats(self):
        return {
            "queue_depth": self.q.qsize(),
            "running": list(self.running.keys()),
            "concurrency": MAX_CONCURRENCY,
        }

orchestrator = Orchestrator()
