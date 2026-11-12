import type { Point, Rect, Zone } from './types';
export type { Point } from './types';
export type Bounds = { left: number; top: number; width: number; height: number };
const clamp = (value: number) => Math.min(1, Math.max(0, value));

export function normalizedPoint(x: number, y: number, bounds: Bounds): Point {
  return { x: clamp((x - bounds.left) / Math.max(1, bounds.width)), y: clamp((y - bounds.top) / Math.max(1, bounds.height)) };
}

export function rectangle(a: Point, b: Point): Rect | null {
  const rect = { x1: clamp(Math.min(a.x, b.x)), y1: clamp(Math.min(a.y, b.y)), x2: clamp(Math.max(a.x, b.x)), y2: clamp(Math.max(a.y, b.y)) };
  return rect.x2 - rect.x1 >= 0.005 && rect.y2 - rect.y1 >= 0.005 ? rect : null;
}

const epsilon = 1e-9;
const cross = (a: Point, b: Point, c: Point) => (b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);
const onSegment = (p: Point, a: Point, b: Point) => Math.abs(cross(a,b,p)) <= epsilon && p.x >= Math.min(a.x,b.x)-epsilon && p.x <= Math.max(a.x,b.x)+epsilon && p.y >= Math.min(a.y,b.y)-epsilon && p.y <= Math.max(a.y,b.y)+epsilon;

function intersects(a: Point, b: Point, c: Point, d: Point) {
  const ac=cross(a,b,c), ad=cross(a,b,d), ca=cross(c,d,a), cb=cross(c,d,b);
  return (((ac>epsilon && ad< -epsilon)||(ac< -epsilon && ad>epsilon)) && ((ca>epsilon && cb< -epsilon)||(ca< -epsilon && cb>epsilon))) || onSegment(c,a,b) || onSegment(d,a,b) || onSegment(a,c,d) || onSegment(b,c,d);
}

export function polygonArea(points: Point[]) {
  return Math.abs(points.reduce((sum,a,i) => { const b=points[(i+1)%points.length]; return sum+a.x*b.y-b.x*a.y; },0))/2;
}

export function polygonBounds(points: Point[]): Rect {
  return { x1: Math.min(...points.map(p=>p.x)), y1: Math.min(...points.map(p=>p.y)), x2: Math.max(...points.map(p=>p.x)), y2: Math.max(...points.map(p=>p.y)) };
}

export function polygonError(points: Point[]): string | null {
  if (points.length<3 || points.length>64) return 'Use between 3 and 64 points to define a polygon.';
  if (points.some(p=>!Number.isFinite(p.x)||!Number.isFinite(p.y)||p.x<0||p.x>1||p.y<0||p.y>1)) return 'All points must be within the video (0–1).';
  for (let i=0;i<points.length;i++) {
    if (points.slice(i+1).some(p=>Math.abs(p.x-points[i].x)<1e-7 && Math.abs(p.y-points[i].y)<1e-7)) return 'Each point must be distinct. Close the shape without repeating the first point.';
    for (let j=i+1;j<points.length;j++) {
      if (j===i+1 || i===0 && j===points.length-1) continue;
      if (intersects(points[i],points[(i+1)%points.length],points[j],points[(j+1)%points.length])) return 'Polygon edges cannot cross or touch. Undo a point and try again.';
    }
  }
  const bounds=polygonBounds(points);
  if (polygonArea(points)<0.000025 || bounds.x2-bounds.x1<0.005 || bounds.y2-bounds.y1<0.005) return 'Polygon is too small or its points form a straight line.';
  return null;
}

export function pointInPolygon(point: Point, points: Point[]) {
  let inside=false;
  for (let i=0;i<points.length;i++) {
    const a=points[i], b=points[(i+1)%points.length];
    if (onSegment(point,a,b)) return true;
    if ((a.y>point.y)!==(b.y>point.y) && point.x<(b.x-a.x)*(point.y-a.y)/(b.y-a.y)+a.x) inside=!inside;
  }
  return inside;
}

export function zoneAt(point: Point, zones: Zone[]) {
  const area = (zone: Zone) => zone.shape==='polygon' && zone.points ? polygonArea(zone.points) : (zone.rect.x2-zone.rect.x1)*(zone.rect.y2-zone.rect.y1);
  return zones.filter(zone => { const r=zone.rect; return point.x>=r.x1 && point.x<=r.x2 && point.y>=r.y1 && point.y<=r.y2 && (zone.shape!=='polygon' || !!zone.points && pointInPolygon(point,zone.points)); })
    .sort((a,b)=>area(a)-area(b))[0];
}

export const formatTime = (seconds: number) => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
export const formatDate = (value: string) => new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Bangkok', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(new Date(value));
