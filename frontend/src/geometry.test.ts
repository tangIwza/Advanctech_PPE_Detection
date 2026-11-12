import { describe, expect, it } from 'vitest';
import { normalizedPoint, pointInPolygon, polygonArea, polygonBounds, polygonError, rectangle, zoneAt } from './geometry';
import type { Zone } from './types';

describe('normalized ROI coordinates', () => {
  it('keeps the same rectangle across display resolutions', () => {
    const small = normalizedPoint(330, 200, { left: 10, top: 20, width: 640, height: 360 });
    const large = normalizedPoint(660, 400, { left: 20, top: 40, width: 1280, height: 720 });
    expect(small).toEqual({ x: .5, y: .5 });
    expect(large).toEqual(small);
  });
  it('supports reverse drags and clamps to the displayed frame', () => {
    expect(rectangle({ x: .8, y: .9 }, { x: -.1, y: .2 })).toEqual({ x1: 0, y1: .2, x2: .8, y2: .9 });
    expect(normalizedPoint(5000, -20, { left: 0, top: 0, width: 640, height: 360 })).toEqual({ x: 1, y: 0 });
  });
  it('discards clicks and negligible rectangles', () => {
    expect(rectangle({ x: .1, y: .1 }, { x: .101, y: .8 })).toBeNull();
  });
  it('selects the smallest overlapping zone', () => {
    const base = { name: 'Test', source_id: 'source', kind: 'ppe', anchor: 'feet', enabled: true, required_class_ids: [6], version: 1, updated_at: '' } as const;
    const zones = [{ ...base, id: 'large', rect: { x1: 0, y1: 0, x2: 1, y2: 1 }, required_class_ids: [6] }, { ...base, id: 'small', rect: { x1: .2, y1: .2, x2: .4, y2: .4 }, required_class_ids: [6] }] as Zone[];
    expect(zoneAt({ x: .3, y: .3 }, zones)?.id).toBe('small');
  });
});

describe('polygon geometry', () => {
  const points=[{x:.1,y:.1},{x:.9,y:.1},{x:.9,y:.4},{x:.4,y:.4},{x:.4,y:.9},{x:.1,y:.9}];
  it('supports concave polygons, either winding and inclusive boundaries', () => {
    for (const vertices of [points,[...points].reverse()]) {
      expect(pointInPolygon({x:.25,y:.8},vertices)).toBe(true);
      expect(pointInPolygon({x:.75,y:.8},vertices)).toBe(false);
      expect(pointInPolygon({x:.1,y:.5},vertices)).toBe(true);
      expect(pointInPolygon(points[0],vertices)).toBe(true);
    }
    expect(polygonError(points)).toBeNull();
    expect(polygonBounds(points)).toEqual({x1:.1,y1:.1,x2:.9,y2:.9});
    expect(polygonArea(points)).toBeCloseTo(.39);
  });
  it('rejects crossing, repeated, collinear and out-of-frame vertices', () => {
    expect(polygonError([{x:0,y:0},{x:1,y:1},{x:0,y:1},{x:1,y:0}])).toMatch(/cross/);
    expect(polygonError([...points,points[0]])).toMatch(/distinct/);
    expect(polygonError([{x:0,y:0},{x:.5,y:.5},{x:1,y:1}])).toMatch(/straight line/);
    expect(polygonError([{x:-.1,y:0},{x:1,y:0},{x:1,y:1}])).toMatch(/within/);
    expect(polygonError([{x:NaN,y:0},{x:1,y:0},{x:1,y:1}])).toMatch(/within/);
  });
  it('hit-tests the actual outline instead of the bounding box', () => {
    const zone={id:'polygon',shape:'polygon',points,rect:polygonBounds(points)} as Zone;
    expect(zoneAt({x:.25,y:.8},[zone])?.id).toBe('polygon');
    expect(zoneAt({x:.75,y:.8},[zone])).toBeUndefined();
  });
});
