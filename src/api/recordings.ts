import { API_URL, fetchWithTimeout } from './http';
import type { Segment } from './transcription';

export interface JPRRecording {
  filename: string;
  path: string;
  date: string;
  date_folder?: string;
  size_bytes: number;
  status: string;
  effective_status?: string;
  job_id?: string | null;
  transcript_exists: boolean;
  transcript_preview?: string | null;
  speakers?: string[];
  submitted_at?: string | null;
  completed_at?: string | null;
  error?: string | null;
  transcript_path?: string | null;
  source?: 'jpr' | 'upload' | 'youtube';
}

export interface JPRListParams {
  limit?: number;
  offset?: number;
  status?: 'all' | 'unprocessed' | 'processed' | 'processing' | 'failed';
  sort_by?: 'date' | 'completed_at';
  sort_dir?: 'asc' | 'desc';
  q?: string;
}

export interface JPRTranscript {
  path: string;
  filename: string;
  transcript_text: string | null;
  segments: Segment[];
  speakers: string[];
  language: string | null;
  job_id: string | null;
  status: string | null;
}

function recordingParams(params: JPRListParams): URLSearchParams {
  const qs = new URLSearchParams();
  qs.set('limit', String(params.limit ?? 50));
  qs.set('offset', String(params.offset ?? 0));
  if (params.status) qs.set('status', params.status);
  if (params.sort_by) qs.set('sort_by', params.sort_by);
  if (params.sort_dir) qs.set('sort_dir', params.sort_dir);
  if (params.q && params.q.trim()) qs.set('q', params.q.trim());
  return qs;
}

async function fetchJPRRecordings(params: JPRListParams = {}): Promise<{
  recordings: JPRRecording[];
  total: number;
  watcher_status?: { available: boolean; completed?: number; pending?: number; failed?: number };
}> {
  const response = await fetchWithTimeout(`${API_URL}/jpr/recordings?${recordingParams(params)}`);
  if (!response.ok) throw new Error('Failed to fetch recordings');
  return response.json();
}

export async function fetchRecordings(params: JPRListParams = {}): Promise<{
  recordings: JPRRecording[];
  total: number;
  watcher_status?: { available: boolean; completed?: number; pending?: number; failed?: number };
}> {
  const response = await fetchWithTimeout(`${API_URL}/recordings?${recordingParams(params)}`);
  if (!response.ok) throw new Error('Failed to fetch recordings');
  return response.json();
}

export async function fetchJPRTranscript(path: string): Promise<JPRTranscript> {
  const url = `${API_URL}/jpr/recordings/${encodeURI(path)}/transcript`;
  const response = await fetchWithTimeout(url);
  if (!response.ok) throw new Error('Failed to fetch transcript');
  return response.json();
}

export async function renameJPRRecording(path: string, newName: string): Promise<{ status: string; old_path: string; new_path: string }> {
  const url = `${API_URL}/jpr/recordings/${encodeURI(path)}/rename`;
  const response = await fetchWithTimeout(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ new_name: newName }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Rename failed' }));
    throw new Error(err.detail || 'Rename failed');
  }
  return response.json();
}

export interface RenameSourceResponse {
  status: string;
  old_name: string;
  new_name: string;
}

export async function renameJobSource(jobId: string, newName: string): Promise<RenameSourceResponse> {
  const r = await fetchWithTimeout(`${API_URL}/jpr/job/${jobId}/rename`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ new_name: newName }),
  });
  if (!r.ok) {
    const detail = await r.text();
    throw new Error(`renameJobSource failed: ${r.status} ${detail.slice(0, 120)}`);
  }
  return r.json();
}
