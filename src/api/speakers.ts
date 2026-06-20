import { API_URL, fetchWithTimeout } from './http';
import type { CallSpeaker } from './calls';
import type { Segment } from './transcription';

export interface Speaker {
  speaker_id: string;
  name: string;
  folder_path: string;
  embedding_path?: string;
  call_count: number;
  total_speaking_time_seconds: number;
  created_at: string;
}

export interface SpeakerDetail extends Speaker {
  profile_md?: string;
  explicit_insights_md?: string;
  implicit_insights_md?: string;
  personality_md?: string;
  has_embedding?: boolean;
  calls?: CallSpeaker[];
}

export async function fetchSpeakers(): Promise<Speaker[]> {
  const response = await fetchWithTimeout(`${API_URL}/speakers`);
  if (!response.ok) throw new Error('Failed to fetch speakers');
  const data = await response.json();
  return data.speakers;
}

export async function fetchSpeaker(speakerId: string): Promise<SpeakerDetail> {
  const response = await fetchWithTimeout(`${API_URL}/speakers/${speakerId}`);
  if (!response.ok) throw new Error('Failed to fetch speaker');
  return response.json();
}

export async function createSpeaker(name: string): Promise<{ speaker_id: string; name: string }> {
  const response = await fetchWithTimeout(`${API_URL}/speakers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.detail || 'Failed to create speaker');
  }
  return response.json();
}

export async function deleteSpeaker(speakerId: string): Promise<void> {
  const response = await fetchWithTimeout(`${API_URL}/speakers/${speakerId}`, {
    method: 'DELETE',
  });
  if (!response.ok) throw new Error('Failed to delete speaker');
}

async function _putSpeakerSection(speakerId: string, section: string, content: string): Promise<void> {
  const response = await fetchWithTimeout(`${API_URL}/speakers/${speakerId}/${section}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: `Failed to update ${section}` }));
    throw new Error(err.detail || `Failed to update ${section}`);
  }
}

export const updateSpeakerProfile = (id: string, content: string) => _putSpeakerSection(id, 'profile', content);
export const updateSpeakerExplicit = (id: string, content: string) => _putSpeakerSection(id, 'explicit-insights', content);
export const updateSpeakerImplicit = (id: string, content: string) => _putSpeakerSection(id, 'implicit-insights', content);

async function updateSpeakerPersonality(speakerId: string, content: string): Promise<void> {
  const response = await fetchWithTimeout(`${API_URL}/speakers/${speakerId}/personality`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });
  if (!response.ok) throw new Error('Failed to update personality');
}

interface JobSpeakerLabel {
  label: string;
  total_seconds: number;
  segment_count: number;
  anonymous: boolean;
  matched_speaker_id: string | null;
  can_extract_embedding: boolean;
}

async function fetchJobSpeakerLabels(jobId: string): Promise<JobSpeakerLabel[]> {
  const response = await fetchWithTimeout(`${API_URL}/job/${jobId}/speakers/labels`);
  if (!response.ok) throw new Error('Failed to fetch speaker labels');
  const data = await response.json();
  return data.labels || [];
}

interface AutoMatchSuggestion {
  label: string;
  speaker_id: string | null;
  speaker_name: string | null;
  confidence: number;
  source: 'pick' | 'registry' | null;
  matched: boolean;
  total_seconds: number;
}

interface AutoMatchResponse {
  job_id: string;
  mode: 'scoped' | 'global-prefer' | 'global';
  suggestions: AutoMatchSuggestion[];
}

async function fetchJobAutoMatchSuggestions(jobId: string): Promise<AutoMatchResponse> {
  const response = await fetchWithTimeout(`${API_URL}/job/${jobId}/speakers/auto-match`, {
    method: 'POST',
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Auto-match failed' }));
    throw new Error(err.detail || 'Auto-match failed');
  }
  return response.json();
}

interface SpeakerAssignmentInput {
  label: string;
  speaker_name: string;
  create_new: boolean;
}

interface AssignSpeakersResponse {
  job_id: string;
  assignments: {
    label: string;
    speaker_id: string;
    speaker_name: string;
    created: boolean;
    embedding_saved: boolean;
    speaking_time_seconds: number;
  }[];
  insight_extraction_scheduled: boolean;
  segments: Segment[];
  speakers: string[];
}

async function assignJobSpeakers(
  jobId: string,
  assignments: SpeakerAssignmentInput[],
  extractInsights = true,
): Promise<AssignSpeakersResponse> {
  const response = await fetchWithTimeout(`${API_URL}/job/${jobId}/speakers/assign`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ assignments, extract_insights: extractInsights }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Assignment failed' }));
    throw new Error(err.detail || 'Assignment failed');
  }
  return response.json();
}

export async function extractJobSpeakerInsights(jobId: string): Promise<{
  updated: string[];
  skipped: { speaker: string; reason: string }[];
  errors: string[];
}> {
  const response = await fetchWithTimeout(`${API_URL}/job/${jobId}/speakers/extract-insights`, {
    method: 'POST',
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Insight extraction failed' }));
    throw new Error(err.detail || 'Insight extraction failed');
  }
  return response.json();
}
