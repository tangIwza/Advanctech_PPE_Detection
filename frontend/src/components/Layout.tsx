import { useState, type ReactNode } from 'react';
import { Activity, Bell, ChevronDown, ChevronRight, Cpu, Menu, Moon, PanelLeftClose, PanelLeftOpen, Settings, ShieldCheck, Square, Sun, X } from 'lucide-react';
import type { ModelInfo, Page } from '../types';

const titles: Record<Page, [string, string]> = {
  monitor: ['Safety Monitoring', 'Live Monitoring'], zones: ['Safety Rules', 'Detection Zones'],
  alerts: ['Event Management', 'Alert History'], model: ['System', 'AI Model'], settings: ['System', 'Settings']
};
const groups = [
  { name: 'Safety Monitoring', items: [{ page: 'monitor' as Page, name: 'Live Monitoring', icon: Activity }] },
  { name: 'Safety Rules', items: [{ page: 'zones' as Page, name: 'Detection Zones', icon: Square }] },
  { name: 'Event Management', items: [{ page: 'alerts' as Page, name: 'Alert History', icon: Bell }] },
  { name: 'System', items: [{ page: 'model' as Page, name: 'AI Model', icon: Cpu }, { page: 'settings' as Page, name: 'Settings', icon: Settings }] }
];

export default function Layout({ page, onNavigate, dark, onTheme, connected, model, unacknowledged, children }: {
  page: Page; onNavigate: (page: Page) => void; dark: boolean; onTheme: () => void;
  connected: boolean; model: ModelInfo | null; unacknowledged: number; children: ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({ 'Safety Monitoring': true, 'Safety Rules': true, 'Event Management': true, System: true });
  const navigate = (value: Page) => { onNavigate(value); setMobile(false); };
  return <div className={`flex h-screen bg-slate-200 overflow-hidden relative ${dark ? 'dark' : ''}`}>
    {mobile && <button aria-label="Close navigation" className="fixed inset-0 bg-slate-900/50 z-40 lg:hidden" onClick={() => setMobile(false)} />}
    <aside style={{ minWidth: collapsed ? '4rem' : '15rem' }} className={`${collapsed ? 'w-16' : 'w-60'} bg-white dark:bg-slate-900 border-r border-gray-200 dark:border-slate-700/60 min-h-screen flex-col select-none shrink-0 transition-all duration-300 z-50 fixed inset-y-0 left-0 lg:static lg:translate-x-0 ${mobile ? 'flex translate-x-0' : 'hidden lg:flex -translate-x-full'}`}>
      <div className="border-b border-gray-200 flex flex-col items-center justify-center px-4 py-4 gap-2"><div className="flex items-center gap-2"><img src="/images/aics-helmet.svg" alt="AiCS PPE helmet" className="h-10 w-10 object-contain shrink-0" />{!collapsed && <span className="text-[38px] font-black leading-10 tracking-[-0.06em] text-black dark:text-white" style={{fontFamily:"Arial Black, Arial, sans-serif"}}>AiCS</span>}</div>{!collapsed && <span className="text-[9px] font-semibold tracking-[0.19em] text-gray-400 uppercase">Smart Safety & PPE</span>}</div>
      <button className="flex items-center gap-2 mx-2 mt-2 px-3 py-2 rounded-lg text-gray-500 hover:text-gray-800 hover:bg-gray-100 transition-colors text-xs" onClick={() => setCollapsed(!collapsed)} aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}>{collapsed ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}{!collapsed && 'Collapse'}</button>
      <nav className="flex-1 py-1 px-2 overflow-y-auto modern-scrollbar">{groups.map(group => <div key={group.name} className="mb-1"><button title={collapsed ? group.name : undefined} className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-semibold text-gray-500 uppercase tracking-wider hover:text-gray-700 ${collapsed ? 'justify-center opacity-40' : ''}`} onClick={() => setExpanded({ ...expanded, [group.name]: !expanded[group.name] })}>{collapsed ? <span className="mx-auto text-[9px]">•••</span> : <><span>{group.name}</span>{expanded[group.name] ? <ChevronDown size={13} /> : <ChevronRight size={13} />}</>}</button>{(collapsed || expanded[group.name]) && <div className={`${collapsed ? '' : 'ml-2 mt-0.5'} space-y-0.5`}>{group.items.map(item => <button key={item.page} title={item.name} aria-current={page === item.page ? 'page' : undefined} onClick={() => navigate(item.page)} className={`w-full flex items-center ${collapsed ? 'justify-center p-2.5' : 'gap-2.5 px-3 py-2'} rounded-lg text-sm transition-colors whitespace-nowrap ${page === item.page ? 'bg-blue-900 text-white font-medium dark:bg-blue-900/20 dark:text-blue-400' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800 dark:text-slate-400 dark:hover:bg-slate-800'}`}><item.icon size={16} />{!collapsed && item.name}</button>)}</div>}</div>)}</nav>
      <div className={`border-t border-gray-100 ${collapsed ? 'p-3' : 'p-4'}`}>{collapsed ? <ShieldCheck size={19} className={connected ? 'text-emerald-600' : 'text-gray-400'} /> : <><div className="flex items-center gap-2 mb-2"><span className={`h-1.5 w-1.5 rounded-full ${connected ? 'bg-emerald-500' : 'bg-gray-400'}`} /><span className="text-[10px] font-semibold text-gray-600 uppercase tracking-wider">{connected ? 'AI model ready' : 'Backend offline'}</span></div><p className="text-xs text-gray-800 font-semibold truncate">{model?.model_name || 'Waiting for backend'}</p><p className="text-[10px] text-gray-400 mt-1">{model ? `${model.class_count} classes · ${(model.device.startsWith('cuda') ? 'GPU · '+model.device.toUpperCase() : model.device.toUpperCase())}` : 'Connect to start monitoring'}</p></>}</div>
    </aside>
    <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
      <header className={`${dark ? 'bg-[#0b1520] border-slate-700/60' : 'bg-white border-gray-200'} border-b px-4 sm:px-6 py-3.5 flex items-center justify-between shrink-0 gap-3`}>
        <button aria-label="Open navigation" onClick={() => setMobile(true)} className="lg:hidden icon-button"><Menu size={20} /></button>
        <div className="flex-1 min-w-0 flex items-baseline gap-2 truncate whitespace-nowrap"><span className="text-sm text-gray-500 hidden md:inline">{titles[page][0]} /</span><h1 className="text-lg sm:text-xl font-bold text-gray-800">{titles[page][1]}</h1></div>
        <div className="flex items-center gap-2 sm:gap-3 shrink-0"><div className="hidden sm:flex items-center gap-2.5"><div className="w-8 h-8 rounded-full bg-slate-600 flex items-center justify-center text-xs font-medium text-white">OP</div><div className="text-right"><p className="text-xs font-semibold text-gray-800 leading-tight">Safety Operator</p><p className="text-[10px] text-gray-400 leading-tight">Monitoring workspace</p></div></div><button className="icon-button" aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'} onClick={onTheme}>{dark ? <Sun size={17} /> : <Moon size={17} />}</button><button className="icon-button relative" aria-label="View alert history" onClick={() => navigate('alerts')}><Bell size={17} />{unacknowledged > 0 && <span className="absolute -top-1 -right-1 h-4 min-w-4 px-1 rounded-full bg-red-500 text-white text-[9px] leading-4 font-bold">{unacknowledged}</span>}</button></div>
      </header>
      <main className={`flex-1 overflow-y-auto modern-scrollbar ${dark ? 'bg-[#0b1520]' : 'bg-slate-200'}`}><div className="p-4 sm:p-6 space-y-6">{children}</div></main>
    </div>
  </div>;
}
