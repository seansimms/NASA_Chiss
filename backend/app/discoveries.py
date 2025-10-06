"""
Discoveries API - Multi-sector search results
"""
from __future__ import annotations
import json
import numpy as np
from pathlib import Path
from typing import List, Optional, Dict, Any
from .models import JobInfo
from .storage import list_jobs, load_job
from .lightcurve_utils import (
    load_lightcurve_npz,
    decimate_lightcurve,
    compute_phase_fold,
    compute_transit_model,
    identify_sector_boundaries,
    compute_lightcurve_stats
)
from .vetting_utils import generate_vetting_report
from .diagnostics_utils import generate_diagnostics_report

def list_discoveries() -> List[Dict[str, Any]]:
    """
    List all completed multi-sector searches with key metrics.
    Returns list of discovery summaries sorted by most recent first.
    """
    jobs = list_jobs()
    discoveries = []
    
    for job in jobs:
        if job.job_type != "multi-sector":
            continue
        
        # Only include succeeded jobs
        if job.state != "succeeded":
            continue
        
        # Try to load search results
        try:
            result = load_discovery_result(job.job_id)
            if result:
                discoveries.append({
                    "job_id": job.job_id,
                    "tic_id": result.get("tic_id"),
                    "created_at": job.created_at,
                    "started_at": job.started_at,
                    "finished_at": job.finished_at,
                    "duration_seconds": (job.finished_at - job.started_at) if (job.finished_at and job.started_at) else None,
                    "n_sectors": result.get("n_sectors"),
                    "n_points": result.get("n_points"),
                    "timespan_days": result.get("timespan_days"),
                    # TLS results
                    "period": _safe_get_tls(result, "period"),
                    "depth": _safe_get_tls(result, "depth"),
                    "duration": _safe_get_tls(result, "duration"),
                    "sde": _safe_get_tls(result, "SDE"),
                    "snr": _safe_get_tls(result, "snr"),
                    "t0": _safe_get_tls(result, "T0"),
                    # Detection quality
                    "skipped": result.get("tls", {}).get("skipped", False),
                    "status": "completed" if not result.get("tls", {}).get("skipped") else "no_detection",
                })
        except Exception as e:
            # Job completed but results couldn't be loaded
            discoveries.append({
                "job_id": job.job_id,
                "tic_id": job.params.get("tic"),
                "created_at": job.created_at,
                "status": "error",
                "error": str(e)
            })
    
    # Sort by most recent first
    discoveries.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    
    return discoveries


def get_discovery_detail(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Get complete discovery details for a specific multi-sector search.
    """
    job = load_job(job_id)
    if not job:
        return None
    
    if job.job_type != "multi-sector":
        return None
    
    result = load_discovery_result(job_id)
    if not result:
        return None
    
    return {
        "job_id": job_id,
        "job": {
            "state": job.state,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "params": job.params,
            "artifacts_dir": job.artifacts_dir,
            "log_path": job.log_path,
        },
        "search_results": result,
        # Convenience fields for frontend
        "tic_id": result.get("tic_id"),
        "n_sectors": result.get("n_sectors"),
        "n_points": result.get("n_points"),
        "timespan_days": result.get("timespan_days"),
        "period_range": result.get("period_range"),
        "grid_meta": result.get("grid_meta"),
        "tls": result.get("tls"),
    }


def load_discovery_result(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Load the search results JSON for a multi-sector job.
    """
    job = load_job(job_id)
    if not job:
        return None
    
    # Find the search results JSON file
    artifacts_dir = Path(job.artifacts_dir) / "multi_sector"
    if not artifacts_dir.exists():
        return None
    
    # Look for TIC_*_search.json
    search_files = list(artifacts_dir.glob("TIC_*_search.json"))
    if not search_files:
        return None
    
    # Load the first (should be only) search result
    with open(search_files[0], 'r') as f:
        return json.load(f)


def get_discovery_lightcurve(job_id: str) -> Optional[str]:
    """
    Get path to the NPZ file containing the stitched light curve.
    """
    job = load_job(job_id)
    if not job:
        return None
    
    artifacts_dir = Path(job.artifacts_dir) / "multi_sector"
    if not artifacts_dir.exists():
        return None
    
    # Look for TIC_*_stitched.npz
    npz_files = list(artifacts_dir.glob("TIC_*_stitched.npz"))
    if not npz_files:
        return None
    
    return str(npz_files[0])


def _safe_get_tls(result: Dict, key: str) -> Optional[float]:
    """
    Safely extract TLS metric, handling various formats and None values.
    """
    tls = result.get("tls", {})
    value = tls.get(key)
    
    if value is None or value == "None":
        return None
    
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def get_lightcurve_data(job_id: str, max_points: int = 10000) -> Optional[Dict[str, Any]]:
    """
    Get decimated light curve data for visualization.
    
    Args:
        job_id: Job ID for the multi-sector search
        max_points: Maximum points to return (for performance)
    
    Returns:
        Dict with time, flux, sectors, and stats
    """
    npz_path = get_discovery_lightcurve(job_id)
    if not npz_path:
        return None
    
    try:
        # Load full light curve
        time, flux = load_lightcurve_npz(npz_path)
        
        # Get discovery details for transit parameters
        detail = get_discovery_detail(job_id)
        period = detail.get('tls', {}).get('period') if detail else None
        duration = detail.get('tls', {}).get('duration') if detail else None
        
        # Parse to float if they're strings
        if period and isinstance(period, str):
            period = float(period)
        if duration and isinstance(duration, str):
            duration = float(duration)
        
        # Decimate with transit preservation
        time_dec, flux_dec = decimate_lightcurve(
            time, flux, 
            max_points=max_points,
            period=period,
            duration=duration
        )
        
        # Identify sectors
        sectors = identify_sector_boundaries(time_dec, gap_threshold=3.0)
        
        # Compute stats
        stats = compute_lightcurve_stats(time, flux)
        
        return {
            'time': time_dec.tolist(),
            'flux': flux_dec.tolist(),
            'sectors': sectors,
            'stats': stats,
            'decimated': len(time_dec) < len(time),
            'original_n_points': len(time),
            'returned_n_points': len(time_dec)
        }
    
    except Exception as e:
        return {'error': str(e)}


def get_phase_fold_data(job_id: str, n_bins: int = 200) -> Optional[Dict[str, Any]]:
    """
    Get phase-folded light curve data for transit visualization.
    
    Args:
        job_id: Job ID for the multi-sector search
        n_bins: Number of bins for phase folding
    
    Returns:
        Dict with phase-folded data and transit model
    """
    npz_path = get_discovery_lightcurve(job_id)
    if not npz_path:
        return None
    
    detail = get_discovery_detail(job_id)
    if not detail or not detail.get('tls'):
        return None
    
    tls = detail['tls']
    
    # Extract parameters (handle both TLS and BLS field names)
    period = tls.get('period') or tls.get('best_period')
    t0 = tls.get('T0') or tls.get('t0') or tls.get('best_t0')
    depth = tls.get('depth') or tls.get('best_depth')
    duration = tls.get('duration') or tls.get('best_duration')
    
    # Parse to float if needed
    if period and isinstance(period, str):
        period = float(period) if period != "None" else None
    if t0 and isinstance(t0, str):
        t0 = float(t0) if t0 != "None" else None
    if depth and isinstance(depth, str):
        depth = float(depth) if depth != "None" else None
    if duration and isinstance(duration, str):
        duration = float(duration) if duration != "None" else None
    
    # Check we have required params
    if not (period and t0 and depth and duration):
        return {'error': 'Missing required transit parameters'}
    
    try:
        # Load light curve
        time, flux = load_lightcurve_npz(npz_path)
        
        # Phase fold
        phase_data = compute_phase_fold(
            time, flux,
            period=period,
            t0=t0,
            duration=duration,
            n_bins=n_bins
        )
        
        # Generate model overlay
        phase_model = np.linspace(-0.5, 0.5, 1000)
        duration_phase = duration / period
        flux_model = compute_transit_model(phase_model, depth, duration_phase)
        
        phase_data['phase_model'] = phase_model.tolist()
        phase_data['flux_model'] = flux_model.tolist()
        phase_data['period'] = period
        phase_data['t0'] = t0
        phase_data['depth'] = depth
        phase_data['duration'] = duration
        
        return phase_data
    
    except Exception as e:
        return {'error': str(e)}


def get_vetting_data(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Get comprehensive vetting report for a discovery.
    
    Args:
        job_id: Job ID for the multi-sector search
    
    Returns:
        Dict with quality score, data sources, external links, and recommendations
    """
    detail = get_discovery_detail(job_id)
    if not detail:
        return None
    
    try:
        report = generate_vetting_report(detail)
        return report
    except Exception as e:
        return {'error': str(e)}


def get_diagnostics_data(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Get advanced diagnostic tests for a discovery.
    
    Args:
        job_id: Job ID for the multi-sector search
    
    Returns:
        Dict with odd/even test, secondary eclipse search, residuals, shape analysis
    """
    npz_path = get_discovery_lightcurve(job_id)
    if not npz_path:
        return None
    
    detail = get_discovery_detail(job_id)
    if not detail or not detail.get('tls'):
        return None
    
    try:
        # Load light curve
        time, flux = load_lightcurve_npz(npz_path)
        
        # Generate diagnostics
        diagnostics = generate_diagnostics_report(time, flux, detail['tls'])
        
        return diagnostics
    except Exception as e:
        return {'error': str(e), 'available': False}

