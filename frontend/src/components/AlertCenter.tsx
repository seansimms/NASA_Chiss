import React from "react";
import { API_BASE, apiFetch } from "../lib/api";

function Field({label, children}:{label:string, children:any}){
  return <div style={{marginBottom:8}}>
    <div style={{fontSize:12, opacity:0.75}}>{label}</div>
    {children}
  </div>
}

export default function AlertCenter(){
  const [recent,setRecent]=React.useState<any[]>([]);
  const [status,setStatus]=React.useState<"all"|"sent"|"failed">("all");
  const [limit,setLimit]=React.useState(100);
  const [rules,setRules]=React.useState<any[]>([]);
  const [channels,setChannels]=React.useState<any>({});
  const [form,setForm]=React.useState<any>({name:"Default rule", p_min:0.80, p_std_max:0.10, run_scope:"*", muted:false, channels:{}});
  const [test,setTest]=React.useState<any>({star:"TIC12345678", run_id:"RUN-EXAMPLE", p_final:0.91, p_std:0.08, url:""});
  const [msg,setMsg]=React.useState<string>("");

  const loadRecent = async ()=>{
    const r = await apiFetch(`${API_BASE}/api/alerts/recent?limit=${limit}&status=${status}`);
    if(r.ok){ const j = await r.json(); setRecent(j.items||[]); }
  };
  const loadRules = async ()=>{
    const r = await apiFetch(`${API_BASE}/api/alerts/rules`);
    if(r.ok){ const j = await r.json(); setRules(j.rules||[]); setChannels(j.channels||{}); }
  };
  React.useEffect(()=>{ loadRecent(); loadRules(); },[]);
  React.useEffect(()=>{ loadRecent(); },[status,limit]);

  const saveRule = async ()=>{
    setMsg("");
    const r = await apiFetch(`${API_BASE}/api/alerts/rules`, {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(form)});
    setMsg(r.ok ? "Saved." : `Error: ${await r.text()}`);
    await loadRules();
  };
  const mute = async (id:string, m:boolean)=>{
    setMsg("");
    const r = await apiFetch(`${API_BASE}/api/alerts/rules/${id}/${m?'mute':'unmute'}`, {method:"POST"});
    setMsg(r.ok ? (m?"Muted.":"Unmuted.") : `Error: ${await r.text()}`);
    await loadRules();
  };
  const del = async (id:string)=>{
    setMsg("");
    const r = await apiFetch(`${API_BASE}/api/alerts/rules/${id}`, {method:"DELETE"});
    setMsg(r.ok ? "Deleted." : `Error: ${await r.text()}`);
    await loadRules();
  };
  const testSend = async ()=>{
    setMsg("");
    const ch:any = {};
    if(form.channels?.slack_webhook) ch.slack_webhook = form.channels.slack_webhook;
    if(form.channels?.webhook_url)   ch.webhook_url   = form.channels.webhook_url;
    const payload = {...test, channels: ch};
    const r = await apiFetch(`${API_BASE}/api/alerts/test_send`, {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(payload)});
    setMsg(r.ok ? "Test sent. Check recent list / channel / outbox." : `Error: ${await r.text()}`);
    await loadRecent();
  };

  return (
    <div>
      <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:8}}>
        <h3 style={{margin:0}}>Alert Center</h3>
        <div style={{fontSize:12, opacity:0.7}}>
          Channels — Slack: {channels.slack_webhook_configured ? "configured" : "—"} · Webhook: {channels.webhook_configured ? "configured" : "—"}
        </div>
      </div>
      {msg ? <div style={{marginBottom:8, color:"#055"}}>{msg}</div> : null}
      <div style={{display:"grid", gridTemplateColumns:"1.2fr 1fr", gap:12}}>
        {/* Recent Alerts */}
        <div style={{border:"1px solid #eee", borderRadius:8, padding:8}}>
          <div style={{display:"flex", justifyContent:"space-between", alignItems:"center"}}>
            <h4 style={{margin:0}}>Recent Alerts</h4>
            <div>
              <label style={{marginRight:6}}>Status:</label>
              <select value={status} onChange={e=>setStatus(e.target.value as any)}>
                <option value="all">All</option>
                <option value="sent">Sent</option>
                <option value="failed">Failed</option>
              </select>
              <label style={{margin:"0 6px 0 12px"}}>Limit:</label>
              <select value={limit} onChange={e=>setLimit(parseInt(e.target.value))}>
                {[25,50,100,200].map(n=><option key={n} value={n}>{n}</option>)}
              </select>
              <a href={`${API_BASE}/api/alerts/recent.csv?limit=${limit}&status=${status}`} target="_blank" rel="noreferrer"><button style={{marginLeft:8}}>CSV</button></a>
            </div>
          </div>
          <table style={{marginTop:8}}>
            <thead>
              <tr><th>Time</th><th>Star</th><th>Run</th><th>p</th><th>σ</th><th>Channels</th><th>Status</th></tr>
            </thead>
            <tbody>
              {recent.map((r:any)=>(
                <tr key={r.id}>
                  <td>{r.ts}</td>
                  <td>{r.star}</td>
                  <td>{r.run_id}</td>
                  <td>{typeof r.p_final==="number" ? r.p_final.toFixed(3) : r.p_final}</td>
                  <td>{typeof r.p_std==="number" ? r.p_std.toFixed(3) : r.p_std}</td>
                  <td>{(r.channels||[]).join(",")}</td>
                  <td style={{color: r.sent ? "#070" : "#900"}}>{r.status}</td>
                </tr>
              ))}
              {recent.length===0 ? <tr><td colSpan={7} style={{opacity:0.7}}>No alerts.</td></tr> : null}
            </tbody>
          </table>
        </div>

        {/* Rules panel */}
        <div style={{border:"1px solid #eee", borderRadius:8, padding:8}}>
          <h4 style={{margin:0}}>Rules</h4>
          {/* Existing rules */}
          <div style={{marginTop:8, maxHeight:220, overflow:"auto", border:"1px solid #f0f0f0", borderRadius:6, padding:6}}>
            {rules.length===0 ? <div style={{opacity:0.7}}>No rules yet.</div> :
              rules.map((r:any)=>(
                <div key={r.id} style={{display:"flex", alignItems:"center", justifyContent:"space-between", borderBottom:"1px dashed #eee", padding:"4px 0"}}>
                  <div>
                    <div><strong>{r.name}</strong> {r.muted ? <span style={{color:"#b60"}}>(muted)</span> : null}</div>
                    <div style={{fontSize:12, opacity:0.75}}>p_min={r.p_min} · σ_max={r.p_std_max} · scope={r.run_scope}</div>
                  </div>
                  <div>
                    <button onClick={()=>mute(r.id, !r.muted)}>{r.muted ? "Unmute" : "Mute"}</button>
                    <button style={{marginLeft:6}} onClick={()=>del(r.id)}>Delete</button>
                    <button style={{marginLeft:6}} onClick={()=>setForm(r)}>Edit</button>
                  </div>
                </div>
              ))
            }
          </div>
          {/* Editor */}
          <div style={{marginTop:8, borderTop:"1px solid #eee", paddingTop:8}}>
            <h5 style={{margin:"4px 0"}}>Create / Edit Rule</h5>
            <Field label="Name">
              <input style={{width:"100%"}} value={form.name||""} onChange={e=>setForm({...form, name:e.target.value})} />
            </Field>
            <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:8}}>
              <Field label="p_min">
                <input type="number" step="0.01" min="0" max="1" value={form.p_min} onChange={e=>setForm({...form, p_min: parseFloat(e.target.value)})} />
              </Field>
              <Field label="σ_max (p_std_max)">
                <input type="number" step="0.01" min="0" max="1" value={form.p_std_max} onChange={e=>setForm({...form, p_std_max: parseFloat(e.target.value)})} />
              </Field>
            </div>
            <Field label="Run scope (run id or '*')">
              <input style={{width:"100%"}} value={form.run_scope||"*"} onChange={e=>setForm({...form, run_scope:e.target.value})} />
            </Field>
            <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:8}}>
              <Field label="Slack webhook URL (optional)">
                <input style={{width:"100%"}} value={form.channels?.slack_webhook||""} onChange={e=>setForm({...form, channels:{...form.channels, slack_webhook:e.target.value}})} />
              </Field>
              <Field label="Generic webhook URL (optional)">
                <input style={{width:"100%"}} value={form.channels?.webhook_url||""} onChange={e=>setForm({...form, channels:{...form.channels, webhook_url:e.target.value}})} />
              </Field>
            </div>
            <div style={{display:"flex", justifyContent:"flex-end", gap:8}}>
              <button onClick={saveRule}>Save Rule</button>
            </div>
            <h5 style={{margin:"12px 0 4px"}}>Test Send</h5>
            <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:8}}>
              <Field label="Star ID"><input value={test.star} onChange={e=>setTest({...test, star:e.target.value})} /></Field>
              <Field label="Run ID"><input value={test.run_id} onChange={e=>setTest({...test, run_id:e.target.value})} /></Field>
              <Field label="p_final"><input type="number" step="0.001" value={test.p_final} onChange={e=>setTest({...test, p_final: parseFloat(e.target.value)})} /></Field>
              <Field label="p_std"><input type="number" step="0.001" value={test.p_std} onChange={e=>setTest({...test, p_std: parseFloat(e.target.value)})} /></Field>
            </div>
            <Field label="Dossier URL (optional)">
              <input style={{width:"100%"}} value={test.url} onChange={e=>setTest({...test, url:e.target.value})} />
            </Field>
            <div style={{display:"flex", justifyContent:"flex-end"}}>
              <button onClick={testSend}>Send Test Alert</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
