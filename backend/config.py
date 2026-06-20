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

# Enable web verification (DuckDuckGo search) for uncertain terms during refinement.
# Default to False for privacy.
ENABLE_WEB_VERIFICATION = os.environ.get("ENABLE_WEB_VERIFICATION", "false").lower() == "true"

# Transcript refinement provider.
# - claude: Claude CLI, default for the current MVP.
# - ollama: local Ollama /api/generate backend.
# - disabled: no refinement service at startup.
REFINEMENT_PROVIDER = os.environ.get("REFINEMENT_PROVIDER", "claude").strip().lower()
REFINEMENT_MODEL = os.environ.get(
    "REFINEMENT_MODEL",
    "qwen3.5:27b" if REFINEMENT_PROVIDER == "ollama" else "sonnet",
).strip()
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")

# Vision-language model used by MLX-VLM for document/video visual analysis.
VISION_MODEL_PATH = os.environ.get(
    "VISION_MODEL_PATH",
    "mlx-community/Qwen2.5-VL-3B-Instruct-4bit",
).strip()
VISION_MODEL_LABEL = os.environ.get("VISION_MODEL_LABEL", VISION_MODEL_PATH.split("/")[-1]).strip()

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

# Parakeet MLX model variants — optimized for Apple Silicon.
# v2 is English-only (60x real-time, baseline).
# v3 adds 25 European languages and class-leading noise robustness, same ~600M params.
PARAKEET_MODELS = {
    "parakeet-en-v2": {
        "path": "mlx-community/parakeet-tdt-0.6b-v2",
        "description": "60x real-time, English only (~600M params)",
        "language": "en",
        "supported_languages": ["en"],
    },
    "parakeet-multi-v3": {
        "path": "mlx-community/parakeet-tdt-0.6b-v3",
        "description": "Multilingual (25 EU languages), best noise robustness (~600M params)",
        "language": "multi",
        "supported_languages": [
            "en", "fr", "de", "es", "it", "pt", "nl", "ru",
        ],
    },
}

# Backwards-compat alias: legacy callers referenced PARAKEET_MODEL as a single dict.
# Keep it pointing at the English v2 model so existing behavior is unchanged.
PARAKEET_MODEL = PARAKEET_MODELS["parakeet-en-v2"]

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
