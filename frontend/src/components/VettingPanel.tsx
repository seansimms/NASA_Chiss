import React from "react";

const API_BASE = (import.meta as any).env?.VITE_API_BASE || "http://localhost:8000";

type VettingPanelProps = {
  jobId: string;
  ticId: string;
};

type VettingData = {
  quality: {
    score: number;
    grade: string;
    confidence: string;
    flags: string[];
    verdict: string;
    metrics: Record<string, any>;
  };
  data_sources: {
    primary: string;
    pipeline: string;
    access_method: string;
    search_algorithm: string;
    references: string[];
  };
  external_links: Record<string, string>;
  checklist: Array<{
    item: string;
    status: string;
    value: string;
  }>;
  recommendations: string[];
  tic_id: string;
};

export function VettingPanel({ jobId, ticId }: VettingPanelProps) {
  const [data, setData] = React.useState<VettingData | null>(null);
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
      const resp = await fetch(`${API_BASE}/api/discoveries/${jobId}/vetting`, {
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
        <p>Loading vetting report...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 20, background: "#FFEBEE", color: "#C62828", borderRadius: 8 }}>
        <strong>Error loading vetting report:</strong> {error}
      </div>
    );
  }

  if (!data) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "#999" }}>
        <p>No vetting data available</p>
      </div>
    );
  }

  const getScoreColor = (score: number) => {
    if (score >= 85) return "#00C853";
    if (score >= 70) return "#2196F3";
    if (score >= 55) return "#FFC107";
    if (score >= 40) return "#FF9800";
    return "#D32F2F";
  };

  const getGradeEmoji = (grade: string) => {
    switch (grade) {
      case 'A': return '🌟';
      case 'B': return '✨';
      case 'C': return '📊';
      case 'D': return '⚠️';
      case 'F': return '❌';
      default: return '';
    }
  };

  const getChecklistIcon = (status: string) => {
    switch (status) {
      case 'pass': return '✅';
      case 'warn': return '⚠️';
      case 'fail': return '❌';
      default: return '•';
    }
  };

  return (
    <div>
      {/* Quality Score Card */}
      <div style={{ 
        marginBottom: 24, 
        padding: 20, 
        background: "white", 
        borderRadius: 12, 
        border: `3px solid ${getScoreColor(data.quality.score)}`,
        boxShadow: "0 4px 12px rgba(0,0,0,0.1)"
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <h3 style={{ fontSize: 20, margin: 0 }}>🔬 CANDIDATE QUALITY ASSESSMENT</h3>
          <div style={{ fontSize: 48 }}>{getGradeEmoji(data.quality.grade)}</div>
        </div>
        
        <div style={{ display: "grid", gridTemplateColumns: "auto 1fr auto", gap: 16, alignItems: "center" }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ 
              fontSize: 64, 
              fontWeight: 700, 
              color: getScoreColor(data.quality.score),
              lineHeight: 1
            }}>
              {data.quality.score}
            </div>
            <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>Score</div>
          </div>
          
          <div>
            <div style={{ fontSize: 24, fontWeight: 600, color: getScoreColor(data.quality.score), marginBottom: 8 }}>
              {data.quality.verdict}
            </div>
            <div style={{ fontSize: 14, color: "#666", marginBottom: 8 }}>
              Grade: <strong>{data.quality.grade}</strong> • 
              Confidence: <strong>{data.quality.confidence.replace('_', ' ').toUpperCase()}</strong>
            </div>
            {data.quality.flags.length > 0 && (
              <div style={{ marginTop: 8 }}>
                {data.quality.flags.map((flag, idx) => (
                  <div key={idx} style={{ fontSize: 12, color: "#FF5722", marginBottom: 4 }}>
                    ⚠️ {flag}
                  </div>
                ))}
              </div>
            )}
          </div>
          
          <div style={{ textAlign: "center", padding: 16, background: "#f5f5f5", borderRadius: 8 }}>
            <div style={{ fontSize: 48, marginBottom: 8 }}>{data.quality.grade}</div>
            <div style={{ fontSize: 12, color: "#666" }}>LETTER GRADE</div>
          </div>
        </div>

        {/* Metrics Breakdown */}
        {Object.keys(data.quality.metrics).length > 0 && (
          <div style={{ marginTop: 20, paddingTop: 20, borderTop: "1px solid #eee" }}>
            <div style={{ fontSize: 12, color: "#666", marginBottom: 12, textTransform: "uppercase" }}>
              Score Breakdown
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
              {Object.entries(data.quality.metrics).map(([key, metric]: [string, any]) => (
                <div key={key} style={{ padding: 12, background: "#fafafa", borderRadius: 6 }}>
                  <div style={{ fontSize: 11, color: "#666", marginBottom: 4, textTransform: "uppercase" }}>
                    {key.replace('_', ' ')}
                  </div>
                  <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 2 }}>
                    {metric.value?.toFixed?.(1) ?? metric.value}
                  </div>
                  <div style={{ fontSize: 11, color: "#999" }}>
                    Score: {metric.score?.toFixed(0)} • Weight: {(metric.weight * 100).toFixed(0)}%
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Vetting Checklist */}
      {data.checklist.length > 0 && (
        <div style={{ marginBottom: 24, padding: 20, background: "white", borderRadius: 8, border: "1px solid #ddd" }}>
          <h3 style={{ fontSize: 16, margin: "0 0 16px 0" }}>✓ VETTING CHECKLIST</h3>
          <div style={{ display: "grid", gap: 8 }}>
            {data.checklist.map((item, idx) => (
              <div key={idx} style={{ 
                display: "flex", 
                alignItems: "center", 
                padding: 12, 
                background: "#fafafa", 
                borderRadius: 6,
                borderLeft: `4px solid ${item.status === 'pass' ? '#00C853' : item.status === 'warn' ? '#FFC107' : '#D32F2F'}`
              }}>
                <div style={{ fontSize: 20, marginRight: 12 }}>{getChecklistIcon(item.status)}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 14, fontWeight: 500 }}>{item.item}</div>
                </div>
                <div style={{ fontSize: 14, color: "#666", fontWeight: 600 }}>{item.value}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {data.recommendations.length > 0 && (
        <div style={{ marginBottom: 24, padding: 20, background: "#F0F7FF", borderRadius: 8, border: "2px solid #2196F3" }}>
          <h3 style={{ fontSize: 16, margin: "0 0 16px 0", color: "#0B3D91" }}>💡 RECOMMENDATIONS</h3>
          <div style={{ display: "grid", gap: 8 }}>
            {data.recommendations.map((rec, idx) => (
              <div key={idx} style={{ padding: 12, background: "white", borderRadius: 6, fontSize: 14 }}>
                {rec}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Data Sources & Attribution */}
      <div style={{ marginBottom: 24, padding: 20, background: "white", borderRadius: 8, border: "1px solid #ddd" }}>
        <h3 style={{ fontSize: 16, margin: "0 0 16px 0" }}>📡 DATA SOURCES & ATTRIBUTION</h3>
        
        <div style={{ marginBottom: 16 }}>
          <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "8px 16px", fontSize: 14 }}>
            <div style={{ color: "#666" }}>Primary Source:</div>
            <div style={{ fontWeight: 600 }}>{data.data_sources.primary}</div>
            
            <div style={{ color: "#666" }}>Pipeline:</div>
            <div style={{ fontWeight: 600 }}>{data.data_sources.pipeline}</div>
            
            <div style={{ color: "#666" }}>Access Method:</div>
            <div style={{ fontWeight: 600 }}>{data.data_sources.access_method}</div>
            
            <div style={{ color: "#666" }}>Search Algorithm:</div>
            <div style={{ fontWeight: 600 }}>{data.data_sources.search_algorithm}</div>
          </div>
        </div>

        {data.data_sources.references.length > 0 && (
          <div style={{ paddingTop: 16, borderTop: "1px solid #eee" }}>
            <div style={{ fontSize: 12, color: "#666", marginBottom: 8, textTransform: "uppercase" }}>References</div>
            {data.data_sources.references.map((ref, idx) => (
              <div key={idx} style={{ fontSize: 12, color: "#0B3D91", marginBottom: 4 }}>
                • {ref}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* External Resources */}
      {Object.keys(data.external_links).length > 0 && (
        <div style={{ padding: 20, background: "white", borderRadius: 8, border: "1px solid #ddd" }}>
          <h3 style={{ fontSize: 16, margin: "0 0 16px 0" }}>🔗 EXTERNAL RESOURCES</h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
            {Object.entries(data.external_links).map(([key, url]) => (
              <a
                key={key}
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  padding: 12,
                  background: "#f5f5f5",
                  borderRadius: 6,
                  textDecoration: "none",
                  color: "#0B3D91",
                  fontWeight: 500,
                  fontSize: 14,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  transition: "all 0.2s",
                  border: "1px solid #ddd"
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "#0B3D91";
                  e.currentTarget.style.color = "white";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "#f5f5f5";
                  e.currentTarget.style.color = "#0B3D91";
                }}
              >
                <span>{key.replace('_', ' ').toUpperCase()}</span>
                <span>↗</span>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

