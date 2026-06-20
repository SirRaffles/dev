"""
Shared mutable application state.
All global state lives here to avoid circular imports.
"""

import os
import time
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

from migrations import run_migrations
from job_models import JobStore, RefinementStore, SpeakerStore, CallSpeakerStore, CallMetadataStore


DB_PATH = os.path.expanduser("~/.whisper_transcription_jobs.db")
_db_dir = os.path.dirname(DB_PATH)
if _db_dir:
    os.makedirs(_db_dir, exist_ok=True)
run_migrations(DB_PATH)


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


# Thread pool for transcription tasks
# max_workers=1: serialize all transcription jobs to prevent Metal GPU OOM.
# Diarization (pyannote) + transcription (Whisper) together use most
# of the 24GB unified memory on M3. Concurrent jobs cause crashes.
transcription_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="whisper")

# Global model state
whisper_model_path = None
whisper_model_ready = False
diarization_pipeline = None

# Parakeet state.
# _parakeet_model holds a single cached parakeet_mlx model.
# _parakeet_model_path tracks which HF path is currently loaded so we can
# swap between variants (English v2 vs multilingual v3) on demand.
_parakeet_available = False
_parakeet_model = None
_parakeet_model_path = None

# Check if Parakeet is available
if os.environ.get("DISABLE_PARAKEET_PROBE", "false").lower() != "true":
    try:
        import parakeet_mlx
        if hasattr(parakeet_mlx, 'from_pretrained'):
            _parakeet_available = True
    except ImportError:
        pass

# Refinement state
refinement_available = False
refinement_service = None
refinement_store = None

# Configure refinement service
import shutil as _shutil
from config import REFINEMENT_MODEL, REFINEMENT_PROVIDER, OLLAMA_HOST

_claude_path = _shutil.which("claude")

if REFINEMENT_PROVIDER == "disabled":
    refinement_available = False
elif REFINEMENT_PROVIDER == "ollama":
    from services.refinement import RefinementService
    refinement_service = RefinementService(
        provider="ollama",
        model=REFINEMENT_MODEL,
        ollama_host=OLLAMA_HOST,
    )
    refinement_store = RefinementStore(DB_PATH)
    refinement_available = True
elif _claude_path:
    from services.refinement import RefinementService
    refinement_service = RefinementService(
        claude_path=_claude_path,
        provider="claude",
        model=REFINEMENT_MODEL,
    )
    refinement_store = RefinementStore(DB_PATH)
    refinement_available = True

# Application startup time for uptime tracking
startup_time = None

# Job stores
job_store = JobStore(DB_PATH)
batch_jobs = BoundedDict(max_size=500)
multimodal_jobs = BoundedDict(max_size=500)
jobs = job_store  # Legacy compatibility alias

# Call intelligence stores
speaker_store = SpeakerStore(DB_PATH)
call_speaker_store = CallSpeakerStore(DB_PATH)
call_metadata_store = CallMetadataStore(DB_PATH)

# Speaker embedding service (lazy-loaded, uses pyannote)
_speaker_embedding_service = None

def get_speaker_embedding_service():
    """Get or create the speaker embedding service singleton."""
    global _speaker_embedding_service
    if _speaker_embedding_service is None:
        from services.speaker_embedding import SpeakerEmbeddingService
        _speaker_embedding_service = SpeakerEmbeddingService()
    return _speaker_embedding_service

# Deliverable generation service (requires claude CLI)
deliverable_service = None
deliverable_available = False

if _claude_path:
    from services.deliverable_service import DeliverableService
    deliverable_service = DeliverableService(_claude_path)
    deliverable_available = True
