import { useEffect, useState } from 'react';
import { Download, RefreshCw, ChevronLeft, ChevronRight } from 'lucide-react';
import { api, exportAlerts } from '../api';
import type { Alert } from '../types';
import AlertFeed from './AlertFeed';
import { Badge, Card } from './ui';

export default function AlertHistory({ newestId, refreshKey, onAcknowledge, onSnapshot, onError }: { newestId: string; refreshKey: number; onAcknowledge: (alert: Alert) => void; onSnapshot: (alert: Alert) => void; onError: (message: string) => void }) {
  const [kind, setKind] = useState('');
  const [acknowledged, setAcknowledged] = useState('');
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [data, setData] = useState<{ items: Alert[]; total: number }>({ items: [], total: 0 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    let disposed = false, inFlight = false;
    const fetch = async () => {
      if (inFlight) return;
      inFlight = true; setBusy(true);
      const query = new URLSearchParams({ limit: '30', offset: String(offset) });
      if (kind) query.set('kind', kind);
      if (acknowledged) query.set('acknowledged', acknowledged);
      try { const result = await api<{ items: Alert[]; total: number }>(`/api/alerts?${query}`); if (!disposed) { setData(result); setError(''); } }
      catch (failure) { if (!disposed) setError(failure instanceof Error ? failure.message : 'Unable to load alerts'); }
      finally { inFlight = false; if (!disposed) setBusy(false); }
    };
    void fetch(); const timer = setInterval(fetch, 5000);
    return () => { disposed = true; clearInterval(timer); };
  }, [kind, acknowledged, offset, revision, newestId, refreshKey]);
  return <Card><div className="section-header flex-wrap gap-3"><div className="flex items-center gap-2"><h2 className="text-sm font-bold text-gray-800">Safety event history</h2><Badge>{data.total} events</Badge></div><div className="flex gap-2"><button className="btn-secondary" disabled={busy} onClick={() => setRevision(revision + 1)}><RefreshCw size={13} className={busy ? 'animate-spin' : ''} />Refresh</button><button className="btn-primary" onClick={() => void exportAlerts().catch(e => onError(e.message))}><Download size={13} />Export CSV</button></div></div><div className="p-4 border-b border-gray-100 flex flex-wrap gap-3"><select aria-label="Filter alert type" className="field !w-auto" value={kind} onChange={e => { setKind(e.target.value); setOffset(0); }}><option value="">All alert types</option><option value="missing_ppe">Missing PPE</option><option value="intrusion">Intrusion</option></select><select aria-label="Filter acknowledgement" className="field !w-auto" value={acknowledged} onChange={e => { setAcknowledged(e.target.value); setOffset(0); }}><option value="">All acknowledgement states</option><option value="false">Unacknowledged</option><option value="true">Acknowledged</option></select><span className="text-[11px] text-gray-400 self-center ml-auto">Times shown in Bangkok (ICT)</span></div>{error && <p role="alert" className="px-4 py-3 text-xs bg-red-50 text-red-700">{error}</p>}<AlertFeed alerts={data.items} onAcknowledge={onAcknowledge} onSnapshot={onSnapshot} /><div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 text-xs text-gray-500"><span>{data.total ? `${offset + 1}–${Math.min(offset + 30, data.total)} of ${data.total}` : '0 events'}</span><div className="flex gap-2"><button className="btn-secondary !px-2" aria-label="Previous alerts" disabled={offset === 0 || busy} onClick={() => setOffset(Math.max(0, offset - 30))}><ChevronLeft size={14} /></button><button className="btn-secondary !px-2" aria-label="Next alerts" disabled={offset + 30 >= data.total || busy} onClick={() => setOffset(offset + 30)}><ChevronRight size={14} /></button></div></div></Card>;
}
