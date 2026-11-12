import { fireEvent, render, screen, waitFor, cleanup } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ZoneEditor from './ZoneEditor';
import type { ClassInfo } from '../types';

afterEach(cleanup);
const classes: ClassInfo[] = [
  { id: 0, name: 'person', kind: 'person', color: '#123' },
  { id: 3, name: 'foot', kind: 'body_part', color: '#123' },
  { id: 6, name: 'helmet', kind: 'ppe', color: '#123' },
  { id: 9, name: 'safety-vest', kind: 'ppe', color: '#123' }
];
const props = { sourceId: 'source', rect: { x1: .1234, y1: .2, x2: .9, y2: .9 }, classes, onClose: vi.fn() };

describe('dynamic zone PPE selection', () => {
  it('offers only wearable PPE with the actual model IDs', async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    render(<ZoneEditor {...props} onSave={save} />);
    expect(screen.getByRole('checkbox', { name: 'helmet' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'safety-vest' })).toBeChecked();
    expect(screen.queryByRole('checkbox', { name: 'foot' })).not.toBeInTheDocument();
    expect(screen.queryByRole('checkbox', { name: 'person' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Save zone' }));
    await waitFor(() => expect(save).toHaveBeenCalledOnce());
    expect(save.mock.calls[0][0].required_class_ids).toEqual([6, 9]);
    expect(save.mock.calls[0][0].rect.x1).toBe(.1234);
  });
  it('clears PPE requirements in restricted-zone submissions', async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    render(<ZoneEditor {...props} onSave={save} />);
    fireEvent.click(screen.getByRole('button', { name: /Restricted \/ no entry/ }));
    expect(screen.queryByRole('checkbox', { name: 'helmet' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Save zone' }));
    await waitFor(() => expect(save).toHaveBeenCalledOnce());
    expect(save.mock.calls[0][0].kind).toBe('restricted');
    expect(save.mock.calls[0][0].required_class_ids).toEqual([]);
  });
  it('blocks empty PPE rules before sending them', async () => {
    const save = vi.fn();
    render(<ZoneEditor {...props} onSave={save} />);
    fireEvent.click(screen.getByRole('checkbox', { name: 'helmet' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'safety-vest' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save zone' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Select at least one');
    expect(save).not.toHaveBeenCalled();
  });
  it('preserves polygon points and recalculates bounds after editing a point', async () => {
    const save=vi.fn().mockResolvedValue(undefined);
    const points=[{x:.1,y:.1},{x:.9,y:.1},{x:.1,y:.9}];
    render(<ZoneEditor {...props} shape="polygon" points={points} onSave={save} />);
    expect(screen.queryByRole('spinbutton',{name:'x1'})).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole('spinbutton',{name:'Point 2 x'}),{target:{value:'.8'}});
    fireEvent.click(screen.getByRole('button',{name:'Save zone'}));
    await waitFor(()=>expect(save).toHaveBeenCalledOnce());
    expect(save.mock.calls[0][0].shape).toBe('polygon');
    expect(save.mock.calls[0][0].points[1]).toEqual({x:.8,y:.1});
    expect(save.mock.calls[0][0].rect).toEqual({x1:.1,y1:.1,x2:.8,y2:.9});
  });
  it('blocks a self-intersecting polygon before sending rules', async () => {
    const save=vi.fn();
    const points=[{x:0,y:0},{x:1,y:1},{x:0,y:1},{x:1,y:0}];
    render(<ZoneEditor {...props} shape="polygon" points={points} onSave={save} />);
    fireEvent.click(screen.getByRole('button',{name:'Save zone'}));
    expect(await screen.findByRole('alert')).toHaveTextContent('cannot cross');
    expect(save).not.toHaveBeenCalled();
  });
});
