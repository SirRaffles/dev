"""
Application configuration constants and model definitions.
"""

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
