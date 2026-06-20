const isLocalDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

export const API_URL = import.meta.env.VITE_API_URL || (isLocalDev ? 'http://localhost:8000' : '');

// Fetch with timeout - prevents requests from hanging indefinitely.
export function fetchWithTimeout(url: string, options: RequestInit = {}, timeoutMs = 30000): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, { ...options, signal: controller.signal }).finally(() => clearTimeout(timer));
}
