import React from "react";
const API_BASE = (import.meta as any).env?.VITE_API_BASE || "http://localhost:8000";
type MetricsSummary = { n:number; n_pos:number; auprc:number; brier:number; ece:number; recall_small_at_1pct?:number|null; source:string };
type BenchRow = { id:string; name:string; auprc?:number|null; brier?:number|null; recall_small_at_1pct?:number|null };
type BenchReport = { rows: BenchRow[]; table_path: string };

export function MetricsPanel(){
  const [m,setM]=React.useState<MetricsSummary|null>(null);
  const [b,setB]=React.useState<BenchReport|null>(null);
  const [err,setErr]=React.useState<string|null>(null);
  const refresh=async ()=>{
    setErr(null);
    try{
      const r = await fetch(`${API_BASE}/api/metrics/latest`);
      if(r.ok) setM(await r.json());
    }catch(e:any){ setErr(e.message); }
    try{
      const r2 = await fetch(`${API_BASE}/api/benchmarks/latest`);
      if(r2.ok) setB(await r2.json());
    }catch{}
  };
  React.useEffect(()=>{ refresh(); },[]);
  return (
    <div style={{border:"1px solid #ddd", borderRadius:8, padding:12}}>
      <div style={{display:"flex", justifyContent:"space-between"}}>
        <h3>Metrics</h3>
        <button onClick={refresh}>Refresh</button>
      </div>
      {!m? <p>— No metrics yet —</p> :
      <div style={{display:"grid", gridTemplateColumns:"repeat(5,1fr)", gap:8}}>
        <Card label="AUPRC" value={m.auprc.toFixed(3)}/>
        <Card label="Brier" value={m.brier.toFixed(3)}/>
        <Card label="ECE" value={m.ece.toFixed(3)}/>
        <Card label="Recall@1% (small)" value={m.recall_small_at_1pct!=null?m.recall_small_at_1pct.toFixed(3):"—"}/>
        <Card label="Positives / N" value={`${m.n_pos}/${m.n}`}/>
      </div>}
      {b && <div style={{marginTop:12}}>
        <h4>Benchmarks</h4>
        <table>
          <thead><tr><th>Method</th><th>AUPRC</th><th>Brier</th><th>Recall@1% (small)</th></tr></thead>
          <tbody>
            {b.rows.map((r,i)=>(<tr key={i}><td>{r.name}</td><td>{fmt(r.auprc)}</td><td>{fmt(r.brier)}</td><td>{fmt(r.recall_small_at_1pct)}</td></tr>))}
          </tbody>
        </table>
      </div>}
    </div>
  );
}
function Card({label,value}:{label:string;value:string}){ return (
  <div style={{border:"1px solid #eee", borderRadius:8, padding:"8px 12px", background:"#fafafa"}}>
    <div style={{fontSize:12, color:"#666"}}>{label}</div>
    <div style={{fontSize:20, fontWeight:600}}>{value}</div>
  </div>
);}
const fmt=(x:any)=> (x==null||isNaN(Number(x))? "—" : Number(x).toFixed(3));
