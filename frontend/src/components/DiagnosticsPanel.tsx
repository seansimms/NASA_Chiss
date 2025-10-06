import React from "react";

const API_BASE = (import.meta as any).env?.VITE_API_BASE || "http://localhost:8000";

type DiagnosticsPanelProps = {
  jobId: string;
  ticId: string;
};

type DiagnosticsData = {
  available: boolean;
  odd_even_test: any;
  secondary_eclipse_test: any;
  residuals_analysis: any;
  shape_analysis: any;
  summary: {
    tests_passed: number;
    tests_warned: number;
    tests_failed: number;
    overall_verdict: string;
    overall_message: string;
  };
};

export function DiagnosticsPanel({ jobId, ticId }: DiagnosticsPanelProps) {
  const [data, setData] = React.useState<DiagnosticsData | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    loadData();
  }, [jobId]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const apiKey = localStorage.getItem("apiKey") || "";
      const resp = await fetch(`${API_BASE}/api/discoveries/${jobId}/diagnostics`, {
        headers: { "X-API-Key": apiKey }
      });
      
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
      }
      
      const json = await resp.json();
      setData(json);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "#999" }}>
        <div style={{ fontSize: 32, marginBottom: 16 }}>⏳</div>
        <p>Running advanced diagnostics...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 20, background: "#FFEBEE", color: "#C62828", borderRadius: 8 }}>
        <strong>Error loading diagnostics:</strong> {error}
      </div>
    );
  }

  if (!data || !data.available) {
    return (
      <div style={{ padding: 20, background: "#FFF3CD", color: "#856404", borderRadius: 8 }}>
        <strong>Diagnostics unavailable:</strong> {data?.error || "Missing transit parameters"}
      </div>
    );
  }

  const getVerdictColor = (verdict: string) => {
    if (verdict === 'pass' || verdict === 'planet') return "#00C853";
    if (verdict === 'warn' || verdict === 'uncertain' || verdict === 'pass_with_warnings') return "#FFC107";
    if (verdict === 'fail' || verdict === 'eb') return "#D32F2F";
    return "#757575";
  };

  const getVerdictIcon = (verdict: string) => {
    if (verdict === 'pass' || verdict === 'planet') return "✅";
    if (verdict === 'warn' || verdict === 'uncertain' || verdict === 'pass_with_warnings') return "⚠️";
    if (verdict === 'fail' || verdict === 'eb') return "❌";
    return "❓";
  };

  const getOverallColor = (verdict: string) => {
    if (verdict === 'pass') return "#00C853";
    if (verdict === 'pass_with_warnings') return "#2196F3";
    if (verdict === 'uncertain') return "#FFC107";
    if (verdict === 'fail') return "#D32F2F";
    return "#757575";
  };

  return (
    <div>
      {/* Overall Summary */}
      <div style={{ 
        marginBottom: 24, 
        padding: 20, 
        background: "white", 
        borderRadius: 12, 
        border: `3px solid ${getOverallColor(data.summary.overall_verdict)}`,
        boxShadow: "0 4px 12px rgba(0,0,0,0.1)"
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <h3 style={{ fontSize: 20, margin: 0 }}>🔬 ADVANCED DIAGNOSTICS</h3>
          <div style={{ fontSize: 48 }}>{getVerdictIcon(data.summary.overall_verdict)}</div>
        </div>
        
        <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: 16, alignItems: "center" }}>
          <div style={{ textAlign: "center", padding: 16, background: "#f5f5f5", borderRadius: 8 }}>
            <div style={{ fontSize: 48, color: getOverallColor(data.summary.overall_verdict), fontWeight: 700 }}>
              {data.summary.tests_passed}/{data.summary.tests_passed + data.summary.tests_warned + data.summary.tests_failed}
            </div>
            <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>TESTS PASSED</div>
          </div>
          
          <div>
            <div style={{ fontSize: 18, fontWeight: 600, color: getOverallColor(data.summary.overall_verdict), marginBottom: 8 }}>
              {data.summary.overall_message}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, auto)", gap: 16, fontSize: 14 }}>
              <div>
                <span style={{ color: "#00C853", fontWeight: 600 }}>✅ {data.summary.tests_passed}</span> Passed
              </div>
              <div>
                <span style={{ color: "#FFC107", fontWeight: 600 }}>⚠️ {data.summary.tests_warned}</span> Warned
              </div>
              <div>
                <span style={{ color: "#D32F2F", fontWeight: 600 }}>❌ {data.summary.tests_failed}</span> Failed
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Odd/Even Transit Test */}
      {data.odd_even_test && !data.odd_even_test.error && (
        <div style={{ 
          marginBottom: 24, 
          padding: 20, 
          background: "white", 
          borderRadius: 8, 
          border: `2px solid ${getVerdictColor(data.odd_even_test.verdict)}`
        }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
            <h3 style={{ fontSize: 16, margin: 0 }}>🔀 ODD/EVEN TRANSIT COMPARISON</h3>
            <div style={{ fontSize: 24 }}>{getVerdictIcon(data.odd_even_test.verdict)}</div>
          </div>
          
          <div style={{ marginBottom: 12, padding: 12, background: "#f5f5f5", borderRadius: 6 }}>
            <div style={{ fontWeight: 600, marginBottom: 8, color: getVerdictColor(data.odd_even_test.verdict) }}>
              {data.odd_even_test.message}
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
            <div style={{ padding: 12, background: "#F0F7FF", borderRadius: 6 }}>
              <div style={{ fontSize: 11, color: "#666", marginBottom: 4 }}>ODD TRANSITS</div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>{data.odd_even_test.odd_depth_ppm?.toFixed(1)} ppm</div>
              <div style={{ fontSize: 11, color: "#999" }}>{data.odd_even_test.n_odd_transits} transits</div>
            </div>
            
            <div style={{ padding: 12, background: "#F0F7FF", borderRadius: 6 }}>
              <div style={{ fontSize: 11, color: "#666", marginBottom: 4 }}>EVEN TRANSITS</div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>{data.odd_even_test.even_depth_ppm?.toFixed(1)} ppm</div>
              <div style={{ fontSize: 11, color: "#999" }}>{data.odd_even_test.n_even_transits} transits</div>
            </div>
            
            <div style={{ padding: 12, background: "#FFF3E0", borderRadius: 6 }}>
              <div style={{ fontSize: 11, color: "#666", marginBottom: 4 }}>DIFFERENCE</div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>{data.odd_even_test.depth_difference_ppm?.toFixed(1)} ppm</div>
              <div style={{ fontSize: 11, color: "#999" }}>Ratio: {data.odd_even_test.depth_ratio?.toFixed(3)}</div>
            </div>
          </div>

          <div style={{ marginTop: 12, fontSize: 12, color: "#666", fontStyle: "italic" }}>
            💡 Eclipsing binaries show different depths for odd/even transits. Planets should be consistent.
          </div>
        </div>
      )}

      {/* Secondary Eclipse Test */}
      {data.secondary_eclipse_test && !data.secondary_eclipse_test.error && (
        <div style={{ 
          marginBottom: 24, 
          padding: 20, 
          background: "white", 
          borderRadius: 8, 
          border: `2px solid ${getVerdictColor(data.secondary_eclipse_test.verdict)}`
        }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
            <h3 style={{ fontSize: 16, margin: 0 }}>🌑 SECONDARY ECLIPSE SEARCH</h3>
            <div style={{ fontSize: 24 }}>{getVerdictIcon(data.secondary_eclipse_test.verdict)}</div>
          </div>
          
          <div style={{ marginBottom: 12, padding: 12, background: "#f5f5f5", borderRadius: 6 }}>
            <div style={{ fontWeight: 600, marginBottom: 8, color: getVerdictColor(data.secondary_eclipse_test.verdict) }}>
              {data.secondary_eclipse_test.message}
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
            <div style={{ padding: 12, background: "#F0F7FF", borderRadius: 6 }}>
              <div style={{ fontSize: 11, color: "#666", marginBottom: 4 }}>DETECTION</div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>
                {data.secondary_eclipse_test.detected ? "DETECTED" : "NOT DETECTED"}
              </div>
              <div style={{ fontSize: 11, color: "#999" }}>
                {data.secondary_eclipse_test.significance_sigma?.toFixed(1)}σ
              </div>
            </div>
            
            <div style={{ padding: 12, background: "#F0F7FF", borderRadius: 6 }}>
              <div style={{ fontSize: 11, color: "#666", marginBottom: 4 }}>SECONDARY DEPTH</div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>
                {data.secondary_eclipse_test.secondary_depth_ppm?.toFixed(1)} ppm
              </div>
              <div style={{ fontSize: 11, color: "#999" }}>
                {data.secondary_eclipse_test.n_secondary_points} points
              </div>
            </div>
            
            <div style={{ padding: 12, background: "#FFF3E0", borderRadius: 6 }}>
              <div style={{ fontSize: 11, color: "#666", marginBottom: 4 }}>DEPTH RATIO</div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>
                {(data.secondary_eclipse_test.depth_ratio * 100)?.toFixed(1)}%
              </div>
              <div style={{ fontSize: 11, color: "#999" }}>Secondary/Primary</div>
            </div>
          </div>

          <div style={{ marginTop: 12, fontSize: 12, color: "#666", fontStyle: "italic" }}>
            💡 Planets show no secondary eclipse. Eclipsing binaries show strong secondary eclipse at phase 0.5.
          </div>
        </div>
      )}

      {/* Transit Shape Analysis */}
      {data.shape_analysis && !data.shape_analysis.error && (
        <div style={{ 
          marginBottom: 24, 
          padding: 20, 
          background: "white", 
          borderRadius: 8, 
          border: `2px solid ${getVerdictColor(data.shape_analysis.verdict)}`
        }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
            <h3 style={{ fontSize: 16, margin: 0 }}>📊 TRANSIT SHAPE ANALYSIS</h3>
            <div style={{ fontSize: 24 }}>{getVerdictIcon(data.shape_analysis.verdict)}</div>
          </div>
          
          <div style={{ marginBottom: 12, padding: 12, background: "#f5f5f5", borderRadius: 6 }}>
            <div style={{ fontWeight: 600, marginBottom: 8, color: getVerdictColor(data.shape_analysis.verdict) }}>
              {data.shape_analysis.message}
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
            <div style={{ padding: 12, background: "#F0F7FF", borderRadius: 6 }}>
              <div style={{ fontSize: 11, color: "#666", marginBottom: 4 }}>SHAPE</div>
              <div style={{ fontSize: 18, fontWeight: 600, textTransform: "uppercase" }}>
                {data.shape_analysis.shape}
              </div>
            </div>
            
            <div style={{ padding: 12, background: "#F0F7FF", borderRadius: 6 }}>
              <div style={{ fontSize: 11, color: "#666", marginBottom: 4 }}>CURVATURE</div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>
                {(data.shape_analysis.bottom_curvature * 1000)?.toFixed(3)}
              </div>
            </div>
            
            <div style={{ padding: 12, background: "#F0F7FF", borderRadius: 6 }}>
              <div style={{ fontSize: 11, color: "#666", marginBottom: 4 }}>SYMMETRY</div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>
                {(data.shape_analysis.symmetry * 100)?.toFixed(1)}%
              </div>
            </div>
          </div>

          <div style={{ marginTop: 12, fontSize: 12, color: "#666", fontStyle: "italic" }}>
            💡 V-shaped transits suggest grazing eclipses. U-shaped transits are consistent with planets.
          </div>
        </div>
      )}

      {/* Model Residuals */}
      {data.residuals_analysis && (
        <div style={{ 
          marginBottom: 24, 
          padding: 20, 
          background: "white", 
          borderRadius: 8, 
          border: "1px solid #ddd"
        }}>
          <h3 style={{ fontSize: 16, margin: "0 0 16px 0" }}>📈 MODEL RESIDUALS ANALYSIS</h3>
          
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
            <div style={{ padding: 12, background: "#f5f5f5", borderRadius: 6 }}>
              <div style={{ fontSize: 11, color: "#666", marginBottom: 4 }}>RMS</div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>
                {data.residuals_analysis.rms_ppm?.toFixed(1)} ppm
              </div>
            </div>
            
            <div style={{ padding: 12, background: "#f5f5f5", borderRadius: 6 }}>
              <div style={{ fontSize: 11, color: "#666", marginBottom: 4 }}>REDUCED χ²</div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>
                {data.residuals_analysis.reduced_chi_squared?.toFixed(2)}
              </div>
            </div>
            
            <div style={{ padding: 12, background: "#f5f5f5", borderRadius: 6 }}>
              <div style={{ fontSize: 11, color: "#666", marginBottom: 4 }}>NORMALITY</div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>
                {data.residuals_analysis.is_normal ? "✅ YES" : "❌ NO"}
              </div>
              <div style={{ fontSize: 11, color: "#999" }}>
                p = {data.residuals_analysis.normality_p_value?.toFixed(3)}
              </div>
            </div>
          </div>

          <div style={{ marginTop: 12, fontSize: 12, color: "#666", fontStyle: "italic" }}>
            💡 Good fits show normally distributed residuals with reduced χ² ≈ 1.
          </div>
        </div>
      )}

      {/* Diagnostic Summary */}
      <div style={{ padding: 16, background: "#E8F5E9", borderRadius: 8, border: "2px solid #00C853" }}>
        <h4 style={{ margin: "0 0 12px 0", fontSize: 14, color: "#1B5E20" }}>
          🎯 DIAGNOSTIC INTERPRETATION
        </h4>
        <div style={{ fontSize: 13, color: "#1B5E20", lineHeight: 1.6 }}>
          {data.summary.overall_verdict === 'pass' && (
            <div>
              <strong>✅ High Confidence:</strong> All diagnostic tests passed. This candidate shows characteristics 
              consistent with a transiting exoplanet. Recommended for follow-up observations.
            </div>
          )}
          {data.summary.overall_verdict === 'pass_with_warnings' && (
            <div>
              <strong>⚠️ Good with Caveats:</strong> Diagnostic tests mostly passed with minor warnings. 
              Additional vetting recommended before committing significant follow-up resources.
            </div>
          )}
          {data.summary.overall_verdict === 'uncertain' && (
            <div>
              <strong>❓ Uncertain:</strong> Mixed diagnostic results. This candidate requires careful investigation 
              and additional data to determine its nature.
            </div>
          )}
          {data.summary.overall_verdict === 'fail' && (
            <div style={{ background: "#FFEBEE", color: "#C62828", padding: 12, borderRadius: 6, border: "1px solid #D32F2F" }}>
              <strong>❌ Likely False Positive:</strong> One or more diagnostic tests failed. This candidate 
              is likely an eclipsing binary or systematic artifact, not a planet.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

