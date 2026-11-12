import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import VideoCanvas from './VideoCanvas';
import type { DisplayFrame, Packet } from '../types';

const frame:DisplayFrame={url:'frame.jpg',packet:{width:640,height:360,state:'paused',violations:[],detections:[],source:null} as unknown as Packet};
const bounds={left:0,top:0,width:640,height:360,right:640,bottom:360,x:0,y:0,toJSON:()=>({})};
const initial={frame,zones:[],classes:[],drawing:true,drawingMode:'polygon' as const,selectedId:null,draft:null,onSelect:vi.fn(),onCancelDraw:vi.fn()};

beforeEach(()=>{
  vi.stubGlobal('ResizeObserver',class { observe() {} disconnect() {} });
  vi.stubGlobal('PointerEvent',MouseEvent);
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});

function canvas() {
  const element=screen.getByLabelText('Interactive detection zone canvas') as HTMLCanvasElement;
  vi.spyOn(element,'getBoundingClientRect').mockReturnValue(bounds);
  element.setPointerCapture=vi.fn();
  element.hasPointerCapture=()=>true;
  element.releasePointerCapture=vi.fn();
  return element;
}
const click=(element:HTMLElement,x:number,y:number)=>fireEvent.pointerDown(element,{button:0,clientX:x,clientY:y,pointerId:1});

describe('interactive drawing modes',()=>{
  it('closes a polygon by clicking the first point without adding a duplicate',()=>{
    const complete=vi.fn();
    render(<VideoCanvas {...initial} onComplete={complete} />);
    const element=canvas();
    click(element,64,36);click(element,576,36);click(element,320,324);
    expect(screen.getByText('Polygon / Pen · 3/64 points')).toBeInTheDocument();
    click(element,65,37);
    expect(complete).toHaveBeenCalledExactlyOnceWith({shape:'polygon',rect:{x1:.1,y1:.1,x2:.9,y2:.9},points:[{x:.1,y:.1},{x:.9,y:.1},{x:.5,y:.9}]});
  });
  it('supports button and keyboard undo and Enter to finish',()=>{
    const complete=vi.fn();
    render(<VideoCanvas {...initial} onComplete={complete} />);
    const element=canvas();
    click(element,64,36);click(element,576,36);click(element,320,324);
    fireEvent.click(screen.getByRole('button',{name:'Undo last point'}));
    expect(screen.getByRole('button',{name:'Finish polygon'})).toBeDisabled();
    fireEvent.keyDown(window,{key:'Backspace'});
    expect(screen.getByText('Polygon / Pen · 1/64 points')).toBeInTheDocument();
    click(element,576,36);click(element,320,324);
    fireEvent.keyDown(window,{key:'Enter'});
    expect(complete).toHaveBeenCalledOnce();
  });
  it('rejects crossing edges and lets the user cancel without saving',()=>{
    const complete=vi.fn(),cancel=vi.fn();
    render(<VideoCanvas {...initial} onComplete={complete} onCancelDraw={cancel} />);
    const element=canvas();
    click(element,64,36);click(element,576,324);click(element,64,324);click(element,576,36);
    fireEvent.click(screen.getByRole('button',{name:'Finish polygon'}));
    expect(screen.getByRole('alert')).toHaveTextContent('cannot cross');
    expect(complete).not.toHaveBeenCalled();
    fireEvent.keyDown(window,{key:'Escape'});
    expect(cancel).toHaveBeenCalledOnce();
  });
  it('clears unfinished points when changing drawing modes',()=>{
    const complete=vi.fn();
    const {rerender}=render(<VideoCanvas {...initial} onComplete={complete} />);
    click(canvas(),64,36);
    rerender(<VideoCanvas {...initial} drawingMode="rectangle" onComplete={complete} />);
    rerender(<VideoCanvas {...initial} onComplete={complete} />);
    expect(screen.getByText('Polygon / Pen · 0/64 points')).toBeInTheDocument();
    expect(complete).not.toHaveBeenCalled();
  });
  it('keeps reverse-drag rectangle drawing available',()=>{
    const complete=vi.fn();
    render(<VideoCanvas {...initial} drawingMode="rectangle" onComplete={complete} />);
    const element=canvas();
    click(element,576,324);
    fireEvent.pointerMove(element,{clientX:64,clientY:36});
    fireEvent.pointerUp(element,{button:0,clientX:64,clientY:36,pointerId:1});
    expect(complete).toHaveBeenCalledExactlyOnceWith({shape:'rectangle',rect:{x1:.1,y1:.1,x2:.9,y2:.9},points:null});
  });
});
