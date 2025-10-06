import React from "react";
import Plotly from "plotly.js-dist-min";
import { apiFetch } from "../lib/api";
import { getParam, setQuery } from "../lib/url";
import { exportPlotPng, copyPermalink } from "../lib/export";
const API_BASE = (import.meta as any).env?.VITE_API_BASE || "http://localhost:8000";

type RunItem = { run_id: string, created_at?: string, auprc?: number };
type HistoryResp = { items: RunItem[] };

export function RunCompare(){
  const [runs,setRuns]=React.useState<RunItem[]>([]);
  const [a,setA]=React.useState<string>(getParam("run_a") || "");
  const [b,setB]=React.useState<string>(getParam("run_b") || "");
  const [metrics,setMetrics]=React.useState<any>(null);
  const [gates,setGates]=React.useState<any>(null);
  const [model,setModel]=React.useState<"ens"|"h1">("ens");
  const [calBins,setCalBins]=React.useState<number>(15);
  const [err,setErr]=React.useState<string|null>(null);

  const loadRuns = async ()=>{
    setErr(null);
    try{
      const r = await apiFetch(`${API_BASE}/api/metrics/history?limit=200`);
      const j = await r.json() as HistoryResp;
      setRuns(j.items || []);
      if(!a && j.items?.length) setA(j.items[0].run_id);
      if(!b && j.items?.length>1) setB(j.items[1].run_id);
    }catch(e:any){ setErr(e.message); }
  };

  const drawPR = async ()=>{
    if(!a || !b) return;
    const r = await apiFetch(`${API_BASE}/api/reliability/compare_pr?run_a=${encodeURIComponent(a)}&run_b=${encodeURIComponent(b)}&model=${model}`);
    if(!r.ok){ return; }
    const j = await r.json();
    const recall = j.recall;
    const pa = j.precision_a;
    const pb = j.precision_b;
    const dp = j.delta_precision;
    const overlayDiv = document.getElementById("cmp-pr") as any;
    const deltaDiv = document.getElementById("cmp-pr-delta") as any;
    Plotly.react(overlayDiv, [
      {x: recall, y: pa, mode:"lines", name:`A ${a} (${model})`},
      {x: recall, y: pb, mode:"lines", name:`B ${b} (${model})`}
    ], {margin:{t:28}, xaxis:{title:"Recall"}, yaxis:{title:"Precision"}, legend:{orientation:"h"}}, {displaylogo:false});
    Plotly.react(deltaDiv, [
      {x: recall, y: dp, mode:"lines", name:"Δ precision (B−A)"},
      {x: [0,1], y:[0,0], mode:"lines", name:"0 baseline", line:{dash:"dot"} as any}
    ], {margin:{t:28}, xaxis:{title:"Recall"}, yaxis:{title:"Δ Precision"}, legend:{orientation:"h"}}, {displaylogo:false});
  };

  const drawCal = async ()=>{
    if(!a || !b) return;
    const url = `${API_BASE}/api/reliability/compare_cal?run_a=${encodeURIComponent(a)}&run_b=${encodeURIComponent(b)}&model=${model}&bins=${calBins}`;
    const r = await apiFetch(url);
    if(!r.ok) return;
    const j = await r.json();
    const x = j.centers;
    const confA = j.confidence_a, confB = j.confidence_b;
    const accA  = j.accuracy_a,  accB  = j.accuracy_b;
    const gapD  = j.delta_gap;
    const relDiv = document.getElementById("cmp-calib") as any;
    const gapDiv = document.getElementById("cmp-calib-delta") as any;
    // Reliability overlay: accuracy vs confidence for A and B, plus y=x
    Plotly.react(relDiv, [
      {x: confA, y: accA, mode:"lines+markers", name:`A ${a}`},
      {x: confB, y: accB, mode:"lines+markers", name:`B ${b}`},
      {x: [0,1], y:[0,1], mode:"lines", name:"perfect", line: {dash:"dot"} as any}
    ], {margin:{t:28}, xaxis:{title:"Confidence (mean p in bin)", range:[0,1]}, yaxis:{title:"Accuracy (empirical)", range:[0,1]}, legend:{orientation:"h"}}, {displaylogo:false});
    // Δ gap bar chart: (acc - conf)_B - (acc - conf)_A vs bin center
    Plotly.react(gapDiv, [
      {x, y: gapD, type:"bar", name:"Δ (acc−conf) B−A"}
    ], {margin:{t:28}, xaxis:{title:"Bin center (p)"}, yaxis:{title:"Δ calibration gap (B−A)"}, legend:{orientation:"h"}}, {displaylogo:false});
    // ECE summary
    const ece = document.getElementById("cmp-calib-ece");
    if(ece){
      (ece as any).textContent = `ECE — A: ${j.ece_a.toFixed(3)}  |  B: ${j.ece_b.toFixed(3)}  |  Δ: ${j.delta_ece.toFixed(3)}`;
    }
  };

  const loadMeta = async ()=>{
    if(!a || !b) return;
    const m = await (await apiFetch(`${API_BASE}/api/metrics/compare?run_a=${encodeURIComponent(a)}&run_b=${encodeURIComponent(b)}`)).json();
    const g = await (await apiFetch(`${API_BASE}/api/gates/compare?run_a=${encodeURIComponent(a)}&run_b=${encodeURIComponent(b)}`)).json();
    setMetrics(m); setGates(g);
  };

  React.useEffect(()=>{ loadRuns(); },[]);
  React.useEffect(()=>{
    if(a && b){
      setQuery({ tab:"compare", run_a:a, run_b:b });
      loadMeta(); drawPR(); drawCal();
    }
  },[a,b,model,calBins]);

  const csvUrl = a && b ? `${API_BASE}/api/reliability/compare_pr.csv?run_a=${encodeURIComponent(a)}&run_b=${encodeURIComponent(b)}&model=${model}` : "#";
  const rptCsvUrl = a && b ? `${API_BASE}/api/compare/report.csv?run_a=${encodeURIComponent(a)}&run_b=${encodeURIComponent(b)}` : "#";
  const rptMdUrl  = a && b ? `${API_BASE}/api/compare/report.md?run_a=${encodeURIComponent(a)}&run_b=${encodeURIComponent(b)}` : "#";
  const calCsvUrl = a && b ? `${API_BASE}/api/reliability/compare_cal.csv?run_a=${encodeURIComponent(a)}&run_b=${encodeURIComponent(b)}&model=${model}&bins=${calBins}` : "#";
  const gatesCsvUrl = a && b ? `${API_BASE}/api/gates/delta.csv?run_a=${encodeURIComponent(a)}&run_b=${encodeURIComponent(b)}` : "#";

  return (
    <div style={{border:"1px solid #ddd", borderRadius:8, padding:12}}>
      <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:8}}>
        <h3>Run Comparator</h3>
        <div>
          <label style={{marginRight:6}}>Run A:</label>
          <select value={a} onChange={e=>setA(e.target.value)}>
            {runs.map(r=><option key={r.run_id} value={r.run_id}>{r.run_id}</option>)}
          </select>
          <label style={{margin:"0 6px 0 12px"}}>Run B:</label>
          <select value={b} onChange={e=>setB(e.target.value)}>
            {runs.map(r=><option key={r.run_id} value={r.run_id}>{r.run_id}</option>)}
          </select>
          <label style={{margin:"0 6px 0 12px"}}>Model:</label>
          <select value={model} onChange={e=>setModel(e.target.value as any)}>
            <option value="ens">Ensemble</option>
            <option value="h1">H1</option>
          </select>
          <label style={{margin:"0 6px 0 12px"}}>Bins:</label>
          <select value={calBins} onChange={e=>setCalBins(parseInt(e.target.value))}>
            {[10,15,20,30].map(n=><option key={n} value={n}>{n}</option>)}
          </select>
          <a href={csvUrl} target="_blank" rel="noreferrer"><button style={{marginLeft:8}}>CSV PR Δ</button></a>
          <button style={{marginLeft:6}} onClick={()=>exportPlotPng("cmp-pr", `compare_pr_${a}_vs_${b}_${model}.png`)}>PNG PR</button>
          <button style={{marginLeft:6}} onClick={()=>exportPlotPng("cmp-pr-delta", `compare_pr_delta_${a}_vs_${b}_${model}.png`)}>PNG Δ</button>
          <span style={{marginLeft:12, opacity:0.7}}>Export Report:</span>
          <a href={rptCsvUrl} target="_blank" rel="noreferrer"><button style={{marginLeft:6}}>CSV</button></a>
          <a href={rptMdUrl} target="_blank" rel="noreferrer"><button style={{marginLeft:6}}>Markdown</button></a>
          <button style={{marginLeft:6}} onClick={()=>copyPermalink()}>Copy Link</button>
        </div>
      </div>

      <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:12}}>
        <div id="cmp-pr" style={{height:320}} />
        <div id="cmp-pr-delta" style={{height:320}} />
      </div>

      <div style={{marginTop:12, display:"grid", gridTemplateColumns:"1fr 1fr", gap:12}}>
        <div style={{border:"1px solid #eee", borderRadius:8, padding:8}}>
          <h4>Key Metrics (B − A)</h4>
          {metrics ? (
            <table>
              <thead><tr><th>Metric</th><th>A</th><th>B</th><th>Δ (B−A)</th></tr></thead>
              <tbody>
                {["auprc","brier","ece","recall_small_at_1pct","n","n_pos"].map(k=>{
                  const aV = metrics.run_a?.[k]; const bV = metrics.run_b?.[k]; const dV = metrics.delta_b_minus_a?.[k];
                  return (<tr key={k}>
                    <td>{k}</td><td>{aV ?? "—"}</td><td>{bV ?? "—"}</td><td style={{color: (dV||0) >= 0 ? "#070" : "#900"}}>{dV ?? "—"}</td>
                  </tr>);
                })}
              </tbody>
            </table>
          ) : <p>Loading…</p>}
        </div>
        <div style={{border:"1px solid #eee", borderRadius:8, padding:8}}>
          <div style={{display:"flex", justifyContent:"space-between", alignItems:"center"}}>
            <h4 style={{margin:0}}>Gate Changes</h4>
            <div>
              <a href={gatesCsvUrl} target="_blank" rel="noreferrer"><button>CSV Gates Δ</button></a>
            </div>
          </div>
          {gates ? (
            <div style={{display:"flex", flexWrap:"wrap", gap:8}}>
              {Object.entries(gates.changes || {}).map(([k, v]: [string, any])=>{
                const aPass = v.a; const bPass = v.b;
                const color = aPass===bPass ? "#555" : (bPass ? "#070" : "#900");
                const label = aPass===bPass ? (aPass ? "PASS↔PASS" : "FAIL↔FAIL") : (aPass ? "PASS→FAIL" : "FAIL→PASS");
                return <span key={k} style={{border:`1px solid ${color}`, color, padding:"2px 6px", borderRadius:6, fontSize:12}}>{k}: {label}</span>
              })}
            </div>
          ) : <p>Loading…</p>}
        </div>
      </div>

    </div>
  );
}
