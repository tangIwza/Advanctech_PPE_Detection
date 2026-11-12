import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useStream } from './useStream';
import type { Alert, Packet } from './types';

vi.mock('./api', () => ({ websocketUrl: () => 'ws://localhost/ws/stream' }));

class Socket {
  static instances: Socket[] = [];
  onopen?: () => void;
  onmessage?: (event: { data: string | Blob }) => void;
  onclose?: (event: { code: number }) => void;
  onerror?: () => void;
  constructor() { Socket.instances.push(this); }
  close() { this.onclose?.({ code: 1000 }); }
  sendPacket(value: Packet) { this.onmessage?.({ data: JSON.stringify(value) }); }
  sendImage() { this.onmessage?.({ data: new Blob(['jpeg']) }); }
}
class DeferredImage {
  static instances: DeferredImage[] = [];
  onload?: () => void;
  onerror?: () => void;
  src = '';
  constructor() { DeferredImage.instances.push(this); }
}
const packet = (sequence: number, alerts: Alert[] = [], has_frame = true) =>
  ({ type: 'frame', sequence, has_frame, alerts } as Packet);

describe('stream frame pairing and reconnect', () => {
  beforeEach(() => {
    vi.useFakeTimers(); Socket.instances = []; DeferredImage.instances = [];
    vi.stubGlobal('WebSocket', Socket); vi.stubGlobal('Image', DeferredImage);
    let id = 0;
    vi.stubGlobal('URL', { createObjectURL: vi.fn(() => `blob:${++id}`), revokeObjectURL: vi.fn() });
  });
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

  it('shows only the decoded image that matches the latest metadata', () => {
    const { result, unmount } = renderHook(() => useStream('', vi.fn()));
    const socket = Socket.instances[0];
    act(() => { socket.sendPacket(packet(1)); socket.sendImage(); socket.sendPacket(packet(2)); socket.sendImage(); });
    act(() => DeferredImage.instances[0].onload?.());
    expect(result.current.frame).toBeNull();
    act(() => DeferredImage.instances[1].onload?.());
    expect(result.current.frame?.packet.sequence).toBe(2);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:1');
    unmount();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:2');
  });

  it('rejects an old connection image when the backend sequence restarts', () => {
    const { result, unmount } = renderHook(() => useStream('', vi.fn()));
    const old = Socket.instances[0];
    act(() => { old.sendPacket(packet(999)); old.sendImage(); old.close(); vi.advanceTimersByTime(1000); });
    const next = Socket.instances[1];
    act(() => { next.onopen?.(); next.sendPacket(packet(1)); next.sendImage(); DeferredImage.instances[1].onload?.(); });
    expect(result.current.frame?.packet.sequence).toBe(1);
    act(() => DeferredImage.instances[0].onload?.());
    expect(result.current.frame?.packet.sequence).toBe(1);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:1');
    unmount();
  });

  it('notifies once for new alerts and keeps historical alerts silent', () => {
    const notify = vi.fn();
    const { unmount } = renderHook(() => useStream('', notify));
    const old = { id: 'old' } as Alert, fresh = { id: 'new' } as Alert;
    act(() => Socket.instances[0].sendPacket(packet(1, [old], false)));
    expect(notify).not.toHaveBeenCalled();
    act(() => Socket.instances[0].sendPacket(packet(2, [fresh, old], false)));
    act(() => Socket.instances[0].sendPacket(packet(3, [fresh, old], false)));
    expect(notify).toHaveBeenCalledExactlyOnceWith([fresh]);
    unmount();
  });

  it('does not connect with a malformed token', () => {
    const { result, unmount } = renderHook(() => useStream('bad token!', vi.fn()));
    expect(result.current.connection).toBe('unauthorized');
    expect(Socket.instances).toHaveLength(0);
    unmount();
  });
});
