import { useEffect, useState } from 'react';
import { Download, Loader2 } from 'lucide-react';
import { getBlob } from '../api';
import { formatDate } from '../geometry';
import type { Alert } from '../types';
import { Modal } from './ui';

export default function SnapshotDialog({ alert, onClose }: { alert: Alert; onClose: () => void }) {
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    let disposed = false, objectUrl = '';
    if (alert.snapshot_url) getBlob(alert.snapshot_url).then(blob => {
      objectUrl = URL.createObjectURL(blob);
      if (disposed) URL.revokeObjectURL(objectUrl); else setUrl(objectUrl);
    }).catch(failure => { if (!disposed) setError(failure.message); });
    return () => { disposed = true; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [alert.id, alert.snapshot_url]);
  return <Modal title={`${alert.kind === 'intrusion' ? 'Intrusion' : 'Missing PPE'} · ${alert.zone_name}`} wide onClose={onClose}>
    <div className="space-y-4"><div className="text-xs text-gray-600 flex flex-wrap justify-between gap-2"><span>Person #{alert.track_id} · {alert.source_name}</span><time>{formatDate(alert.created_at)} ICT</time></div>{alert.missing_classes.length > 0 && <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-xs text-red-700">Missing: <strong>{alert.missing_classes.join(', ')}</strong></div>}<div className="bg-[#0b1520] rounded-lg min-h-48 flex items-center justify-center overflow-hidden">{url ? <img src={url} alt={`Safety alert in ${alert.zone_name}`} className="w-full max-h-[65vh] object-contain" /> : error ? <p role="alert" className="p-5 text-sm text-red-300">{error}</p> : <Loader2 className="animate-spin text-slate-400 m-12" />}</div>{url && <div className="flex justify-end"><a className="btn-primary" href={url} download={`safety-alert-${alert.id}.jpg`}><Download size={14} />Download snapshot</a></div>}</div>
  </Modal>;
}
