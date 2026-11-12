import { useCallback, useEffect, useRef, useState } from 'react';
import { Activity, AlertTriangle, Bell, Check, Cpu, Edit3, Info, KeyRound, Layers, Loader2, Plus, RefreshCw, ShieldCheck, Square, Trash2, Volume2, VolumeX, Wifi, WifiOff, X } from 'lucide-react';
import { api, ApiError, readToken, setToken } from './api';
import { useStream } from './useStream';
import type { Alert, ModelInfo, MonitorSettings, Page, Toast, VideoSource, Zone, ZoneGeometry, ZoneInput, ZoneShape } from './types';
import Layout from './components/Layout';
import VideoCanvas from './components/VideoCanvas';
import DrawingModeSelector from './components/DrawingModeSelector';
import SourcePanel from './components/SourcePanel';
import ZoneEditor from './components/ZoneEditor';
import ZoneList from './components/ZoneList';
import AlertFeed from './components/AlertFeed';
import AlertHistory from './components/AlertHistory';
import SettingsPanel from './components/SettingsPanel';
import SnapshotDialog from './components/SnapshotDialog';
import { Badge, Card, Modal } from './components/ui';

const pages: Page[] = ['monitor','zones','alerts','model','settings'];
const currentPage = (): Page => pages.includes(location.hash.slice(1) as Page) ? location.hash.slice(1) as Page : 'monitor';

export default function App() {
  const [page, setPage] = useState<Page>(currentPage);
  const [dark, setDark] = useState(() => localStorage.getItem('ppe-theme') === 'dark');
  const [token, updateToken] = useState(readToken);
  const [model, setModel] = useState<ModelInfo | null>(null);
  const [settings, setSettings] = useState<MonitorSettings | null>(null);
  const [videos, setVideos] = useState<VideoSource[]>([]);
  const [bootError, setBootError] = useState('');
  const [reload, setReload] = useState(0);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastId = useRef(0);
  const [sound, setSound] = useState(false);
  const audio = useRef<AudioContext | null>(null);
  const soundRef = useRef(sound); soundRef.current = sound;
  const [connectionOpen, setConnectionOpen] = useState(false);
  const [tokenDraft, setTokenDraft] = useState(token);
  const [tokenError, setTokenError] = useState('');
  const [drawing, setDrawing] = useState(false);
  const [drawingMode, setDrawingMode] = useState<ZoneShape>('rectangle');
  const [drawingTarget, setDrawingTarget] = useState<Zone | null>(null);
  const [draft, setDraft] = useState<ZoneGeometry | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [editor, setEditor] = useState<{ zone?: Zone; geometry: ZoneGeometry; sourceId: string } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Zone | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [snapshot, setSnapshot] = useState<Alert | null>(null);
  const [zoneSource, setZoneSource] = useState('');
  const [managedZones, setManagedZones] = useState<Zone[]>([]);
  const [alertRefresh, setAlertRefresh] = useState(0);

  const toast = useCallback((message: string, kind: Toast['kind'] = 'success') => {
    const id = ++toastId.current;
    setToasts(previous => [...previous, { id, message, kind }].slice(-3));
    setTimeout(() => setToasts(previous => previous.filter(item => item.id !== id)), kind === 'alert' ? 7000 : 5000);
  }, []);
  const error = useCallback((message: string) => toast(message, 'error'), [toast]);
  const newAlerts = useCallback((values: Alert[]) => {
    for (const value of values.slice(0, 2)) toast(`${value.kind === 'intrusion' ? 'Intrusion' : 'Missing PPE'} · ${value.zone_name} · Person #${value.track_id}${value.missing_classes.length ? ': ' + value.missing_classes.join(', ') : ''}`, 'alert');
    if (values.length > 2) toast(`${values.length - 2} more safety alerts. Open Alert History for details.`, 'alert');
    const context = audio.current;
    if (soundRef.current && context?.state === 'running') {
      const oscillator = context.createOscillator(), gain = context.createGain();
      oscillator.connect(gain); gain.connect(context.destination);
      oscillator.frequency.value = 740; gain.gain.setValueAtTime(0.08, context.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, context.currentTime + 0.28);
      oscillator.start(); oscillator.stop(context.currentTime + 0.3);
    }
  }, [toast]);
  const { packet, frame, connection } = useStream(token, newAlerts);
  const connected = connection === 'connected';
  const ready = !!model && connected;
  const zones = packet?.zones || [];
  const classes = model?.classes || [];
  const alerts = packet?.alerts || [];
  const sourceId = packet?.source?.id;
  const visibleManagedZones = zoneSource === sourceId ? zones : managedZones;

  const navigate = useCallback((value: Page) => {
    setPage(value); history.pushState({ page: value }, '', `#${value}`);
    document.querySelector('main')?.scrollTo({ top: 0 });
  }, []);
  useEffect(() => {
    const listener = () => setPage(currentPage());
    window.addEventListener('popstate', listener); window.addEventListener('hashchange', listener);
    return () => { window.removeEventListener('popstate', listener); window.removeEventListener('hashchange', listener); };
  }, []);
  useEffect(() => {
    let disposed = false;
    setModel(null); setBootError('');
    Promise.all([api<ModelInfo>('/api/classes'), api<{ items: VideoSource[] }>('/api/videos'), api<MonitorSettings>('/api/settings')])
      .then(([info, library, options]) => { if (!disposed) { setModel(info); setVideos(library.items); setSettings(options); } })
      .catch(failure => { if (!disposed) { setBootError(failure.message || 'Backend unavailable'); if (failure instanceof ApiError && failure.status === 401) setConnectionOpen(true); } });
    return () => { disposed = true; };
  }, [token, reload, connected]);
  useEffect(() => { if (connection === 'unauthorized') setConnectionOpen(true); }, [connection]);
  useEffect(() => {
    if (sourceId && page === 'monitor') setZoneSource(sourceId);
    else if (!zoneSource && videos[0]) setZoneSource(videos[0].id);
  }, [sourceId, videos, zoneSource, page]);
  const reloadVideos = async () => setVideos((await api<{ items: VideoSource[] }>('/api/videos')).items);
  const reloadZones = useCallback(async () => {
    if (zoneSource) setManagedZones((await api<{ items: Zone[] }>(`/api/zones?source_id=${encodeURIComponent(zoneSource)}`)).items);
  }, [zoneSource]);
  useEffect(() => {
    if (page !== 'zones' || !zoneSource) return;
    let disposed = false;
    api<{ items: Zone[] }>(`/api/zones?source_id=${encodeURIComponent(zoneSource)}`).then(result => { if (!disposed) setManagedZones(result.items); }).catch(failure => { if (!disposed) error(failure.message); });
    return () => { disposed = true; };
  }, [zoneSource, page, error]);
  useEffect(() => {
    if (page === 'settings' && model) api<MonitorSettings>('/api/settings').then(setSettings).catch(failure => error(failure.message));
  }, [page, model, error]);
  useEffect(() => {
    setDrawing(false); setDrawingTarget(null); setDraft(null); setEditor(null); setSelected(null);
  }, [sourceId]);

  const beginDraw = (zone?: Zone) => {
    if (!frame || !sourceId || (zone && zone.source_id !== sourceId)) { error('Start this source in Live Monitoring before drawing its zones.'); return; }
    if (zone) setDrawingMode(zone.shape || 'rectangle');
    setDrawingTarget(zone || null); setSelected(zone?.id || null); setDrawing(true); setDraft(null); navigate('monitor');
  };
  const geometryDrawn = useCallback((geometry: ZoneGeometry) => {
    if (!sourceId) return;
    setDraft(geometry); setDrawing(false);
    setEditor({ zone: drawingTarget || undefined, geometry, sourceId });
  }, [sourceId, drawingTarget]);
  const cancelDraw = useCallback(() => { setDrawing(false); setDrawingTarget(null); setDraft(null); }, []);
  const saveZone = async (value: ZoneInput, expectedVersion?: number) => {
    const zone = await api<Zone>(editor?.zone ? `/api/zones/${editor.zone.id}` : '/api/zones', {
      method: editor?.zone ? 'PATCH' : 'POST',
      body: editor?.zone ? { name: value.name, kind: value.kind, rect: value.rect, shape: value.shape || 'rectangle', points: value.points || null, required_class_ids: value.required_class_ids, anchor: value.anchor, enabled: value.enabled, expected_version: expectedVersion } : value
    });
    setEditor(null); setDraft(null); setDrawingTarget(null); setSelected(zone.id);
    toast('Zone saved. Rules update immediately when its source is monitored.');
    void reloadZones().catch(failure => error(failure.message));
  };
  const toggleZone = async (zone: Zone) => {
    try { await api(`/api/zones/${zone.id}`, { method: 'PATCH', body: { enabled: !zone.enabled, expected_version: zone.version } }); await reloadZones(); }
    catch (failure) { error(failure instanceof Error ? failure.message : 'Unable to toggle zone'); }
  };
  const acknowledge = async (alert: Alert) => {
    try { await api(`/api/alerts/${alert.id}/acknowledge`, { method: 'POST' }); setAlertRefresh(value => value + 1); toast('Alert acknowledged. Monitoring continues.'); }
    catch (failure) { error(failure instanceof Error ? failure.message : 'Unable to acknowledge alert'); }
  };
  const toggleSound = async () => {
    if (sound) { setSound(false); return; }
    try { audio.current ||= new AudioContext(); await audio.current.resume(); setSound(true); }
    catch { error('Your browser could not enable audio. Visual alerts remain available.'); }
  };
  const editZone = (zone: Zone) => { setSelected(zone.id); setEditor({ zone, geometry: {shape: zone.shape || 'rectangle', rect: zone.rect, points: zone.points || null}, sourceId: zone.source_id }); };

  const stats = [
    { label: 'Persons in frame', value: packet ? classes.filter(item => item.kind === 'person').reduce((sum, item) => sum + (packet.counts[item.name] || 0), 0) : '—', color: 'text-blue-900' },
    { label: 'Enabled zones', value: zones.filter(zone => zone.enabled).length, color: 'text-gray-800' },
    { label: 'Violations in frame', value: packet?.violations.length || 0, color: packet?.violations.length ? 'text-red-600' : 'text-emerald-600' },
    { label: 'Active events', value: packet?.active_alert_count || 0, color: packet?.active_alert_count ? 'text-red-600' : 'text-gray-800' },
    { label: 'Processing speed', value: packet?.state === 'running' ? `${packet.fps} FPS` : '—', color: 'text-blue-900' },
    { label: 'Frames processed', value: packet?.frames_processed.toLocaleString() || '0', color: 'text-gray-800' }
  ];

  return <Layout page={page} onNavigate={navigate} dark={dark} onTheme={() => { localStorage.setItem('ppe-theme', dark ? 'light' : 'dark'); setDark(!dark); }} connected={connected && !!model} model={model} unacknowledged={alerts.filter(item => !item.acknowledged_at).length}>
    <div className="flex items-center justify-between gap-3"><div><p className="text-xs text-gray-500">Smart Safety & PPE Monitoring</p><div className="flex items-center gap-2 mt-1"><ShieldCheck size={16} className="text-blue-900" /><p className="text-sm font-semibold text-gray-700">{packet?.source?.name || 'Safety control workspace'}</p></div></div><div className="flex items-center gap-2"><Badge tone={connected ? 'green' : 'amber'}>{connected ? <Wifi size={11} /> : <WifiOff size={11} />}{connection === 'connected' ? 'Live connection' : connection === 'unauthorized' ? 'Authentication required' : connection === 'connecting' ? 'Connecting' : 'Reconnecting'}</Badge><button className="icon-button border border-gray-200 bg-white" aria-label="Connection settings" onClick={() => { setTokenDraft(token); setConnectionOpen(true); }}><KeyRound size={14} /></button></div></div>
    {(bootError || packet?.error) && <div role="alert" className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3"><AlertTriangle size={17} className="text-red-600 mt-0.5 shrink-0" /><div className="flex-1 text-xs text-red-700 leading-relaxed">{bootError || packet?.error}</div><button className="text-xs font-semibold text-red-700 flex items-center gap-1" onClick={() => setReload(reload + 1)}><RefreshCw size={12} />Retry</button></div>}

    {page === 'monitor' && <>
      <div><h2 className="section-label">Monitoring overview</h2><div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">{stats.map(stat => <Card key={stat.label} className="p-4"><p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">{stat.label}</p><p className={`text-2xl font-bold mt-1.5 tabular-nums ${stat.color}`}>{stat.value}</p></Card>)}</div></div>
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 items-start"><div className="xl:col-span-8 space-y-6"><Card className="overflow-hidden"><div className="section-header flex-wrap gap-3"><div className="flex items-center gap-2"><div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center text-blue-900"><Activity size={17} /></div><div><h2 className="text-sm font-bold text-gray-800">Live safety view</h2><p className="text-[10px] text-gray-500">Draw zones directly on the video · select a zone to edit</p></div></div><div className="flex flex-wrap items-center gap-2"><DrawingModeSelector value={drawingMode} onChange={setDrawingMode} /><button className={drawing ? 'btn-secondary' : 'btn-primary'} disabled={!frame} onClick={() => drawing ? cancelDraw() : beginDraw()}>{drawing ? <X size={14} /> : <Plus size={14} />}{drawing ? 'Cancel drawing' : 'Draw zone'}</button></div></div><VideoCanvas frame={frame} zones={zones} classes={classes} drawing={drawing} drawingMode={drawingMode} selectedId={selected} draft={draft} onComplete={geometryDrawn} onSelect={zone => setSelected(zone.id)} onCancelDraw={cancelDraw} /><div className="px-4 py-3 flex flex-wrap gap-2 border-t border-gray-100">{classes.map(item => <span key={item.id} className="inline-flex items-center gap-1.5 rounded-md bg-slate-50 border border-gray-100 text-[10px] px-2 py-1 text-gray-600"><span className="w-1.5 h-1.5 rounded-sm" style={{ backgroundColor: item.color }} />{item.name}<strong className="text-gray-800 ml-0.5 tabular-nums">{packet?.counts[item.name] || 0}</strong></span>)}</div><div className="px-4 pb-3 text-[10px] text-gray-400 flex justify-between gap-2"><span>{packet?.width ? `${packet.width} × ${packet.height} · ${packet.inference_ms} ms inference` : 'Waiting for first frame'}</span><span>{packet?.state === 'paused' ? 'Paused · showing last frame' : packet && ['ended','stopped'].includes(packet.state) ? 'Stopped · showing last frame' : 'Zones remain aligned across display sizes'}</span></div></Card><Card><div className="section-header"><div className="flex items-center gap-2"><Bell size={16} className="text-blue-900" /><h2 className="text-sm font-bold text-gray-800">Recent safety alerts</h2><Badge>{alerts.length}</Badge></div><div className="flex items-center gap-2"><button className="icon-button" aria-label={sound ? 'Mute alerts' : 'Enable alert sound'} onClick={() => void toggleSound()}>{sound ? <Volume2 size={14} /> : <VolumeX size={14} />}</button><button className="text-[11px] text-blue-900 font-semibold" onClick={() => navigate('alerts')}>View history</button></div></div><AlertFeed alerts={alerts.slice(0, 12)} onAcknowledge={alert => void acknowledge(alert)} onSnapshot={setSnapshot} compact /></Card></div><div className="xl:col-span-4 space-y-6"><SourcePanel videos={videos} packet={packet} settings={settings} ready={ready} onVideos={reloadVideos} onError={error} /><Card><div className="section-header"><div className="flex items-center gap-2"><Layers size={16} className="text-blue-900" /><h2 className="text-sm font-bold text-gray-800">Detection zones</h2><Badge>{zones.length}</Badge></div><button className="icon-button" aria-label="Draw a new zone" disabled={!frame} onClick={() => beginDraw()}><Plus size={16} /></button></div><ZoneList zones={zones} classes={classes} results={packet?.zone_results || []} selected={selected} onSelect={zone => setSelected(zone.id)} onEdit={editZone} onRedraw={zone => beginDraw(zone)} onToggle={zone => void toggleZone(zone)} onDelete={setDeleteTarget} /><div className="px-4 py-3 border-t border-gray-100 flex items-start gap-2 text-[10px] leading-relaxed text-gray-500"><Info size={13} className="shrink-0 mt-0.5" /><span>Blue zones check PPE per person. Amber zones prohibit entry. Red outlines indicate a current rule violation.</span></div></Card></div></div>
    </>}

    {page === 'zones' && <Card><div className="section-header flex-wrap gap-3"><div className="flex items-center gap-2"><Layers size={16} className="text-blue-900" /><h2 className="text-sm font-bold text-gray-800">Detection zone configuration</h2><Badge>{visibleManagedZones.length} zones</Badge></div><div className="flex gap-2"><button className="btn-secondary" onClick={() => void reloadZones().catch(failure => error(failure.message))}><RefreshCw size={13} />Refresh</button><button className="btn-primary" disabled={!frame || zoneSource !== sourceId} onClick={() => beginDraw()}><Plus size={14} />Draw new zone</button></div></div><div className="p-4 border-b border-gray-100"><label htmlFor="zone-source" className="field-label">Source-specific zones</label><select id="zone-source" className="field max-w-lg" value={zoneSource} onChange={event => setZoneSource(event.target.value)}><option value="" disabled>Select a source</option>{packet?.source?.kind === 'camera' && <option value={packet.source.id}>{packet.source.name}</option>}{videos.map(video => <option key={video.id} value={video.id}>{video.name}</option>)}</select><p className="help-text">Start the source in Live Monitoring to draw or redraw its rectangle or polygon zones.</p></div><div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead className="bg-slate-50 border-b border-gray-100 text-[10px] text-gray-500 uppercase tracking-wider"><tr><th className="p-4">Zone</th><th className="p-4">Rules</th><th className="p-4">Anchor</th><th className="p-4">Status</th><th className="p-4 text-right">Actions</th></tr></thead><tbody className="divide-y divide-gray-100">{visibleManagedZones.map(zone => <tr key={zone.id} className="hover:bg-slate-50/50"><td className="p-4 font-semibold text-gray-800">{zone.name}<span className="block text-[10px] text-gray-400 font-normal mt-1">{zone.kind === 'ppe' ? 'PPE compliance' : 'Restricted / no entry'} · {zone.shape === 'polygon' ? 'Polygon · ' + zone.points?.length + ' points' : 'Rectangle'}</span></td><td className="p-4 text-gray-600 max-w-xs">{zone.kind === 'restricted' ? 'No person entry' : zone.required_class_ids.map(id => classes.find(item => item.id === id)?.name || `Class ${id}`).join(', ')}</td><td className="p-4 text-gray-500">{zone.anchor === 'feet' ? 'Bottom-center' : 'Centroid'}</td><td className="p-4"><button onClick={() => void toggleZone(zone)}><Badge tone={zone.enabled ? 'green' : 'slate'}>{zone.enabled ? 'Enabled' : 'Disabled'}</Badge></button></td><td className="p-4"><div className="flex justify-end gap-1"><button className="icon-button" title="Edit zone" aria-label={`Edit ${zone.name}`} onClick={() => editZone(zone)}><Edit3 size={14} /></button><button className="icon-button hover:!text-red-600" title="Delete zone" aria-label={`Delete ${zone.name}`} onClick={() => setDeleteTarget(zone)}><Trash2 size={14} /></button></div></td></tr>)}{!visibleManagedZones.length && <tr><td colSpan={5} className="text-center p-12 text-gray-400">No zones for this source. Start monitoring and draw a rectangle to create one.</td></tr>}</tbody></table></div></Card>}

    {page === 'alerts' && <AlertHistory newestId={alerts[0]?.id || ''} refreshKey={alertRefresh} onAcknowledge={alert => void acknowledge(alert)} onSnapshot={setSnapshot} onError={error} />}
    {page === 'model' && <div className="space-y-6"><div className="grid lg:grid-cols-3 gap-6"><Card className="p-5 lg:col-span-2"><div className="flex items-center gap-2 mb-4"><Cpu size={18} className="text-blue-900" /><h2 className="text-sm font-bold text-gray-800">Custom-trained YOLO model</h2><Badge tone={model ? 'green' : 'slate'}>{model ? 'Loaded' : 'Offline'}</Badge></div><dl className="grid sm:grid-cols-2 gap-5 text-xs"><div><dt className="text-gray-500">Weights</dt><dd className="text-gray-800 font-semibold mt-1">{model?.model_name || '—'}</dd></div><div><dt className="text-gray-500">Inference device</dt><dd className="text-gray-800 font-semibold mt-1">{model?.device.toUpperCase() || '—'}</dd></div><div className="sm:col-span-2"><dt className="text-gray-500">Checkpoint SHA-256</dt><dd className="text-[10px] font-mono text-gray-600 mt-1 break-all">{model?.sha256 || '—'}</dd></div></dl></Card><Card className="p-5"><h2 className="text-sm font-bold text-gray-800 mb-4">Training validation</h2>{model?.training ? <div className="space-y-3 text-xs text-gray-600"><p>Checkpoint: <strong className="text-gray-800">{model.training.recorded_training_epochs} / {model.training.target_epochs} epochs</strong></p><div className="grid grid-cols-2 gap-3"><div><p className="text-[10px] text-gray-500">mAP@50</p><strong className="text-xl text-blue-900">{(Number(model.training.best_validation['metrics/mAP50(B)'] || 0)*100).toFixed(1)}%</strong></div><div><p className="text-[10px] text-gray-500">mAP@50–95</p><strong className="text-xl text-blue-900">{(Number(model.training.best_validation['metrics/mAP50-95(B)'] || 0)*100).toFixed(1)}%</strong></div></div><p className="text-[10px] leading-relaxed text-gray-400">Validation metrics from the training run; not an independent test set.</p></div> : <p className="text-xs text-gray-500">No matching training report attached.</p>}</Card></div><Card><div className="section-header"><h2 className="text-sm font-bold text-gray-800">Classes read from model.names</h2><Badge tone="blue">{classes.length} classes</Badge></div><div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3 p-5">{classes.map(item => <div key={item.id} className="rounded-lg border border-gray-200 p-3" style={{ borderTopWidth: 3, borderTopColor: item.color }}><p className="text-[10px] text-gray-400">CLASS {item.id}</p><p className="text-sm font-bold text-gray-800 mt-1">{item.name}</p><span className="text-[10px] text-gray-500">{item.kind === 'ppe' ? 'Selectable PPE' : item.kind === 'person' ? 'Person detection' : item.kind === 'body_part' ? 'Body part · not PPE' : 'Other object'}</span></div>)}</div><p className="px-5 pb-5 text-xs text-gray-500 leading-relaxed">PPE rules use spatial containment and exclusive ownership, not global object counts. Person track numbers are temporary within a monitoring session.</p></Card></div>}
    {page === 'settings' && <SettingsPanel value={settings} sound={sound} onSound={() => void toggleSound()} onConnection={() => { setTokenDraft(token); setConnectionOpen(true); }} onSave={async value => { setSettings(await api<MonitorSettings>('/api/settings', { method: 'PUT', body: value })); toast('Monitoring settings saved.'); }} />}

    {editor && <ZoneEditor sourceId={editor.sourceId} zone={editor.zone} rect={editor.geometry.rect} shape={editor.geometry.shape} points={editor.geometry.points} classes={classes} onSave={saveZone} onClose={() => { setEditor(null); setDraft(null); setDrawingTarget(null); }} />}
    {deleteTarget && <Modal title="Delete detection zone" onClose={() => { if (!deleting) setDeleteTarget(null); }}><p className="text-sm text-gray-700">Delete <strong>{deleteTarget.name}</strong>?</p><p className="text-xs text-gray-500 mt-2">This removes its rules from monitoring immediately. Existing alert history is retained.</p><div className="flex justify-end gap-2 mt-6"><button className="btn-secondary" disabled={deleting} onClick={() => setDeleteTarget(null)}>Cancel</button><button className="btn-danger" disabled={deleting} onClick={async () => { setDeleting(true); try { await api(`/api/zones/${deleteTarget.id}`, { method: 'DELETE' }); setDeleteTarget(null); await reloadZones(); toast('Zone deleted.'); } catch (failure) { error(failure instanceof Error ? failure.message : 'Unable to delete zone'); } finally { setDeleting(false); } }}>{deleting ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}Delete zone</button></div></Modal>}
    {snapshot && <SnapshotDialog alert={snapshot} onClose={() => setSnapshot(null)} />}
    {connectionOpen && <Modal title="Connection settings" onClose={() => setConnectionOpen(false)}><form className="space-y-4" onSubmit={event => { event.preventDefault(); const value = tokenDraft.trim(); if (value && !/^[A-Za-z0-9_-]+$/.test(value)) { setTokenError('Token may contain only letters, digits, underscores and hyphens.'); return; } setToken(value); updateToken(value); setReload(previous => previous + 1); setTokenError(''); setConnectionOpen(false); }}><p className="text-xs leading-relaxed text-gray-500">For a protected backend, enter the operator API token. It is kept only in this browser tab's session. Leave blank for local development mode.</p><div><label className="field-label" htmlFor="api-token">Operator API token</label><input id="api-token" type="password" autoComplete="off" className="field font-mono" value={tokenDraft} onChange={event => setTokenDraft(event.target.value)} /></div>{tokenError && <p role="alert" className="text-xs text-red-600">{tokenError}</p>}<div className="flex justify-end gap-2"><button type="button" className="btn-secondary" onClick={() => setConnectionOpen(false)}>Cancel</button><button type="submit" className="btn-primary"><KeyRound size={14} />Connect</button></div></form></Modal>}
    <div className="fixed bottom-4 right-4 z-[150] w-[min(420px,calc(100vw-2rem))] space-y-2" aria-live="polite">{toasts.map(item => <div key={item.id} role={item.kind === 'alert' || item.kind === 'error' ? 'alert' : 'status'} className={`rounded-xl shadow-lg border px-4 py-3 flex items-start gap-2.5 text-xs leading-relaxed ${item.kind === 'success' ? 'bg-blue-900 border-blue-800 text-white' : 'bg-red-600 border-red-700 text-white'}`}>{item.kind === 'success' ? <Check size={16} className="shrink-0" /> : <AlertTriangle size={16} className="shrink-0" />}<span className="flex-1">{item.message}</span><button aria-label="Dismiss notification" onClick={() => setToasts(previous => previous.filter(value => value.id !== item.id))}><X size={14} /></button></div>)}</div>
  </Layout>;
}
