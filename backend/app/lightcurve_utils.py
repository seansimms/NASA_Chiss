"""
Light curve data processing utilities for discoveries visualization.
"""
from __future__ import annotations
import numpy as np
from typing import Dict, List, Tuple, Optional
from pathlib import Path


def load_lightcurve_npz(npz_path: str) -> Tuple[np.ndarray, np.ndarray]:
    """Load time and flux arrays from NPZ file."""
    data = np.load(npz_path)
    time = data['time']
    flux = data['flux']
    return time, flux


def decimate_lightcurve(
    time: np.ndarray, 
    flux: np.ndarray, 
    max_points: int = 10000,
    period: Optional[float] = None,
    duration: Optional[float] = None
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Intelligently decimate light curve preserving transits.
    
    Strategy:
    - If period/duration known: keep all points near transits, downsample rest
    - Otherwise: uniform decimation with slight randomization for visual smoothness
    """
    n = len(time)
    if n <= max_points:
        return time, flux
    
    # Remove NaN values
    mask = np.isfinite(time) & np.isfinite(flux)
    time = time[mask]
    flux = flux[mask]
    n = len(time)
    
    if period and duration and period > 0 and duration > 0:
        # Identify transit windows (±2 durations around each predicted transit)
        t0 = time[0]
        phase = ((time - t0) % period) / period
        # Transits occur near phase 0 and 1
        transit_window = 2 * duration / period  # Fractional window
        near_transit = (phase < transit_window) | (phase > (1 - transit_window))
        
        # Keep all transit points
        transit_idx = np.where(near_transit)[0]
        non_transit_idx = np.where(~near_transit)[0]
        
        # Downsample non-transit points
        n_keep_transit = len(transit_idx)
        n_keep_non_transit = max_points - n_keep_transit
        
        if n_keep_non_transit > 0 and len(non_transit_idx) > n_keep_non_transit:
            # Random sampling for smooth appearance
            keep_non_transit = np.random.choice(
                non_transit_idx, 
                size=n_keep_non_transit, 
                replace=False
            )
            keep_idx = np.sort(np.concatenate([transit_idx, keep_non_transit]))
        else:
            keep_idx = np.sort(transit_idx)
        
        return time[keep_idx], flux[keep_idx]
    
    else:
        # Uniform decimation with slight jitter
        stride = n // max_points
        indices = np.arange(0, n, stride)
        # Add small random offset for visual smoothness
        jitter = np.random.randint(-stride//4, stride//4, size=len(indices))
        indices = np.clip(indices + jitter, 0, n-1)
        indices = np.unique(indices)  # Remove duplicates
        return time[indices], flux[indices]


def compute_phase_fold(
    time: np.ndarray,
    flux: np.ndarray,
    period: float,
    t0: float,
    duration: float,
    n_bins: int = 200
) -> Dict:
    """
    Compute phase-folded light curve with binning.
    
    Returns:
        dict with:
        - phase_raw: individual phase points
        - flux_raw: individual flux points
        - phase_binned: binned phase centers
        - flux_binned: binned flux means
        - flux_binned_std: binned flux standard deviations
    """
    # Compute phase (centered at 0)
    phase = ((time - t0) % period) / period
    phase[phase > 0.5] -= 1  # Center at 0 (range: -0.5 to 0.5)
    
    # Sort by phase
    sort_idx = np.argsort(phase)
    phase = phase[sort_idx]
    flux = flux[sort_idx]
    
    # Bin the data
    bin_edges = np.linspace(-0.5, 0.5, n_bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    
    flux_binned = []
    flux_binned_std = []
    
    for i in range(n_bins):
        mask = (phase >= bin_edges[i]) & (phase < bin_edges[i+1])
        if np.sum(mask) > 0:
            flux_binned.append(np.nanmean(flux[mask]))
            flux_binned_std.append(np.nanstd(flux[mask]))
        else:
            flux_binned.append(np.nan)
            flux_binned_std.append(np.nan)
    
    return {
        'phase_raw': phase.tolist(),
        'flux_raw': flux.tolist(),
        'phase_binned': bin_centers.tolist(),
        'flux_binned': [float(x) if not np.isnan(x) else None for x in flux_binned],
        'flux_binned_std': [float(x) if not np.isnan(x) else None for x in flux_binned_std],
        'n_points': len(phase),
        'n_bins': n_bins
    }


def compute_transit_model(
    phase: np.ndarray,
    depth: float,
    duration_phase: float
) -> np.ndarray:
    """
    Simple box model for transit overlay.
    
    Args:
        phase: Phase array (centered at 0)
        depth: Transit depth (fractional, not ppm)
        duration_phase: Transit duration as fraction of period
    """
    model = np.ones_like(phase)
    
    # Box transit
    in_transit = np.abs(phase) < (duration_phase / 2)
    model[in_transit] = 1 - depth
    
    return model


def identify_sector_boundaries(
    time: np.ndarray,
    gap_threshold: float = 3.0
) -> List[Tuple[int, int]]:
    """
    Identify sector boundaries based on data gaps.
    
    Args:
        time: Time array (days)
        gap_threshold: Gap size (days) to identify sector breaks
    
    Returns:
        List of (start_idx, end_idx) tuples for each sector
    """
    if len(time) == 0:
        return []
    
    # Find gaps
    dt = np.diff(time)
    gap_idx = np.where(dt > gap_threshold)[0]
    
    # Define sectors (convert numpy int64 to Python int for JSON serialization)
    sectors = []
    start = 0
    for gap in gap_idx:
        sectors.append((int(start), int(gap + 1)))
        start = int(gap + 1)
    sectors.append((int(start), int(len(time))))
    
    return sectors


def compute_lightcurve_stats(time: np.ndarray, flux: np.ndarray) -> Dict:
    """Compute basic statistics for light curve."""
    return {
        'n_points': int(len(time)),
        'time_min': float(np.min(time)),
        'time_max': float(np.max(time)),
        'timespan_days': float(np.max(time) - np.min(time)),
        'flux_median': float(np.nanmedian(flux)),
        'flux_std': float(np.nanstd(flux)),
        'flux_min': float(np.nanmin(flux)),
        'flux_max': float(np.nanmax(flux)),
    }

