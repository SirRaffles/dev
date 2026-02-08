"""
Shared mutable application state.
All global state lives here to avoid circular imports.
"""

import os
import time
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

from job_models import JobStore


class BoundedDict:
    """Thread-safe dictionary with LRU eviction when max_size is reached."""

    def __init__(self, max_size: int = 1000):
        self._data = OrderedDict()
        self._lock = threading.Lock()
        self._max_size = max_size

    def __setitem__(self, key, value):
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = value
            while len(self._data) > self._max_size:
                self._data.popitem(last=False)

    def __getitem__(self, key):
        with self._lock:
            self._data.move_to_end(key)
            return self._data[key]

    def __contains__(self, key):
        with self._lock:
            return key in self._data

    def __delitem__(self, key):
        with self._lock:
            del self._data[key]

    def get(self, key, default=None):
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                return self._data[key]
            return default

    def pop(self, key, *args):
        with self._lock:
            return self._data.pop(key, *args)

    def values(self):
        with self._lock:
            return list(self._data.values())

    def items(self):
        with self._lock:
            return list(self._data.items())

    def __len__(self):
        with self._lock:
            return len(self._data)


# Thread pool for MLX-Whisper transcription tasks
# IMPORTANT: max_workers=1 to prevent Metal GPU race conditions on macOS 26.x
transcription_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="whisper")

# Global model state
whisper_model_path = None
whisper_model_ready = False
diarization_pipeline = None

# Voxtral cloud transcription state
_voxtral_available = False
_voxtral_service = None

# Parakeet state
_parakeet_available = False
_parakeet_model = None

# Check if Parakeet is available
try:
    import parakeet_mlx
    if hasattr(parakeet_mlx, 'from_pretrained'):
        _parakeet_available = True
except ImportError:
    pass

# Application startup time for uptime tracking
startup_time = None

# Job stores
job_store = JobStore()
batch_jobs = BoundedDict(max_size=500)
multimodal_jobs = BoundedDict(max_size=500)
jobs = job_store  # Legacy compatibility alias
