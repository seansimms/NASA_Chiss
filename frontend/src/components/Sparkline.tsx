import React from "react";

type Props = {
  data: number[];              // ordered oldest→newest
  width?: number;
  height?: number;
  stroke?: string;             // optional override
  fill?: string;               // optional under-area fill
  thickness?: number;
  round?: boolean;             // rounded line caps
  title?: string;
};

export function Sparkline({ data, width=140, height=28, stroke, fill, thickness=2, round=true, title="" }: Props){
  if(!data || data.length===0) return <svg width={width} height={height} role="img" aria-label="empty sparkline"></svg>;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const pad = 2;
  const n = data.length;
  const scaleX = (i:number)=> pad + (i*(width-2*pad)/(n-1 || 1));
  const scaleY = (v:number)=> {
    if(max===min) return height/2;
    return height - pad - ((v - min) * (height-2*pad) / (max - min));
  };
  const pts = data.map((v,i)=> `${scaleX(i)},${scaleY(v)}`).join(" ");
  const d = `M ${pts}`;
  const areaD = `M ${scaleX(0)},${height-pad} L ${pts} L ${scaleX(n-1)},${height-pad} Z`;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title}>
      {fill ? <path d={areaD} fill={fill} opacity="0.08" /> : null}
      <path d={d} fill="none" stroke={stroke || "currentColor"} strokeWidth={thickness} strokeLinejoin="round" strokeLinecap={round?"round":"butt"} />
    </svg>
  );
}
