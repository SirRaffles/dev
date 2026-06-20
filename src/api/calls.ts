import { API_URL, fetchWithTimeout } from './http';

export interface CallMetadata {
  job_id: string;
  title?: string;
  context_path?: string;
  call_folder_path?: string;
  speakers_identified: number;
  context_assigned: number;
  deliverables_generated: number;
  deliverables_generated_at?: string;
  source_type: string;
  source_path?: string;
  created_at: string;
  speakers?: CallSpeaker[];
  speaker_identifications?: CallSpeaker[];
  readiness?: { ready: boolean; missing: string[] };
}

export interface CallSpeaker {
  call_id: string;
  speaker_id: string;
  speaker_label?: string;
  confidence: number;
  confirmed: number;
  name?: string;
}

interface RegisterCallResponse {
  job_id: string;
  status: string;
}

export interface IdentifySpeakersResponse {
  identifications: CallSpeaker[];
  all_matched: boolean;
}

export interface ConfirmSpeakerResponse {
  status: string;
  speaker_id: string;
  confirmed: boolean;
}

export interface GenerateDeliverablesResponse {
  status: string;
  job_id: string;
}

export interface DeliverablesResponse {
  generated: boolean;
  generated_at?: string;
  summary_md?: string;
  analysis_md?: string;
  call_folder?: string;
}

export async function fetchCalls(limit = 50, offset = 0, status?: string): Promise<{ calls: CallMetadata[]; total: number }> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (status) params.append('status', status);
  const response = await fetchWithTimeout(`${API_URL}/calls?${params}`);
  if (!response.ok) throw new Error('Failed to fetch calls');
  return response.json();
}

export async function fetchCall(jobId: string): Promise<CallMetadata> {
  const response = await fetchWithTimeout(`${API_URL}/calls/${jobId}`);
  if (!response.ok) throw new Error('Failed to fetch call');
  return response.json();
}

async function registerCall(jobId: string, sourceType = 'upload', sourcePath?: string): Promise<RegisterCallResponse> {
  const response = await fetchWithTimeout(`${API_URL}/calls/${jobId}/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_type: sourceType, source_path: sourcePath }),
  });
  if (!response.ok) throw new Error('Failed to register call');
  return response.json();
}

export async function identifySpeakers(jobId: string): Promise<IdentifySpeakersResponse> {
  const response = await fetchWithTimeout(`${API_URL}/calls/${jobId}/identify-speakers`, {
    method: 'POST',
  });
  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.detail || 'Failed to identify speakers');
  }
  return response.json();
}

export async function confirmSpeaker(
  jobId: string,
  speakerLabel: string,
  speakerName: string,
  createNew = false,
): Promise<ConfirmSpeakerResponse> {
  const response = await fetchWithTimeout(`${API_URL}/calls/${jobId}/confirm-speaker`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ speaker_label: speakerLabel, speaker_name: speakerName, create_new: createNew }),
  });
  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.detail || 'Failed to confirm speaker');
  }
  return response.json();
}

export async function setCallTitle(jobId: string, title: string): Promise<void> {
  const response = await fetchWithTimeout(`${API_URL}/calls/${jobId}/title`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  if (!response.ok) throw new Error('Failed to set title');
}

export async function assignContext(jobId: string, contextPath: string): Promise<void> {
  const response = await fetchWithTimeout(`${API_URL}/calls/${jobId}/context`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ context_path: contextPath }),
  });
  if (!response.ok) throw new Error('Failed to assign context');
}

export async function generateDeliverables(jobId: string): Promise<GenerateDeliverablesResponse> {
  const response = await fetchWithTimeout(`${API_URL}/calls/${jobId}/generate-deliverables`, {
    method: 'POST',
  });
  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.detail || 'Failed to generate deliverables');
  }
  return response.json();
}

export async function fetchDeliverables(jobId: string): Promise<DeliverablesResponse> {
  const response = await fetchWithTimeout(`${API_URL}/calls/${jobId}/deliverables`);
  if (!response.ok) throw new Error('Failed to fetch deliverables');
  return response.json();
}
