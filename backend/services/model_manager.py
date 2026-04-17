"""
Model lifecycle management with memory-aware loading/unloading.

Manages MLX-Whisper, GLM-4.6V-Flash, and Pyannote models with:
- Sequential loading to avoid OOM
- Memory tracking
- On-demand loading with automatic unloading
"""
import gc
import logging
import time
from typing import Dict, Optional, Any, ContextManager
from contextlib import contextmanager
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ModelName(str, Enum):
    WHISPER = "whisper"
    VISION = "vision"
    DIARIZATION = "diarization"
    EMBEDDING = "embedding"
    VOXTRAL_LOCAL = "voxtral_local"


class ModelConfig:
    """Configuration for each model."""
    # TODO: switch memory estimates to RSS deltas measured at load time
    # (audit #13). Constants below are rough fp16/int4 footprints.
    CONFIGS = {
        ModelName.WHISPER: {
            "priority": 1,  # Highest - always loaded first
            "memory_mb": 3000,
            "unloadable": False,  # Keep loaded as primary use case
            "load_timeout": 60,
        },
        ModelName.VISION: {
            "priority": 3,  # Lowest - load on demand
            "memory_mb": 8000,  # INT4 quantized GLM-4.6V-Flash
            "unloadable": True,
            "load_timeout": 120,
        },
        ModelName.DIARIZATION: {
            "priority": 2,  # Medium
            "memory_mb": 2000,
            "unloadable": True,
            "load_timeout": 60,
        },
        ModelName.EMBEDDING: {
            "priority": 2,  # Medium — same as diarization
            "memory_mb": 200,  # Speaker embedding model is lightweight (~200MB)
            "unloadable": True,
            "load_timeout": 60,
        },
        ModelName.VOXTRAL_LOCAL: {
            "priority": 1,  # Same tier as Whisper — primary transcription engine
            "memory_mb": 10000,  # Voxtral Mini 3B fp16; 4-bit variant uses ~3500MB
            "unloadable": True,
            "load_timeout": 120,
        },
    }


class ModelManager:
    """
    Manages model lifecycle with memory-aware loading/unloading.

    Strategy:
    1. Whisper is always loaded (primary use case)
    2. Vision model loaded on-demand, unloaded after batch
    3. Diarization loaded on-demand, kept if memory allows
    """

    # Leave 4GB headroom for system and processing
    MEMORY_THRESHOLD_MB = 20000  # 20GB max for models

    def __init__(self):
        self._models: Dict[ModelName, Any] = {}
        self._model_status: Dict[ModelName, dict] = {
            name: {
                "loaded": False,
                "memory_mb": 0,
                "device": "cpu",
                "last_used": None,
                "load_count": 0,
            }
            for name in ModelName
        }
        self._whisper_model_size = "large-v3-turbo"
        self._vision_model_path: Optional[str] = None
        # Audit #13: memoize available memory for up to 2s to avoid repeated syscalls.
        self._avail_mem_cache_mb: Optional[int] = None
        self._avail_mem_cache_at: float = 0.0

    def get_available_memory_mb(self) -> int:
        """Get available system memory in MB via psutil (audit #13)."""
        now = time.monotonic()
        if self._avail_mem_cache_mb is not None and (now - self._avail_mem_cache_at) < 2.0:
            return self._avail_mem_cache_mb
        try:
            import psutil
            avail = int(psutil.virtual_memory().available // (1024 * 1024))
        except Exception:
            avail = 8000  # conservative fallback
        self._avail_mem_cache_mb = avail
        self._avail_mem_cache_at = now
        return avail

    def get_total_loaded_memory_mb(self) -> int:
        """Get total memory used by loaded models."""
        return sum(
            status["memory_mb"]
            for status in self._model_status.values()
            if status["loaded"]
        )

    def is_loaded(self, model_name: ModelName) -> bool:
        """Check if a model is currently loaded."""
        return self._model_status[model_name]["loaded"]

    def get_model(self, model_name: ModelName) -> Optional[Any]:
        """Get a loaded model instance."""
        return self._models.get(model_name)

    def _can_load_model(self, model_name: ModelName) -> bool:
        """Check if we have enough memory to load a model."""
        if self.is_loaded(model_name):
            return True

        config = ModelConfig.CONFIGS[model_name]
        current_usage = self.get_total_loaded_memory_mb()
        required = config["memory_mb"]

        return (current_usage + required) <= self.MEMORY_THRESHOLD_MB

    def _unload_lower_priority_models(self, target_model: ModelName) -> bool:
        """
        Unload lower priority models to make room for target model.
        Returns True if enough memory was freed.
        """
        target_config = ModelConfig.CONFIGS[target_model]
        target_priority = target_config["priority"]
        target_memory = target_config["memory_mb"]

        # Get unloadable models with lower priority (higher number)
        candidates = [
            (name, ModelConfig.CONFIGS[name])
            for name in ModelName
            if self.is_loaded(name)
            and ModelConfig.CONFIGS[name]["unloadable"]
            and ModelConfig.CONFIGS[name]["priority"] > target_priority
        ]

        # Sort by priority (lowest priority first = highest number)
        candidates.sort(key=lambda x: -x[1]["priority"])

        freed_memory = 0
        current_usage = self.get_total_loaded_memory_mb()
        needed = (current_usage + target_memory) - self.MEMORY_THRESHOLD_MB

        if needed <= 0:
            return True  # Already have enough

        for model_name, config in candidates:
            if freed_memory >= needed:
                break

            logger.info(f"Unloading {model_name.value} to free memory")
            self.unload_model(model_name)
            freed_memory += config["memory_mb"]

        return freed_memory >= needed

    async def load_whisper(self, model_size: str = "large-v3-turbo") -> bool:
        """Load MLX-Whisper model.

        TODO(audit #11): mlx-whisper 0.4.x does not expose a stable top-level
        load_model(path) API — transcribe() loads on demand. We keep the
        module reference here so the rest of the manager's accounting/unload
        logic can still track the "in-memory" state of the weights.
        """
        if self.is_loaded(ModelName.WHISPER):
            if self._whisper_model_size == model_size:
                return True
            # Different size requested, unload first
            self.unload_model(ModelName.WHISPER)

        if not self._can_load_model(ModelName.WHISPER):
            if not self._unload_lower_priority_models(ModelName.WHISPER):
                raise MemoryError("Not enough memory to load Whisper model")

        try:
            # Import here to avoid loading at startup
            import mlx_whisper

            logger.info(f"Loading MLX-Whisper model: {model_size}")
            # Model will be loaded on first use
            self._models[ModelName.WHISPER] = mlx_whisper
            self._whisper_model_size = model_size
            self._model_status[ModelName.WHISPER].update({
                "loaded": True,
                "memory_mb": ModelConfig.CONFIGS[ModelName.WHISPER]["memory_mb"],
                "device": "mps",
                "last_used": datetime.now(),
                "load_count": self._model_status[ModelName.WHISPER]["load_count"] + 1,
            })
            return True

        except Exception as e:
            logger.error(f"Failed to load Whisper: {e}")
            return False

    async def load_vision(
        self,
        model_name: Optional[str] = None,
    ) -> bool:
        """
        Load vision model using MLX-VLM (optimized for Apple Silicon).

        Args:
            model_name: HuggingFace model name or local path.
                        Default: mlx-community/Qwen2.5-VL-3B-Instruct-4bit
        """
        if self.is_loaded(ModelName.VISION):
            return True

        if not self._can_load_model(ModelName.VISION):
            if not self._unload_lower_priority_models(ModelName.VISION):
                raise MemoryError("Not enough memory to load Vision model")

        try:
            from mlx_vlm import load
            from mlx_vlm.utils import load_config

            # Use a lightweight quantized model that works well on Apple Silicon
            if model_name is None:
                model_name = self._vision_model_path or "mlx-community/Qwen2.5-VL-3B-Instruct-4bit"

            logger.info(f"Loading vision model via MLX-VLM: {model_name}")

            # Load model and processor
            model, processor = load(model_name)
            config = load_config(model_name)

            # Store as tuple for vision service
            self._models[ModelName.VISION] = {
                "model": model,
                "processor": processor,
                "config": config,
                "model_name": model_name,
            }
            self._vision_model_path = model_name
            self._model_status[ModelName.VISION].update({
                "loaded": True,
                "memory_mb": ModelConfig.CONFIGS[ModelName.VISION]["memory_mb"],
                "device": "mps",
                "last_used": datetime.now(),
                "load_count": self._model_status[ModelName.VISION]["load_count"] + 1,
            })
            logger.info(f"Vision model loaded: {model_name}")
            return True

        except ImportError:
            logger.warning("mlx-vlm not installed, vision features disabled")
            return False
        except Exception as e:
            logger.error(f"Failed to load Vision model: {e}")
            return False

    async def load_diarization(self) -> bool:
        """Load pyannote diarization model (kept in memory across jobs)."""
        if self.is_loaded(ModelName.DIARIZATION):
            return True

        if not self._can_load_model(ModelName.DIARIZATION):
            if not self._unload_lower_priority_models(ModelName.DIARIZATION):
                raise MemoryError("Not enough memory to load Diarization model")

        try:
            import os
            import torch
            import torch.serialization

            hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN") or ""
            if not hf_token:
                logger.warning("HF_TOKEN not set, diarization may fail")
                return False

            # PyTorch 2.6+ defaults to weights_only=True but pyannote checkpoints
            # contain custom classes. We trust HuggingFace-hosted pyannote models.
            torch.serialization._default_to_weights_only = lambda pickle_module: False

            from pyannote.audio import Pipeline

            logger.info("Loading pyannote diarization pipeline (singleton)")

            # Set HF_TOKEN in env — pyannote reads it from there.
            # Passing use_auth_token= can cause errors with newer huggingface_hub.
            os.environ["HF_TOKEN"] = hf_token
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
            )

            device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
            pipeline.to(device)

            self._models[ModelName.DIARIZATION] = pipeline
            self._model_status[ModelName.DIARIZATION].update({
                "loaded": True,
                "memory_mb": ModelConfig.CONFIGS[ModelName.DIARIZATION]["memory_mb"],
                "device": str(device),
                "last_used": datetime.now(),
                "load_count": self._model_status[ModelName.DIARIZATION]["load_count"] + 1,
            })
            logger.info("Diarization pipeline loaded on %s", device)
            return True

        except Exception as e:
            logger.error(f"Failed to load Diarization model: {e}")
            return False

    async def load_embedding(self) -> bool:
        """Load pyannote speaker embedding model for voice fingerprinting."""
        if self.is_loaded(ModelName.EMBEDDING):
            return True

        if not self._can_load_model(ModelName.EMBEDDING):
            if not self._unload_lower_priority_models(ModelName.EMBEDDING):
                raise MemoryError("Not enough memory to load Embedding model")

        try:
            import os
            import torch
            import torch.serialization

            hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN") or ""
            if not hf_token:
                logger.warning("HF_TOKEN not set, embedding model may fail")
                return False

            torch.serialization._default_to_weights_only = lambda pickle_module: False

            from pyannote.audio import Inference

            logger.info("Loading pyannote speaker embedding model")
            os.environ["HF_TOKEN"] = hf_token
            inference = Inference("pyannote/embedding", window="whole")

            device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
            inference.to(device)

            self._models[ModelName.EMBEDDING] = inference
            self._model_status[ModelName.EMBEDDING].update({
                "loaded": True,
                "memory_mb": ModelConfig.CONFIGS[ModelName.EMBEDDING]["memory_mb"],
                "device": str(device),
                "last_used": datetime.now(),
                "load_count": self._model_status[ModelName.EMBEDDING]["load_count"] + 1,
            })
            logger.info("Speaker embedding model loaded on %s", device)
            return True

        except Exception as e:
            logger.error(f"Failed to load Embedding model: {e}")
            return False

    async def load_voxtral_local(self, model_path: str) -> bool:
        """Load Voxtral Local (mlx-audio) with ModelManager accounting (audit #12).

        Different `model_path` values (fp16 vs 4-bit) both map to VOXTRAL_LOCAL;
        we unload + reload if the caller asks for a different variant.
        """
        current = self._models.get(ModelName.VOXTRAL_LOCAL)
        if (
            self.is_loaded(ModelName.VOXTRAL_LOCAL)
            and isinstance(current, dict)
            and current.get("path") == model_path
        ):
            return True

        if self.is_loaded(ModelName.VOXTRAL_LOCAL):
            self.unload_model(ModelName.VOXTRAL_LOCAL)

        if not self._can_load_model(ModelName.VOXTRAL_LOCAL):
            if not self._unload_lower_priority_models(ModelName.VOXTRAL_LOCAL):
                raise MemoryError("Not enough memory to load Voxtral Local model")

        try:
            from mlx_audio.stt.utils import load as mlx_audio_load
            logger.info("Loading Voxtral Local model: %s", model_path)
            model = mlx_audio_load(model_path)
            mem_mb = ModelConfig.CONFIGS[ModelName.VOXTRAL_LOCAL]["memory_mb"]
            # 4-bit variants carry ~3.5 GB, not ~10 GB.
            if "4bit" in model_path.lower():
                mem_mb = 3500
            self._models[ModelName.VOXTRAL_LOCAL] = {"model": model, "path": model_path}
            self._model_status[ModelName.VOXTRAL_LOCAL].update({
                "loaded": True,
                "memory_mb": mem_mb,
                "device": "mps",
                "last_used": datetime.now(),
                "load_count": self._model_status[ModelName.VOXTRAL_LOCAL]["load_count"] + 1,
            })
            # Mirror into legacy state.* slots so existing readers stay coherent.
            state_mod = None
            try:
                import state as state_mod  # type: ignore
            except Exception:
                pass
            if state_mod is not None:
                state_mod._voxtral_local_model = model
                state_mod._voxtral_local_model_name = model_path
            return True
        except Exception as e:
            logger.error(f"Failed to load Voxtral Local model: {e}")
            return False

    def unload_model(self, model_name: ModelName) -> bool:
        """Explicitly unload a model to free memory."""
        if not self.is_loaded(model_name):
            return True

        config = ModelConfig.CONFIGS[model_name]
        if not config["unloadable"]:
            logger.warning(f"Model {model_name.value} is not unloadable")
            return False

        try:
            logger.info(f"Unloading model: {model_name.value}")

            # Delete model reference
            if model_name in self._models:
                del self._models[model_name]

            # Force garbage collection
            gc.collect()

            # For PyTorch models, also clear CUDA/MPS cache
            try:
                import torch
                if torch.backends.mps.is_available():
                    torch.mps.empty_cache()
            except Exception:
                pass

            self._model_status[model_name].update({
                "loaded": False,
                "memory_mb": 0,
            })

            if model_name == ModelName.VOXTRAL_LOCAL:
                try:
                    import state as state_mod  # type: ignore
                    state_mod._voxtral_local_model = None
                    state_mod._voxtral_local_model_name = None
                except Exception:
                    pass

            return True

        except Exception as e:
            logger.error(f"Failed to unload {model_name.value}: {e}")
            return False

    @contextmanager
    def ensure_model(self, model_name: ModelName) -> ContextManager[Any]:
        """
        Context manager that ensures a model is loaded for an operation.
        Automatically manages loading if needed.
        """
        import asyncio

        # Load model if not already loaded. Audit #7: always use a fresh loop
        # — the old `asyncio.get_event_loop()` path could race with the running
        # server loop when invoked from a thread.
        if not self.is_loaded(model_name):
            _loop = asyncio.new_event_loop()
            try:
                if model_name == ModelName.WHISPER:
                    _loop.run_until_complete(self.load_whisper())
                elif model_name == ModelName.VISION:
                    _loop.run_until_complete(self.load_vision())
                elif model_name == ModelName.DIARIZATION:
                    _loop.run_until_complete(self.load_diarization())
                elif model_name == ModelName.EMBEDDING:
                    _loop.run_until_complete(self.load_embedding())
            finally:
                _loop.close()

        # Update last used
        self._model_status[model_name]["last_used"] = datetime.now()

        try:
            yield self._models.get(model_name)
        finally:
            # Optional: unload after use for vision model (heavy)
            # For now, keep loaded until memory pressure
            pass

    def get_status(self) -> dict:
        """Get current status of all models."""
        return {
            "models": {
                name.value: {
                    "loaded": status["loaded"],
                    "memory_mb": status["memory_mb"],
                    "device": status["device"],
                    "last_used": status["last_used"].isoformat() if status["last_used"] else None,
                }
                for name, status in self._model_status.items()
            },
            "total_memory_used_mb": self.get_total_loaded_memory_mb(),
            "available_memory_mb": self.get_available_memory_mb(),
            "memory_threshold_mb": self.MEMORY_THRESHOLD_MB,
        }


# Global singleton instance
_model_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """Get or create the global ModelManager instance."""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager
