import React from "react";
import Plotly from "plotly.js-dist-min";
import { getParam, setQuery } from "../lib/url";
import { exportPlotPng, copyPermalink } from "../lib/export";
import { apiFetch } from "../lib/api";
const API_BASE = (import.meta as any).env?.VITE_API_BASE || "http://localhost:8000";

type HistoryItem = { run_id:string; created_at:number };
type HistoryResp = { total:number; items:HistoryItem[] };

export function ReliabilityPanel(){
  const [runs,setRuns]=React.useState<HistoryItem[]>([]);
  const [run,setRun]=React.useState<string>(getParam("run") || "");
  const [err,setErr]=React.useState<string|null>(null);
  const [haveH1,setHaveH1]=React.useState<boolean>(true);

  const loadRuns = async ()=>{
    try{
      const r = await apiFetch(`${API_BASE}/api/metrics/history?limit=200`);
      const j = await r.json() as HistoryResp;
      setRuns(j.items || []);
      if(j.items && j.items.length>0 && !run){
        const initial = getParam("run") || j.items[0].run_id;
        setRun(initial);
      }
    }catch(e:any){ setErr(e.message); }
  };
  React.useEffect(()=>{ loadRuns(); }, []);

  const draw = async ()=>{
    if(!run) return;
    setErr(null);
    try{
      // Calibration (ens)
      const cal = await (await apiFetch(`${API_BASE}/api/reliability/run/${encodeURIComponent(run)}/calibration?bins=15&model=ens`)).json();
      Plotly.newPlot("rel-cal", [
        {x: cal.bin_mid, y: cal.acc, mode:"lines+markers", name:"Accuracy"},
        {x: cal.bin_mid, y: cal.conf_mean, mode:"lines+markers", name:"Confidence"},
        {x: [0,1], y: [0,1], mode:"lines", name:"Ideal", line:{dash:"dash"}}
      ] as any, {title:`Calibration (ENS) — ECE=${cal.ece.toFixed(3)}`, xaxis:{title:"Confidence"}, yaxis:{title:"Accuracy"}, margin:{l:50,r:10,t:40,b:40}} as any, {displaylogo:false});

      // ECE bars (ens)
      const gaps = cal.acc.map((a:number, i:number)=> Math.abs((a ?? 0) - cal.conf_mean[i]));
      Plotly.newPlot("rel-ece", [
        {x: cal.bin_mid, y: gaps, type:"bar", name:"|acc-conf|"}
      ] as any, {title:"ECE Bin Gaps (ENS)", xaxis:{title:"Confidence bin mid"}, yaxis:{title:"Gap"}, margin:{l:50,r:10,t:40,b:40}} as any, {displaylogo:false});

      // PR overlay
      const pr = await (await apiFetch(`${API_BASE}/api/reliability/run/${encodeURIComponent(run)}/pr_overlay`)).json();
      const traces:any[] = [
        {x: pr.curves.ens.recall, y: pr.curves.ens.precision, mode:"lines", name:`ENS (AUPRC=${pr.curves.ens.auprc.toFixed(3)})`}
      ];
      if(pr.curves.h1){
        setHaveH1(true);
        traces.push({x: pr.curves.h1.recall, y: pr.curves.h1.precision, mode:"lines", name:`H1 (AUPRC=${pr.curves.h1.auprc.toFixed(3)})`});
      } else {
        setHaveH1(false);
      }
      if(pr.baselines && pr.baselines.length){
        for(const b of pr.baselines){
          traces.push({x: b.recall, y: b.precision, mode:"lines", name:b.name});
        }
      }
      Plotly.newPlot("rel-pr", traces as any, {title:"Precision–Recall Overlay", xaxis:{title:"Recall"}, yaxis:{title:"Precision"}, margin:{l:50,r:10,t:40,b:40}} as any, {displaylogo:false});
    }catch(e:any){ setErr(e.message); }
  };
  React.useEffect(()=>{ draw(); }, [run]);

  return (
    <div style={{border:"1px solid #ddd", borderRadius:8, padding:12}}>
      <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:8}}>
        <h3>Reliability & PR Overlays</h3>
        <div>
          <label style={{marginRight:8}}>Run:</label>
          <select value={run} onChange={e=>{
              const val = e.target.value; setRun(val);
              setQuery({ run: val, tab: "reliability" });
            }}>
            {runs.map(r=><option value={r.run_id} key={r.run_id}>{r.run_id}</option>)}
          </select>
          <button style={{marginLeft:8}} onClick={()=>draw()}>Refresh</button>
          {run && (
            <>
              <a style={{marginLeft:8}} href={`${API_BASE}/api/reliability/run/${encodeURIComponent(run)}/calibration.csv?bins=15&model=ens`} target="_blank" rel="noreferrer"><button>CSV Calibration</button></a>
              <a style={{marginLeft:6}} href={`${API_BASE}/api/reliability/run/${encodeURIComponent(run)}/pr_curve.csv?model=ens`} target="_blank" rel="noreferrer"><button>CSV PR (ENS)</button></a>
            </>
          )}
          <button style={{marginLeft:6}} onClick={()=>copyPermalink()}>Copy Link</button>
        </div>
      </div>
      {err && <p style={{color:"#b00"}}>{err}</p>}
      <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:12}}>
        <div>
          <div id="rel-cal" style={{height:320}} />
          <div style={{textAlign:"right"}}><button onClick={()=>exportPlotPng("rel-cal", `reliability_cal_${run||"run"}.png`)}>Export PNG</button></div>
        </div>
        <div>
          <div id="rel-ece" style={{height:320}} />
          <div style={{textAlign:"right"}}><button onClick={()=>exportPlotPng("rel-ece", `reliability_ece_${run||"run"}.png`)}>Export PNG</button></div>
        </div>
      </div>
      <div id="rel-pr" style={{height:340, marginTop:12}} />
      <div style={{textAlign:"right"}}><button onClick={()=>exportPlotPng("rel-pr", `reliability_pr_${run||"run"}.png`)}>Export PNG</button></div>
      {!haveH1 && <p style={{fontSize:12, color:"#666"}}>No H1 scores found in OOF; overlay shows ENS only.</p>}
    </div>
  );
}
