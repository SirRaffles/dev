// API configuration
const isLocalDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
export const API_URL = import.meta.env.VITE_API_URL || (isLocalDev ? 'http://localhost:8000' : '');

// Fetch with timeout — prevents requests from hanging indefinitely
function fetchWithTimeout(url: string, options: RequestInit = {}, timeoutMs = 30000): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, { ...options, signal: controller.signal }).finally(() => clearTimeout(timer));
}

// --- Interfaces ---

export interface WakeStatus {
  mac_state: string;
  model_loaded: boolean;
}

export type RefinementStatus = "pending" | "processing" | "done" | "failed" | null;
export type LearningStatus = "ok" | "partial" | "failed" | null;

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
  // Plan 5A backend extension: 2nd-best registry candidate from the cosine
  // similarity ranking. Null when registry has <2 candidates or when the
  // runner-up confidence is below the min threshold (~0.4). Optional so
  // pre-Plan-5 jobs and the legacy code path continue to deserialise.
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
    source?: string;           // "youtube_captions" | undefined for audio engines
    is_generated?: boolean;    // true for YouTube auto-captions
  };
  error?: string;
  filename?: string;
  created_at?: string;
  original_filename?: string;  // JPR-sourced jobs only; non-JPR jobs leave undefined
  is_generated?: boolean;      // mirrored at top level by the captions fast-path
  source?: string;
  // B2 auto-refine fields (populated post-completion by the refinement pipeline).
  refinement_status?: RefinementStatus;
  auto_speaker_matches?: Record<string, AutoSpeakerMatch> | null;
  learning_summary?: LearningSummary | null;
  learning_status?: LearningStatus;
  // Sub-plan A: orchestrator's current pipeline phase
  // ("diarizing" | "transcribing" | "aligning" | "refining" | "learning" | null)
  phase?: string | null;
}

export async function fetchJobAutoRefineState(jobId: string): Promise<{
  refinement_status: RefinementStatus;
  learning_status: LearningStatus;
  learning_summary: LearningSummary | null;
  auto_speaker_matches: Record<string, AutoSpeakerMatch> | null;
  phase: string | null;
}> {
  const res = await fetchWithTimeout(`${API_URL}/job/${jobId}`);
  if (!res.ok) throw new Error(`fetchJobAutoRefineState failed: ${res.status}`);
  const j = await res.json();
  return {
    refinement_status: j.refinement_status ?? null,
    learning_status: j.learning_status ?? null,
    learning_summary: j.learning_summary ?? null,
    auto_speaker_matches: j.auto_speaker_matches ?? null,
    phase: j.phase ?? null,
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
  // Quality dial mode — backend orchestrator picks the actual engine + model.
  engine?: 'auto-best' | 'auto-quick';
  translateToEnglish?: boolean;
  numSpeakers?: number;
  contextPath?: string;   // Relative path under CONTEXTS_DIR to a .md context document
  speakerIds?: string[];  // Expected speakers — their personality.md is merged into the prompt
}

export interface ExportFormatInfo {
  label: string;
  ext: string;
}

// --- Wake-on-LAN proxy status (NAS deployment only) ---

export async function checkWakeStatus(): Promise<WakeStatus | null> {
  try {
    const response = await fetchWithTimeout(`${API_URL}/api/wake-status`, {}, 10000);
    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
}

// Supported languages
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

// Export formats
export const EXPORT_FORMATS: Record<string, ExportFormatInfo> = {
  txt: { label: 'Plain Text', ext: '.txt' },
  md: { label: 'Markdown', ext: '.md' },
  srt: { label: 'SRT Subtitles', ext: '.srt' },
  vtt: { label: 'WebVTT Subtitles', ext: '.vtt' },
  pdf: { label: 'PDF Document', ext: '.pdf' },
  docx: { label: 'Word Document', ext: '.docx' },
  json: { label: 'JSON', ext: '.json' },
};

// File type detection
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

// API helper functions
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
  // Query params for settings not in YouTubeRequest body
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

  // Body contains YouTubeRequest fields
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

/**
 * Soft-cancel a transcription job. Deletes the job record from the backend
 * (frees the UI immediately) but the underlying executor thread keeps running
 * until its current chunk completes — Python's ThreadPoolExecutor.cancel()
 * doesn't interrupt already-running tasks. For a true hard-stop, restart the
 * backend (`launchctl kickstart -k gui/$(id -u)/com.whisper.backend`).
 */
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

export async function updateSpeakers(jobId: string, speakerMapping: Record<string, string>): Promise<{ status: string; segments?: Segment[]; speakers?: string[] }> {
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

// --- Call Intelligence Types ---

export interface Speaker {
  speaker_id: string;
  name: string;
  folder_path: string;
  embedding_path?: string;
  call_count: number;
  total_speaking_time_seconds: number;
  created_at: string;
}

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

export interface JPRRecording {
  filename: string;
  path: string;
  date: string;                 // ISO timestamp of the recording (file mtime)
  date_folder?: string;         // legacy; kept for back-compat
  size_bytes: number;
  status: string;               // raw watcher status
  effective_status?: string;    // UI-facing: completed | processing | failed | unprocessed (driven by transcript_exists OR watcher)
  job_id?: string | null;
  transcript_exists: boolean;
  transcript_preview?: string | null;
  speakers?: string[];
  submitted_at?: string | null;
  completed_at?: string | null;
  error?: string | null;
  transcript_path?: string | null;
  // Where this entry came from. Set by the unified /recordings endpoint.
  // Absent on rows from the legacy /jpr/recordings endpoint (treat as 'jpr').
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

export interface SpeakerDetail extends Speaker {
  // 4-part profile. See backend/routes/speakers.py for the file layout.
  profile_md?: string;                // bio / resume — user-maintained
  explicit_insights_md?: string;      // LLM: concrete facts captured in transcripts
  implicit_insights_md?: string;      // LLM: inferred personality / style / values
  personality_md?: string;            // legacy alias (== implicit_insights_md)
  has_embedding?: boolean;            // voice profile present?
  calls?: CallSpeaker[];
}

export interface RegisterCallResponse {
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

// --- Speaker API ---

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

export async function updateSpeakerPersonality(speakerId: string, content: string): Promise<void> {
  const response = await fetchWithTimeout(`${API_URL}/speakers/${speakerId}/personality`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });
  if (!response.ok) throw new Error('Failed to update personality');
}

// --- Calls API ---

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

export async function registerCall(jobId: string, sourceType = 'upload', sourcePath?: string): Promise<RegisterCallResponse> {
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

// --- Context API ---

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
  // data.tree is the root node; we want its children as the top-level list
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

// Backend routes use `{path:path}` which preserves slashes — encodeURI keeps
// `/` unescaped, unlike encodeURIComponent.
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

// Uploads a .md or .txt file into a context folder by reading its text and
// PUTing it through the regular write endpoint. Keeps the backend simple
// (no multipart) at the cost of not supporting binary formats — which we
// don't accept anyway.
export async function uploadContextFile(folderPath: string, file: File): Promise<string> {
  const ext = file.name.toLowerCase().match(/\.[^.]+$/)?.[0] || '';
  if (!['.md', '.txt'].includes(ext)) {
    throw new Error('Only .md and .txt files are supported');
  }
  // Cap at 1 MB — these are bias prompts, not documents to archive.
  if (file.size > 1_000_000) {
    throw new Error('File too large (max 1 MB)');
  }
  const text = await file.text();
  await updateContextFile(folderPath, file.name, text);
  return file.name;
}

// --- JPR Recordings API ---

export async function fetchJPRRecordings(params: JPRListParams = {}): Promise<{
  recordings: JPRRecording[];
  total: number;
  watcher_status?: { available: boolean; completed?: number; pending?: number; failed?: number };
}> {
  const qs = new URLSearchParams();
  qs.set('limit', String(params.limit ?? 50));
  qs.set('offset', String(params.offset ?? 0));
  if (params.status) qs.set('status', params.status);
  if (params.sort_by) qs.set('sort_by', params.sort_by);
  if (params.sort_dir) qs.set('sort_dir', params.sort_dir);
  if (params.q && params.q.trim()) qs.set('q', params.q.trim());
  const response = await fetchWithTimeout(`${API_URL}/jpr/recordings?${qs}`);
  if (!response.ok) throw new Error('Failed to fetch recordings');
  return response.json();
}

/**
 * Unified recordings list — merges JPR-discovered files with direct uploads
 * and YouTube ingests. Same param shape as {@link fetchJPRRecordings} so the
 * hook can swap endpoints without UI-state changes. Each returned recording
 * carries a `source` field ('jpr' | 'upload' | 'youtube') the UI can use to
 * render a badge.
 */
export async function fetchRecordings(params: JPRListParams = {}): Promise<{
  recordings: JPRRecording[];
  total: number;
  watcher_status?: { available: boolean; completed?: number; pending?: number; failed?: number };
}> {
  const qs = new URLSearchParams();
  qs.set('limit', String(params.limit ?? 50));
  qs.set('offset', String(params.offset ?? 0));
  if (params.status) qs.set('status', params.status);
  if (params.sort_by) qs.set('sort_by', params.sort_by);
  if (params.sort_dir) qs.set('sort_dir', params.sort_dir);
  if (params.q && params.q.trim()) qs.set('q', params.q.trim());
  const response = await fetchWithTimeout(`${API_URL}/recordings?${qs}`);
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

// --- Job-level speaker assignment ---

export interface JobSpeakerLabel {
  label: string;
  total_seconds: number;
  segment_count: number;
  anonymous: boolean;
  matched_speaker_id: string | null;
  can_extract_embedding: boolean;
}

export async function fetchJobSpeakerLabels(jobId: string): Promise<JobSpeakerLabel[]> {
  const response = await fetchWithTimeout(`${API_URL}/job/${jobId}/speakers/labels`);
  if (!response.ok) throw new Error('Failed to fetch speaker labels');
  const data = await response.json();
  return data.labels || [];
}

export interface AutoMatchSuggestion {
  label: string;
  speaker_id: string | null;
  speaker_name: string | null;
  confidence: number;
  source: 'pick' | 'registry' | null;
  matched: boolean;
  total_seconds: number;
}

export interface AutoMatchResponse {
  job_id: string;
  mode: 'scoped' | 'global-prefer' | 'global';
  suggestions: AutoMatchSuggestion[];
}

export async function fetchJobAutoMatchSuggestions(jobId: string): Promise<AutoMatchResponse> {
  const response = await fetchWithTimeout(`${API_URL}/job/${jobId}/speakers/auto-match`, {
    method: 'POST',
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Auto-match failed' }));
    throw new Error(err.detail || 'Auto-match failed');
  }
  return response.json();
}

export interface SpeakerAssignmentInput {
  label: string;
  speaker_name: string;
  create_new: boolean;
}

export interface AssignSpeakersResponse {
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

export async function assignJobSpeakers(
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

// --- Learning log (activity timeline) ---

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

/**
 * Plan 5: trigger a single re-refinement run with corrected speaker
 * assignments. `assignments` maps a diarization label (e.g. "SPEAKER_00")
 * to one of:
 *   - a speaker UUID (re-attribute to existing speaker)
 *   - the literal string "unknown" (strip name, mark anonymous)
 *   - "new:<Display Name>" (create a new speaker; backend extracts a voice
 *     embedding from that label's segments via register_speaker)
 *
 * Backend dispatches a single Sonnet refinement call on success, transitioning
 * job.phase from null → "refining" → "learning" → null.
 */
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
