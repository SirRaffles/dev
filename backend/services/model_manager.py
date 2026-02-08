"""
Model lifecycle management with memory-aware loading/unloading.

Manages MLX-Whisper, GLM-4.6V-Flash, and Pyannote models with:
- Sequential loading to avoid OOM
- Memory tracking
- On-demand loading with automatic unloading
"""
import gc
import logging
from typing import Dict, Optional, Any, ContextManager
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
import platform
import subprocess

logger = logging.getLogger(__name__)


class ModelName(str, Enum):
    WHISPER = "whisper"
    VISION = "vision"
    DIARIZATION = "diarization"


class ModelConfig:
    """Configuration for each model."""
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

    def get_available_memory_mb(self) -> int:
        """Get available system memory in MB."""
        if platform.system() == "Darwin":
            # macOS: Use vm_stat
            try:
                result = subprocess.run(
                    ["vm_stat"], capture_output=True, text=True
                )
                lines = result.stdout.split("\n")
                # Parse page size from first line of vm_stat output
                page_size = 16384  # Default for Apple Silicon
                if lines and "page size of" in lines[0]:
                    try:
                        page_size = int(lines[0].split("page size of")[1].strip().split()[0])
                    except (ValueError, IndexError):
                        pass

                free_pages = 0
                for line in lines:
                    if "Pages free" in line:
                        free_pages = int(line.split(":")[1].strip().rstrip("."))
                        break

                return (free_pages * page_size) // (1024 * 1024)
            except Exception:
                return 8000  # Conservative default
        else:
            # Linux: Use /proc/meminfo
            try:
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        if "MemAvailable" in line:
                            return int(line.split()[1]) // 1024
            except Exception:
                return 8000

        return 8000  # Default fallback

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
        """Load MLX-Whisper model."""
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
        """Load pyannote diarization model."""
        if self.is_loaded(ModelName.DIARIZATION):
            return True

        if not self._can_load_model(ModelName.DIARIZATION):
            if not self._unload_lower_priority_models(ModelName.DIARIZATION):
                raise MemoryError("Not enough memory to load Diarization model")

        try:
            import os
            from pyannote.audio import Pipeline
            import torch

            hf_token = os.environ.get("HF_TOKEN")
            if not hf_token:
                logger.warning("HF_TOKEN not set, diarization may fail")

            logger.info("Loading pyannote diarization pipeline")

            device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=hf_token,
            )
            pipeline.to(device)

            self._models[ModelName.DIARIZATION] = pipeline
            self._model_status[ModelName.DIARIZATION].update({
                "loaded": True,
                "memory_mb": ModelConfig.CONFIGS[ModelName.DIARIZATION]["memory_mb"],
                "device": str(device),
                "last_used": datetime.now(),
                "load_count": self._model_status[ModelName.DIARIZATION]["load_count"] + 1,
            })
            return True

        except Exception as e:
            logger.error(f"Failed to load Diarization model: {e}")
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

        # Load model if not already loaded
        if not self.is_loaded(model_name):
            loop = asyncio.get_event_loop()

            if model_name == ModelName.WHISPER:
                loop.run_until_complete(self.load_whisper())
            elif model_name == ModelName.VISION:
                loop.run_until_complete(self.load_vision())
            elif model_name == ModelName.DIARIZATION:
                loop.run_until_complete(self.load_diarization())

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
