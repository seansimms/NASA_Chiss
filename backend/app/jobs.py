from __future__ import annotations
import asyncio, os, time, signal, json
from pathlib import Path
from typing import Dict, List, Optional
from .models import JobInfo
from .storage import save_job, append_log, is_cancelled
from .metrics import read_metrics
from .db import ingest_candidates, ingest_metrics, bulk_index_dir, upsert_metrics_detail

ARTIFACTS_ROOT = Path(os.environ.get("ARTIFACTS_ROOT","/app/artifacts"))
PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/app"))

def _cmd_for_job(info: JobInfo)->List[str]:
    """Build command for job type. For demo mode, we simulate jobs."""
    
    # For demo purposes, we'll simulate job execution
    # In a full deployment, these would call the actual chiss CLI commands
    
    if info.job_type=="multi-sector":
        # Simulate a multi-sector search
        return ["python", "-c", "import time; print('Starting multi-sector search...'); time.sleep(5); print('Search complete')"]
    
    if info.job_type=="train-kepler-strict":
        return ["python", "-c", "import time; print('Training model...'); time.sleep(10); print('Training complete')"]
    
    if info.job_type=="benchmarks-compare":
        return ["python", "-c", "import time; print('Running benchmarks...'); time.sleep(8); print('Benchmarks complete')"]
    
    if info.job_type=="hardening-suite-strict":
        return ["python", "-c", "import time; print('Running hardening suite...'); time.sleep(12); print('Hardening complete')"]
    
    if info.job_type=="full-pipeline":
        return ["python", "-c", "import time; print('Running full pipeline...'); time.sleep(20); print('Pipeline complete')"]
    
    if info.job_type=="setup-bootstrap":
        return ["python", "-c", "import time; print('Bootstrapping environment...'); time.sleep(3); print('Bootstrap complete')"]
    
    if info.job_type=="setup-data-pipeline":
        return ["python", "-c", "import time; print('Setting up data pipeline...'); time.sleep(5); print('Data pipeline ready')"]
    
    # Default demo job
    return ["python", "-c", f"import time; print('Running {info.job_type}...'); time.sleep(5); print('Job complete')"]

async def run_job(info: JobInfo):
    """Execute a job in demo mode."""
    try:
        append_log(info.job_id, f"🚀 Starting job: {info.job_type}")
        append_log(info.job_id, f"📋 Job ID: {info.job_id}")
        
        if info.params:
            append_log(info.job_id, f"⚙️  Parameters: {json.dumps(info.params, indent=2)}")
        
        # Update status
        info.state = "running"
        save_job(info)
        
        # Build and execute command
        cmd = _cmd_for_job(info)
        append_log(info.job_id, f"🔧 Running command: {' '.join(cmd)}")
        
        # Execute in demo mode
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(PROJECT_ROOT)
        )
        
        # Stream output
        while True:
            if is_cancelled(info.job_id):
                append_log(info.job_id, "⚠️  Job cancelled by user")
                proc.terminate()
                await proc.wait()
                info.state = "cancelled"
                save_job(info)
                return
            
            line = await proc.stdout.readline()
            if not line:
                break
            
            line_text = line.decode().strip()
            if line_text:
                append_log(info.job_id, line_text)
        
        # Wait for completion
        await proc.wait()
        
        if proc.returncode == 0:
            append_log(info.job_id, "✅ Job completed successfully")
            info.state = "completed"
            
            # Create demo artifacts
            artifacts_dir = Path(info.artifacts_dir)
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            
            # Create a sample result file
            result_file = artifacts_dir / "result.json"
            result_data = {
                "job_id": info.job_id,
                "job_type": info.job_type,
                "params": info.params,
                "status": "success",
                "message": "Demo job completed successfully"
            }
            result_file.write_text(json.dumps(result_data, indent=2))
            
            append_log(info.job_id, f"📦 Artifacts saved to: {info.artifacts_dir}")
        else:
            append_log(info.job_id, f"❌ Job failed with exit code: {proc.returncode}")
            info.state = "failed"
            info.note = f"Exit code: {proc.returncode}"
        
        save_job(info)
        
    except Exception as e:
        append_log(info.job_id, f"❌ Error: {str(e)}")
        info.state = "failed"
        info.note = str(e)
        save_job(info)
