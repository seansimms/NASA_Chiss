export const API_BASE = (import.meta as any).env?.VITE_API_BASE || "http://localhost:8001";
export type JobType = "train-kepler-strict"|"benchmarks-compare"|"hardening-suite-strict"|"multi-sector";
export interface JobInfo { job_id:string; job_type:JobType; state:string; artifacts_dir:string; note?:string; }

export async function apiFetch(url: string, init: RequestInit = {}) {
  const key = localStorage.getItem("chiss_api_key") || "";
  const headers = new Headers(init.headers || {});
  if (key) headers.set("X-API-Key", key);
  const res = await fetch(url, { ...init, headers });
  return res;
}

export async function startJob(job_type: JobType, params: Record<string,string> = {}) {
  const r = await apiFetch(`${API_BASE}/api/jobs`, {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({job_type, params})});
  if(r.status===409){ const body=await r.json(); throw new Error(`Duplicate running job (id=${body?.detail?.job_id||"?"})`); }
  if(!r.ok) throw new Error(`startJob failed: ${r.status}`);
  return await r.json() as JobInfo;
}
export async function listJobs() {
  const r = await apiFetch(`${API_BASE}/api/jobs`); if(!r.ok) throw new Error("listJobs failed");
  return (await r.json()).jobs as JobInfo[];
}
export function logsSocket(job_id: string): WebSocket {
  const url = `${API_BASE.replace("http","ws")}/api/jobs/${job_id}/logs`;
  return new WebSocket(url);
}
export async function listArtifacts(job_id: string) {
  const r = await apiFetch(`${API_BASE}/api/jobs/${job_id}/artifacts`);
  if(!r.ok) throw new Error("listArtifacts failed");
  return await r.json();
}
export async function cancelJob(job_id: string) {
  const r = await apiFetch(`${API_BASE}/api/jobs/${job_id}/cancel`, {method:"POST"});
  if(!r.ok) throw new Error(`cancelJob failed: ${r.status}`);
  return await r.json();
}
export async function orchStats(){
  const r = await apiFetch(`${API_BASE}/api/orchestrator/stats`);
  if(!r.ok) throw new Error("stats failed");
  return await r.json();
}

export async function clearAllJobs(){
  const r = await apiFetch(`${API_BASE}/api/jobs/clear`, {method:"DELETE"});
  if(!r.ok) throw new Error("clearJobs failed");
  return await r.json();
}

