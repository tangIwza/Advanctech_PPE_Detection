import { useEffect, useRef, useState } from 'react';
import { Camera, FileVideo, Upload, Play, Pause, Square, Loader2, RefreshCw } from 'lucide-react';
import { api } from '../api';
import type { MonitorSettings, Packet, VideoSource } from '../types';
import { formatTime } from '../geometry';
import { Badge, Card } from './ui';

type Start = { kind: 'camera'; address: string } | { kind: 'video'; video_id: string; loop: boolean };
type Props = { videos: VideoSource[]; packet: Packet | null; settings: MonitorSettings | null; ready: boolean; onVideos: () => Promise<void>; onError: (message: string) => void };

export default function SourcePanel({ videos, packet, settings, ready, onVideos, onError }: Props) {
  const [mode, setMode] = useState<'video' | 'camera'>('video');
  const [video, setVideo] = useState('');
  const [address, setAddress] = useState('0');
  const [loop, setLoop] = useState(false);
  const [busy, setBusy] = useState('');
  const fileInput = useRef<HTMLInputElement>(null);
  useEffect(() => { if (!video && videos[0]) setVideo(videos[0].id); }, [videos, video]);
  useEffect(() => {
    if (packet?.source) { setMode(packet.source.kind); if (packet.source.kind === 'video') setVideo(packet.source.id); }
  }, [packet?.source?.id]);
  const active = ['running','paused','opening'].includes(packet?.state || '');
  const action = async (path: string, body?: unknown) => {
    setBusy(path);
    try { await api(path, { method: 'POST', body }); }
    catch (error) { onError(error instanceof Error ? error.message : 'Source operation failed'); }
    finally { setBusy(''); }
  };
  const start = (value: Start) => action('/api/stream/start', value);
  const upload = async (file: File) => {
    if (file.size > (settings?.max_upload_mb || 500) * 1024 * 1024) { onError(`Video exceeds ${settings?.max_upload_mb || 500} MB limit`); return; }
    setBusy('upload');
    try {
      const body = new FormData(); body.append('file', file);
      const result = await api<VideoSource>('/api/videos', { method: 'POST', body });
      await onVideos(); setVideo(result.id);
      await api('/api/stream/start', { method: 'POST', body: { kind: 'video', video_id: result.id, loop } });
    } catch (error) { onError(error instanceof Error ? error.message : 'Unable to upload video'); }
    finally { setBusy(''); }
  };
  return <Card>
    <div className="section-header"><div className="flex items-center gap-2"><FileVideo size={16} className="text-blue-900" /><h2 className="text-sm font-bold text-gray-800">Input source</h2></div><Badge tone={packet?.state === 'running' ? 'green' : packet?.state === 'error' ? 'red' : 'slate'}>{packet?.state || 'idle'}</Badge></div>
    <div className="p-4 space-y-4">
      <div className="flex bg-slate-100 rounded-lg p-1 text-xs font-semibold"><button className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-md ${mode === 'video' ? 'bg-white text-blue-900 shadow-sm' : 'text-gray-500'}`} onClick={() => setMode('video')}><FileVideo size={14} />Video file</button><button className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-md ${mode === 'camera' ? 'bg-white text-blue-900 shadow-sm' : 'text-gray-500'}`} onClick={() => setMode('camera')}><Camera size={14} />Live camera</button></div>
      {mode === 'video' ? <div className="space-y-3"><div><label className="field-label" htmlFor="video-select">Video library</label><div className="flex gap-2"><select id="video-select" className="field min-w-0" value={video} onChange={e => setVideo(e.target.value)}><option value="" disabled>Select a video</option>{videos.map(item => <option key={item.id} value={item.id}>{item.sample ? 'Sample · ' : ''}{item.name}</option>)}</select><button className="icon-button border border-gray-200 shrink-0" title="Refresh videos" aria-label="Refresh videos" onClick={() => void onVideos().catch(e => onError(e.message))}><RefreshCw size={14} /></button></div></div><button className="btn-secondary w-full !py-2.5 border-dashed" disabled={!ready || !!busy} onClick={() => fileInput.current?.click()}>{busy === 'upload' ? <Loader2 size={15} className="animate-spin" /> : <Upload size={15} />}{busy === 'upload' ? 'Uploading and validating…' : 'Upload & play video'}</button><input ref={fileInput} type="file" accept=".mp4,.avi,.mov" className="hidden" onChange={e => { const file = e.target.files?.[0]; if (file) void upload(file); e.target.value = ''; }} /><div className="flex items-center justify-between gap-2 text-[11px] text-gray-500"><span>MP4, AVI, MOV · up to {settings?.max_upload_mb || 500} MB</span><label className="flex items-center gap-1.5"><input className="accent-blue-900" type="checkbox" checked={loop} disabled={active} onChange={e => setLoop(e.target.checked)} />Loop</label></div></div> : <div><label className="field-label" htmlFor="camera-address">Camera index or stream URL</label><input id="camera-address" className="field" spellCheck={false} autoComplete="off" placeholder="0 or rtsp://camera/stream" value={address} onChange={e => setAddress(e.target.value)} /><p className="text-[11px] leading-relaxed text-gray-500 mt-2">Use 0 for the backend PC's webcam, or enter an RTSP / HTTP(S) camera address.</p></div>}
      <div className="flex gap-2"><button className="btn-primary flex-1" disabled={!ready || !!busy || (mode === 'video' ? !video : !address.trim())} onClick={() => void start(mode === 'video' ? { kind: 'video', video_id: video, loop } : { kind: 'camera', address: address.trim() })}>{busy && busy !== 'upload' ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}{active ? 'Switch / restart' : 'Start monitoring'}</button>{active && <><button className="btn-secondary !px-2.5" title={packet?.state === 'paused' ? 'Resume' : 'Pause'} aria-label={packet?.state === 'paused' ? 'Resume monitoring' : 'Pause monitoring'} disabled={!!busy || packet?.state === 'opening'} onClick={() => void action(packet?.state === 'paused' ? '/api/stream/resume' : '/api/stream/pause')}>{packet?.state === 'paused' ? <Play size={14} /> : <Pause size={14} />}</button><button className="btn-secondary !px-2.5 text-red-600" title="Stop" aria-label="Stop monitoring" disabled={!!busy} onClick={() => void action('/api/stream/stop')}><Square size={14} /></button></>}</div>
      {!!packet?.duration_seconds && <div><div className="h-1.5 rounded-full bg-slate-100 overflow-hidden"><div className="h-full bg-blue-900 rounded-full transition-all" style={{ width: `${Math.min(100, packet.position_seconds / packet.duration_seconds * 100)}%` }} /></div><div className="mt-1 flex justify-between text-[10px] text-gray-400 tabular-nums"><span>{formatTime(packet.position_seconds)}</span><span>{formatTime(packet.duration_seconds)}</span></div></div>}
    </div>
  </Card>;
}
