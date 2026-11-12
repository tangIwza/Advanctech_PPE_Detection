const base = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
export const tokenKey = 'smart-safety-token';
export const readToken = () => sessionStorage.getItem(tokenKey) || '';
export const setToken = (value: string) => value ? sessionStorage.setItem(tokenKey, value) : sessionStorage.removeItem(tokenKey);

type Options = Omit<RequestInit, 'body'> & { body?: unknown };

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

async function response(path: string, options: Options = {}) {
  const token = readToken();
  const headers = new Headers(options.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const form = options.body instanceof FormData;
  if (options.body !== undefined && !form) headers.set('Content-Type', 'application/json');
  const result = await fetch(`${base}${path}`, { ...options, headers, body: options.body === undefined ? undefined : form ? options.body as FormData : JSON.stringify(options.body) });
  if (!result.ok) {
    const data = await result.json().catch(() => ({}));
    const message = Array.isArray(data.detail) ? data.detail.map((item: { msg: string }) => item.msg).join('; ') : data.detail;
    throw new ApiError(message || `Request failed (${result.status})`, result.status);
  }
  return result;
}

export async function api<T>(path: string, options?: Options): Promise<T> {
  const result = await response(path, options);
  return result.status === 204 ? undefined as T : result.json();
}

export async function getBlob(path: string) { return (await response(path)).blob(); }

export function websocketUrl() {
  const url = new URL(base || window.location.origin);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  url.pathname = '/ws/stream';
  url.search = '';
  return url.toString();
}

export async function exportAlerts() {
  const url = URL.createObjectURL(await getBlob('/api/alerts/export'));
  const link = document.createElement('a');
  link.href = url; link.download = 'safety-alerts.csv'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
