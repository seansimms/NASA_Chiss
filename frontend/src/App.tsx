import React, { useEffect, useState } from "react";
import { startJob, listJobs, logsSocket, listArtifacts, cancelJob, orchStats, clearAllJobs, type JobInfo } from "./lib/api";
import { MetricsPanel } from "./components/Metrics";
import { CandidatesPanel } from "./components/Candidates";
import { Workbench } from "./components/Workbench";
import { MetricsHistory } from "./components/MetricsHistory";
import { ReliabilityPanel } from "./components/Reliability";
import { RunCompare } from "./components/RunCompare";
import AlertCenter from "./components/AlertCenter";
import { DiscoveriesTab } from "./components/DiscoveriesTab";
import { SettingsBar } from "./components/Settings";
import { getParam, scrollToTab } from "./lib/url";

export default function App() {
  const [jobs, setJobs] = useState<JobInfo[]>([]);
  const [active, setActive] = useState<JobInfo|null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [stats,setStats]=useState<any|null>(null);
  const [tab, setTab] = useState("discoveries");
  const refresh = async ()=> setJobs(await listJobs());
  useEffect(()=>{
    refresh();
    const id=setInterval(async ()=>{
      await refresh();
      try{ setStats(await orchStats()); }catch{}
    }, 2000);
    return ()=>clearInterval(id);
  },[]);

  useEffect(()=>{
    const urlTab = getParam("tab") || "discoveries";
    setTab(urlTab);
  }, []);

  const setQuery = (params: Record<string, string>) => {
    const url = new URL(window.location.href);
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
    window.history.pushState({}, "", url.toString());
    setTab(params.tab || "reliability");
  };

  React.useEffect(()=>{
    const tab = getParam("tab");
    if(tab){
      // ensure scroll after first paint
      setTimeout(()=>scrollToTab(tab), 200);
    }
    // If phase=true & star present, keep it in URL on load to ensure shareability
    const star = getParam("star"); const phase = getParam("phase");
    if (star && phase==="true"){
      // normalize params
      const params = new URLSearchParams(window.location.search);
      params.set("star", star); params.set("phase","true"); params.set("tab", tab||"workbench");
      const url = `${window.location.pathname}?${params.toString()}${window.location.hash||""}`;
      window.history.replaceState({}, "", url);
    }
  },[]);

  const run = async (job_type: JobInfo["job_type"], params: Record<string,string> = {})=>{
    const j = await startJob(job_type, params); setActive(j); setLogs([]);
    const ws = logsSocket(j.job_id);
    ws.onmessage = (ev)=> setLogs(prev=> [...prev, ev.data as string].slice(-2000));
    ws.onclose = ()=> refresh();
  };

  return (
    <div style={{fontFamily:"Inter, system-ui", padding:"16px"}}>
      <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:8}}>
        <h1 style={{fontSize:24}}>Project Chiss — Command Center</h1>
        <SettingsBar/>
      </div>
      {stats && <div style={{marginBottom:8, display:"flex", justifyContent:"space-between", alignItems:"center"}}>
        <div style={{color:"#444"}}>
          <strong>Queue:</strong> {stats.queue_depth} &nbsp; | &nbsp; <strong>Running:</strong> {stats.running.length} / {stats.concurrency}
        </div>
        <button 
          onClick={async ()=>{
            if(window.confirm("Clear all jobs from the database? This will reset the job history for a fresh demo.")){
              try {
                await clearAllJobs();
                await refresh();
                alert("✅ All jobs cleared!");
              } catch(e: any) {
                alert(`Error clearing jobs: ${e.message}`);
              }
            }
          }}
          style={{
            padding:"6px 12px",
            background:"#FF5722",
            color:"white",
            border:"none",
            borderRadius:6,
            cursor:"pointer",
            fontSize:13,
            fontWeight:600
          }}
        >
          🧹 Clear All Jobs
        </button>
      </div>}
      
      {/* Quick Start - NASA Demo */}
      <div style={{marginBottom:16, padding:16, background:"linear-gradient(135deg, #667eea 0%, #764ba2 100%)", borderRadius:12, color:"white"}}>
        <h2 style={{fontSize:20, marginBottom:8}}>🚀 NASA Demo - Quick Start</h2>
        <p style={{marginBottom:12, opacity:0.9}}>Run the complete Chiss pipeline from data ingest to validated exoplanet candidates</p>
        <button 
          onClick={()=>run("full-pipeline")} 
          style={{
            background:"white",
            color:"#667eea",
            fontSize:16,
            padding:"10px 20px",
            border:"none",
            borderRadius:8,
            cursor:"pointer",
            fontWeight:600,
            boxShadow:"0 2px 8px rgba(0,0,0,0.2)"
          }}
        >
          Run Complete Pipeline (P-01 → P-06)
        </button>
      </div>

      {/* Pipeline Stages */}
      <div style={{marginBottom:16}}>
        <h3 style={{fontSize:16, marginBottom:8}}>Pipeline Stages</h3>
        <div style={{display:"grid", gridTemplateColumns:"repeat(auto-fit, minmax(200px, 1fr))", gap:12}}>
          <div style={{border:"1px solid #ddd", borderRadius:8, padding:12}}>
            <strong style={{display:"block", marginBottom:8}}>Setup</strong>
            <button onClick={()=>run("setup-bootstrap")} style={{fontSize:13, padding:"6px 12px"}}>
              Bootstrap Environment
            </button>
          </div>
          <div style={{border:"1px solid #ddd", borderRadius:8, padding:12}}>
            <strong style={{display:"block", marginBottom:8}}>P-01: Data Ingest</strong>
            <button onClick={()=>run("setup-data-pipeline")} style={{fontSize:13, padding:"6px 12px"}}>
              Fetch & Verify Data
            </button>
          </div>
          <div style={{border:"1px solid #ddd", borderRadius:8, padding:12}}>
            <strong style={{display:"block", marginBottom:8}}>P-02-05: Training</strong>
            <button onClick={()=>run("train-kepler-strict")} style={{fontSize:13, padding:"6px 12px"}}>
              Train Models
            </button>
          </div>
          <div style={{border:"1px solid #ddd", borderRadius:8, padding:12}}>
            <strong style={{display:"block", marginBottom:8}}>P-06: Validation</strong>
            <button onClick={()=>run("benchmarks-compare")} style={{fontSize:13, padding:"6px 12px"}}>
              Run Benchmarks
            </button>
            <button onClick={()=>run("hardening-suite-strict")} style={{fontSize:13, padding:"6px 12px", marginTop:4}}>
              Run Hardening
            </button>
          </div>
          <div style={{border:"1px solid #ddd", borderRadius:8, padding:12}}>
            <strong style={{display:"block", marginBottom:8}}>🌍 Multi-Sector Search</strong>
            <form onSubmit={(e)=>{ 
              e.preventDefault(); 
              const tic=(e.currentTarget.elements.namedItem("tic") as HTMLInputElement).value;
              const period_min=(e.currentTarget.elements.namedItem("period_min") as HTMLInputElement).value || "20";
              const period_max=(e.currentTarget.elements.namedItem("period_max") as HTMLInputElement).value || "100";
              run("multi-sector",{tic, period_min, period_max}); 
            }}>
              <input name="tic" placeholder="TIC ID (e.g., 307210830)" required style={{fontSize:13, padding:"6px", width:"100%", marginBottom:6}} />
              <div style={{display:"flex", gap:6, marginBottom:6}}>
                <div style={{flex:1}}>
                  <label style={{fontSize:11, color:"#666", display:"block", marginBottom:2}}>Min Period (days)</label>
                  <input name="period_min" type="number" defaultValue="20" min="1" style={{fontSize:13, padding:"6px", width:"100%"}} />
                </div>
                <div style={{flex:1}}>
                  <label style={{fontSize:11, color:"#666", display:"block", marginBottom:2}}>Max Period (days)</label>
                  <input name="period_max" type="number" defaultValue="100" min="1" style={{fontSize:13, padding:"6px", width:"100%"}} />
                </div>
              </div>
              <button type="submit" style={{fontSize:13, padding:"8px 12px", width:"100%", background:"#2563eb", color:"white", border:"none", borderRadius:6, cursor:"pointer", fontWeight:600}}>Start Search</button>
            </form>
          </div>
        </div>
      </div>
      <section style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:16, marginBottom:16}}>
        <div style={{border:"1px solid #ddd", borderRadius:8, padding:12, minHeight:240}}>
          <h3>Live Logs</h3>
          <pre style={{whiteSpace:"pre-wrap", fontSize:12, maxHeight:360, overflow:"auto", background:"#0b0b0b", color:"#c7ffd8", padding:8}}>{logs.join("\n")||"—"}</pre>
        </div>
        <div style={{border:"1px solid #ddd", borderRadius:8, padding:12}}>
          <h3>Jobs</h3>
          <table>
            <thead><tr><th>Job</th><th>Type</th><th>State</th><th>Artifacts</th><th>Actions</th></tr></thead>
            <tbody>
              {jobs.map(j=>(
                <tr key={j.job_id}>
                  <td>{j.job_id.slice(0,22)}…</td>
                  <td>{j.job_type}</td>
                  <td>{j.state}{j.note?` (${j.note})`:""}</td>
                  <td><ArtifactsLink job_id={j.job_id}/></td>
                  <td>{(j.state==="queued"||j.state==="running") && <button onClick={async()=>{ await cancelJob(j.job_id); setTimeout(refresh,500); }}>Cancel</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <nav style={{display:"flex", gap:8, marginBottom:12}}>
        <button className={tab==="discoveries"?"active":""} onClick={()=>setQuery({tab:"discoveries"})}>🌟 Discoveries</button>
        <button className={tab==="reliability"?"active":""} onClick={()=>setQuery({tab:"reliability"})}>📊 Reliability</button>
        <button className={tab==="compare"?"active":""} onClick={()=>setQuery({tab:"compare"})}>⚖️ Compare</button>
        <button className={tab==="history"?"active":""} onClick={()=>setQuery({tab:"history"})}>📈 History</button>
        <button className={tab==="alerts"?"active":""} onClick={()=>setQuery({tab:"alerts"})}>🚨 Alerts</button>
      </nav>

      {tab==="discoveries" ? <DiscoveriesTab /> : null}
      {tab==="reliability" ? <ReliabilityPanel /> : null}
      {tab==="compare" ? <RunCompare /> : null}
      {tab==="history" ? <MetricsHistory /> : null}
      {tab==="alerts" ? <AlertCenter /> : null}
    </div>
  );
}

function ArtifactsLink({job_id}:{job_id:string}) {
  const [href,setHref]=React.useState<string|undefined>();
  const onClick=async ()=>{
    const res = await listArtifacts(job_id);
    if(res.files?.length){
      const first = res.files.find((f:any)=> String(f.path).endsWith(".md") || String(f.path).endsWith(".html")) || res.files[0];
      setHref(`/api/artifacts/${first.path}`);
    } else {
      setHref(undefined);
    }
  };
  return <button onClick={onClick} disabled={!job_id} title="Open first artifact">{href?<a href={href} target="_blank">Open</a>:"List"}</button>;
}

