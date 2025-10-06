import React from "react";
const API_BASE = (import.meta as any).env?.VITE_API_BASE || "http://localhost:8000";

export function SettingsBar(){
  const [key,setKey]=React.useState<string>(localStorage.getItem("chiss_api_key")||"");
  const [role,setRole]=React.useState<string>("anonymous");
  const [err,setErr]=React.useState<string|undefined>(undefined);

  const save = ()=>{
    localStorage.setItem("chiss_api_key", key.trim());
    whoami();
  };
  const whoami = async ()=>{
    setErr(undefined);
    try{
      const r = await fetch(`${API_BASE}/api/auth/whoami`, {headers: {"X-API-Key": key.trim()}});
      const j = await r.json();
      setRole(j.role);
    }catch(e:any){ setErr(e.message); }
  };
  React.useEffect(()=>{ whoami(); },[]);
  return (
    <div style={{display:"flex", alignItems:"center", gap:8}}>
      <span style={{fontSize:12, color:"#555"}}>Role: <strong>{role}</strong></span>
      <input placeholder="Paste API key…" value={key} onChange={e=>setKey(e.target.value)} style={{minWidth:280}}/>
      <button onClick={save}>Use Key</button>
      {err && <span style={{color:"#900"}}>{err}</span>}
    </div>
  );
}

