"""
Advanced diagnostic utilities for candidate validation.
"""
from __future__ import annotations
import numpy as np
from typing import Dict, Any, Optional, Tuple, List
from scipy import stats


def compute_odd_even_diagnostic(
    time: np.ndarray,
    flux: np.ndarray,
    period: float,
    t0: float,
    duration: float
) -> Dict[str, Any]:
    """
    Compare odd and even transits to detect eclipsing binaries.
    
    Eclipsing binaries show different depths for odd/even transits.
    True planets should show consistent depths.
    
    Returns:
        dict with:
        - odd_depth: Depth from odd-numbered transits
        - even_depth: Depth from even-numbered transits
        - depth_difference: Absolute difference
        - depth_ratio: Ratio (should be ~1 for planets)
        - chi_squared: Statistical test
        - p_value: Probability they're from same distribution
        - verdict: pass/warn/fail
    """
    # Phase fold the data
    phase = ((time - t0) % period) / period
    phase[phase > 0.5] -= 1  # Center at 0
    
    # Identify transits
    in_transit = np.abs(phase) < (duration / period / 2)
    
    if np.sum(in_transit) < 10:
        return {
            'error': 'Too few transit points for odd/even analysis',
            'verdict': 'insufficient_data'
        }
    
    # Separate odd and even transits
    transit_numbers = np.floor((time[in_transit] - t0) / period).astype(int)
    odd_mask = transit_numbers % 2 == 1
    even_mask = transit_numbers % 2 == 0
    
    flux_odd = flux[in_transit][odd_mask]
    flux_even = flux[in_transit][even_mask]
    
    if len(flux_odd) < 3 or len(flux_even) < 3:
        return {
            'error': 'Insufficient odd or even transits',
            'verdict': 'insufficient_data'
        }
    
    # Compute depths (relative to 1.0 normalized flux)
    odd_depth = 1.0 - np.median(flux_odd)
    even_depth = 1.0 - np.median(flux_even)
    
    # Statistical comparison
    _, p_value = stats.mannwhitneyu(flux_odd, flux_even, alternative='two-sided')
    
    depth_diff = abs(odd_depth - even_depth)
    depth_ratio = odd_depth / even_depth if even_depth > 0 else 0
    
    # Verdict
    if depth_diff < 0.0001:  # < 100 ppm difference
        verdict = 'pass'
        message = 'Consistent transit depths (likely planet)'
    elif depth_diff < 0.0005:  # < 500 ppm difference
        verdict = 'warn'
        message = 'Small depth variation (investigate further)'
    else:
        verdict = 'fail'
        message = 'Significant depth variation (possible eclipsing binary)'
    
    return {
        'odd_depth': float(odd_depth),
        'even_depth': float(even_depth),
        'odd_depth_ppm': float(odd_depth * 1e6),
        'even_depth_ppm': float(even_depth * 1e6),
        'depth_difference': float(depth_diff),
        'depth_difference_ppm': float(depth_diff * 1e6),
        'depth_ratio': float(depth_ratio),
        'p_value': float(p_value),
        'n_odd_transits': int(np.sum(odd_mask)),
        'n_even_transits': int(np.sum(even_mask)),
        'verdict': verdict,
        'message': message
    }


def search_secondary_eclipse(
    time: np.ndarray,
    flux: np.ndarray,
    period: float,
    t0: float,
    depth: float,
    duration: float
) -> Dict[str, Any]:
    """
    Search for secondary eclipse at phase 0.5.
    
    Planets: no secondary eclipse (or very shallow)
    Eclipsing binaries: secondary eclipse at phase 0.5
    
    Returns:
        dict with:
        - detected: bool
        - phase: 0.5 (expected location)
        - depth: Depth at phase 0.5
        - depth_ratio: Secondary/Primary ratio
        - significance: Statistical significance
        - verdict: planet/eb/uncertain
    """
    # Phase fold
    phase = ((time - t0) % period) / period
    phase[phase > 0.5] -= 1  # Center at 0
    
    # Define secondary eclipse window (phase ~0.5 or ~-0.5)
    secondary_window = 0.05  # 5% of period on each side
    near_secondary = (np.abs(phase - 0.5) < secondary_window) | (np.abs(phase + 0.5) < secondary_window)
    
    # Out-of-transit baseline (exclude primary and secondary)
    primary_window = duration / period / 2
    near_primary = np.abs(phase) < primary_window
    out_of_transit = ~near_primary & ~near_secondary
    
    if np.sum(near_secondary) < 5 or np.sum(out_of_transit) < 10:
        return {
            'error': 'Insufficient data for secondary eclipse search',
            'verdict': 'insufficient_data'
        }
    
    # Compute depths
    flux_secondary = flux[near_secondary]
    flux_baseline = flux[out_of_transit]
    
    secondary_depth = 1.0 - np.median(flux_secondary)
    baseline_std = np.std(flux_baseline)
    
    # Significance (in units of baseline noise)
    significance = abs(secondary_depth) / baseline_std if baseline_std > 0 else 0
    
    # Ratio to primary
    depth_ratio = abs(secondary_depth / depth) if depth > 0 else 0
    
    # Verdict
    detected = bool(significance > 3.0)  # 3-sigma detection, convert to Python bool
    
    if not detected:
        verdict = 'planet'
        message = 'No secondary eclipse detected (consistent with planet)'
    elif depth_ratio > 0.5:
        verdict = 'eb'
        message = 'Strong secondary eclipse (likely eclipsing binary)'
    elif depth_ratio > 0.1:
        verdict = 'uncertain'
        message = 'Weak secondary eclipse (investigate further)'
    else:
        verdict = 'planet'
        message = 'Very shallow secondary (likely planet with reflected light)'
    
    return {
        'detected': detected,
        'secondary_depth': float(secondary_depth),
        'secondary_depth_ppm': float(abs(secondary_depth) * 1e6),
        'primary_depth_ppm': float(depth * 1e6),
        'depth_ratio': float(depth_ratio),
        'significance_sigma': float(significance),
        'n_secondary_points': int(np.sum(near_secondary)),
        'verdict': verdict,
        'message': message
    }


def compute_model_residuals(
    time: np.ndarray,
    flux: np.ndarray,
    period: float,
    t0: float,
    depth: float,
    duration: float
) -> Dict[str, Any]:
    """
    Compute residuals after removing transit model.
    
    Returns:
        dict with:
        - residuals: Residual flux values
        - rms: Root mean square of residuals
        - chi_squared: Chi-squared statistic
        - normality_test: Test if residuals are normally distributed
    """
    # Generate simple box model
    phase = ((time - t0) % period) / period
    phase[phase > 0.5] -= 1
    
    model = np.ones_like(flux)
    in_transit = np.abs(phase) < (duration / period / 2)
    model[in_transit] = 1.0 - depth
    
    # Compute residuals
    residuals = flux - model
    
    rms = float(np.sqrt(np.mean(residuals**2)))
    chi_squared = float(np.sum((residuals / rms)**2))
    
    # Normality test (Shapiro-Wilk)
    # Only test on sample if data is large
    sample_size = min(5000, len(residuals))
    sample_idx = np.random.choice(len(residuals), sample_size, replace=False)
    _, normality_p = stats.shapiro(residuals[sample_idx])
    
    is_normal = bool(normality_p > 0.05)  # Convert to Python bool
    
    return {
        'rms': rms,
        'rms_ppm': float(rms * 1e6),
        'chi_squared': chi_squared,
        'reduced_chi_squared': float(chi_squared / (len(residuals) - 4)),
        'normality_p_value': float(normality_p),
        'is_normal': is_normal,
        'n_points': len(residuals)
    }


def compute_transit_shape_metrics(
    time: np.ndarray,
    flux: np.ndarray,
    period: float,
    t0: float,
    duration: float
) -> Dict[str, Any]:
    """
    Analyze the shape of individual transits.
    
    V-shaped: Likely eclipsing binary
    U-shaped: Likely planet
    
    Returns:
        dict with shape metrics
    """
    # Phase fold
    phase = ((time - t0) % period) / period
    phase[phase > 0.5] -= 1
    
    # Focus on transit region
    in_transit = np.abs(phase) < (duration / period / 2 * 1.5)  # Slightly wider window
    
    if np.sum(in_transit) < 10:
        return {
            'error': 'Insufficient transit points',
            'verdict': 'insufficient_data'
        }
    
    phase_transit = phase[in_transit]
    flux_transit = flux[in_transit]
    
    # Sort by phase
    sort_idx = np.argsort(phase_transit)
    phase_transit = phase_transit[sort_idx]
    flux_transit = flux_transit[sort_idx]
    
    # Divide into ingress, bottom, egress
    n = len(flux_transit)
    third = n // 3
    
    flux_ingress = flux_transit[:third]
    flux_bottom = flux_transit[third:2*third]
    flux_egress = flux_transit[2*third:]
    
    # Compute curvature (second derivative approximation)
    # V-shaped has sharp corners, U-shaped is smooth
    if len(flux_bottom) > 5:
        bottom_curvature = np.std(np.diff(np.diff(flux_bottom)))
    else:
        bottom_curvature = 0
    
    # Flatness of bottom
    bottom_std = np.std(flux_bottom) if len(flux_bottom) > 0 else 0
    
    # Symmetry check
    if len(flux_ingress) > 0 and len(flux_egress) > 0:
        ingress_slope = np.median(np.diff(flux_ingress))
        egress_slope = np.median(np.diff(flux_egress))
        symmetry = abs(ingress_slope + egress_slope) / (abs(ingress_slope) + abs(egress_slope) + 1e-10)
    else:
        symmetry = 1.0
    
    # Verdict based on curvature
    if bottom_curvature > 0.001:
        shape = 'v-shaped'
        verdict = 'warn'
        message = 'V-shaped transit (investigate for EB)'
    else:
        shape = 'u-shaped'
        verdict = 'pass'
        message = 'U-shaped transit (consistent with planet)'
    
    return {
        'shape': shape,
        'bottom_curvature': float(bottom_curvature),
        'bottom_flatness': float(bottom_std),
        'symmetry': float(symmetry),
        'verdict': verdict,
        'message': message
    }


def generate_diagnostics_report(
    time: np.ndarray,
    flux: np.ndarray,
    tls_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate comprehensive diagnostics report.
    
    Returns:
        dict with all diagnostic tests
    """
    # Extract parameters (handle both TLS and BLS field names)
    period = tls_result.get('period') or tls_result.get('best_period')
    t0 = tls_result.get('T0') or tls_result.get('t0') or tls_result.get('best_t0')
    depth = tls_result.get('depth') or tls_result.get('best_depth')
    duration = tls_result.get('duration') or tls_result.get('best_duration')
    
    # Convert to float if strings
    if isinstance(period, str):
        period = float(period) if period != "None" else None
    if isinstance(t0, str):
        t0 = float(t0) if t0 != "None" else None
    if isinstance(depth, str):
        depth = float(depth) if depth != "None" else None
    if isinstance(duration, str):
        duration = float(duration) if duration != "None" else None
    
    if not (period and t0 and depth and duration):
        return {
            'error': 'Missing required transit parameters',
            'available': False
        }
    
    # Run all diagnostic tests
    odd_even = compute_odd_even_diagnostic(time, flux, period, t0, duration)
    secondary = search_secondary_eclipse(time, flux, period, t0, depth, duration)
    residuals = compute_model_residuals(time, flux, period, t0, depth, duration)
    shape = compute_transit_shape_metrics(time, flux, period, t0, duration)
    
    # Overall assessment
    tests_passed = 0
    tests_warned = 0
    tests_failed = 0
    
    for test in [odd_even, secondary, shape]:
        verdict = test.get('verdict', 'unknown')
        if verdict == 'pass' or verdict == 'planet':
            tests_passed += 1
        elif verdict == 'warn' or verdict == 'uncertain':
            tests_warned += 1
        elif verdict == 'fail' or verdict == 'eb':
            tests_failed += 1
    
    # Overall verdict
    if tests_failed > 0:
        overall_verdict = 'fail'
        overall_message = 'Failed one or more diagnostic tests (likely false positive)'
    elif tests_warned > 1:
        overall_verdict = 'uncertain'
        overall_message = 'Multiple warning flags (requires additional vetting)'
    elif tests_warned == 1:
        overall_verdict = 'pass_with_warnings'
        overall_message = 'Passed diagnostics with minor warnings'
    else:
        overall_verdict = 'pass'
        overall_message = 'Passed all diagnostic tests (high confidence)'
    
    return {
        'available': True,
        'odd_even_test': odd_even,
        'secondary_eclipse_test': secondary,
        'residuals_analysis': residuals,
        'shape_analysis': shape,
        'summary': {
            'tests_passed': tests_passed,
            'tests_warned': tests_warned,
            'tests_failed': tests_failed,
            'overall_verdict': overall_verdict,
            'overall_message': overall_message
        }
    }

