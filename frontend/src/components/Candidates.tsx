import React from "react";
import { setQuery, scrollToTab } from "../lib/url";
import { apiFetch } from "../lib/api";
const API_BASE = (import.meta as any).env?.VITE_API_BASE || "http://localhost:8000";
type Candidate = { star:string; label?:number|null; p_final:number; run_id?:string; extra?:Record<string,any> };
type Page = { total:number; items: Candidate[] };

export function CandidatesPanel(){
  const [page,setPage]=React.useState<Page|null>(null);
  const [minP,setMinP]=React.useState(0.0);
  const [limit,setLimit]=React.useState(50);
  const refresh=async ()=>{
    const r = await apiFetch(`${API_BASE}/api/candidates?limit=${limit}&min_p=${minP}`);
    if(r.ok) setPage(await r.json());
  };
  React.useEffect(()=>{ refresh(); }, []);

  const openWorkbench = (c: Candidate)=>{
    setQuery({ star: c.star, tab: "workbench" });
    scrollToTab("workbench");
  };
  const openReliability = (c: Candidate)=>{
    if(c.run_id) setQuery({ run: c.run_id, tab: "reliability" });
    else setQuery({ tab: "reliability" });
    scrollToTab("reliability");
  };
  const openPhase = (c: Candidate)=>{
    setQuery({ star: c.star, tab: "workbench", phase: "true" });
    scrollToTab("workbench");
  };

  return (
    <div style={{border:"1px solid #ddd", borderRadius:8, padding:12}}>
      <div style={{display:"flex", justifyContent:"space-between", alignItems:"center"}}>
        <h3>Candidates</h3>
        <form onSubmit={(e)=>{e.preventDefault(); refresh();}}>
          <label>min p:</label> <input style={{width:70}} value={minP} onChange={e=>setMinP(Number(e.target.value))} type="number" min={0} max={1} step={0.01}/>
          <label style={{marginLeft:8}}>limit:</label> <input style={{width:70}} value={limit} onChange={e=>setLimit(Number(e.target.value))} type="number" min={1} max={1000} step={1}/>
          <button style={{marginLeft:8}} type="submit">Apply</button>
        </form>
      </div>
      {!page? <p>— No predictions yet —</p>:
      <table style={{width:"100%", borderCollapse:"collapse"}}>
        <thead><tr>
          <th style={{textAlign:"left"}}>Star</th><th>p_final</th><th>Label</th><th>Run</th><th>Actions</th>
        </tr></thead>
        <tbody>
          {page.items.map((c,i)=>(
            <tr key={c.star+"|"+i}>
              <td style={{padding:"4px 6px"}}>{c.star}</td>
              <td>{c.p_final?.toFixed(3)}</td>
              <td>{c.label ?? "—"}</td>
              <td style={{fontFamily:"monospace"}}>{c.run_id ?? "—"}</td>
              <td>
                <button onClick={()=>openWorkbench(c)}>Workbench</button>
                <button style={{marginLeft:6}} onClick={()=>openPhase(c)}>Phase</button>
                <button style={{marginLeft:6}} onClick={()=>openReliability(c)}>Reliability</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>}
    </div>
  );
}
