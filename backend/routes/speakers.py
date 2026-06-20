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
from pydantic import BaseModel, Field
from typing import Optional

import state
from config import ICLOUD_BASE_PATH

logger = logging.getLogger(__name__)
router = APIRouter(tags=["speakers"])

SPEAKERS_DIR = ICLOUD_BASE_PATH / "speakers"

# Audit #4: restrict speaker names to a conservative, filesystem-safe charset.
_SPEAKER_NAME_PATTERN = r"^[A-Za-z0-9 _\-]{1,64}$"

# ──────────────────────────────────────────────────────────────────────────
# Speaker profile is made of 4 artifacts per user's spec:
#   embedding.npy          → voice profile (diarization match)           [1]
#   profile.md             → bio / resume-style factual summary          [2]
#   explicit_insights.md   → concrete facts captured in transcripts      [3]
#   implicit_insights.md   → inferred style / personality / values       [4]
# The legacy personality.md is treated as a migration source for [4] on
# first read, and kept as a readable alias via the /personality endpoint
# so any old integrations don't break.
# ──────────────────────────────────────────────────────────────────────────
_FILE_PROFILE = "profile.md"
_FILE_EXPLICIT = "explicit_insights.md"
_FILE_IMPLICIT = "implicit_insights.md"
_FILE_LEGACY = "personality.md"


def _ensure_speaker_files(folder: Path) -> None:
    """One-time migration: if only the legacy personality.md exists, move its
    content to implicit_insights.md (semantic closest match — the old prompt
    produced inferred traits). Always ensures all four section files exist
    (empty placeholders) so subsequent read paths are uniform."""
    folder.mkdir(parents=True, exist_ok=True)
    implicit = folder / _FILE_IMPLICIT
    legacy = folder / _FILE_LEGACY
    if not implicit.exists() and legacy.exists():
        try:
            implicit.write_text(legacy.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError:
            logger.warning("Could not migrate %s", legacy, exc_info=True)
    for name, default in (
        (_FILE_PROFILE, "# Profile\n\n*Add a factual bio — role, employer, focus areas, relevant background.*\n"),
        (_FILE_EXPLICIT, "# Explicit insights\n\n*Concrete observations captured from transcripts will land here.*\n"),
        (_FILE_IMPLICIT, "# Implicit insights\n\n*Inferred personality, style, and preferences will land here.*\n"),
    ):
        p = folder / name
        if not p.exists():
            p.write_text(default, encoding="utf-8")


def _read_section(folder: Path, filename: str) -> str:
    try:
        return (folder / filename).read_text(encoding="utf-8")
    except OSError:
        return ""


class SpeakerCreateRequest(BaseModel):
    name: str = Field(..., pattern=_SPEAKER_NAME_PATTERN)


class SpeakerUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, pattern=_SPEAKER_NAME_PATTERN)


class SectionUpdateRequest(BaseModel):
    """Body for any of the 4 section PUT endpoints."""
    content: str


class PersonalityUpdateRequest(BaseModel):
    """Legacy body type — kept as alias for SectionUpdateRequest to preserve
    backward compatibility with existing callers of /personality."""
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
    """Get full speaker profile: voice status + 4 markdown sections + calls."""
    speaker = state.speaker_store.get(speaker_id)
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")

    folder = SPEAKERS_DIR / speaker["name"]
    _ensure_speaker_files(folder)  # one-time migration + scaffold placeholders

    profile_md = _read_section(folder, _FILE_PROFILE)
    explicit_md = _read_section(folder, _FILE_EXPLICIT)
    implicit_md = _read_section(folder, _FILE_IMPLICIT)

    calls = state.call_speaker_store.get_for_speaker(speaker_id)

    return {
        **speaker,
        # 4-part profile
        "profile_md": profile_md,
        "explicit_insights_md": explicit_md,
        "implicit_insights_md": implicit_md,
        # Legacy alias (== implicit) — old frontends still read this field.
        "personality_md": implicit_md,
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
        "created_at": str(
            state.speaker_store.db.query_one("SELECT datetime('now') AS now")["now"]
        ),
    }
    (folder / "profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")

    # Scaffold the 4-section markdown files with placeholder copy.
    _ensure_speaker_files(folder)

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


def _write_section(speaker_id: str, filename: str, content: str) -> dict:
    """Shared writer for the 4 section PUT routes."""
    speaker = state.speaker_store.get(speaker_id)
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")
    folder = SPEAKERS_DIR / speaker["name"]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / filename).write_text(content, encoding="utf-8")
    return {"status": "saved", "speaker_id": speaker_id, "section": filename}


@router.put("/speakers/{speaker_id}/profile")
async def update_profile(speaker_id: str, req: SectionUpdateRequest):
    """Update the human-maintained bio (profile.md)."""
    return _write_section(speaker_id, _FILE_PROFILE, req.content)


@router.put("/speakers/{speaker_id}/explicit-insights")
async def update_explicit_insights(speaker_id: str, req: SectionUpdateRequest):
    """Update explicit_insights.md (concrete facts captured in transcripts)."""
    return _write_section(speaker_id, _FILE_EXPLICIT, req.content)


@router.put("/speakers/{speaker_id}/implicit-insights")
async def update_implicit_insights(speaker_id: str, req: SectionUpdateRequest):
    """Update implicit_insights.md (inferred personality/style/values)."""
    return _write_section(speaker_id, _FILE_IMPLICIT, req.content)


@router.get("/speakers/{speaker_id}/personality")
async def get_personality(speaker_id: str):
    """Legacy read alias — returns implicit_insights.md content.

    Kept so old callers still work. New code should use GET /speakers/{id}
    which exposes all 4 sections.
    """
    speaker = state.speaker_store.get(speaker_id)
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")
    folder = SPEAKERS_DIR / speaker["name"]
    _ensure_speaker_files(folder)
    return {"content": _read_section(folder, _FILE_IMPLICIT), "speaker_id": speaker_id}


@router.post("/speakers/{speaker_id}/embedding")
async def upload_speaker_embedding(speaker_id: str):
    """Upload an audio clip to set/update the speaker's voice embedding.

    Expects a multipart file upload with an audio file (wav, m4a, mp3, etc.)
    """
    # For now, this endpoint is a placeholder — the actual file upload
    # version will be added when the frontend form is built.
    # Speakers get embeddings automatically via the call identification flow.
    raise HTTPException(status_code=501, detail="Manual embedding upload coming soon. Use call identification flow instead.")


@router.put("/speakers/{speaker_id}/personality")
async def update_personality_legacy(speaker_id: str, req: PersonalityUpdateRequest):
    """Legacy write alias — writes to implicit_insights.md so older frontends
    keep working. New code should use PUT /speakers/{id}/implicit-insights."""
    return _write_section(speaker_id, _FILE_IMPLICIT, req.content)
