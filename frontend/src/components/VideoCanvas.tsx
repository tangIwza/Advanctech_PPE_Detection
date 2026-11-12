import { useCallback, useEffect, useRef, useState } from 'react';
import { Camera, Check, Maximize2, MousePointer2, Undo2, X } from 'lucide-react';
import { normalizedPoint, polygonBounds, polygonError, rectangle, zoneAt } from '../geometry';
import type { ClassInfo, DisplayFrame, Point, Zone, ZoneGeometry, ZoneShape } from '../types';
import { Badge } from './ui';

type Props = {
  frame: DisplayFrame | null; zones: Zone[]; classes: ClassInfo[];
  drawing: boolean; drawingMode: ZoneShape; selectedId: string | null; draft: ZoneGeometry | null;
  onComplete: (geometry: ZoneGeometry) => void; onSelect: (zone: Zone) => void; onCancelDraw: () => void;
};

export default function VideoCanvas({ frame, zones, classes, drawing, drawingMode, selectedId, draft, onComplete, onSelect, onCancelDraw }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const wrapper = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<{ start: Point; end: Point } | null>(null);
  const [vertices, setVertices] = useState<Point[]>([]);
  const [hover, setHover] = useState<Point | null>(null);
  const [error, setError] = useState('');
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const element = wrapper.current;
    if (!element) return;
    const observer = new ResizeObserver(() => setSize({ width: element.clientWidth, height: element.clientHeight }));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  useEffect(() => { setDrag(null); setVertices([]); setHover(null); setError(''); }, [drawing, drawingMode]);

  const undo = useCallback(() => { setVertices(previous => previous.slice(0,-1)); setError(''); }, []);
  const finish = useCallback(() => {
    const failure = polygonError(vertices);
    if (failure) { setError(failure); return; }
    onComplete({ shape:'polygon', rect:polygonBounds(vertices), points:vertices.map(point=>({...point})) });
  }, [vertices,onComplete]);
  useEffect(() => {
    if (!drawing) return;
    const keyboard = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLElement && (event.target.matches('input,textarea,select') || event.target.isContentEditable)) return;
      if (event.key==='Escape') { event.preventDefault(); onCancelDraw(); }
      if (drawingMode!=='polygon') return;
      if (event.key==='Enter') { event.preventDefault(); finish(); }
      if (event.key==='Backspace' || event.key==='Delete') { event.preventDefault(); undo(); }
    };
    window.addEventListener('keydown',keyboard);
    return () => window.removeEventListener('keydown',keyboard);
  }, [drawing,drawingMode,finish,undo,onCancelDraw]);

  useEffect(() => {
    const element=canvas.current;
    if (!element || !size.width || !size.height) return;
    const dpr=window.devicePixelRatio || 1;
    element.width=Math.round(size.width*dpr); element.height=Math.round(size.height*dpr);
    const context=element.getContext('2d');
    if (!context) return;
    context.setTransform(dpr,0,0,dpr,0,0); context.clearRect(0,0,size.width,size.height);
    const {width:w,height:h}=size;
    const packet=frame?.packet;
    const offenders=new Set(packet?.violations.map(item=>item.track_id));
    const alarmZones=new Set(packet?.violations.map(item=>item.zone_id));
    const label=(text:string,x:number,y:number,color:string) => {
      context.font='600 11px ui-sans-serif, system-ui, sans-serif';
      const width=Math.min(w-8,context.measureText(text).width+12);
      x=Math.min(Math.max(2,x),w-width-2); y=Math.min(Math.max(0,y),h-20);
      context.fillStyle=color; context.fillRect(x,y,width,20);
      context.fillStyle='#ffffff'; context.fillText(text,x+6,y+14,width-10);
    };
    const polygonPath=(points:Point[],close=true) => {
      context.beginPath();
      points.forEach((point,index)=>index ? context.lineTo(point.x*w,point.y*h) : context.moveTo(point.x*w,point.y*h));
      if (close) context.closePath();
    };
    const shapePath=(geometry:Pick<Zone,'shape'|'rect'|'points'>) => {
      if (geometry.shape==='polygon' && geometry.points) polygonPath(geometry.points);
      else { const r=geometry.rect; context.beginPath(); context.rect(r.x1*w,r.y1*h,(r.x2-r.x1)*w,(r.y2-r.y1)*h); }
    };
    for (const zone of zones) {
      const r=zone.rect;
      const color=!zone.enabled ? '#94a3b8' : alarmZones.has(zone.id) ? '#ef4444' : zone.kind==='restricted' ? '#f59e0b' : '#3b82f6';
      context.globalAlpha=zone.enabled ? 1 : 0.5;
      context.fillStyle=color+(alarmZones.has(zone.id) ? '20' : '0d');
      context.strokeStyle=color; context.lineWidth=selectedId===zone.id ? 3 : 2;
      context.setLineDash(zone.enabled ? [] : [5,4]);
      shapePath(zone); context.fill(); context.stroke(); context.setLineDash([]);
      label(zone.name.slice(0,28)+(!zone.enabled ? ' · disabled' : ''),r.x1*w,r.y1*h,color);
      if (selectedId===zone.id) {
        const handles=zone.shape==='polygon' && zone.points ? zone.points : [{x:r.x1,y:r.y1},{x:r.x2,y:r.y1},{x:r.x2,y:r.y2},{x:r.x1,y:r.y2}];
        context.fillStyle='#ffffff'; handles.forEach(point=>context.fillRect(point.x*w-3,point.y*h-3,6,6));
      }
    }
    context.globalAlpha=1;
    for (const item of packet?.detections || []) {
      const [x1,y1,x2,y2]=item.bbox;
      const info=classes.find(entry=>entry.id===item.class_id);
      const bad=item.track_id!==null && offenders.has(item.track_id);
      const color=bad ? '#ef4444' : info?.color || '#22c55e';
      context.strokeStyle=color; context.lineWidth=bad ? 3 : 1.5;
      context.strokeRect(x1*w,y1*h,(x2-x1)*w,(y2-y1)*h);
      label(item.class_name+(item.track_id ? ' #'+item.track_id : '')+' '+(item.confidence*100).toFixed(0)+'%',x1*w,y1*h-20,color);
      if (item.track_id) { context.beginPath(); context.fillStyle=color; context.arc((x1+x2)*w/2,y2*h,3,0,Math.PI*2); context.fill(); }
    }
    const draggedRect=drag ? rectangle(drag.start,drag.end) : null;
    const preview:ZoneGeometry|null=draggedRect ? {shape:'rectangle',rect:draggedRect,points:null} : draft;
    if (preview) {
      context.strokeStyle='#ffffff'; context.fillStyle='#ffffff20'; context.lineWidth=2; context.setLineDash([6,4]);
      shapePath(preview); context.fill(); context.stroke(); context.setLineDash([]);
    }
    if (drawing && drawingMode==='polygon' && vertices.length) {
      polygonPath(hover ? [...vertices,hover] : vertices); context.fillStyle='#3b82f630'; context.fill();
      polygonPath(vertices,false); context.strokeStyle='#ffffff'; context.lineWidth=2; context.stroke();
      if (hover) {
        const last=vertices[vertices.length-1];
        context.beginPath(); context.moveTo(last.x*w,last.y*h); context.lineTo(hover.x*w,hover.y*h);
        if (vertices.length>1) context.lineTo(vertices[0].x*w,vertices[0].y*h);
        context.setLineDash([6,4]); context.stroke(); context.setLineDash([]);
      }
      vertices.forEach((point,index)=>{
        context.beginPath(); context.arc(point.x*w,point.y*h,index===0 ? 8 : 6,0,Math.PI*2);
        context.fillStyle=index===0 ? '#1e3a8a' : '#ffffff'; context.fill();
        context.strokeStyle='#ffffff'; context.lineWidth=2; context.stroke();
        context.fillStyle=index===0 ? '#ffffff' : '#1e3a8a'; context.font='bold 9px ui-sans-serif, system-ui';
        context.fillText(String(index+1),point.x*w-3,point.y*h+3);
      });
    }
  }, [frame,zones,classes,selectedId,draft,drag,size,drawing,drawingMode,vertices,hover]);

  const point=(event:React.PointerEvent<HTMLCanvasElement>)=>normalizedPoint(event.clientX,event.clientY,event.currentTarget.getBoundingClientRect());
  return <div className="bg-[#0b1520] overflow-hidden">
    <div className="px-4 py-2.5 flex items-center justify-between gap-2 border-b border-slate-700/60">
      <div className="flex items-center gap-2 min-w-0"><span className={'h-1.5 w-1.5 rounded-full '+(frame?.packet.state==='running' ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500')} /><span className="text-xs text-slate-300 truncate">{frame?.packet.source?.name || 'No source connected'}</span></div>
      <div className="flex items-center gap-2">{drawing && <Badge tone="blue"><MousePointer2 size={11} />{drawingMode==='polygon' ? 'Polygon / Pen' : 'Rectangle'}</Badge>}<button className="p-1 text-slate-400 hover:text-white" aria-label="Fullscreen video" onClick={()=>wrapper.current?.requestFullscreen()}><Maximize2 size={15} /></button></div>
    </div>
    <div ref={wrapper} className="relative w-full bg-[#0b1520]" style={{aspectRatio:frame ? frame.packet.width+'/'+frame.packet.height : '16/9'}}>
      {frame ? <img src={frame.url} className="absolute inset-0 w-full h-full object-fill select-none" alt="Live safety monitoring feed" draggable={false} /> : <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-5 text-center text-slate-400"><div className="rounded-2xl border border-slate-700 bg-slate-800 p-4"><Camera size={30} /></div><p className="text-sm font-semibold text-slate-200">Ready to monitor your workspace</p><p className="text-xs max-w-sm leading-relaxed">Start a camera or video, then draw rectangle or polygon zones over the view.</p></div>}
      <canvas ref={canvas} className={'absolute inset-0 h-full w-full touch-none '+(drawing ? 'cursor-crosshair' : 'cursor-default')} aria-label="Interactive detection zone canvas" tabIndex={drawing ? 0 : -1}
        onPointerDown={event=>{
          if (!frame || event.button!==0) return;
          const p=point(event);
          if (!drawing) { const zone=zoneAt(p,zones); if (zone) onSelect(zone); return; }
          event.preventDefault();
          if (drawingMode==='rectangle') { event.currentTarget.setPointerCapture(event.pointerId); setDrag({start:p,end:p}); return; }
          const bounds=event.currentTarget.getBoundingClientRect();
          if (vertices.length && Math.hypot((p.x-vertices[0].x)*bounds.width,(p.y-vertices[0].y)*bounds.height)<=12) {
            if (vertices.length>=3) finish(); else setError('Add at least 3 points before closing the polygon.');
            return;
          }
          if (vertices.length>=64) { setError('Maximum 64 points. Finish the polygon or undo a point.'); return; }
          setVertices(previous=>[...previous,p]); setHover(p); setError('');
        }}
        onPointerMove={event=>{ if (drag) setDrag({...drag,end:point(event)}); else if (drawing && drawingMode==='polygon') setHover(point(event)); }}
        onPointerLeave={()=>setHover(null)}
        onPointerUp={event=>{
          if (!drag) return;
          const result=rectangle(drag.start,point(event)); setDrag(null);
          if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
          if (result) onComplete({shape:'rectangle',rect:result,points:null});
        }}
        onPointerCancel={()=>setDrag(null)} />
    </div>
    {drawing && <div className="border-t border-slate-700 px-4 py-3 bg-slate-900 text-slate-200 space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-xs leading-relaxed"><p className="font-semibold text-white">{drawingMode==='polygon' ? 'Polygon / Pen · '+vertices.length+'/64 points' : 'Rectangle · click and drag'}</p><p className="text-[10px] text-slate-400 mt-1">{drawingMode==='polygon' ? 'Click each corner. Click the first point or Finish to close. Enter: finish · Backspace: undo · Esc: cancel' : 'Drag from one corner to the opposite corner. Esc: cancel'}</p></div>
        <div className="flex items-center gap-2">{drawingMode==='polygon' && <><button className="btn-secondary" aria-label="Undo last point" disabled={!vertices.length} onClick={undo}><Undo2 size={13} />Undo</button><button className="btn-primary" disabled={vertices.length<3} onClick={finish}><Check size={13} />Finish polygon</button></>}<button className="text-xs text-slate-300 hover:text-white inline-flex items-center gap-1" aria-label="Cancel zone drawing" onClick={onCancelDraw}><X size={13} />Cancel</button></div>
      </div>
      {error && <p role="alert" className="text-xs text-red-300">{error}</p>}
    </div>}
  </div>;
}
