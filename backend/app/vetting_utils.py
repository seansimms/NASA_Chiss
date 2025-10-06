"""
Candidate vetting and quality assessment utilities.
"""
from __future__ import annotations
from typing import Dict, Any, Optional, List
import numpy as np


def compute_candidate_score(tls_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute overall candidate quality score based on TLS results.
    
    Returns:
        dict with:
        - score: 0-100 quality score
        - grade: A/B/C/D/F letter grade
        - confidence: low/medium/high/very_high
        - flags: list of warning flags
        - metrics: breakdown of scoring components
    """
    flags = []
    metrics = {}
    
    # Extract key metrics (handle both TLS and BLS field names)
    sde = _safe_float(tls_result.get('SDE') or tls_result.get('best_sde'))
    snr = _safe_float(tls_result.get('snr') or tls_result.get('best_snr'))
    period = _safe_float(tls_result.get('period') or tls_result.get('best_period'))
    depth = _safe_float(tls_result.get('depth') or tls_result.get('best_depth'))
    duration = _safe_float(tls_result.get('duration') or tls_result.get('best_duration'))
    transit_count = _safe_int(tls_result.get('transit_count') or tls_result.get('n_transits'))
    
    # Check if skipped
    if tls_result.get('skipped'):
        return {
            'score': 0,
            'grade': 'F',
            'confidence': 'none',
            'flags': ['No detection'],
            'metrics': {},
            'verdict': 'NO DETECTION'
        }
    
    # Score components (0-100 each)
    score_sde = 0
    score_snr = 0
    score_depth = 0
    score_period = 0
    score_transits = 0
    
    # SDE Score (40% weight) - most important
    if sde is not None:
        if sde >= 10:
            score_sde = 100
        elif sde >= 7:
            score_sde = 75
        elif sde >= 5:
            score_sde = 50
        else:
            score_sde = max(0, sde * 10)
            flags.append(f"Low SDE ({sde:.1f}σ)")
        metrics['sde'] = {'value': sde, 'score': score_sde, 'weight': 0.4}
    
    # SNR Score (20% weight)
    if snr is not None:
        if snr >= 15:
            score_snr = 100
        elif snr >= 10:
            score_snr = 75
        elif snr >= 7:
            score_snr = 50
        else:
            score_snr = max(0, snr * 7)
            flags.append(f"Low SNR ({snr:.1f})")
        metrics['snr'] = {'value': snr, 'score': score_snr, 'weight': 0.2}
    
    # Depth Score (15% weight)
    if depth is not None:
        depth_ppm = depth * 1e6
        if 100 < depth_ppm < 50000:  # Reasonable transit depths
            score_depth = 100
        elif depth_ppm <= 100:
            score_depth = 50
            flags.append(f"Shallow transit ({depth_ppm:.0f} ppm)")
        elif depth_ppm >= 50000:
            score_depth = 30
            flags.append(f"Very deep transit ({depth_ppm:.0f} ppm) - possible eclipse")
        metrics['depth'] = {'value': depth_ppm, 'score': score_depth, 'weight': 0.15}
    
    # Period Score (15% weight)
    if period is not None:
        if 0.5 < period < 500:  # Reasonable periods
            score_period = 100
        elif period <= 0.5:
            score_period = 60
            flags.append(f"Very short period ({period:.2f} d)")
        elif period >= 500:
            score_period = 80  # Long periods are fine, just harder to confirm
        metrics['period'] = {'value': period, 'score': score_period, 'weight': 0.15}
    
    # Transit Count Score (10% weight)
    if transit_count is not None:
        if transit_count >= 5:
            score_transits = 100
        elif transit_count >= 3:
            score_transits = 75
        elif transit_count >= 2:
            score_transits = 50
            flags.append(f"Only {transit_count} transits observed")
        else:
            score_transits = 25
            flags.append(f"Single transit detection")
        metrics['transit_count'] = {'value': transit_count, 'score': score_transits, 'weight': 0.1}
    
    # Compute weighted score
    total_score = (
        score_sde * 0.4 +
        score_snr * 0.2 +
        score_depth * 0.15 +
        score_period * 0.15 +
        score_transits * 0.1
    )
    
    # Determine grade and confidence
    if total_score >= 85:
        grade = 'A'
        confidence = 'very_high'
        verdict = 'HIGH CONFIDENCE CANDIDATE'
    elif total_score >= 70:
        grade = 'B'
        confidence = 'high'
        verdict = 'STRONG CANDIDATE'
    elif total_score >= 55:
        grade = 'C'
        confidence = 'medium'
        verdict = 'CANDIDATE'
    elif total_score >= 40:
        grade = 'D'
        confidence = 'low'
        verdict = 'WEAK CANDIDATE'
    else:
        grade = 'F'
        confidence = 'very_low'
        verdict = 'POOR CANDIDATE'
    
    return {
        'score': round(total_score, 1),
        'grade': grade,
        'confidence': confidence,
        'flags': flags,
        'metrics': metrics,
        'verdict': verdict
    }


def generate_vetting_report(discovery_detail: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate comprehensive vetting report for a discovery.
    
    Returns:
        dict with all vetting information, data sources, and recommendations
    """
    tls = discovery_detail.get('tls', {})
    
    # Compute quality score
    quality = compute_candidate_score(tls)
    
    # Data source attribution
    data_sources = {
        'primary': 'NASA MAST (TESS)',
        'pipeline': 'SPOC (Science Processing Operations Center)',
        'access_method': 'Lightkurve + astroquery',
        'search_algorithm': 'Transit Least Squares (TLS)',
        'references': [
            'TESS Mission: https://tess.mit.edu',
            'MAST Archive: https://archive.stsci.edu',
            'TLS: Hippke & Heller (2019)',
            'Lightkurve: https://docs.lightkurve.org'
        ]
    }
    
    # External resources
    tic_id = discovery_detail.get('tic_id')
    external_links = generate_external_links(tic_id)
    
    # Vetting checklist
    checklist = generate_vetting_checklist(tls, discovery_detail)
    
    # Recommendations
    recommendations = generate_recommendations(quality, tls)
    
    return {
        'quality': quality,
        'data_sources': data_sources,
        'external_links': external_links,
        'checklist': checklist,
        'recommendations': recommendations,
        'tic_id': tic_id
    }


def generate_external_links(tic_id: str) -> Dict[str, str]:
    """Generate links to external resources for a TIC ID."""
    if not tic_id:
        return {}
    
    return {
        'mast': f'https://mast.stsci.edu/portal/Mashup/Clients/Mast/Portal.html?searchQuery={tic_id}',
        'exofop': f'https://exofop.ipac.caltech.edu/tess/target.php?id={tic_id}',
        'simbad': f'http://simbad.u-strasbg.fr/simbad/sim-id?Ident=TIC+{tic_id}',
        'nasa_archive': f'https://exoplanetarchive.ipac.caltech.edu/cgi-bin/TblView/nph-tblView?app=ExoTbls&config=TOI',
        'tess_alert': f'https://tev.mit.edu/event/{tic_id}/'
    }


def generate_vetting_checklist(tls: Dict[str, Any], detail: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generate vetting checklist items.
    
    Returns list of checklist items with status (pass/warn/fail)
    """
    checklist = []
    
    sde = _safe_float(tls.get('SDE'))
    snr = _safe_float(tls.get('snr'))
    depth = _safe_float(tls.get('depth'))
    period = _safe_float(tls.get('period'))
    n_sectors = detail.get('n_sectors', 0)
    
    # SDE check
    if sde:
        if sde >= 10:
            checklist.append({'item': 'SDE ≥ 10σ', 'status': 'pass', 'value': f'{sde:.1f}σ'})
        elif sde >= 7:
            checklist.append({'item': 'SDE ≥ 7σ', 'status': 'warn', 'value': f'{sde:.1f}σ'})
        else:
            checklist.append({'item': 'SDE < 7σ', 'status': 'fail', 'value': f'{sde:.1f}σ'})
    
    # SNR check
    if snr:
        if snr >= 10:
            checklist.append({'item': 'SNR ≥ 10', 'status': 'pass', 'value': f'{snr:.1f}'})
        elif snr >= 7:
            checklist.append({'item': 'SNR ≥ 7', 'status': 'warn', 'value': f'{snr:.1f}'})
        else:
            checklist.append({'item': 'SNR < 7', 'status': 'fail', 'value': f'{snr:.1f}'})
    
    # Depth check
    if depth:
        depth_ppm = depth * 1e6
        if 100 < depth_ppm < 50000:
            checklist.append({'item': 'Reasonable depth', 'status': 'pass', 'value': f'{depth_ppm:.0f} ppm'})
        else:
            checklist.append({'item': 'Unusual depth', 'status': 'warn', 'value': f'{depth_ppm:.0f} ppm'})
    
    # Period check
    if period:
        if 0.5 < period < 500:
            checklist.append({'item': 'Reasonable period', 'status': 'pass', 'value': f'{period:.2f} d'})
        else:
            checklist.append({'item': 'Unusual period', 'status': 'warn', 'value': f'{period:.2f} d'})
    
    # Multi-sector check
    if n_sectors >= 3:
        checklist.append({'item': 'Multi-sector coverage', 'status': 'pass', 'value': f'{n_sectors} sectors'})
    elif n_sectors >= 1:
        checklist.append({'item': 'Limited sector coverage', 'status': 'warn', 'value': f'{n_sectors} sectors'})
    
    return checklist


def generate_recommendations(quality: Dict[str, Any], tls: Dict[str, Any]) -> List[str]:
    """Generate follow-up recommendations based on quality assessment."""
    recommendations = []
    
    confidence = quality.get('confidence', 'none')
    flags = quality.get('flags', [])
    
    if confidence in ['very_high', 'high']:
        recommendations.append('✅ Strong candidate for follow-up spectroscopy')
        recommendations.append('✅ Recommend ground-based photometric confirmation')
        recommendations.append('✅ Check ExoFOP for existing vetting')
    elif confidence == 'medium':
        recommendations.append('⚠️ Candidate requires additional vetting')
        recommendations.append('⚠️ Recommend checking for systematic artifacts')
        recommendations.append('📊 Consider additional TESS observations')
    else:
        recommendations.append('❌ Low priority for follow-up')
        recommendations.append('📊 Requires improved detection significance')
    
    # Specific recommendations based on flags
    if any('Low SDE' in f for f in flags):
        recommendations.append('📈 Need more transits to improve SDE')
    if any('shallow' in f.lower() for f in flags):
        recommendations.append('🔬 Requires high-precision photometry for confirmation')
    if any('Single transit' in f for f in flags):
        recommendations.append('⏰ Ephemeris refinement needed')
    
    return recommendations


def _safe_float(value: Any) -> Optional[float]:
    """Safely convert value to float, handling None and string 'None'."""
    if value is None or value == 'None':
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    """Safely convert value to int, handling None and string 'None'."""
    if value is None or value == 'None':
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None

