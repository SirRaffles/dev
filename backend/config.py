"""
Application configuration constants and model definitions.
"""

import os
from pathlib import Path

# iCloud Drive base path for call intelligence data (speakers, contexts, calls)
ICLOUD_BASE_PATH = Path(os.environ.get(
    "ICLOUD_BASE_PATH",
    os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/Davrine Transcription")
))

# Speaker embedding matching threshold (cosine similarity, 0-1)
SPEAKER_MATCH_THRESHOLD = float(os.environ.get("SPEAKER_MATCH_THRESHOLD", "0.75"))

# Minimum diarization segment duration (seconds) for reliable embedding extraction
MIN_EMBEDDING_SEGMENT_SECONDS = float(os.environ.get("MIN_EMBEDDING_SEGMENT_SECONDS", "5.0"))

# Just Press Record iCloud path
JPR_WATCH_PATH = Path(os.environ.get(
    "JPR_WATCH_PATH",
    os.path.expanduser(
        "~/Library/Mobile Documents/iCloud~com~openplanetsoftware~just-press-record/Documents"
    )
))

# Watcher state file
JPR_STATE_FILE = Path(os.environ.get(
    "JPR_STATE_FILE",
    os.path.expanduser("~/.jpr_watcher_state.json")
))

# Supported languages (Whisper supports 99, these are the most common)
SUPPORTED_LANGUAGES = {
    "auto": "Auto-detect",
    "en": "English",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "ru": "Russian",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ar": "Arabic",
    "hi": "Hindi",
    "pl": "Polish",
}

# Available MLX-Whisper model sizes with descriptions
MLX_MODELS = {
    "tiny": {"path": "mlx-community/whisper-tiny", "description": "Fastest, lowest quality (~39M params)"},
    "base": {"path": "mlx-community/whisper-base", "description": "Fast, good for real-time (~74M params)"},
    "small": {"path": "mlx-community/whisper-small", "description": "Balanced speed/quality (~244M params)"},
    "medium": {"path": "mlx-community/whisper-medium", "description": "High quality, moderate speed (~769M params)"},
    "large-v3": {"path": "mlx-community/whisper-large-v3-mlx", "description": "Best quality, slowest (~1.5B params)"},
    "large-v3-turbo": {"path": "mlx-community/whisper-large-v3-turbo", "description": "6x faster, near-best quality (~809M params)"},
    "distil-large-v3": {"path": "mlx-community/distil-whisper-large-v3", "description": "5x faster, fewer hallucinations (~756M params)"},
}

# English-only optimized model (Parakeet MLX - 60x real-time on Apple Silicon)
PARAKEET_MODEL = {
    "path": "mlx-community/parakeet-tdt-0.6b-v2",
    "description": "60x real-time, English only (~600M params)",
    "language": "en",
}

# Voxtral cloud transcription models (Mistral API)
VOXTRAL_MODELS = {
    "voxtral-mini": {
        "api_id": "voxtral-mini-latest",
        "description": "Cloud: Best accuracy, built-in diarization ($0.003/min)",
        "engine": "voxtral-api",
    },
}

# Voxtral local models (via mlx-audio on Apple Silicon)
VOXTRAL_LOCAL_MODELS = {
    "voxtral-mini-3b": {
        "path": "mlx-community/Voxtral-Mini-3B-2507-bf16",
        "description": "Best accuracy (~4% WER), 13 languages (~9.4GB)",
    },
    "voxtral-mini-3b-4bit": {
        "path": "mzbac/voxtral-mini-3b-4bit-mixed",
        "description": "Best accuracy (~4% WER), lower memory (~3.2GB)",
    },
}

# Voxtral local supported languages (13 languages)
VOXTRAL_LOCAL_LANGUAGES = {
    "auto", "en", "fr", "de", "es", "it", "pt", "nl", "ru", "zh", "ja", "ko", "ar", "hi",
}

# Allowed file extensions for transcription upload
ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".webm", ".mov"}
ALLOWED_EXTENSIONS = ALLOWED_AUDIO_EXTENSIONS | ALLOWED_VIDEO_EXTENSIONS

# Multi-modal supported extensions
SUPPORTED_DOCUMENT_EXTENSIONS = {
    ".pdf": "PDF document",
    ".pptx": "PowerPoint presentation",
    ".ppt": "PowerPoint (legacy)",
}

SUPPORTED_VIDEO_EXTENSIONS_MM = {
    ".mp4": "MP4 video",
    ".mov": "QuickTime video",
    ".mkv": "Matroska video",
    ".avi": "AVI video",
    ".webm": "WebM video",
}
