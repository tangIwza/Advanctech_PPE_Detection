import { useState } from 'react';
import { Ban, ShieldCheck, Save } from 'lucide-react';
import type { ClassInfo, Point, Rect, Zone, ZoneInput, ZoneShape } from '../types';
import { polygonBounds, polygonError } from '../geometry';
import { Modal } from './ui';

type Props = { sourceId: string; zone?: Zone; rect: Rect; shape?: ZoneShape; points?: Point[] | null; classes: ClassInfo[]; onSave: (value: ZoneInput, expectedVersion?: number) => Promise<void>; onClose: () => void };

export default function ZoneEditor({ sourceId, zone, rect, shape=zone?.shape || 'rectangle', points=zone?.points || null, classes, onSave, onClose }: Props) {
  const [name, setName] = useState(zone?.name || 'New safety zone');
  const [kind, setKind] = useState<'ppe' | 'restricted'>(zone?.kind || 'ppe');
  const [anchor, setAnchor] = useState<'feet' | 'centroid'>(zone?.anchor || 'feet');
  const [required, setRequired] = useState(zone?.required_class_ids || classes.filter(item => item.name === 'helmet' || item.name === 'safety-vest').map(item => item.id));
  const [coordinates, setCoordinates] = useState(rect);
  const [vertices, setVertices] = useState(points || []);
  const [enabled, setEnabled] = useState(zone?.enabled ?? true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const wearable = classes.filter(item => item.kind === 'ppe');

  return <Modal title={zone ? `Edit zone · ${zone.name}` : 'Create detection zone'} onClose={() => { if (!busy) onClose(); }}>
    <form className="space-y-5" onSubmit={async event => {
      event.preventDefault(); setError('');
      if (kind === 'ppe' && !required.length) { setError('Select at least one required PPE item.'); return; }
      if (shape === 'polygon') {
        const failure=polygonError(vertices);
        if (failure) { setError(failure); return; }
      } else if (coordinates.x2 - coordinates.x1 < 0.005 || coordinates.y2 - coordinates.y1 < 0.005) { setError('Rectangle must have positive width and height.'); return; }
      setBusy(true);
      try { await onSave({ source_id: sourceId, name: name.trim(), kind, shape, points: shape==='polygon' ? vertices : null, rect: shape==='polygon' ? polygonBounds(vertices) : coordinates, required_class_ids: kind === 'ppe' ? required : [], anchor, enabled }, zone?.version); }
      catch (failure) { setError(failure instanceof Error ? failure.message : 'Unable to save zone'); }
      finally { setBusy(false); }
    }}>
      <div><label className="field-label" htmlFor="zone-name">Zone name</label><input id="zone-name" required maxLength={80} className="field" value={name} onChange={e => setName(e.target.value)} autoFocus /></div>
      <fieldset><legend className="field-label">Zone rules</legend><div className="grid grid-cols-2 gap-3">
        <button type="button" aria-pressed={kind === 'ppe'} className={`rounded-xl border p-3 text-left transition-colors ${kind === 'ppe' ? 'border-blue-900 bg-blue-50' : 'border-gray-200 hover:bg-gray-50'}`} onClick={() => setKind('ppe')}><ShieldCheck size={20} className="text-blue-900 mb-2" /><strong className="text-xs text-gray-800 block">PPE compliance</strong><span className="text-[10px] text-gray-500">โซนตรวจอุปกรณ์ PPE บนตัวคน</span></button>
        <button type="button" aria-pressed={kind === 'restricted'} className={`rounded-xl border p-3 text-left transition-colors ${kind === 'restricted' ? 'border-amber-500 bg-amber-50' : 'border-gray-200 hover:bg-gray-50'}`} onClick={() => setKind('restricted')}><Ban size={20} className="text-amber-600 mb-2" /><strong className="text-xs text-gray-800 block">Restricted / no entry</strong><span className="text-[10px] text-gray-500">โซนห้ามคนเข้า</span></button>
      </div></fieldset>
      {kind === 'ppe' ? <fieldset><legend className="field-label">Required PPE on each person</legend><div className="grid grid-cols-2 gap-2">{wearable.map(item => <label key={item.id} className={`flex items-center gap-2 rounded-lg border p-2.5 cursor-pointer text-xs ${required.includes(item.id) ? 'bg-blue-50 border-blue-200 text-blue-900' : 'border-gray-200 text-gray-600'}`}><input type="checkbox" className="accent-blue-900" checked={required.includes(item.id)} onChange={e => setRequired(previous => e.target.checked ? [...previous, item.id] : previous.filter(id => id !== item.id))} /><span>{item.name}</span></label>)}</div><p className="text-[11px] text-gray-500 mt-2 leading-relaxed">PPE is matched to each person's body. Body-part classes such as foot are not equipment.</p></fieldset> : <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 leading-relaxed">Any person whose selected anchor point enters this zone triggers an intrusion alert, regardless of PPE.</div>}
      <div><label className="field-label" htmlFor="zone-anchor">Person location inside the zone</label><select id="zone-anchor" className="field" value={anchor} onChange={e => setAnchor(e.target.value as 'feet' | 'centroid')}><option value="feet">Bottom-center / feet point (recommended)</option><option value="centroid">Bounding-box centroid</option></select></div>
      {shape==='polygon' ? <fieldset><legend className="field-label">Polygon · normalized points (0–1)</legend><p className="help-text mb-3">{vertices.length} points · The last point connects to the first. Edit coordinates here or use Redraw zone to place a new outline.</p><div className="space-y-2 max-h-48 overflow-y-auto modern-scrollbar pr-1">{vertices.map((vertex,index)=><div key={index} className="grid grid-cols-[28px_1fr_1fr] items-center gap-2"><span className="text-[10px] text-gray-400 font-semibold">#{index+1}</span>{(['x','y'] as const).map(axis=><label key={axis} className="text-[10px] text-gray-500 uppercase">{axis}<input type="number" aria-label={'Point '+(index+1)+' '+axis} className="field mt-1 !px-2" min={0} max={1} step="any" required value={Number(vertex[axis].toFixed(4))} onChange={event=>setVertices(previous=>previous.map((point,i)=>i===index ? {...point,[axis]:Number(event.target.value)} : point))} /></label>)}</div>)}</div></fieldset> : <fieldset><legend className="field-label">Normalized rectangle coordinates (0–1)</legend><div className="grid grid-cols-4 gap-2">{(['x1','y1','x2','y2'] as const).map(key => <label key={key} className="text-[11px] text-gray-500 uppercase">{key}<input type="number" aria-label={key} className="field mt-1 !px-2" min={0} max={1} step="any" required value={Number(coordinates[key].toFixed(4))} onChange={e => setCoordinates({ ...coordinates, [key]: Number(e.target.value) })} /></label>)}</div></fieldset>}
      <label className="flex items-center gap-2 text-xs text-gray-700"><input type="checkbox" className="accent-blue-900" checked={enabled} onChange={e => setEnabled(e.target.checked)} />Enable this zone immediately</label>
      {error && <p role="alert" className="rounded-lg bg-red-50 text-red-700 border border-red-200 px-3 py-2 text-xs">{error}</p>}
      <div className="flex justify-end gap-2 pt-4 border-t border-gray-100"><button type="button" className="btn-secondary" onClick={onClose} disabled={busy}>Cancel</button><button type="submit" className="btn-primary" disabled={busy || !name.trim()}><Save size={14} />{busy ? 'Saving…' : 'Save zone'}</button></div>
    </form>
  </Modal>;
}
