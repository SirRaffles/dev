// API configuration
const isLocalDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
export const API_URL = import.meta.env.VITE_API_URL || (isLocalDev ? 'http://localhost:8000' : '');

// --- Interfaces ---

export interface WakeStatus {
  mac_state: string;
  model_loaded: boolean;
}

export interface HealthResponse {
  status: string;
  voxtral_available?: boolean;
  engines?: Record<string, { available: boolean }>;
}

export interface JobStatus {
  job_id: string;
  status: string;
  progress?: number;
  result?: {
    text?: string;
    segments?: Segment[];
    language?: string;
  };
  error?: string;
  filename?: string;
  created_at?: string;
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
  modelSize?: string;
  wordTimestamps?: boolean;
  translateToEnglish?: boolean;
  speedPriority?: boolean;
  engine?: string;
  twoPass?: boolean;
  outputMode?: string;
  numSpeakers?: number;
  contextTerms?: string;
}

export interface EngineInfo {
  label: string;
  description: string;
  type: string;
  cost: string | null;
}

export interface ModelInfo {
  label: string;
  description: string;
  languageRestriction?: string;
}

export interface ExportFormatInfo {
  label: string;
  ext: string;
}

// --- Wake-on-LAN proxy status (NAS deployment only) ---

export async function checkWakeStatus(): Promise<WakeStatus | null> {
  try {
    const response = await fetch(`${API_URL}/api/wake-status`);
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

// Transcription engines
export const ENGINES: Record<string, EngineInfo> = {
  whisper: {
    label: 'Whisper (Local)',
    description: 'Free, on-device, GPU-accelerated via Metal',
    type: 'local',
    cost: null,
  },
  'voxtral-local': {
    label: 'Voxtral Local',
    description: 'Best accuracy (~4% WER), on-device, 13 languages',
    type: 'local',
    cost: null,
  },
  'voxtral-api': {
    label: 'Voxtral (Cloud)',
    description: 'Best accuracy (~4% WER), built-in diarization',
    type: 'cloud',
    cost: '$0.003/min',
  },
};

// Available model sizes (matching backend MLX_MODELS)
export const MODEL_SIZES: Record<string, ModelInfo> = {
  'tiny': { label: 'Tiny', description: 'Fastest (~1min audio in ~10s)' },
  'base': { label: 'Base', description: 'Fast, good for real-time' },
  'small': { label: 'Small', description: 'Balanced speed/quality' },
  'medium': { label: 'Medium', description: 'High quality, moderate speed' },
  'large-v3': { label: 'Large V3', description: 'Best quality, slowest' },
  'large-v3-turbo': { label: 'Large V3 Turbo', description: '6x faster, near-best quality (Recommended)' },
  'distil-large-v3': { label: 'Distil Large V3', description: '5x faster, fewer hallucinations' },
  'parakeet': { label: 'Parakeet MLX', description: '60x speed, English only', languageRestriction: 'en' },
};

// Voxtral cloud models
export const VOXTRAL_MODELS: Record<string, ModelInfo> = {
  'voxtral-mini': { label: 'Voxtral Mini', description: 'Best accuracy, built-in diarization ($0.003/min)' },
};

// Voxtral local models (via mlx-audio on Apple Silicon)
export const VOXTRAL_LOCAL_MODELS: Record<string, ModelInfo> = {
  'voxtral-mini-3b': { label: 'Voxtral Mini 3B', description: 'Best accuracy (~4% WER), 13 languages (~9.4GB)' },
  'voxtral-mini-3b-4bit': { label: 'Voxtral Mini 3B (4-bit)', description: 'Best accuracy (~4% WER), lower memory (~3.2GB)' },
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

  const response = await fetch(endpoint);
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
    model_size: options.modelSize || 'voxtral-mini-3b',
    word_timestamps: String(options.wordTimestamps ?? false),
    translate_to_english: String(options.translateToEnglish ?? false),
    speed_priority: String(options.speedPriority ?? false),
    engine: options.engine || 'voxtral-local',
    two_pass: String(options.twoPass ?? false),
    output_mode: options.outputMode || 'verbatim',
  });

  if (options.numSpeakers) {
    params.append('num_speakers', String(options.numSpeakers));
  }

  if (options.contextTerms) {
    params.append('context_terms', options.contextTerms);
  }

  const response = await fetch(`${API_URL}/transcribe/file?${params}`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Transcription request failed');
  }

  return response.json();
}

export async function submitMultiModalProcessing(file: File, options: TranscriptionOptions = {}): Promise<{ job_id: string }> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_URL}/process/multimodal`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Processing request failed');
  }

  return response.json();
}

export async function submitYouTubeTranscription(url: string, options: TranscriptionOptions = {}): Promise<{ job_id: string; status?: string }> {
  // Query params for settings not in YouTubeRequest body
  const params = new URLSearchParams({
    model_size: options.modelSize || 'voxtral-mini-3b',
    word_timestamps: String(options.wordTimestamps ?? false),
    speed_priority: String(options.speedPriority ?? false),
    engine: options.engine || 'voxtral-local',
    two_pass: String(options.twoPass ?? false),
    output_mode: options.outputMode || 'verbatim',
  });

  if (options.numSpeakers) {
    params.append('num_speakers', String(options.numSpeakers));
  }

  if (options.contextTerms) {
    params.append('context_terms', options.contextTerms);
  }

  // Body contains YouTubeRequest fields
  const response = await fetch(`${API_URL}/transcribe/youtube?${params}`, {
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

export async function exportTranscript(jobId: string, format: string, isMultiModal = false): Promise<Blob> {
  const endpoint = isMultiModal
    ? `${API_URL}/process/job/${jobId}/export?format=${format}`
    : `${API_URL}/job/${jobId}/export?format=${format}`;

  const response = await fetch(endpoint);

  if (!response.ok) {
    throw new Error('Export failed');
  }

  return response.blob();
}

export async function updateSegments(jobId: string, segments: Segment[]): Promise<{ status: string }> {
  const response = await fetch(`${API_URL}/job/${jobId}/segments`, {
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
  const response = await fetch(`${API_URL}/job/${jobId}/speakers`, {
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
  const response = await fetch(`${API_URL}/batch/${batchId}`);

  if (!response.ok) {
    throw new Error('Failed to fetch batch status');
  }

  return response.json();
}

export async function retryJob(jobId: string): Promise<{ job_id: string; status: string; retried_from: string }> {
  const response = await fetch(`${API_URL}/job/${jobId}/retry`, {
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
    model_size: options.modelSize || 'voxtral-mini-3b',
    word_timestamps: String(options.wordTimestamps ?? false),
    translate_to_english: String(options.translateToEnglish ?? false),
    speed_priority: String(options.speedPriority ?? false),
    engine: options.engine || 'voxtral-local',
    two_pass: String(options.twoPass ?? false),
    output_mode: options.outputMode || 'verbatim',
  });

  if (options.numSpeakers) {
    params.append('num_speakers', String(options.numSpeakers));
  }

  if (options.contextTerms) {
    params.append('context_terms', options.contextTerms);
  }

  const response = await fetch(`${API_URL}/transcribe/batch?${params}`, {
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

export interface ContextTree {
  name: string;
  path: string;
  children?: ContextTree[];
}

export interface JPRRecording {
  filename: string;
  path: string;
  date_folder: string;
  size_bytes: number;
  status: string;
  job_id?: string;
  transcript_exists: boolean;
}

export interface SpeakerDetail extends Speaker {
  personality_md?: string;
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
  const response = await fetch(`${API_URL}/speakers`);
  if (!response.ok) throw new Error('Failed to fetch speakers');
  const data = await response.json();
  return data.speakers;
}

export async function fetchSpeaker(speakerId: string): Promise<SpeakerDetail> {
  const response = await fetch(`${API_URL}/speakers/${speakerId}`);
  if (!response.ok) throw new Error('Failed to fetch speaker');
  return response.json();
}

export async function createSpeaker(name: string): Promise<{ speaker_id: string; name: string }> {
  const response = await fetch(`${API_URL}/speakers`, {
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
  const response = await fetch(`${API_URL}/speakers/${speakerId}`, {
    method: 'DELETE',
  });
  if (!response.ok) throw new Error('Failed to delete speaker');
}

export async function updateSpeakerPersonality(speakerId: string, content: string): Promise<void> {
  const response = await fetch(`${API_URL}/speakers/${speakerId}/personality`, {
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
  const response = await fetch(`${API_URL}/calls?${params}`);
  if (!response.ok) throw new Error('Failed to fetch calls');
  return response.json();
}

export async function fetchCall(jobId: string): Promise<CallMetadata> {
  const response = await fetch(`${API_URL}/calls/${jobId}`);
  if (!response.ok) throw new Error('Failed to fetch call');
  return response.json();
}

export async function registerCall(jobId: string, sourceType = 'upload', sourcePath?: string): Promise<RegisterCallResponse> {
  const response = await fetch(`${API_URL}/calls/${jobId}/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_type: sourceType, source_path: sourcePath }),
  });
  if (!response.ok) throw new Error('Failed to register call');
  return response.json();
}

export async function identifySpeakers(jobId: string): Promise<IdentifySpeakersResponse> {
  const response = await fetch(`${API_URL}/calls/${jobId}/identify-speakers`, {
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
  const response = await fetch(`${API_URL}/calls/${jobId}/confirm-speaker`, {
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
  const response = await fetch(`${API_URL}/calls/${jobId}/title`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  if (!response.ok) throw new Error('Failed to set title');
}

export async function assignContext(jobId: string, contextPath: string): Promise<void> {
  const response = await fetch(`${API_URL}/calls/${jobId}/context`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ context_path: contextPath }),
  });
  if (!response.ok) throw new Error('Failed to assign context');
}

export async function generateDeliverables(jobId: string): Promise<GenerateDeliverablesResponse> {
  const response = await fetch(`${API_URL}/calls/${jobId}/generate-deliverables`, {
    method: 'POST',
  });
  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.detail || 'Failed to generate deliverables');
  }
  return response.json();
}

export async function fetchDeliverables(jobId: string): Promise<DeliverablesResponse> {
  const response = await fetch(`${API_URL}/calls/${jobId}/deliverables`);
  if (!response.ok) throw new Error('Failed to fetch deliverables');
  return response.json();
}

// --- Context API ---

export async function fetchContextFolders(parentPath = ''): Promise<ContextFolder[]> {
  const params = parentPath ? `?path=${encodeURIComponent(parentPath)}` : '';
  const response = await fetch(`${API_URL}/contexts${params}`);
  if (!response.ok) throw new Error('Failed to fetch contexts');
  const data = await response.json();
  return data.folders;
}

export async function fetchContextTree(): Promise<ContextTree[]> {
  const response = await fetch(`${API_URL}/contexts/tree`);
  if (!response.ok) throw new Error('Failed to fetch context tree');
  const data = await response.json();
  // data.tree is the root node; we want its children as the top-level list
  return data.tree?.children || [];
}

export async function createContextFolder(path: string, description = ''): Promise<{ path: string; description: string }> {
  const response = await fetch(`${API_URL}/contexts/folders`, {
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

export async function fetchContextFile(path: string, filename: string): Promise<string> {
  const response = await fetch(
    `${API_URL}/contexts/files/${encodeURIComponent(path)}?filename=${encodeURIComponent(filename)}`,
  );
  if (!response.ok) throw new Error('Failed to fetch file');
  const data = await response.json();
  return data.content;
}

export async function updateContextFile(path: string, filename: string, content: string): Promise<void> {
  const response = await fetch(
    `${API_URL}/contexts/files/${encodeURIComponent(path)}?filename=${encodeURIComponent(filename)}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    },
  );
  if (!response.ok) throw new Error('Failed to update file');
}

// --- JPR Recordings API ---

export async function fetchJPRRecordings(limit = 50, offset = 0): Promise<{ recordings: JPRRecording[]; total: number }> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  const response = await fetch(`${API_URL}/jpr/recordings?${params}`);
  if (!response.ok) throw new Error('Failed to fetch recordings');
  return response.json();
}
