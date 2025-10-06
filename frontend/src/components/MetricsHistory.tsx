import React from "react";
import Plotly from "plotly.js-dist-min";
import { getParam, setQuery, scrollToTab } from "../lib/url";
import { exportPlotPng, copyPermalink } from "../lib/export";
import { apiFetch } from "../lib/api";
import { Sparkline } from "./Sparkline";
const API_BASE = (import.meta as any).env?.VITE_API_BASE || "http://localhost:8000";

type HistoryItem = {
  run_id:string;
  auprc?:number; brier?:number; ece?:number;
  created_at?:string|number;
};

export function MetricsHistory(){
  const [hist,setHist]=React.useState<HistoryItem[]>([]);
  const [err,setErr]=React.useState<string|null>(null);
  const [sel,setSel]=React.useState<string|undefined>(getParam("run"));
  const [detail,setDetail]=React.useState<any|null>(null);
  const [role,setRole]=React.useState<string>("anonymous");
  const [series,setSeries]=React.useState<{auprc:number[], brier:number[], runs:string[]}>({auprc:[], brier:[], runs:[]});

  const load = async ()=>{
    setErr(null);
    try{
      // Compact history for sparklines & deltas
      const r = await apiFetch(`${API_BASE}/api/metrics/history_compact?limit=200`);
      if(!r.ok) throw new Error(await r.text());
      const j = await r.json() as any;
      const items = (j.items || []) as any[];
      setHist(items);
      if(items && items.length>0 && !sel){
        const initial = getParam("run") || items[items.length-1].run_id; // newest
        setSel(initial);
      }
      // Build series oldest→newest
      const au = items.map(it => (typeof it.auprc === "number" ? it.auprc : NaN)).filter(v=>isFinite(v));
      const br = items.map(it => (typeof it.brier === "number" ? it.brier : NaN)).filter(v=>isFinite(v));
      const rn = items.map(it => it.run_id);
      setSeries({ auprc: au.slice(-50), brier: br.slice(-50), runs: rn.slice(-50) });
      const who = await apiFetch(`${API_BASE}/api/auth/whoami`);
      if(who.ok){ const jw = await who.json(); setRole(jw.role || "anonymous"); }
    }catch(e:any){ setErr(e.message); }
  };
  const loadDetail = async (run_id:string)=>{
    try{
      const r = await apiFetch(`${API_BASE}/api/metrics/run/${encodeURIComponent(run_id)}`);
      if(!r.ok) throw new Error(await r.text());
      setDetail(await r.json());
    }catch(e:any){ setErr(e.message); }
  };

  // Helpers for per-row delta vs previous
  const idxByRun = React.useMemo(()=>{
    const m = new Map<string, number>();
    hist.forEach((h,i)=> m.set(h.run_id, i));
    return m;
  },[hist]);
  const deltaFor = (run_id:string, key:"auprc"|"brier")=>{
    const idx = idxByRun.get(run_id);
    if(idx===undefined || idx<=0) return null;
    const prev = hist[idx-1]?.[key];
    const cur  = hist[idx]?.[key];
    if(typeof prev !== "number" || typeof cur !== "number") return null;
    return cur - prev;
  };
  const openComparePrev = (run_id:string)=>{
    const idx = idxByRun.get(run_id);
    if(idx===undefined || idx<=0) return;
    const prev = hist[idx-1]?.run_id;
    if(!prev) return;
    setQuery({ tab:"compare", run_a: prev, run_b: run_id });
    scrollToTab("compare");
  };
  React.useEffect(()=>{ load(); }, []);
  React.useEffect(()=>{ if(sel) loadDetail(sel); }, [sel]);
  React.useEffect(()=>{
    // charts
    if(hist.length>0){
      const x = hist.map(h=>new Date(h.created_at*1000));
      Plotly.newPlot("mh-auprc", [{x, y: hist.map(h=>h.auprc), mode:"lines+markers", name:"AUPRC"}] as any,
        {title:"AUPRC over Runs", xaxis:{title:"Time"}, yaxis:{title:"AUPRC"}, margin:{l:50,r:10,t:40,b:40}} as any, {displaylogo:false});
      Plotly.newPlot("mh-brier", [{x, y: hist.map(h=>h.brier), mode:"lines+markers", name:"Brier"}] as any,
        {title:"Brier over Runs", xaxis:{title:"Time"}, yaxis:{title:"Brier (lower better)"}, margin:{l:50,r:10,t:40,b:40}} as any, {displaylogo:false});
      Plotly.newPlot("mh-ece", [{x, y: hist.map(h=>h.ece), mode:"lines+markers", name:"ECE"}] as any,
        {title:"ECE over Runs", xaxis:{title:"Time"}, yaxis:{title:"ECE (lower better)"}, margin:{l:50,r:10,t:40,b:40}} as any, {displaylogo:false});
      const rs = hist.map(h=>h.recall_small_at_1pct ?? null);
      if(rs.some(v=>v!=null)){
        Plotly.newPlot("mh-smallrecall", [{x, y: rs, mode:"lines+markers", name:"Recall@1% (small)"}] as any,
          {title:"Small-Planet Recall @ FPR≤1%", xaxis:{title:"Time"}, yaxis:{title:"Recall"}, margin:{l:50,r:10,t:40,b:40}} as any, {displaylogo:false});
      } else {
        const el = document.getElementById("mh-smallrecall"); if(el) el.innerHTML = "<div style='padding:8px;color:#666'>No small-planet recall logged yet.</div>";
      }
    }
  }, [hist]);

  return (
    <div style={{border:"1px solid #ddd", borderRadius:8, padding:12}}>
      <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:8}}>
        <h3>Metrics History</h3>
        <div>
          <button onClick={()=>{ copyPermalink(); }}>{`Copy Link`}</button>
        </div>
      </div>
      {err && <p style={{color:"#b00"}}>{err}</p>}
      {/* Sparklines row */}
      <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:12, marginBottom:12}}>
        <div style={{border:"1px solid #eee", borderRadius:8, padding:"6px 8px"}}>
          <div style={{display:"flex", justifyContent:"space-between"}}>
            <strong>AUPRC (last {series.auprc.length})</strong>
            {series.auprc.length>=2 && (
              <span style={{fontVariantNumeric:"tabular-nums", color: (series.auprc[series.auprc.length-1]-series.auprc[series.auprc.length-2])>=0 ? "#070" : "#900"}}>
                Δ {(series.auprc[series.auprc.length-1]-series.auprc[series.auprc.length-2]).toFixed(3)}
              </span>
            )}
          </div>
          <Sparkline data={series.auprc} />
        </div>
        <div style={{border:"1px solid #eee", borderRadius:8, padding:"6px 8px"}}>
          <div style={{display:"flex", justifyContent:"space-between"}}>
            <strong>Brier (last {series.brier.length})</strong>
            {series.brier.length>=2 && (
              <span style={{fontVariantNumeric:"tabular-nums", color: (series.brier[series.brier.length-1]-series.brier[series.brier.length-2])<=0 ? "#070" : "#900"}}>
                Δ {(series.brier[series.brier.length-1]-series.brier[series.brier.length-2]).toFixed(3)}
              </span>
            )}
          </div>
          <Sparkline data={series.brier} />
        </div>
      </div>
      <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:12}}>
        <div>
          <table style={{width:"100%", borderCollapse:"collapse"}}>
            <thead><tr>
              <th style={{textAlign:"left"}}>Run</th>
              <th>Created</th><th>AUPRC (Δ)</th><th>Brier (Δ)</th><th>Actions</th>
            </tr></thead>
            <tbody>
              {hist.slice().reverse().map((h:any)=>(
                <tr key={h.run_id}>
                  <td>{h.run_id}</td>
                  <td>{h.created_at || "—"}</td>
                  <td>
                    {typeof h.auprc==="number" ? h.auprc.toFixed(3) : "—"}
                    {(()=>{
                      const d = deltaFor(h.run_id, "auprc");
                      if(d===null) return null;
                      const good = d>=0;
                      return <button title="Compare vs previous" onClick={()=>openComparePrev(h.run_id)} style={{marginLeft:6, fontSize:11, padding:"1px 6px", borderRadius:6, border:`1px solid ${good?"#0a0":"#a00"}`, color:good?"#070":"#900", background:"transparent"}}>Δ {d>=0?"+":""}{d.toFixed(3)}</button>;
                    })()}
                  </td>
                  <td>
                    {typeof h.brier==="number" ? h.brier.toFixed(3) : "—"}
                    {(()=>{
                      const d = deltaFor(h.run_id, "brier");
                      if(d===null) return null;
                      const good = d<=0;
                      return <button title="Compare vs previous" onClick={()=>openComparePrev(h.run_id)} style={{marginLeft:6, fontSize:11, padding:"1px 6px", borderRadius:6, border:`1px solid ${good?"#0a0":"#a00"}`, color:good?"#070":"#900", background:"transparent"}}>Δ {d>=0?"+":""}{d.toFixed(3)}</button>;
                    })()}
                  </td>
                  <td>
                    <button onClick={()=>{ setSel(h.run_id); setQuery({ run: h.run_id, tab:"reliability" }); }}>Reliability</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{border:"1px solid #eee", borderRadius:8, padding:8}}>
          <h4>Run Detail</h4>
          {!detail && <p>Select a run to view details.</p>}
          {detail && (
            <>
              <p><strong>Run:</strong> {detail.summary.run_id}</p>
              <p><strong>AUPRC:</strong> {detail.summary.auprc?.toFixed(3)} &nbsp; <strong>Brier:</strong> {detail.summary.brier?.toFixed(3)} &nbsp; <strong>ECE:</strong> {detail.summary.ece?.toFixed(3)}</p>
              <p><strong>Counts:</strong> n={detail.summary.n}, n_pos={detail.summary.n_pos} &nbsp; <strong>Candidates stored:</strong> {detail.candidates_count}</p>
              {detail.detail?.gates && (
                <div style={{marginTop:6}}>
                  <strong>Gates:</strong>{" "}
                  {Object.entries(detail.detail.gates).map(([k,v]:[string,any])=>(
                    <span key={k} style={{marginRight:8, color: v ? "#070" : "#900"}}>{k}:{v ? "PASS" : "FAIL"}</span>
                  ))}
                </div>
              )}
              {detail.job && (
                <p style={{marginTop:6}}>
                  <strong>Job:</strong> {detail.job.job_type} • state={detail.job.state} • started={detail.job.started_at ? new Date(detail.job.started_at*1000).toLocaleString():"—"}
                </p>
              )}
              {sel && (
                <div style={{marginTop:8, display:"flex", gap:8, flexWrap:"wrap"}}>
                  <a href={`${API_BASE}/api/reliability/run/${encodeURIComponent(sel)}/calibration.csv?bins=15&model=ens`} target="_blank" rel="noreferrer"><button>Export Calibration CSV (ENS)</button></a>
                  <a href={`${API_BASE}/api/reliability/run/${encodeURIComponent(sel)}/pr_curve.csv?model=ens`} target="_blank" rel="noreferrer"><button>Export PR CSV (ENS)</button></a>
                </div>
              )}
              {role === "admin" && sel && (
                <div style={{marginTop:8}}>
                  <button onClick={async ()=>{
                    const r = await apiFetch(`${API_BASE}/api/reliability/run/${encodeURIComponent(sel)}/cache`, {method:"POST"});
                    if(!r.ok){ alert("Cache build failed: " + await r.text()); }
                    else { alert("Cache built"); }
                  }}>Build Reliability Cache (admin)</button>
                  <button style={{marginLeft:8}} onClick={async ()=>{
                    const r = await apiFetch(`${API_BASE}/api/reliability/cache_recent`, {method:"POST"});
                    if(!r.ok){ alert("Cache recent failed: " + await r.text()); }
                    else { alert("Cache built for recent runs"); }
                  }}>Cache Recent Runs</button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
