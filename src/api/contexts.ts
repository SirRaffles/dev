import { API_URL, fetchWithTimeout } from './http';

export interface ContextFolder {
  name: string;
  path: string;
  description?: string;
  created_at?: string;
  has_insights: boolean;
  has_context: boolean;
}

export interface ContextFile {
  name: string;
  path: string;
  size_bytes: number;
  modified_at: number;
}

export interface ContextTree {
  name: string;
  path: string;
  children?: ContextTree[];
  files?: ContextFile[];
}

export async function fetchContextFolders(parentPath = ''): Promise<ContextFolder[]> {
  const params = parentPath ? `?path=${encodeURIComponent(parentPath)}` : '';
  const response = await fetchWithTimeout(`${API_URL}/contexts${params}`);
  if (!response.ok) throw new Error('Failed to fetch contexts');
  const data = await response.json();
  return data.folders;
}

export async function fetchContextTree(): Promise<ContextTree[]> {
  const response = await fetchWithTimeout(`${API_URL}/contexts/tree`);
  if (!response.ok) throw new Error('Failed to fetch context tree');
  const data = await response.json();
  return data.tree?.children || [];
}

export async function createContextFolder(path: string, description = ''): Promise<{ path: string; description: string }> {
  const response = await fetchWithTimeout(`${API_URL}/contexts/folders`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, description }),
  });
  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.detail || 'Failed to create context folder');
  }
  return response.json();
}

function _encodeContextPath(folder: string, filename?: string): string {
  const full = filename ? `${folder}/${filename}` : folder;
  return encodeURI(full);
}

export async function fetchContextFile(path: string, filename: string): Promise<string> {
  const response = await fetchWithTimeout(
    `${API_URL}/contexts/files/${_encodeContextPath(path, filename)}`,
  );
  if (!response.ok) throw new Error('Failed to fetch file');
  const data = await response.json();
  return data.content;
}

export async function updateContextFile(path: string, filename: string, content: string): Promise<void> {
  const response = await fetchWithTimeout(
    `${API_URL}/contexts/files/${_encodeContextPath(path, filename)}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    },
  );
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to update file' }));
    throw new Error(err.detail || 'Failed to update file');
  }
}

export async function deleteContextFile(path: string, filename: string): Promise<void> {
  const response = await fetchWithTimeout(
    `${API_URL}/contexts/files/${_encodeContextPath(path, filename)}`,
    { method: 'DELETE' },
  );
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to delete file' }));
    throw new Error(err.detail || 'Failed to delete file');
  }
}

export async function deleteContextFolder(path: string): Promise<void> {
  const response = await fetchWithTimeout(
    `${API_URL}/contexts/folders/${encodeURI(path)}`,
    { method: 'DELETE' },
  );
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to delete folder' }));
    throw new Error(err.detail || 'Failed to delete folder');
  }
}

export async function uploadContextFile(folderPath: string, file: File): Promise<string> {
  const ext = file.name.toLowerCase().match(/\.[^.]+$/)?.[0] || '';
  if (!['.md', '.txt'].includes(ext)) {
    throw new Error('Only .md and .txt files are supported');
  }
  if (file.size > 1_000_000) {
    throw new Error('File too large (max 1 MB)');
  }
  const text = await file.text();
  await updateContextFile(folderPath, file.name, text);
  return file.name;
}

export interface GlobalGlossaryDoc {
  content: string;
  exists: boolean;
  modified_at?: number;
}

export async function fetchGlobalGlossary(): Promise<GlobalGlossaryDoc> {
  const r = await fetchWithTimeout(`${API_URL}/contexts/_global`);
  if (!r.ok) throw new Error(`fetchGlobalGlossary failed: ${r.status}`);
  return r.json();
}

export async function saveGlobalGlossary(content: string): Promise<void> {
  const r = await fetchWithTimeout(`${API_URL}/contexts/_global`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });
  if (!r.ok) throw new Error(`saveGlobalGlossary failed: ${r.status}`);
}
