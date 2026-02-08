"""
Shared mutable application state.
All global state lives here to avoid circular imports.
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor

from job_models import JobStore

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
batch_jobs = {}
multimodal_jobs = {}
jobs = job_store  # Legacy compatibility alias
