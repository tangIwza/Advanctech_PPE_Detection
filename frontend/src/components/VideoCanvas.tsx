import { useEffect, useRef, useState } from 'react';
import { Camera, Maximize2, MousePointer2, Square, X } from 'lucide-react';
import { normalizedPoint, rectangle, zoneAt, type Point } from '../geometry';
import type { ClassInfo, DisplayFrame, Rect, Zone } from '../types';
import { Badge } from './ui';

type Props = {
  frame: DisplayFrame | null; zones: Zone[]; classes: ClassInfo[];
  drawing: boolean; selectedId: string | null; draft: Rect | null;
  onRectangle: (rect: Rect) => void; onSelect: (zone: Zone) => void; onCancelDraw: () => void;
};

export default function VideoCanvas({ frame, zones, classes, drawing, selectedId, draft, onRectangle, onSelect, onCancelDraw }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const wrapper = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<{ start: Point; end: Point } | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    const element = wrapper.current;
    if (!element) return;
    const observer = new ResizeObserver(() => setSize({ width: element.clientWidth, height: element.clientHeight }));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') { setDrag(null); onCancelDraw(); } };
    window.addEventListener('keydown', escape);
    return () => window.removeEventListener('keydown', escape);
  }, [onCancelDraw]);
  useEffect(() => { if (!drawing) setDrag(null); }, [drawing]);

  useEffect(() => {
    const element = canvas.current;
    if (!element || !size.width || !size.height) return;
    const dpr = window.devicePixelRatio || 1;
    element.width = Math.round(size.width * dpr); element.height = Math.round(size.height * dpr);
    const context = element.getContext('2d');
    if (!context) return;
    context.setTransform(dpr, 0, 0, dpr, 0, 0);
    context.clearRect(0, 0, size.width, size.height);
    const { width: w, height: h } = size;
    const packet = frame?.packet;
    const offenders = new Set(packet?.violations.map(item => item.track_id));
    const alarmZones = new Set(packet?.violations.map(item => item.zone_id));
    const label = (text: string, x: number, y: number, color: string) => {
      context.font = '600 11px ui-sans-serif, system-ui, sans-serif';
      const width = Math.min(w - 8, context.measureText(text).width + 12);
      x = Math.min(Math.max(2, x), w - width - 2);
      y = Math.min(Math.max(0, y), h - 20);
      context.fillStyle = color; context.fillRect(x, y, width, 20);
      context.fillStyle = '#ffffff'; context.fillText(text, x + 6, y + 14, width - 10);
    };
    for (const zone of zones) {
      const r = zone.rect;
      const color = !zone.enabled ? '#94a3b8' : alarmZones.has(zone.id) ? '#ef4444' : zone.kind === 'restricted' ? '#f59e0b' : '#3b82f6';
      const x = r.x1*w, y = r.y1*h, width = (r.x2-r.x1)*w, height = (r.y2-r.y1)*h;
      context.globalAlpha = zone.enabled ? 1 : 0.5;
      context.fillStyle = color + (alarmZones.has(zone.id) ? '20' : '0d');
      context.fillRect(x, y, width, height);
      context.strokeStyle = color; context.lineWidth = selectedId === zone.id ? 3 : 2;
      context.setLineDash(zone.enabled ? [] : [5, 4]); context.strokeRect(x, y, width, height);
      context.setLineDash([]);
      label(`${zone.name.slice(0, 28)}${!zone.enabled ? ' · disabled' : ''}`, x, y, color);
      if (selectedId === zone.id) {
        context.fillStyle = '#ffffff';
        for (const [cx, cy] of [[x,y], [x+width,y], [x,y+height], [x+width,y+height]]) context.fillRect(cx-3, cy-3, 6, 6);
      }
    }
    context.globalAlpha = 1;
    for (const item of packet?.detections || []) {
      const [x1,y1,x2,y2] = item.bbox;
      const info = classes.find(entry => entry.id === item.class_id);
      const bad = item.track_id !== null && offenders.has(item.track_id);
      const color = bad ? '#ef4444' : info?.color || '#22c55e';
      context.strokeStyle = color; context.lineWidth = bad ? 3 : 1.5;
      context.strokeRect(x1*w,y1*h,(x2-x1)*w,(y2-y1)*h);
      label(`${item.class_name}${item.track_id ? ' #' + item.track_id : ''} ${(item.confidence*100).toFixed(0)}%`, x1*w, y1*h-20, color);
      if (item.track_id) {
        context.beginPath(); context.fillStyle = color; context.arc((x1+x2)*w/2, y2*h, 3, 0, Math.PI*2); context.fill();
      }
    }
    const preview = drag ? rectangle(drag.start, drag.end) : draft;
    if (preview) {
      context.strokeStyle = '#ffffff'; context.fillStyle = '#ffffff20'; context.lineWidth = 2; context.setLineDash([6,4]);
      context.fillRect(preview.x1*w,preview.y1*h,(preview.x2-preview.x1)*w,(preview.y2-preview.y1)*h);
      context.strokeRect(preview.x1*w,preview.y1*h,(preview.x2-preview.x1)*w,(preview.y2-preview.y1)*h);
      context.setLineDash([]);
    }
  }, [frame, zones, classes, selectedId, draft, drag, size]);

  const point = (event: React.PointerEvent<HTMLCanvasElement>) => normalizedPoint(event.clientX, event.clientY, event.currentTarget.getBoundingClientRect());
  return <div className="bg-[#0b1520] overflow-hidden">
    <div className="px-4 py-2.5 flex items-center justify-between gap-2 border-b border-slate-700/60">
      <div className="flex items-center gap-2 min-w-0"><span className={`h-1.5 w-1.5 rounded-full ${frame?.packet.state === 'running' ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} /><span className="text-xs text-slate-300 truncate">{frame?.packet.source?.name || 'No source connected'}</span></div>
      <div className="flex items-center gap-2">{drawing && <Badge tone="blue"><MousePointer2 size={11} />Draw rectangle</Badge>}<button className="p-1 text-slate-400 hover:text-white" aria-label="Fullscreen video" onClick={() => wrapper.current?.requestFullscreen()}><Maximize2 size={15} /></button></div>
    </div>
    <div ref={wrapper} className="relative w-full bg-[#0b1520]" style={{ aspectRatio: frame ? `${frame.packet.width}/${frame.packet.height}` : '16/9' }}>
      {frame ? <img src={frame.url} className="absolute inset-0 w-full h-full object-fill select-none" alt="Live safety monitoring feed" draggable={false} /> : <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-5 text-center text-slate-400"><div className="rounded-2xl border border-slate-700 bg-slate-800 p-4"><Camera size={30} /></div><p className="text-sm font-semibold text-slate-200">Ready to monitor your workspace</p><p className="text-xs max-w-sm leading-relaxed">Start a camera or video, then draw rectangular zones directly over the view.</p></div>}
      <canvas ref={canvas} className={`absolute inset-0 h-full w-full touch-none ${drawing ? 'cursor-crosshair' : 'cursor-default'}`} aria-label="Interactive rectangular detection zone canvas"
        onPointerDown={event => {
          if (!frame || event.button !== 0) return;
          if (drawing) { const p = point(event); event.currentTarget.setPointerCapture(event.pointerId); setDrag({ start: p, end: p }); }
          else { const zone = zoneAt(point(event), zones); if (zone) onSelect(zone); }
        }}
        onPointerMove={event => { if (drag) setDrag({ ...drag, end: point(event) }); }}
        onPointerUp={event => {
          if (!drag) return;
          const result = rectangle(drag.start, point(event)); setDrag(null);
          if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
          if (result) onRectangle(result);
        }}
        onPointerCancel={() => setDrag(null)} />
      {drawing && <div className="absolute left-1/2 -translate-x-1/2 bottom-4 flex items-center gap-2 bg-slate-950/90 text-white px-3 py-2 rounded-lg text-xs shadow-lg"><Square size={13} />Click and drag to define a zone<button aria-label="Cancel drawing" onClick={onCancelDraw} className="ml-2 hover:text-red-300"><X size={14} /></button></div>}
    </div>
  </div>;
}
