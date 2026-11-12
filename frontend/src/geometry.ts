import type { Rect, Zone } from './types';
export type Point = { x: number; y: number };
export type Bounds = { left: number; top: number; width: number; height: number };
const clamp = (value: number) => Math.min(1, Math.max(0, value));

export function normalizedPoint(x: number, y: number, bounds: Bounds): Point {
  return { x: clamp((x - bounds.left) / Math.max(1, bounds.width)), y: clamp((y - bounds.top) / Math.max(1, bounds.height)) };
}

export function rectangle(a: Point, b: Point): Rect | null {
  const rect = { x1: clamp(Math.min(a.x, b.x)), y1: clamp(Math.min(a.y, b.y)), x2: clamp(Math.max(a.x, b.x)), y2: clamp(Math.max(a.y, b.y)) };
  return rect.x2 - rect.x1 >= 0.005 && rect.y2 - rect.y1 >= 0.005 ? rect : null;
}

export function zoneAt(point: Point, zones: Zone[]) {
  return zones.filter(({ rect: r }) => point.x >= r.x1 && point.x <= r.x2 && point.y >= r.y1 && point.y <= r.y2)
    .sort((a, b) => (a.rect.x2 - a.rect.x1) * (a.rect.y2 - a.rect.y1) - (b.rect.x2 - b.rect.x1) * (b.rect.y2 - b.rect.y1))[0];
}

export const formatTime = (seconds: number) => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
export const formatDate = (value: string) => new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Bangkok', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(new Date(value));
