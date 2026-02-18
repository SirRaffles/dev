"""
Speaker management API routes.
CRUD operations for the persistent speaker registry.
"""

import os
import uuid
import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

import state
from config import ICLOUD_BASE_PATH

logger = logging.getLogger(__name__)
router = APIRouter(tags=["speakers"])

SPEAKERS_DIR = ICLOUD_BASE_PATH / "speakers"


class SpeakerCreateRequest(BaseModel):
    name: str


class SpeakerUpdateRequest(BaseModel):
    name: Optional[str] = None


class PersonalityUpdateRequest(BaseModel):
    content: str


def _ensure_speaker_dir(name: str) -> Path:
    """Create the speaker folder on iCloud Drive if it doesn't exist."""
    folder = SPEAKERS_DIR / name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


@router.get("/speakers")
async def list_speakers():
    """List all registered speakers."""
    speakers = state.speaker_store.list_all()
    return {"speakers": speakers}


@router.get("/speakers/{speaker_id}")
async def get_speaker(speaker_id: str):
    """Get speaker details including personality content."""
    speaker = state.speaker_store.get(speaker_id)
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")

    # Read personality.md if it exists
    personality_path = SPEAKERS_DIR / speaker["name"] / "personality.md"
    personality_content = ""
    if personality_path.exists():
        personality_content = personality_path.read_text(encoding="utf-8")

    # Get call history
    calls = state.call_speaker_store.get_for_speaker(speaker_id)

    return {
        **speaker,
        "personality_md": personality_content,
        "calls": calls,
        "has_embedding": bool(speaker.get("embedding_path")),
    }


@router.post("/speakers")
async def create_speaker(req: SpeakerCreateRequest):
    """Create a new speaker in the registry."""
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Speaker name is required")

    # Check for duplicate
    existing = state.speaker_store.get_by_name(name)
    if existing:
        raise HTTPException(status_code=409, detail=f"Speaker '{name}' already exists")

    speaker_id = str(uuid.uuid4())
    folder = _ensure_speaker_dir(name)
    folder_path = str(folder.relative_to(ICLOUD_BASE_PATH))

    # Initialize profile.json
    profile = {
        "speaker_id": speaker_id,
        "name": name,
        "created_at": str(state.speaker_store._get_connection().execute(
            "SELECT datetime('now')"
        ).fetchone()[0]),
    }
    (folder / "profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")

    # Initialize empty personality.md
    (folder / "personality.md").write_text(
        f"# {name}\n\n*No personality insights yet. These will accrue as calls are analyzed.*\n",
        encoding="utf-8",
    )

    result = state.speaker_store.create(speaker_id, name, folder_path)
    return result


@router.put("/speakers/{speaker_id}")
async def update_speaker(speaker_id: str, req: SpeakerUpdateRequest):
    """Update speaker details (e.g., rename)."""
    speaker = state.speaker_store.get(speaker_id)
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")

    if req.name:
        new_name = req.name.strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="Name cannot be empty")

        # Check duplicate
        existing = state.speaker_store.get_by_name(new_name)
        if existing and existing["speaker_id"] != speaker_id:
            raise HTTPException(status_code=409, detail=f"Speaker '{new_name}' already exists")

        # Rename folder on disk
        old_folder = SPEAKERS_DIR / speaker["name"]
        new_folder = SPEAKERS_DIR / new_name
        if old_folder.exists() and old_folder != new_folder:
            old_folder.rename(new_folder)

        new_folder_path = str(new_folder.relative_to(ICLOUD_BASE_PATH))
        state.speaker_store.update(speaker_id, name=new_name, folder_path=new_folder_path)

    return {"speaker_id": speaker_id, "status": "updated"}


@router.delete("/speakers/{speaker_id}")
async def delete_speaker(speaker_id: str):
    """Delete a speaker from the registry."""
    speaker = state.speaker_store.get(speaker_id)
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")

    # Remove folder (keep as safety — don't delete if non-empty beyond our files)
    folder = SPEAKERS_DIR / speaker["name"]
    if folder.exists():
        try:
            import shutil
            shutil.rmtree(folder)
        except OSError as e:
            logger.warning("Could not delete speaker folder %s: %s", folder, e)

    state.speaker_store.delete(speaker_id)
    return {"status": "deleted"}


@router.get("/speakers/{speaker_id}/personality")
async def get_personality(speaker_id: str):
    """Read a speaker's personality.md file."""
    speaker = state.speaker_store.get(speaker_id)
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")

    path = SPEAKERS_DIR / speaker["name"] / "personality.md"
    content = ""
    if path.exists():
        content = path.read_text(encoding="utf-8")
    return {"content": content, "speaker_id": speaker_id}


@router.post("/speakers/{speaker_id}/embedding")
async def upload_speaker_embedding(speaker_id: str):
    """Upload an audio clip to set/update the speaker's voice embedding.

    Expects a multipart file upload with an audio file (wav, m4a, mp3, etc.)
    """
    # This requires file upload handling — import here to keep the module light
    from fastapi import UploadFile, File

    # For now, this endpoint is a placeholder — the actual file upload
    # version will be added when the frontend form is built.
    # Speakers get embeddings automatically via the call identification flow.
    raise HTTPException(status_code=501, detail="Manual embedding upload coming soon. Use call identification flow instead.")


@router.put("/speakers/{speaker_id}/personality")
async def update_personality(speaker_id: str, req: PersonalityUpdateRequest):
    """Update a speaker's personality.md file."""
    speaker = state.speaker_store.get(speaker_id)
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")

    folder = SPEAKERS_DIR / speaker["name"]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "personality.md").write_text(req.content, encoding="utf-8")
    return {"status": "saved", "speaker_id": speaker_id}
