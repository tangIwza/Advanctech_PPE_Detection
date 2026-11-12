import { StrictMode, Component, type ReactNode, type ErrorInfo } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './index.css';

class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error('Safety interface error', error, info.componentStack); }
  render() {
    return this.state.failed ? <div className="min-h-screen bg-slate-200 flex items-center justify-center p-6"><div className="bg-white rounded-xl shadow-sm border border-gray-100 p-8 max-w-md"><h1 className="text-xl font-bold text-gray-800">Unable to display monitoring</h1><p className="text-sm text-gray-500 mt-3">Reload the interface to reconnect. Monitoring on the backend continues independently.</p><button className="btn-primary mt-5" onClick={() => location.reload()}>Reload interface</button></div></div> : this.props.children;
  }
}

createRoot(document.getElementById('root')!).render(<StrictMode><ErrorBoundary><App /></ErrorBoundary></StrictMode>);
