import { PenTool, Square } from 'lucide-react';
import type { ZoneShape } from '../types';

export default function DrawingModeSelector({ value, onChange }: { value: ZoneShape; onChange: (value: ZoneShape) => void }) {
  return <div role="group" aria-label="Drawing mode" className="inline-flex rounded-lg border border-gray-200 bg-slate-50 p-1 gap-1">
    {([{shape:'rectangle',name:'Rectangle',Icon:Square},{shape:'polygon',name:'Polygon / Pen',Icon:PenTool}] as const).map(({shape,name,Icon})=>
      <button key={shape} type="button" aria-pressed={value===shape} onClick={()=>onChange(shape)} className={'inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[11px] font-semibold transition-colors '+(value===shape ? 'bg-blue-900 text-white shadow-sm' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800')}><Icon size={13} />{name}</button>
    )}
  </div>;
}
