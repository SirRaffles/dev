"""
Configuration constants for the Just Press Record auto-transcription watcher.
"""

import os
from pathlib import Path

# iCloud paths
ICLOUD_PATH = Path(os.path.expanduser(
    "~/Library/Mobile Documents/iCloud~com~openplanetsoftware~just-press-record/Documents"
))
WATCH_EXTENSIONS = {".m4a"}

# Backend API
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
API_TIMEOUT = 300  # seconds for API calls (large files need more time)
POLL_INTERVAL = 5  # seconds between status polls
MAX_POLL_TIME = 3600  # 1 hour max transcription time (for long recordings)

# Transcription settings
TRANSCRIPTION_SETTINGS = {
    "language": "auto",
    "enable_diarization": True,
    "enable_noise_reduction": False,
    "model_size": "large-v3-turbo",
    "word_timestamps": False,
    "translate_to_english": False,
}

# iCloud sync detection
SYNC_STABILITY_DELAY = 2  # seconds to wait after file stops changing
SYNC_CHECK_INTERVAL = 1  # seconds between size checks
SYNC_TIMEOUT = 300  # 5 minutes max wait for sync (large recordings need more time)

# Retry settings
RETRY_DELAY_BASE = 60  # seconds
RETRY_MAX_ATTEMPTS = 5
RETRY_BACKOFF_MULTIPLIER = 2

# State persistence
STATE_FILE = Path(os.path.expanduser("~/.jpr_watcher_state.json"))
LOG_FILE = Path(os.path.expanduser("~/.jpr_watcher.log"))

# Logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 3
