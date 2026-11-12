import { Ban, Edit3, MousePointer2, ShieldCheck, Trash2 } from 'lucide-react';
import type { ClassInfo, Zone, ZoneResult } from '../types';
import { Badge } from './ui';

type Props = { zones: Zone[]; results: ZoneResult[]; classes: ClassInfo[]; selected: string | null; onSelect: (zone: Zone) => void; onEdit: (zone: Zone) => void; onRedraw: (zone: Zone) => void; onToggle: (zone: Zone) => void; onDelete: (zone: Zone) => void };

export default function ZoneList({ zones, results, classes, selected, onSelect, onEdit, onRedraw, onToggle, onDelete }: Props) {
  if (!zones.length) return <div className="py-10 px-5 text-center"><ShieldCheck size={28} className="mx-auto text-gray-300 mb-3" /><p className="text-xs font-semibold text-gray-600">No detection zones yet</p><p className="text-[11px] text-gray-400 mt-1.5 leading-relaxed">Start a source and click Draw zone to set your first safety rule.</p></div>;
  return <div className="p-3 space-y-2.5 max-h-[520px] overflow-y-auto modern-scrollbar">{zones.map(zone => {
    const result = results.find(item => item.zone_id === zone.id);
    const alarm = zone.enabled && !!result?.violation_count;
    return <article key={zone.id} className={`rounded-lg border p-3 transition-colors ${alarm ? 'border-red-200 bg-red-50/40' : selected === zone.id ? 'border-blue-300 bg-blue-50/30' : 'border-gray-200 bg-slate-50/50'} ${!zone.enabled ? 'opacity-60' : ''}`}>
      <div className="flex gap-2 items-start"><button className="min-w-0 text-left flex-1 flex items-start gap-2" onClick={() => onSelect(zone)}>{zone.kind === 'restricted' ? <Ban size={16} className="text-amber-600 mt-0.5 shrink-0" /> : <ShieldCheck size={16} className="text-blue-900 mt-0.5 shrink-0" />}<span className="min-w-0"><strong className="block text-xs text-gray-800 truncate">{zone.name}</strong><span className="text-[10px] text-gray-500">{zone.kind === 'restricted' ? 'Restricted area' : 'PPE compliance'}</span></span></button><button role="switch" aria-checked={zone.enabled} aria-label={`${zone.enabled ? 'Disable' : 'Enable'} zone ${zone.name}`} onClick={() => onToggle(zone)} className={`w-8 h-[18px] rounded-full p-0.5 transition-colors shrink-0 ${zone.enabled ? 'bg-blue-900' : 'bg-gray-300'}`}><span className={`block h-3.5 w-3.5 rounded-full bg-white shadow-sm transition-transform ${zone.enabled ? 'translate-x-3.5' : ''}`} /></button></div>
      <div className="flex flex-wrap gap-1 mt-3">{zone.kind === 'restricted' ? <Badge tone="amber">No person entry</Badge> : zone.required_class_ids.map(id => <Badge key={id} tone="blue">{classes.find(item => item.id === id)?.name || `Class ${id}`}</Badge>)}</div>
      <div className="flex items-center justify-between mt-3 pt-2 border-t border-gray-100"><span className="text-[10px] text-gray-500">{!zone.enabled ? 'Disabled' : `${result?.occupancy || 0} inside`}{alarm && <span className="font-semibold text-red-600"> · {result?.violation_count} alert</span>}</span><div className="flex items-center gap-0.5"><button className="icon-button !w-6 !h-6" aria-label={`Edit zone ${zone.name}`} title="Edit rules" onClick={() => onEdit(zone)}><Edit3 size={12} /></button><button className="icon-button !w-6 !h-6" aria-label={`Redraw zone ${zone.name}`} title="Redraw rectangle" onClick={() => onRedraw(zone)}><MousePointer2 size={12} /></button><button className="icon-button !w-6 !h-6 hover:!text-red-600" aria-label={`Delete zone ${zone.name}`} title="Delete zone" onClick={() => onDelete(zone)}><Trash2 size={12} /></button></div></div>
    </article>;
  })}</div>;
}
