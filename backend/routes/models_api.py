"""
Model management API routes: list, preload, unload, status.
"""

import os
import time
from typing import List

from fastapi import APIRouter, HTTPException, Query

from config import SUPPORTED_LANGUAGES, MLX_MODELS, PARAKEET_MODEL, VOXTRAL_MODELS
from services.model_manager import get_model_manager, ModelName
import state

router = APIRouter()


@router.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "model_loaded": state.whisper_model_ready,
        "model_type": "MLX-Whisper (GPU-accelerated)",
        "model_path": state.whisper_model_path,
        "diarization_available": bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")),
        "supported_languages": SUPPORTED_LANGUAGES,
        "message": "Transcription API is running with MLX-Whisper"
    }


@router.get("/health")
async def health():
    """Detailed health check with model functionality verification."""
    is_ready = state.whisper_model_ready
    status = "healthy" if is_ready else "degraded"

    uptime_seconds = None
    if state.startup_time:
        uptime_seconds = int(time.time() - state.startup_time)

    gpu_available = False
    try:
        import mlx.core as mx
        gpu_available = mx.metal.is_available()
    except Exception:
        pass

    return {
        "status": status,
        "model_loaded": state.whisper_model_ready,
        "model_functional": is_ready,
        "model_type": "MLX-Whisper",
        "model_path": state.whisper_model_path,
        "gpu_available": gpu_available,
        "diarization_available": bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")),
        "voxtral_available": state._voxtral_available,
        "engines": {
            "whisper": {"available": state.whisper_model_ready, "type": "local"},
            "voxtral-api": {"available": state._voxtral_available, "type": "cloud"},
        },
        "active_jobs": state.job_store.get_active_count(),
        "total_jobs": len(state.job_store),
        "uptime_seconds": uptime_seconds,
        "supported_languages": list(SUPPORTED_LANGUAGES.keys())
    }


@router.get("/models")
async def list_models():
    """List available transcription models with descriptions."""
    models = [
        {"id": key, "path": val["path"], "description": val["description"], "engine": "whisper"}
        for key, val in MLX_MODELS.items()
    ]

    if state._parakeet_available:
        models.append({
            "id": "parakeet",
            "path": PARAKEET_MODEL["path"],
            "description": PARAKEET_MODEL["description"],
            "language": "en",
            "engine": "whisper",
        })

    if state._voxtral_available:
        for key, val in VOXTRAL_MODELS.items():
            models.append({
                "id": key,
                "api_id": val["api_id"],
                "description": val["description"],
                "engine": val["engine"],
            })

    return {
        "models": models,
        "default": "large-v3-turbo",
        "parakeet_available": state._parakeet_available,
        "voxtral_available": state._voxtral_available,
    }


@router.get("/models/status")
async def get_models_status():
    """Get current model loading status and memory usage."""
    model_manager = get_model_manager()
    return model_manager.get_status()


@router.post("/models/preload")
async def preload_models(
    models: List[str] = Query(..., description="Models to preload: whisper, vision, diarization"),
):
    """Preload models for faster processing."""
    model_manager = get_model_manager()
    results = {}

    for model_name in models:
        try:
            if model_name == "whisper":
                success = await model_manager.load_whisper()
            elif model_name == "vision":
                success = await model_manager.load_vision()
            elif model_name == "diarization":
                success = await model_manager.load_diarization()
            else:
                results[model_name] = {"success": False, "error": "Unknown model"}
                continue

            results[model_name] = {"success": success}
        except Exception as e:
            results[model_name] = {"success": False, "error": str(e)}

    return {"results": results, "status": model_manager.get_status()}


@router.post("/models/unload")
async def unload_models(
    models: List[str] = Query(..., description="Models to unload: vision, diarization"),
):
    """Unload models to free memory."""
    model_manager = get_model_manager()
    results = {}

    model_mapping = {
        "whisper": ModelName.WHISPER,
        "vision": ModelName.VISION,
        "diarization": ModelName.DIARIZATION,
    }

    for model_name in models:
        if model_name not in model_mapping:
            results[model_name] = {"success": False, "error": "Unknown model"}
            continue

        try:
            success = model_manager.unload_model(model_mapping[model_name])
            results[model_name] = {"success": success}
        except Exception as e:
            results[model_name] = {"success": False, "error": str(e)}

    return {"results": results, "status": model_manager.get_status()}
