import Plotly from "plotly.js-dist-min";

export async function exportPlotPng(divId: string, filename: string){
  const el = document.getElementById(divId) as any;
  if(!el){ throw new Error(`Plot div #${divId} not found`); }
  const url = await (Plotly as any).toImage(el, {format:"png", height:600, width:900, scale:2});
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
}

export function copyPermalink(){
  const url = window.location.href;
  if(navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(url);
  } else {
    const ta = document.createElement("textarea");
    ta.value = url; document.body.appendChild(ta); ta.select();
    document.execCommand("copy"); ta.remove();
  }
}

