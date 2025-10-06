import React from "react";
import Plot from "react-plotly.js";

const API_BASE = (import.meta as any).env?.VITE_API_BASE || "http://localhost:8000";

type PhaseFoldPlotProps = {
  jobId: string;
  ticId: string;
};

export function PhaseFoldPlot({ jobId, ticId }: PhaseFoldPlotProps) {
  const [data, setData] = React.useState<any>(null);
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
      const resp = await fetch(`${API_BASE}/api/discoveries/${jobId}/phase?n_bins=200`, {
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
        <p>Loading phase-folded data...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 20, background: "#FFEBEE", color: "#C62828", borderRadius: 8 }}>
        <strong>Error loading phase fold:</strong> {error}
      </div>
    );
  }

  if (!data || data.error) {
    return (
      <div style={{ padding: 20, background: "#FFF3CD", color: "#856404", borderRadius: 8 }}>
        <strong>Phase fold unavailable:</strong> {data?.error || "Missing transit parameters"}
      </div>
    );
  }

  // Build traces
  const traces: any[] = [];

  // Raw phase points (light gray, background)
  if (data.phase_raw && data.flux_raw && data.phase_raw.length < 50000) {
    traces.push({
      x: data.phase_raw,
      y: data.flux_raw,
      mode: 'markers',
      type: 'scatter',
      name: 'Individual Points',
      marker: {
        size: 1,
        color: '#cccccc',
        opacity: 0.3
      },
      hoverinfo: 'skip',
      showlegend: true
    });
  }

  // Binned phase points (blue, main signal)
  if (data.phase_binned && data.flux_binned) {
    traces.push({
      x: data.phase_binned,
      y: data.flux_binned,
      mode: 'markers',
      type: 'scatter',
      name: 'Binned Data',
      marker: {
        size: 6,
        color: '#0B3D91',
        opacity: 0.8,
        line: { width: 1, color: 'white' }
      },
      error_y: data.flux_binned_std ? {
        type: 'data',
        array: data.flux_binned_std,
        visible: true,
        color: '#0B3D91',
        thickness: 1,
        width: 2
      } : undefined,
      hovertemplate: '<b>Phase:</b> %{x:.4f}<br><b>Flux:</b> %{y:.6f}<extra></extra>'
    });
  }

  // Transit model overlay (red line)
  if (data.phase_model && data.flux_model) {
    traces.push({
      x: data.phase_model,
      y: data.flux_model,
      mode: 'lines',
      type: 'scatter',
      name: 'Transit Model',
      line: {
        color: '#D32F2F',
        width: 3,
        dash: 'solid'
      },
      hoverinfo: 'skip'
    });
  }

  const layout = {
    title: {
      text: `TIC ${ticId} — Phase-Folded Transit (P = ${data.period?.toFixed(3)} d)`,
      font: { size: 18, family: 'system-ui, sans-serif' }
    },
    xaxis: {
      title: 'Phase',
      showgrid: true,
      gridcolor: '#eee',
      zeroline: true,
      zerolinecolor: '#999',
      range: [-0.15, 0.15]  // Zoom to transit
    },
    yaxis: {
      title: 'Normalized Flux',
      showgrid: true,
      gridcolor: '#eee',
      zeroline: false
    },
    hovermode: 'closest',
    showlegend: true,
    legend: {
      orientation: 'h',
      y: -0.15,
      x: 0.5,
      xanchor: 'center'
    },
    margin: { l: 60, r: 40, t: 60, b: 80 },
    plot_bgcolor: '#fafafa',
    paper_bgcolor: 'white',
    height: 400,
    annotations: [
      {
        x: 0,
        y: 1 - (data.depth || 0),
        xref: 'x',
        yref: 'y',
        text: `Depth: ${((data.depth || 0) * 1e6).toFixed(0)} ppm`,
        showarrow: true,
        arrowhead: 2,
        arrowsize: 1,
        arrowwidth: 2,
        arrowcolor: '#D32F2F',
        ax: 40,
        ay: -40,
        font: { size: 12, color: '#D32F2F' },
        bgcolor: 'rgba(255,255,255,0.9)',
        bordercolor: '#D32F2F',
        borderwidth: 1,
        borderpad: 4
      }
    ]
  };

  const config = {
    displayModeBar: true,
    displaylogo: false,
    modeBarButtonsToRemove: ['select2d', 'lasso2d'],
    toImageButtonOptions: {
      format: 'png',
      filename: `TIC_${ticId}_phase_fold`,
      height: 800,
      width: 1400,
      scale: 2
    }
  };

  return (
    <div>
      <Plot
        data={traces}
        layout={layout as any}
        config={config}
        style={{ width: '100%' }}
        useResizeHandler={true}
      />
      
      <div style={{ fontSize: 12, color: '#666', marginTop: 8, textAlign: 'center' }}>
        📊 {data.n_points?.toLocaleString()} points folded into {data.n_bins} phase bins
        {data.duration && (
          <span> • Transit duration: {(data.duration * 24).toFixed(2)} hours</span>
        )}
      </div>
    </div>
  );
}

