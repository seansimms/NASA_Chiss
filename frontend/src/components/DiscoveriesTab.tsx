import React from "react";
import { apiFetch } from "../lib/api";
import { LightCurvePlot } from "./LightCurvePlot";
import { PhaseFoldPlot } from "./PhaseFoldPlot";
import { VettingPanel } from "./VettingPanel";
import { DiagnosticsPanel } from "./DiagnosticsPanel";
import { ExportPanel } from "./ExportPanel";

const API_BASE = (import.meta as any).env?.VITE_API_BASE || "http://localhost:8000";

type Discovery = {
  job_id: string;
  tic_id: string;
  created_at: number;
  finished_at?: number;
  duration_seconds?: number;
  n_sectors?: number;
  n_points?: number;
  timespan_days?: number;
  period?: number;
  depth?: number;
  duration?: number;
  sde?: number;
  snr?: number;
  t0?: number;
  skipped?: boolean;
  status: string;
  error?: string;
};

type DiscoveryDetail = {
  job_id: string;
  tic_id: string;
  n_sectors: number;
  n_points: number;
  timespan_days: number;
  period_range: [number, number];
  grid_meta: any;
  tls: any;
  job: any;
  search_results: any;
};

export function DiscoveriesTab() {
  const [discoveries, setDiscoveries] = React.useState<Discovery[]>([]);
  const [selected, setSelected] = React.useState<string | null>(null);
  const [detail, setDetail] = React.useState<DiscoveryDetail | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const loadDiscoveries = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await apiFetch(`${API_BASE}/api/discoveries`);
      const data = await resp.json();
      setDiscoveries(data.discoveries || []);
      
      // Auto-select most recent if none selected
      if (!selected && data.discoveries && data.discoveries.length > 0) {
        setSelected(data.discoveries[0].job_id);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const loadDetail = async (jobId: string) => {
    try {
      const resp = await apiFetch(`${API_BASE}/api/discoveries/${jobId}`);
      const data = await resp.json();
      setDetail(data);
    } catch (e: any) {
      setError(e.message);
    }
  };

  React.useEffect(() => {
    loadDiscoveries();
    // Refresh every 5 seconds
    const interval = setInterval(loadDiscoveries, 5000);
    return () => clearInterval(interval);
  }, []);

  React.useEffect(() => {
    if (selected) {
      loadDetail(selected);
    }
  }, [selected]);

  const formatDate = (timestamp?: number) => {
    if (!timestamp) return "—";
    return new Date(timestamp * 1000).toLocaleString();
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return "—";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}m ${secs}s`;
  };

  const getStatusBadge = (discovery: Discovery) => {
    if (discovery.status === "error") {
      return <span style={{ color: "#D32F2F", fontWeight: 600 }}>❌ ERROR</span>;
    }
    if (discovery.skipped || discovery.status === "no_detection") {
      return <span style={{ color: "#FFC107", fontWeight: 600 }}>⚠️ NO DETECTION</span>;
    }
    if (discovery.sde && discovery.sde >= 10) {
      return <span style={{ color: "#00C853", fontWeight: 600 }}>✅ HIGH CONFIDENCE</span>;
    }
    if (discovery.sde && discovery.sde >= 7) {
      return <span style={{ color: "#2196F3", fontWeight: 600 }}>✓ CANDIDATE</span>;
    }
    return <span style={{ color: "#757575" }}>• COMPLETED</span>;
  };

  const getQualityColor = (sde?: number) => {
    if (!sde) return "#757575";
    if (sde >= 10) return "#00C853";
    if (sde >= 7) return "#2196F3";
    if (sde >= 5) return "#FFC107";
    return "#FF5722";
  };

  return (
    <div style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 24 }}>
          🌟 Discoveries
          {discoveries.length > 0 && (
            <span style={{ fontSize: 14, marginLeft: 8, color: "#666", fontWeight: "normal" }}>
              ({discoveries.length} searches)
            </span>
          )}
        </h2>
        <button onClick={loadDiscoveries} disabled={loading}>
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>

      {error && (
        <div style={{ padding: 12, background: "#FFEBEE", color: "#C62828", borderRadius: 6, marginBottom: 16 }}>
          Error: {error}
        </div>
      )}

      {!loading && discoveries.length === 0 && (
        <div style={{ padding: 40, textAlign: "center", color: "#999" }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🔭</div>
          <h3 style={{ color: "#666" }}>No discoveries yet</h3>
          <p>Run a multi-sector search to see results here.</p>
        </div>
      )}

      {discoveries.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 16 }}>
          {/* Left: Discovery List */}
          <div style={{ border: "1px solid #eee", borderRadius: 8, padding: 8, maxHeight: "70vh", overflowY: "auto" }}>
            <h3 style={{ fontSize: 14, textTransform: "uppercase", color: "#666", marginBottom: 8 }}>
              Recent Searches
            </h3>
            {discoveries.map((d) => (
              <div
                key={d.job_id}
                onClick={() => setSelected(d.job_id)}
                style={{
                  padding: 12,
                  marginBottom: 8,
                  border: `2px solid ${selected === d.job_id ? "#0B3D91" : "#eee"}`,
                  borderRadius: 8,
                  cursor: "pointer",
                  background: selected === d.job_id ? "#F5F8FF" : "white",
                  transition: "all 0.2s",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start", marginBottom: 4 }}>
                  <div style={{ fontWeight: 600, fontSize: 16 }}>TIC {d.tic_id}</div>
                  {getStatusBadge(d)}
                </div>
                
                {d.period && (
                  <div style={{ fontSize: 14, color: "#333", marginBottom: 2 }}>
                    <strong>Period:</strong> {d.period.toFixed(3)} days
                  </div>
                )}
                
                {d.sde && (
                  <div style={{ fontSize: 14, color: getQualityColor(d.sde), fontWeight: 600, marginBottom: 2 }}>
                    SDE: {d.sde.toFixed(1)} σ
                  </div>
                )}
                
                {d.n_sectors && (
                  <div style={{ fontSize: 12, color: "#666" }}>
                    {d.n_sectors} sectors • {d.n_points?.toLocaleString()} points
                  </div>
                )}
                
                <div style={{ fontSize: 11, color: "#999", marginTop: 4 }}>
                  {formatDate(d.created_at)}
                </div>
              </div>
            ))}
          </div>

          {/* Right: Discovery Detail */}
          <div style={{ border: "1px solid #eee", borderRadius: 8, padding: 16 }}>
            {!detail && (
              <div style={{ padding: 40, textAlign: "center", color: "#999" }}>
                <p>Select a discovery to view details</p>
              </div>
            )}

            {detail && (
              <div>
                <div style={{ marginBottom: 24 }}>
                  <h2 style={{ fontSize: 28, margin: "0 0 8px 0" }}>
                    TIC {detail.tic_id}
                  </h2>
                  <div style={{ fontSize: 14, color: "#666" }}>
                    Job ID: {detail.job_id.slice(0, 30)}...
                  </div>
                </div>

                {/* Candidate Parameters */}
                {detail.tls && !detail.tls.skipped && (
                  <div style={{ marginBottom: 24, padding: 16, background: "#F5F8FF", borderRadius: 8, border: "2px solid #0B3D91" }}>
                    <h3 style={{ fontSize: 16, margin: "0 0 12px 0", color: "#0B3D91" }}>
                      🪐 CANDIDATE PARAMETERS
                    </h3>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                      {detail.tls.period && (
                        <div>
                          <div style={{ fontSize: 12, color: "#666" }}>Orbital Period</div>
                          <div style={{ fontSize: 20, fontWeight: 600 }}>{parseFloat(detail.tls.period).toFixed(3)} days</div>
                        </div>
                      )}
                      {detail.tls.depth && (
                        <div>
                          <div style={{ fontSize: 12, color: "#666" }}>Transit Depth</div>
                          <div style={{ fontSize: 20, fontWeight: 600 }}>{(parseFloat(detail.tls.depth) * 1e6).toFixed(0)} ppm</div>
                        </div>
                      )}
                      {detail.tls.duration && (
                        <div>
                          <div style={{ fontSize: 12, color: "#666" }}>Duration</div>
                          <div style={{ fontSize: 20, fontWeight: 600 }}>{(parseFloat(detail.tls.duration) * 24).toFixed(2)} hours</div>
                        </div>
                      )}
                      {detail.tls.T0 && (
                        <div>
                          <div style={{ fontSize: 12, color: "#666" }}>Epoch (T0)</div>
                          <div style={{ fontSize: 16, fontWeight: 600 }}>BJD {parseFloat(detail.tls.T0).toFixed(3)}</div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Detection Quality */}
                {detail.tls && !detail.tls.skipped && (
                  <div style={{ marginBottom: 24, padding: 16, background: "#FFFEF0", borderRadius: 8 }}>
                    <h3 style={{ fontSize: 16, margin: "0 0 12px 0" }}>
                      📊 DETECTION QUALITY
                    </h3>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
                      {detail.tls.SDE && (
                        <div>
                          <div style={{ fontSize: 12, color: "#666" }}>SDE (Signal Detection)</div>
                          <div style={{ fontSize: 20, fontWeight: 600, color: getQualityColor(parseFloat(detail.tls.SDE)) }}>
                            {parseFloat(detail.tls.SDE).toFixed(1)} σ
                          </div>
                        </div>
                      )}
                      {detail.tls.snr && (
                        <div>
                          <div style={{ fontSize: 12, color: "#666" }}>SNR</div>
                          <div style={{ fontSize: 20, fontWeight: 600 }}>{parseFloat(detail.tls.snr).toFixed(1)}</div>
                        </div>
                      )}
                      {detail.tls.transit_count && (
                        <div>
                          <div style={{ fontSize: 12, color: "#666" }}>Transit Count</div>
                          <div style={{ fontSize: 20, fontWeight: 600 }}>{detail.tls.transit_count}</div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Data Coverage */}
                <div style={{ marginBottom: 24, padding: 16, background: "#F5F5F5", borderRadius: 8 }}>
                  <h3 style={{ fontSize: 16, margin: "0 0 12px 0" }}>
                    📡 DATA COVERAGE
                  </h3>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
                    <div>
                      <div style={{ fontSize: 12, color: "#666" }}>TESS Sectors</div>
                      <div style={{ fontSize: 20, fontWeight: 600 }}>{detail.n_sectors}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 12, color: "#666" }}>Data Points</div>
                      <div style={{ fontSize: 20, fontWeight: 600 }}>{detail.n_points?.toLocaleString()}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 12, color: "#666" }}>Timespan</div>
                      <div style={{ fontSize: 20, fontWeight: 600 }}>{detail.timespan_days?.toFixed(0)} days</div>
                    </div>
                    {detail.grid_meta?.duty_cycle && (
                      <div>
                        <div style={{ fontSize: 12, color: "#666" }}>Duty Cycle</div>
                        <div style={{ fontSize: 20, fontWeight: 600 }}>{(detail.grid_meta.duty_cycle * 100).toFixed(1)}%</div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Search Configuration */}
                <div style={{ marginBottom: 16, padding: 16, background: "#FAFAFA", borderRadius: 8 }}>
                  <h3 style={{ fontSize: 16, margin: "0 0 12px 0" }}>
                    ⚙️ SEARCH PARAMETERS
                  </h3>
                  <div style={{ fontSize: 14, color: "#666", lineHeight: 1.8 }}>
                    <div><strong>Period Range:</strong> {detail.period_range?.[0]} - {detail.period_range?.[1]} days</div>
                    {detail.grid_meta && (
                      <>
                        <div><strong>Grid Size:</strong> {detail.grid_meta.n_periods} test periods</div>
                        <div><strong>Effective Baseline:</strong> {detail.grid_meta.effective_baseline_days?.toFixed(1)} days</div>
                      </>
                    )}
                    {detail.job && (
                      <>
                        <div><strong>Duration:</strong> {formatDuration(detail.job.finished_at - detail.job.started_at)}</div>
                        <div><strong>Completed:</strong> {formatDate(detail.job.finished_at)}</div>
                      </>
                    )}
                  </div>
                </div>

                {/* No Detection Message */}
                {detail.tls?.skipped && (
                  <div style={{ padding: 16, background: "#FFF3CD", border: "2px solid #FFC107", borderRadius: 8, marginBottom: 16 }}>
                    <h3 style={{ fontSize: 16, margin: "0 0 8px 0", color: "#856404" }}>
                      ⚠️ No Transit Detected
                    </h3>
                    <p style={{ margin: 0, color: "#856404" }}>
                      {detail.tls.notes || "TLS search completed but did not detect any significant transit signals."}
                    </p>
                  </div>
                )}

                {/* Vetting & Quality Assessment */}
                <div style={{ marginTop: 24 }}>
                  <h3 style={{ fontSize: 16, margin: "0 0 16px 0" }}>
                    🔬 VETTING & QUALITY ASSESSMENT
                  </h3>
                  <VettingPanel jobId={detail.job_id} ticId={detail.tic_id} />
                </div>

                {/* Advanced Diagnostics */}
                {!detail.tls?.skipped && (
                  <div style={{ marginTop: 24 }}>
                    <DiagnosticsPanel jobId={detail.job_id} ticId={detail.tic_id} />
                  </div>
                )}

                {/* Visualizations */}
                {!detail.tls?.skipped && (
                  <div style={{ marginTop: 24 }}>
                    <h3 style={{ fontSize: 16, margin: "0 0 16px 0" }}>
                      📈 LIGHT CURVE ANALYSIS
                    </h3>
                    
                    {/* Full Light Curve */}
                    <div style={{ marginBottom: 24, padding: 16, background: "white", borderRadius: 8, border: "1px solid #ddd" }}>
                      <LightCurvePlot jobId={detail.job_id} ticId={detail.tic_id} />
                    </div>
                    
                    {/* Phase-Folded Transit */}
                    <div style={{ marginBottom: 24, padding: 16, background: "white", borderRadius: 8, border: "1px solid #ddd" }}>
                      <PhaseFoldPlot jobId={detail.job_id} ticId={detail.tic_id} />
                    </div>
                  </div>
                )}

                {/* Export & Share */}
                <div style={{ marginTop: 24 }}>
                  <ExportPanel jobId={detail.job_id} ticId={detail.tic_id} discoveryDetail={detail} />
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

