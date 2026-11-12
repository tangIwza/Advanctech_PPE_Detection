import { useEffect, useRef, useState } from 'react';
import { websocketUrl } from './api';
import type { Alert, DisplayFrame, Packet } from './types';

export function useStream(token: string, onAlerts: (alerts: Alert[]) => void) {
  const [packet, setPacket] = useState<Packet | null>(null);
  const [frame, setFrame] = useState<DisplayFrame | null>(null);
  const [connection, setConnection] = useState<'connecting' | 'connected' | 'disconnected' | 'unauthorized'>('connecting');
  const notify = useRef(onAlerts);
  notify.current = onAlerts;
  const known = useRef(new Set<string>());
  const seeded = useRef(false);
  const currentUrl = useRef<string | null>(null);

  useEffect(() => {
    let disposed = false, retry: ReturnType<typeof setTimeout>, socket: WebSocket;
    let attempt = 0, generation = 0;
    setFrame(null); setPacket(null);
    const connect = () => {
      if (disposed) return;
      if (token && !/^[A-Za-z0-9_-]+$/.test(token)) { setConnection('unauthorized'); return; }
      const activeGeneration = ++generation;
      let pending: Packet | null = null, newest = -1;
      setConnection('connecting');
      const activeSocket = new WebSocket(websocketUrl(), token ? ['safety-stream', `bearer.${token}`] : ['safety-stream']);
      socket = activeSocket;
      activeSocket.onopen = () => { if (!disposed && activeGeneration === generation) { attempt = 0; setConnection('connected'); } };
      activeSocket.onmessage = event => {
        if (disposed || activeGeneration !== generation) return;
        if (typeof event.data === 'string') {
          const value = JSON.parse(event.data) as Packet | { type: 'heartbeat' };
          if (value.type !== 'frame') return;
          pending = value;
          newest = value.sequence;
          setPacket(value);
          const unseen = value.alerts.filter(alert => !known.current.has(alert.id));
          value.alerts.forEach(alert => known.current.add(alert.id));
          if (seeded.current && unseen.length) notify.current(unseen);
          seeded.current = true;
          if (known.current.size > 10000) known.current = new Set(value.alerts.map(alert => alert.id));
          if (!value.has_frame) {
            setFrame(null);
            if (currentUrl.current) URL.revokeObjectURL(currentUrl.current);
            currentUrl.current = null;
          }
          return;
        }
        const metadata = pending;
        pending = null;
        if (!metadata || !(event.data instanceof Blob)) return;
        const url = URL.createObjectURL(event.data);
        const image = new Image();
        image.onload = () => {
          if (disposed || activeGeneration !== generation || metadata.sequence !== newest) { URL.revokeObjectURL(url); return; }
          const old = currentUrl.current;
          currentUrl.current = url;
          setFrame({ url, packet: metadata });
          if (old) setTimeout(() => URL.revokeObjectURL(old), 250);
        };
        image.onerror = () => URL.revokeObjectURL(url);
        image.src = url;
      };
      activeSocket.onclose = event => {
        if (disposed || activeGeneration !== generation) return;
        ++generation;
        setFrame(null);
        if (currentUrl.current) URL.revokeObjectURL(currentUrl.current);
        currentUrl.current = null;
        if (event.code === 4401 || event.code === 4403) { setConnection('unauthorized'); return; }
        setConnection('disconnected');
        retry = setTimeout(connect, Math.min(15000, 1000 * 2 ** attempt++));
      };
      activeSocket.onerror = () => activeSocket.close();
    };
    connect();
    return () => {
      disposed = true; clearTimeout(retry); socket?.close();
      if (currentUrl.current) URL.revokeObjectURL(currentUrl.current);
      currentUrl.current = null;
    };
  }, [token]);
  return { packet, frame, connection };
}
