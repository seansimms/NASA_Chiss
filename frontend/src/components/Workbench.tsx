import React from "react";
import Plotly from "plotly.js-dist-min";
import { getParam, setQuery } from "../lib/url";
import { apiFetch } from "../lib/api";
const API_BASE = (import.meta as any).env?.VITE_API_BASE || "http://localhost:8000";

type LC = { star:string; n:number; time:number[]; flux:number[]; gaps:[number,number][]; source:string };
type Phase = { star:string; phase:number[]; flux:number[]; model?:number[]|null; period?:number|null; t0?:number|null; duration?:number|null; source:string };
type OE = { odd:{phase:number[]; flux:number[]; depth?:number|null}, even:{phase:number[]; flux:number[]; depth?:number|null}, z?:number|null, source:string };
type Centroid = { time:number[]; dx:number[]; dy:number[]; r:number[]; source:string };
type Index = { star:string; artifacts:{run_id:string; kind:string; path:string; size:number; mtime:number}[] };

export function Workbench(){
  const [star,setStar]=React.useState<string>(getParam("star") || "");
  const [phaseMode,setPhaseMode]=React.useState<boolean>((getParam("phase")||"").toLowerCase()==="true");
  const [phaseWindow,setPhaseWindow]=React.useState<number|undefined>(undefined);
  const [lc,setLC]=React.useState<LC|null>(null);
  const [ph,setPH]=React.useState<Phase|null>(null);
  const [oe,setOE]=React.useState<OE|null>(null);
  const [ct,setCT]=React.useState<Centroid|null>(null);
  const [err,setErr]=React.useState<string|null>(null);

  const load = async ()=>{
    setErr(null); setLC(null); setPH(null); setOE(null); setCT(null);
    try{
      const idxr = await apiFetch(`${API_BASE}/api/workbench/index/${encodeURIComponent(star)}`);
      if(!idxr.ok){ setErr("Index not available."); return; }
      const idx = await idxr.json() as Index;
      const kinds = new Set(idx.artifacts.map(a=>a.kind));
      const reqs: Promise<Response>[] = [];
      if(kinds.has("lc_raw")) reqs.push(apiFetch(`${API_BASE}/api/workbench/lightcurve/${encodeURIComponent(star)}`)); else reqs.push(Promise.resolve(new Response(null)));
      if(kinds.has("phase")||kinds.has("fit")||kinds.has("tls_result")) reqs.push(apiFetch(`${API_BASE}/api/workbench/phase/${encodeURIComponent(star)}`)); else reqs.push(Promise.resolve(new Response(null)));
      if(kinds.has("odd_even")) reqs.push(apiFetch(`${API_BASE}/api/workbench/oddeven/${encodeURIComponent(star)}`)); else reqs.push(Promise.resolve(new Response(null)));
      if(kinds.has("centroid")) reqs.push(apiFetch(`${API_BASE}/api/workbench/centroid/${encodeURIComponent(star)}`)); else reqs.push(Promise.resolve(new Response(null)));
      const [rlc, rph, roe, rct] = await Promise.all(reqs);
      if(rlc && rlc.ok){ setLC(await rlc.json()); }
      if(rph && rph.ok){
        const phj = await rph.json();
        setPH(phj);
        // compute ±2.5 duration window in phase units if meta present
        try{
          const pd = phj?.meta?.period_days;
          const dd = phj?.meta?.duration_days;
          if (pd && dd && isFinite(pd) && isFinite(dd) && pd>0 && dd>0){
            setPhaseWindow(2.5 * (dd / pd));
          } else {
            setPhaseWindow(undefined);
          }
        }catch{}
      }
      if(roe && roe.ok){ setOE(await roe.json()); }
      if(rct && rct.ok){ setCT(await rct.json()); }
      if(!(rlc as any)?.ok && !(rph as any)?.ok && !(roe as any)?.ok && !(rct as any)?.ok){
        setErr("No artifacts available for this star yet.");
      }
    }catch(e:any){ setErr(e.message); }
    setTimeout(renderAll, 50);
  };

  const renderAll = ()=>{
    if(lc){
      Plotly.newPlot("plot-lc", [{
        x: lc.time, y: lc.flux, mode:"markers", type:"scattergl", name:"Flux"
      } as any], {
        title: `Raw Light Curve (${lc.star})`,
        xaxis:{title:"Time [BJD]"}, yaxis:{title:"Normalized Flux"},
        margin:{l:50,r:10,t:40,b:40}
      } as any, {displaylogo:false});
    }
    if(ph){
      const data:any[] = [{x: ph.phase, y: ph.flux, mode:"markers", type:"scattergl", name:"Phase"}];
      if(ph.model && ph.model.length===ph.phase.length){
        data.push({x: ph.phase, y: ph.model, mode:"lines", name:"Model"});
      }
      const layout:any = {
        title:`Phase-folded (${ph.star})` + (ph.period?` — P=${ph.period} d`:""),
        xaxis:{title:"Phase [cycles]"}, yaxis:{title:"Flux"},
        margin:{l:50,r:10,t:40,b:40}
      };
      if (phaseMode && phaseWindow && isFinite(phaseWindow)){
        layout.xaxis = layout.xaxis || {};
        layout.xaxis.range = [-phaseWindow, +phaseWindow];
      }
      Plotly.react("plot-phase", data, layout, {displaylogo:false});
    }
    if(oe && oe.odd?.phase && oe.even?.phase){
      Plotly.newPlot("plot-oddeven", [
        {x: oe.odd.phase, y: oe.odd.flux, mode:"markers", type:"scattergl", name:"Odd"},
        {x: oe.even.phase, y: oe.even.flux, mode:"markers", type:"scattergl", name:"Even"},
      ] as any, {
        title:`Odd/Even (${star})` + (oe.z!=null?` — z=${oe.z.toFixed(2)}`:""),
        xaxis:{title:"Phase"}, yaxis:{title:"Flux"},
        margin:{l:50,r:10,t:40,b:40}
      } as any, {displaylogo:false});
    }
    if(ct){
      Plotly.newPlot("plot-centroid", [
        {x: ct.time, y: ct.dx, mode:"lines", name:"dx"},
        {x: ct.time, y: ct.dy, mode:"lines", name:"dy"},
        {x: ct.time, y: ct.r, mode:"lines", name:"r"},
      ] as any, {
        title:`Centroid Drift (${star})`,
        xaxis:{title:"Time [BJD]"}, yaxis:{title:"Pixels"},
        margin:{l:50,r:10,t:40,b:40}
      } as any, {displaylogo:false});
    }
  };

  React.useEffect(()=>{ renderAll(); }, [lc,ph,oe,ct]);

  // Preload from URL param
  React.useEffect(()=>{
    const s = getParam("star");
    if(s && s !== star){
      setStar(s);
      // auto-load on initial url-provided star
      void (async ()=>{ await load(); })();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div id="workbench" style={{border:"1px solid #ddd", borderRadius:8, padding:12}}>
      <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:8}}>
        <h3>Workbench</h3>
        <div>
          <input placeholder="TIC or KIC..." value={star} onChange={e=>setStar(e.target.value)} style={{marginRight:8}}/>
          <button onClick={()=>{
            setQuery({ star, tab: "workbench", phase: phaseMode ? "true" : undefined });
            load();
          }}>Load</button>
          <label style={{marginLeft:12, userSelect:"none"}}>
            <input type="checkbox" checked={phaseMode} onChange={e=>{
              const on = e.target.checked;
              setPhaseMode(on);
              setQuery({ star, tab:"workbench", phase: on ? "true" : undefined });
              setTimeout(renderAll, 0);
            }}/>
            &nbsp;Phase fold focus (±2.5×dur)
          </label>
          <button style={{marginLeft:8}} onClick={()=>copyPermalink()}>Copy Link</button>
        </div>
      </div>
      {err && <p style={{color:"#b00"}}>{err}</p>}
      <div id="plot-lc" style={{height:320, marginBottom:12}} />
      <div id="plot-phase" style={{height:320, marginBottom:12}} />
      <div id="plot-oddeven" style={{height:320, marginBottom:12}} />
      <div id="plot-centroid" style={{height:320}} />
      <p style={{fontSize:12, color:"#666", marginTop:8}}>Tip: run <em>Training</em> and <em>Vetting</em> jobs to populate phase/odd-even/centroid artifacts. The Workbench now uses a fast DB index—first load may index files for this star.</p>
    </div>
  );
}
