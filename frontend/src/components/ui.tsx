import { useEffect, useRef, type ReactNode } from 'react';
import { X } from 'lucide-react';

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`bg-white rounded-xl border border-gray-100 shadow-sm ${className}`}>{children}</section>;
}

export function Badge({ children, tone = 'slate' }: { children: ReactNode; tone?: 'slate' | 'blue' | 'green' | 'red' | 'amber' }) {
  const tones = { slate: 'bg-slate-100 text-slate-600 border-slate-200', blue: 'bg-blue-50 text-blue-800 border-blue-200', green: 'bg-emerald-50 text-emerald-700 border-emerald-200', red: 'bg-red-50 text-red-700 border-red-200', amber: 'bg-amber-50 text-amber-700 border-amber-200' };
  return <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold whitespace-nowrap ${tones[tone]}`}>{children}</span>;
}

export function Modal({ title, children, onClose, wide = false }: { title: string; children: ReactNode; onClose: () => void; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose); closeRef.current = onClose;
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    ref.current?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeRef.current();
      if (event.key !== 'Tab') return;
      const elements = Array.from(ref.current?.querySelectorAll<HTMLElement>('button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea,a[href],[tabindex="0"]') || []);
      if (!elements.length) { event.preventDefault(); return; }
      const first = elements[0], last = elements[elements.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === ref.current)) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener('keydown', handler);
    return () => { window.removeEventListener('keydown', handler); before?.focus(); };
  }, []);
  return <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
    <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
    <div ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="dialog-title" className={`relative bg-white rounded-xl shadow-xl w-full ${wide ? 'max-w-4xl' : 'max-w-xl'} max-h-[92vh] flex flex-col outline-none`}>
      <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100"><h2 id="dialog-title" className="text-base font-semibold text-gray-800">{title}</h2><button className="icon-button" aria-label="Close dialog" onClick={onClose}><X size={17} /></button></div>
      <div className="px-5 py-4 overflow-y-auto modern-scrollbar">{children}</div>
    </div>
  </div>;
}
