import { API_URL, fetchWithTimeout } from './http';

export interface WakeStatus {
  mac_state: string;
  model_loaded: boolean;
}

export type RefinementStatus = "pending" | "processing" | "done" | "failed" | null;
export type LearningStatus = "ok" | "partial" | "failed" | null;
export type RefinementMode = "auto" | "always" | "off";
export type SpeakerReviewStatus = "not_needed" | "needs_review" | "reviewed";

export interface LearningSummary {
  embeddings_updated: number;
  insights_added: number;
  terms_learned: number;
}

export interface AutoSpeakerMatch {
  name: string | null;
  confidence: number;
  speaker_id: string | null;
  matched: boolean;
  source?: "pick" | "registry" | null;
  note?: string;
  runner_up?: {
    speaker_id: string;
    name: string;
    confidence: number;
  } | null;
}

export interface JobStatus {
  job_id: string;
  status: string;
  progress?: number;
  result?: {
    text?: string;
    segments?: Segment[];
    language?: string;
    source?: string;
    is_generated?: boolean;
  };
  error?: string;
  filename?: string;
  created_at?: string;
  original_filename?: string;
  is_generated?: boolean;
  source?: string;
  refinement_status?: RefinementStatus;
  refinement_mode?: RefinementMode | null;
  refinement_reason?: string | null;
  auto_speaker_matches?: Record<string, AutoSpeakerMatch> | null;
  learning_summary?: LearningSummary | null;
  learning_status?: LearningStatus;
  phase?: string | null;
  speakers_resolved?: boolean;
  speaker_review_status?: SpeakerReviewStatus;
}

export async function fetchJobAutoRefineState(jobId: string): Promise<{
  refinement_status: RefinementStatus;
  refinement_mode: RefinementMode | null;
  refinement_reason: string | null;
  learning_status: LearningStatus;
  learning_summary: LearningSummary | null;
  auto_speaker_matches: Record<string, AutoSpeakerMatch> | null;
  phase: string | null;
  speakers_resolved: boolean;
  speaker_review_status: SpeakerReviewStatus;
}> {
  const res = await fetchWithTimeout(`${API_URL}/job/${jobId}`);
  if (!res.ok) throw new Error(`fetchJobAutoRefineState failed: ${res.status}`);
  const j = await res.json();
  return {
    refinement_status: j.refinement_status ?? null,
    refinement_mode: j.refinement_mode ?? null,
    refinement_reason: j.refinement_reason ?? null,
    learning_status: j.learning_status ?? null,
    learning_summary: j.learning_summary ?? null,
    auto_speaker_matches: j.auto_speaker_matches ?? null,
    phase: j.phase ?? null,
    speakers_resolved: j.speakers_resolved ?? true,
    speaker_review_status: j.speaker_review_status ?? (j.speakers_resolved === false ? "needs_review" : "not_needed"),
  };
}

export interface Segment {
  start: number;
  end: number;
  text: string;
  speaker?: string;
  paragraph_break?: boolean;
}

export interface BatchStatus {
  batch_id: string;
  status: string;
  jobs: JobStatus[];
  total: number;
  completed: number;
  failed: number;
  overall_status?: string;
  overall_progress?: number;
  job_ids?: string[];
}

export interface TranscriptionOptions {
  language?: string;
  enableDiarization?: boolean;
  enableNoiseReduction?: boolean;
  engine?: 'auto-best' | 'auto-quick';
  translateToEnglish?: boolean;
  numSpeakers?: number;
  contextPath?: string;
  speakerIds?: string[];
  refinementMode?: RefinementMode;
  autoRefine?: boolean | null;
}

export interface ExportFormatInfo {
  label: string;
  ext: string;
}

export async function checkWakeStatus(): Promise<WakeStatus | null> {
  try {
    const response = await fetchWithTimeout(`${API_URL}/api/wake-status`, {}, 10000);
    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
}

export const LANGUAGES: Record<string, string> = {
  auto: 'Auto-detect',
  en: 'English',
  fr: 'French (Français)',
  de: 'German (Deutsch)',
  es: 'Spanish (Español)',
  it: 'Italian (Italiano)',
  pt: 'Portuguese (Português)',
  nl: 'Dutch (Nederlands)',
  ru: 'Russian (Русский)',
  zh: 'Chinese (中文)',
  ja: 'Japanese (日本語)',
  ko: 'Korean (한국어)',
  ar: 'Arabic (العربية)',
  hi: 'Hindi (हिन्दी)',
  pl: 'Polish (Polski)',
};

export const EXPORT_FORMATS: Record<string, ExportFormatInfo> = {
  txt: { label: 'Plain Text', ext: '.txt' },
  md: { label: 'Markdown', ext: '.md' },
  srt: { label: 'SRT Subtitles', ext: '.srt' },
  vtt: { label: 'WebVTT Subtitles', ext: '.vtt' },
  pdf: { label: 'PDF Document', ext: '.pdf' },
  docx: { label: 'Word Document', ext: '.docx' },
  json: { label: 'JSON', ext: '.json' },
};

export const AUDIO_EXTENSIONS = ['mp3', 'wav', 'flac', 'ogg', 'm4a', 'aac'];
export const VIDEO_EXTENSIONS = ['mp4', 'mkv', 'avi', 'webm', 'mov'];
export const DOCUMENT_EXTENSIONS = ['pdf', 'pptx', 'ppt', 'docx'];

export function getFileType(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase() ?? '';

  if (AUDIO_EXTENSIONS.includes(ext)) return 'audio';
  if (VIDEO_EXTENSIONS.includes(ext)) return 'video';
  if (DOCUMENT_EXTENSIONS.includes(ext)) return 'document';

  return 'unknown';
}

export function getSourceType(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase() ?? '';

  if (AUDIO_EXTENSIONS.includes(ext)) return 'audio';
  if (VIDEO_EXTENSIONS.includes(ext)) return 'video';
  if (ext === 'pdf') return 'pdf';
  if (['pptx', 'ppt'].includes(ext)) return 'pptx';
  if (ext === 'docx') return 'docx';

  return 'unknown';
}

export function isDocumentFile(filename: string): boolean {
  return getFileType(filename) === 'document';
}

export function isMediaFile(filename: string): boolean {
  const type = getFileType(filename);
  return type === 'audio' || type === 'video';
}

function appendRefinementMode(params: URLSearchParams, options: TranscriptionOptions) {
  if (options.refinementMode) {
    params.append('refinement_mode', options.refinementMode);
  } else if (options.autoRefine !== undefined && options.autoRefine !== null) {
    params.append('auto_refine', String(options.autoRefine));
  }
}

export async function fetchJobStatus(jobId: string, isMultiModal = false): Promise<JobStatus> {
  const endpoint = isMultiModal
    ? `${API_URL}/process/job/${jobId}`
    : `${API_URL}/job/${jobId}`;

  const response = await fetchWithTimeout(endpoint);
  if (!response.ok) {
    throw new Error('Failed to fetch job status');
  }
  return response.json();
}

export async function submitTranscription(file: File, options: TranscriptionOptions = {}): Promise<{ job_id: string }> {
  const formData = new FormData();
  formData.append('file', file);

  const params = new URLSearchParams({
    language: options.language || 'auto',
    enable_diarization: String(options.enableDiarization ?? true),
    enable_noise_reduction: String(options.enableNoiseReduction ?? false),
    translate_to_english: String(options.translateToEnglish ?? false),
    engine: options.engine || 'auto-best',
  });

  if (options.numSpeakers) {
    params.append('num_speakers', String(options.numSpeakers));
  }

  if (options.contextPath) {
    params.append('context_path', options.contextPath);
  }

  if (options.speakerIds && options.speakerIds.length > 0) {
    params.append('speaker_ids', options.speakerIds.join(','));
  }
  appendRefinementMode(params, options);

  const response = await fetchWithTimeout(`${API_URL}/transcribe/file?${params}`, {
    method: 'POST',
    body: formData,
  }, 600000);

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Transcription request failed');
  }

  return response.json();
}

export async function submitMultiModalProcessing(file: File, options: TranscriptionOptions = {}): Promise<{ job_id: string }> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetchWithTimeout(`${API_URL}/process/multimodal`, {
    method: 'POST',
    body: formData,
  }, 600000);

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Processing request failed');
  }

  return response.json();
}

export async function submitYouTubeTranscription(url: string, options: TranscriptionOptions = {}): Promise<{ job_id: string; status?: string }> {
  const params = new URLSearchParams({
    engine: options.engine || 'auto-best',
  });

  if (options.numSpeakers) {
    params.append('num_speakers', String(options.numSpeakers));
  }

  if (options.contextPath) {
    params.append('context_path', options.contextPath);
  }

  if (options.speakerIds && options.speakerIds.length > 0) {
    params.append('speaker_ids', options.speakerIds.join(','));
  }
  appendRefinementMode(params, options);

  const response = await fetchWithTimeout(`${API_URL}/transcribe/youtube?${params}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      url,
      language: options.language || 'auto',
      enable_diarization: options.enableDiarization ?? true,
      enable_noise_reduction: options.enableNoiseReduction ?? false,
      translate_to_english: options.translateToEnglish ?? false,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'YouTube transcription request failed');
  }

  return response.json();
}

export async function cancelJob(jobId: string): Promise<void> {
  const res = await fetchWithTimeout(`${API_URL}/job/${jobId}`, { method: 'DELETE' });
  if (!res.ok && res.status !== 404) {
    throw new Error(`cancelJob failed: ${res.status}`);
  }
}

export async function exportTranscript(jobId: string, format: string, isMultiModal = false): Promise<Blob> {
  const endpoint = isMultiModal
    ? `${API_URL}/process/job/${jobId}/export?format=${format}`
    : `${API_URL}/job/${jobId}/export?format=${format}`;

  const response = await fetchWithTimeout(endpoint);

  if (!response.ok) {
    throw new Error('Export failed');
  }

  return response.blob();
}

export async function updateSegments(jobId: string, segments: Segment[]): Promise<{ status: string }> {
  const response = await fetchWithTimeout(`${API_URL}/job/${jobId}/segments`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ segments }),
  });

  if (!response.ok) {
    throw new Error('Failed to save edits');
  }

  return response.json();
}

async function updateSpeakers(jobId: string, speakerMapping: Record<string, string>): Promise<{ status: string; segments?: Segment[]; speakers?: string[] }> {
  const response = await fetchWithTimeout(`${API_URL}/job/${jobId}/speakers`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ speaker_mapping: speakerMapping }),
  });

  if (!response.ok) {
    throw new Error('Failed to rename speaker');
  }

  return response.json();
}

export async function fetchBatchStatus(batchId: string): Promise<BatchStatus> {
  const response = await fetchWithTimeout(`${API_URL}/batch/${batchId}`);

  if (!response.ok) {
    throw new Error('Failed to fetch batch status');
  }

  return response.json();
}

export async function retryJob(jobId: string): Promise<{ job_id: string; status: string; retried_from: string }> {
  const response = await fetchWithTimeout(`${API_URL}/job/${jobId}/retry`, {
    method: 'POST',
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Retry failed');
  }

  return response.json();
}

export async function submitBatchTranscription(files: File[], options: TranscriptionOptions = {}): Promise<{ batch_id: string; job_ids: string[] }> {
  const formData = new FormData();
  files.forEach(f => formData.append('files', f));

  const params = new URLSearchParams({
    language: options.language || 'auto',
    enable_diarization: String(options.enableDiarization ?? true),
    translate_to_english: String(options.translateToEnglish ?? false),
    engine: options.engine || 'auto-best',
  });

  if (options.numSpeakers) {
    params.append('num_speakers', String(options.numSpeakers));
  }

  if (options.contextPath) {
    params.append('context_path', options.contextPath);
  }

  if (options.speakerIds && options.speakerIds.length > 0) {
    params.append('speaker_ids', options.speakerIds.join(','));
  }
  appendRefinementMode(params, options);

  const response = await fetchWithTimeout(`${API_URL}/transcribe/batch?${params}`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Batch transcription request failed');
  }

  return response.json();
}

export type LearningEventType =
  | 'embedding_update' | 'embedding_skipped' | 'embedding_failed'
  | 'glossary_add'
  | 'insight_added' | 'insight_failed';

export interface LearningEvent {
  ts: string;
  type: LearningEventType | string;
  job_id?: string;
  speaker_id?: string | null;
  speaker_name?: string;
  term?: string;
  source_phrase?: string;
  reason?: string;
  category?: string;
  duration_sec?: number;
}

export interface LearningLogResponse {
  events: LearningEvent[];
  total: number;
  offset: number;
  limit: number;
}

export async function fetchLearningLog(params: {
  since?: string;
  type?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<LearningLogResponse> {
  const qs = new URLSearchParams();
  if (params.since) qs.set('since', params.since);
  if (params.type) qs.set('type', params.type);
  if (params.limit !== undefined) qs.set('limit', String(params.limit));
  if (params.offset !== undefined) qs.set('offset', String(params.offset));
  const r = await fetchWithTimeout(`${API_URL}/learning/log?${qs.toString()}`);
  if (!r.ok) throw new Error(`fetchLearningLog failed: ${r.status}`);
  return r.json();
}

export interface ReRefineResponse {
  job_id: string;
  status: string;
  phase: string | null;
  speakers_created: Array<{ speaker_id: string; name: string }>;
  speakers_assigned: number;
}

export async function reRefineJob(
  jobId: string,
  assignments: Record<string, string>,
): Promise<ReRefineResponse> {
  const r = await fetchWithTimeout(`${API_URL}/job/${jobId}/re-refine`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ speaker_assignments: assignments }),
  });
  if (!r.ok) {
    const detail = await r.text();
    throw new Error(`reRefineJob failed: ${r.status} ${detail.slice(0, 200)}`);
  }
  return r.json();
}

export interface ConfirmSpeakersResponse {
  job_id: string;
  status: string;
  phase: string | null;
  speakers_created: Array<{ speaker_id: string; name: string }>;
  speakers_assigned: number;
  speakers_ignored: number;
}

export async function confirmSpeakers(
  jobId: string,
  assignments: Record<string, string>,
): Promise<ConfirmSpeakersResponse> {
  const r = await fetchWithTimeout(`${API_URL}/job/${jobId}/confirm-speakers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ speaker_assignments: assignments }),
  });
  if (!r.ok) {
    const detail = await r.text();
    throw new Error(`confirmSpeakers failed: ${r.status} ${detail.slice(0, 200)}`);
  }
  return r.json();
}
