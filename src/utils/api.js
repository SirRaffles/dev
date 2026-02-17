// API configuration
const isLocalDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
export const API_URL = process.env.REACT_APP_API_URL || (isLocalDev ? 'http://localhost:8000' : '');
const API_KEY = process.env.REACT_APP_API_KEY || '';

// Wake-on-LAN proxy status (NAS deployment only)
export async function checkWakeStatus() {
  try {
    const response = await fetch(`${API_URL}/api/wake-status`, { headers: authHeaders() });
    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
}

// Helper to build headers with optional API key
function authHeaders(extra = {}) {
  const headers = { ...extra };
  if (API_KEY) headers['X-API-Key'] = API_KEY;
  return headers;
}

// Supported languages
export const LANGUAGES = {
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
export const ENGINES = {
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
export const MODEL_SIZES = {
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
export const VOXTRAL_MODELS = {
  'voxtral-mini': { label: 'Voxtral Mini', description: 'Best accuracy, built-in diarization ($0.003/min)' },
};

// Voxtral local models (via mlx-audio on Apple Silicon)
export const VOXTRAL_LOCAL_MODELS = {
  'voxtral-mini-3b': { label: 'Voxtral Mini 3B', description: 'Best accuracy (~4% WER), 13 languages (~9.4GB)' },
  'voxtral-mini-3b-4bit': { label: 'Voxtral Mini 3B (4-bit)', description: 'Best accuracy (~4% WER), lower memory (~3.2GB)' },
};

// Export formats
export const EXPORT_FORMATS = {
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

export function getFileType(filename) {
  const ext = filename.split('.').pop().toLowerCase();

  if (AUDIO_EXTENSIONS.includes(ext)) return 'audio';
  if (VIDEO_EXTENSIONS.includes(ext)) return 'video';
  if (DOCUMENT_EXTENSIONS.includes(ext)) return 'document';

  return 'unknown';
}

export function getSourceType(filename) {
  const ext = filename.split('.').pop().toLowerCase();

  if (AUDIO_EXTENSIONS.includes(ext)) return 'audio';
  if (VIDEO_EXTENSIONS.includes(ext)) return 'video';
  if (ext === 'pdf') return 'pdf';
  if (['pptx', 'ppt'].includes(ext)) return 'pptx';
  if (ext === 'docx') return 'docx';

  return 'unknown';
}

export function isDocumentFile(filename) {
  return getFileType(filename) === 'document';
}

export function isMediaFile(filename) {
  const type = getFileType(filename);
  return type === 'audio' || type === 'video';
}

// API helper functions
export async function fetchJobStatus(jobId, isMultiModal = false) {
  const endpoint = isMultiModal
    ? `${API_URL}/process/job/${jobId}`
    : `${API_URL}/job/${jobId}`;

  const response = await fetch(endpoint, { headers: authHeaders() });
  if (!response.ok) {
    throw new Error('Failed to fetch job status');
  }
  return response.json();
}

export async function submitTranscription(file, options = {}) {
  const formData = new FormData();
  formData.append('file', file);

  const params = new URLSearchParams({
    language: options.language || 'auto',
    enable_diarization: options.enableDiarization ?? true,
    enable_noise_reduction: options.enableNoiseReduction ?? false,
    model_size: options.modelSize || 'voxtral-mini-3b',
    word_timestamps: options.wordTimestamps ?? false,
    translate_to_english: options.translateToEnglish ?? false,
    speed_priority: options.speedPriority ?? false,
    engine: options.engine || 'voxtral-local',
    two_pass: options.twoPass ?? false,
    output_mode: options.outputMode || 'verbatim',
  });

  if (options.numSpeakers) {
    params.append('num_speakers', options.numSpeakers);
  }

  if (options.contextTerms) {
    params.append('context_terms', options.contextTerms);
  }

  const response = await fetch(`${API_URL}/transcribe/file?${params}`, {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Transcription request failed');
  }

  return response.json();
}

export async function submitMultiModalProcessing(file, options = {}) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_URL}/process/multimodal`, {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Processing request failed');
  }

  return response.json();
}

export async function submitYouTubeTranscription(url, options = {}) {
  // Query params for settings not in YouTubeRequest body
  const params = new URLSearchParams({
    model_size: options.modelSize || 'voxtral-mini-3b',
    word_timestamps: options.wordTimestamps ?? false,
    speed_priority: options.speedPriority ?? false,
    engine: options.engine || 'voxtral-local',
    two_pass: options.twoPass ?? false,
    output_mode: options.outputMode || 'verbatim',
  });

  if (options.numSpeakers) {
    params.append('num_speakers', options.numSpeakers);
  }

  if (options.contextTerms) {
    params.append('context_terms', options.contextTerms);
  }

  // Body contains YouTubeRequest fields
  const response = await fetch(`${API_URL}/transcribe/youtube?${params}`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
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

export async function exportTranscript(jobId, format, isMultiModal = false) {
  const endpoint = isMultiModal
    ? `${API_URL}/process/job/${jobId}/export?format=${format}`
    : `${API_URL}/job/${jobId}/export?format=${format}`;

  const response = await fetch(endpoint, { headers: authHeaders() });

  if (!response.ok) {
    throw new Error('Export failed');
  }

  return response.blob();
}

export async function updateSegments(jobId, segments) {
  const response = await fetch(`${API_URL}/job/${jobId}/segments`, {
    method: 'PUT',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ segments }),
  });

  if (!response.ok) {
    throw new Error('Failed to save edits');
  }

  return response.json();
}

export async function updateSpeakers(jobId, speakerMapping) {
  const response = await fetch(`${API_URL}/job/${jobId}/speakers`, {
    method: 'PUT',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ speaker_mapping: speakerMapping }),
  });

  if (!response.ok) {
    throw new Error('Failed to rename speaker');
  }

  return response.json();
}

export async function fetchBatchStatus(batchId) {
  const response = await fetch(`${API_URL}/batch/${batchId}`, { headers: authHeaders() });

  if (!response.ok) {
    throw new Error('Failed to fetch batch status');
  }

  return response.json();
}

export async function submitBatchTranscription(files, options = {}) {
  const formData = new FormData();
  files.forEach(f => formData.append('files', f));

  const params = new URLSearchParams({
    language: options.language || 'auto',
    enable_diarization: options.enableDiarization ?? true,
    model_size: options.modelSize || 'voxtral-mini-3b',
    word_timestamps: options.wordTimestamps ?? false,
    translate_to_english: options.translateToEnglish ?? false,
    speed_priority: options.speedPriority ?? false,
    engine: options.engine || 'voxtral-local',
    two_pass: options.twoPass ?? false,
    output_mode: options.outputMode || 'verbatim',
  });

  if (options.numSpeakers) {
    params.append('num_speakers', options.numSpeakers);
  }

  if (options.contextTerms) {
    params.append('context_terms', options.contextTerms);
  }

  const response = await fetch(`${API_URL}/transcribe/batch?${params}`, {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Batch transcription request failed');
  }

  return response.json();
}
