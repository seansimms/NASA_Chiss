import React from "react";
import Plot from "react-plotly.js";

const API_BASE = (import.meta as any).env?.VITE_API_BASE || "http://localhost:8000";

type LightCurvePlotProps = {
  jobId: string;
  ticId: string;
};

export function LightCurvePlot({ jobId, ticId }: LightCurvePlotProps) {
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
      const resp = await fetch(`${API_BASE}/api/discoveries/${jobId}/lightcurve?max_points=10000`, {
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
        <p>Loading light curve data...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 20, background: "#FFEBEE", color: "#C62828", borderRadius: 8 }}>
        <strong>Error loading light curve:</strong> {error}
      </div>
    );
  }

  if (!data || !data.time || data.time.length === 0) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "#999" }}>
        <p>No light curve data available</p>
      </div>
    );
  }

  // Build traces for each sector (different colors)
  const sectorColors = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
    '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
  ];

  const traces = data.sectors.map((sector: [number, number], idx: number) => {
    const [start, end] = sector;
    const sectorTime = data.time.slice(start, end);
    const sectorFlux = data.flux.slice(start, end);
    
    return {
      x: sectorTime,
      y: sectorFlux,
      mode: 'markers',
      type: 'scatter',
      name: `Sector ${idx + 1}`,
      marker: {
        size: 2,
        color: sectorColors[idx % sectorColors.length],
        opacity: 0.6
      },
      hovertemplate: '<b>Time:</b> %{x:.4f} BTJD<br><b>Flux:</b> %{y:.6f}<extra></extra>'
    };
  });

  const layout = {
    title: {
      text: `TIC ${ticId} — Full Light Curve`,
      font: { size: 18, family: 'system-ui, sans-serif' }
    },
    xaxis: {
      title: 'Time (BTJD)',
      showgrid: true,
      gridcolor: '#eee',
      zeroline: false
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
    height: 400
  };

  const config = {
    displayModeBar: true,
    displaylogo: false,
    modeBarButtonsToRemove: ['select2d', 'lasso2d'],
    toImageButtonOptions: {
      format: 'png',
      filename: `TIC_${ticId}_lightcurve`,
      height: 800,
      width: 1400,
      scale: 2
    }
  };

  return (
    <div>
      <Plot
        data={traces as any}
        layout={layout as any}
        config={config}
        style={{ width: '100%' }}
        useResizeHandler={true}
      />
      
      <div style={{ fontSize: 12, color: '#666', marginTop: 8, textAlign: 'center' }}>
        {data.decimated && (
          <span>
            📊 Showing {data.returned_n_points.toLocaleString()} of {data.original_n_points.toLocaleString()} points
            (decimated for performance, transits preserved)
          </span>
        )}
        {!data.decimated && (
          <span>📊 Showing all {data.returned_n_points.toLocaleString()} data points</span>
        )}
      </div>
    </div>
  );
}

