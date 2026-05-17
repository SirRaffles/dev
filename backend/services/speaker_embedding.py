"""
Speaker voice embedding extraction and matching service.

Uses pyannote/embedding to extract 512-dim speaker voice embeddings,
store them as .npy files, and match unknown speakers against the registry.
"""

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from config import ICLOUD_BASE_PATH, SPEAKER_MATCH_THRESHOLD, MIN_EMBEDDING_SEGMENT_SECONDS
import state

logger = logging.getLogger(__name__)

SPEAKERS_DIR = ICLOUD_BASE_PATH / "speakers"
UNKNOWN_DIR = SPEAKERS_DIR / "_unknown"


class SpeakerEmbeddingService:
    """Extract and compare speaker voice embeddings using pyannote."""

    EMBEDDING_DIM = 512

    def __init__(self):
        self._known_embeddings: Dict[str, np.ndarray] = {}  # name -> embedding
        self._cache_loaded = False

    def _get_embedding_model(self):
        """Get the pyannote embedding model via ModelManager."""
        from services.model_manager import get_model_manager, ModelName

        manager = get_model_manager()
        if not manager.is_loaded(ModelName.EMBEDDING):
            loop = asyncio.new_event_loop()
            try:
                loaded = loop.run_until_complete(manager.load_embedding())
            finally:
                loop.close()
            if not loaded:
                raise RuntimeError("Failed to load speaker embedding model")

        model = manager.get_model(ModelName.EMBEDDING)
        if model is None:
            raise RuntimeError("Speaker embedding model not available")
        return model

    def _load_known_embeddings(self):
        """Load all known speaker embeddings from disk into cache."""
        if self._cache_loaded:
            return

        self._known_embeddings.clear()
        if not SPEAKERS_DIR.exists():
            self._cache_loaded = True
            return

        for speaker_dir in SPEAKERS_DIR.iterdir():
            if not speaker_dir.is_dir() or speaker_dir.name.startswith("_"):
                continue

            npy_path = speaker_dir / "embedding.npy"
            if npy_path.exists():
                try:
                    embedding = np.load(str(npy_path))
                    self._known_embeddings[speaker_dir.name] = embedding
                except Exception as e:
                    logger.warning("Failed to load embedding for %s: %s", speaker_dir.name, e)

        self._cache_loaded = True
        logger.info("Loaded %d known speaker embeddings", len(self._known_embeddings))

    def invalidate_cache(self):
        """Force reload of known embeddings on next match operation."""
        self._cache_loaded = False

    def extract_embedding(self, audio_path: str, start: float, end: float) -> np.ndarray:
        """Extract a voice embedding from a specific audio segment.

        Args:
            audio_path: Path to the audio file.
            start: Start time in seconds.
            end: End time in seconds.

        Returns:
            512-dim numpy array (float32).
        """
        inference = self._get_embedding_model()

        # Use pyannote's crop parameter to extract from a specific segment
        from pyannote.core import Segment
        excerpt = Segment(start, end)
        embedding = inference.crop(audio_path, excerpt)

        # embedding shape is (1, 512) or (512,) depending on version
        emb = np.array(embedding).flatten().astype(np.float32)

        # Normalize to unit vector for cosine similarity
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm

        return emb

    def extract_speaker_embeddings(
        self, audio_path: str, speaker_turns: List[dict]
    ) -> Dict[str, np.ndarray]:
        """Extract one embedding per speaker label from diarization output.

        For each speaker, selects the longest contiguous segment (most
        representative voice sample), extracts the embedding from it.

        Args:
            audio_path: Path to the audio file.
            speaker_turns: List of diarization turns [{start, end, speaker}].

        Returns:
            Dict mapping speaker labels to embeddings: {"SPEAKER_00": np.array([...])}.
        """
        # Group turns by speaker and find the longest segment for each
        speaker_segments: Dict[str, List[dict]] = {}
        for turn in speaker_turns:
            label = turn.get("speaker", "Unknown")
            if label not in speaker_segments:
                speaker_segments[label] = []
            speaker_segments[label].append(turn)

        embeddings = {}
        for label, turns in speaker_segments.items():
            # Find the longest segment (most representative)
            best_turn = max(turns, key=lambda t: t["end"] - t["start"])
            duration = best_turn["end"] - best_turn["start"]

            if duration < MIN_EMBEDDING_SEGMENT_SECONDS:
                logger.warning(
                    "Speaker %s: longest segment %.1fs < %.1fs minimum, skipping embedding",
                    label, duration, MIN_EMBEDDING_SEGMENT_SECONDS,
                )
                continue

            try:
                emb = self.extract_embedding(audio_path, best_turn["start"], best_turn["end"])
                embeddings[label] = emb
                logger.info(
                    "Extracted embedding for %s (%.1fs segment)",
                    label, duration,
                )
            except Exception as e:
                logger.warning("Failed to extract embedding for %s: %s", label, e)

        return embeddings

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two embeddings."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    # Tiebreaker gap: when a "preferred" pick is within this many cosine
    # points of the global best match, we prefer the pick. Noise tolerance.
    PREFER_GAP = 0.03

    # Plan 5A: minimum cosine score for a 2nd-best candidate to be worth
    # suggesting in the Speaker Review reject-flow modal.
    RUNNER_UP_THRESHOLD = 0.4

    def match_speaker(
        self,
        embedding: np.ndarray,
        restrict_to_names: Optional[List[str]] = None,
        prefer_names: Optional[List[str]] = None,
    ) -> Tuple[Optional[str], float, Optional[Dict[str, object]]]:
        """Compare an embedding against known speakers.

        Args:
            restrict_to_names: hard-scope — only match against these names.
                Non-empty list = scoped mode; empty list or None = full registry.
            prefer_names: when in full-registry mode, bump these ahead of the
                global best match if they're within PREFER_GAP cosine points.

        Returns:
            (speaker_name, confidence, runner_up) — runner_up is a dict
            {"speaker_id": str|None, "name": str, "confidence": float} when a
            qualifying 2nd-best candidate (>= RUNNER_UP_THRESHOLD) exists,
            else None. (None, 0.0, None) when no speakers / no qualifying
            match.
        """
        self._load_known_embeddings()

        if not self._known_embeddings:
            return None, 0.0, None

        if restrict_to_names:
            # Filter a fresh dict — never mutate the shared cache.
            pool = {
                name: emb
                for name, emb in self._known_embeddings.items()
                if name in restrict_to_names
            }
        else:
            pool = self._known_embeddings

        if not pool:
            return None, 0.0, None

        best_name: Optional[str] = None
        best_score = 0.0
        second_name: Optional[str] = None
        second_score = 0.0
        for name, known_emb in pool.items():
            score = self.cosine_similarity(embedding, known_emb)
            if score > best_score:
                second_name, second_score = best_name, best_score
                best_name, best_score = name, score
            elif score > second_score:
                second_name, second_score = name, score

        # Tiebreaker only applies in full-registry mode (restrict_to is falsy).
        if not restrict_to_names and prefer_names and best_name not in prefer_names:
            # Find the best scorer among preferred picks.
            pref_best_name: Optional[str] = None
            pref_best_score = 0.0
            for name in prefer_names:
                emb = self._known_embeddings.get(name)
                if emb is None:
                    continue
                s = self.cosine_similarity(embedding, emb)
                if s > pref_best_score:
                    pref_best_score = s
                    pref_best_name = name
            if pref_best_name is not None and (best_score - pref_best_score) <= self.PREFER_GAP:
                best_name, best_score = pref_best_name, pref_best_score

        # Build runner-up dict — second best only if it clears the threshold.
        runner_up: Optional[Dict[str, object]] = None
        if second_name is not None and second_score >= self.RUNNER_UP_THRESHOLD:
            try:
                sp = state.speaker_store.get_by_name(second_name)
            except Exception:
                sp = None
            runner_up = {
                "speaker_id": sp["speaker_id"] if sp else None,
                "name": second_name,
                "confidence": round(float(second_score), 3),
            }

        if best_score >= SPEAKER_MATCH_THRESHOLD:
            return best_name, best_score, runner_up
        return None, best_score, runner_up

    def register_speaker(self, name: str, embedding: np.ndarray) -> str:
        """Create a new speaker with a voice embedding.

        Creates folder structure on iCloud Drive and DB entry.

        Returns:
            The new speaker_id.
        """
        speaker_id = str(uuid.uuid4())
        folder = SPEAKERS_DIR / name
        folder.mkdir(parents=True, exist_ok=True)
        folder_path = str(folder.relative_to(ICLOUD_BASE_PATH))

        # Save embedding
        npy_path = folder / "embedding.npy"
        np.save(str(npy_path), embedding)
        embedding_path = str(npy_path.relative_to(ICLOUD_BASE_PATH))

        # Save profile.json
        from datetime import datetime
        profile = {
            "speaker_id": speaker_id,
            "name": name,
            "created_at": datetime.now().isoformat(),
            "embedding_dim": len(embedding),
        }
        (folder / "profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")

        # Initialize personality.md
        if not (folder / "personality.md").exists():
            (folder / "personality.md").write_text(
                f"# {name}\n\n*No personality insights yet. These will accrue as calls are analyzed.*\n",
                encoding="utf-8",
            )

        # DB entry
        state.speaker_store.create(speaker_id, name, folder_path, embedding_path)

        # Update cache
        self._known_embeddings[name] = embedding
        logger.info("Registered new speaker: %s (id: %s)", name, speaker_id)

        return speaker_id

    def update_embedding(self, name: str, new_embedding: np.ndarray, alpha: float = 0.3):
        """Update a speaker's embedding using exponential moving average.

        new = alpha * sample + (1 - alpha) * existing

        This gradually improves the voiceprint as more samples are collected.

        Also persists `embedding_path` in the speaker_store so `has_embedding`
        flips to true the first time we capture a voice for an existing
        speaker who was created without one.
        """
        self._load_known_embeddings()

        if name in self._known_embeddings:
            existing = self._known_embeddings[name]
            updated = alpha * new_embedding + (1 - alpha) * existing
            # Re-normalize
            norm = np.linalg.norm(updated)
            if norm > 0:
                updated = updated / norm
        else:
            updated = new_embedding

        # Save to disk
        folder = SPEAKERS_DIR / name
        folder.mkdir(parents=True, exist_ok=True)
        npy_path = folder / "embedding.npy"
        np.save(str(npy_path), updated)

        # Reflect in the speaker_store so the Speakers UI + auto-match both
        # see the embedding. Missing DB row (or missing column) is non-fatal.
        try:
            speaker = state.speaker_store.get_by_name(name)
            if speaker:
                rel = str(npy_path.relative_to(ICLOUD_BASE_PATH))
                if speaker.get("embedding_path") != rel:
                    state.speaker_store.update(speaker["speaker_id"], embedding_path=rel)
        except Exception:
            logger.warning("Failed to persist embedding_path for %s", name, exc_info=True)

        # Update cache
        self._known_embeddings[name] = updated
        logger.info("Updated embedding for speaker: %s", name)

    def save_unknown_embedding(self, speaker_label: str, job_id: str, embedding: np.ndarray):
        """Save an unmatched speaker's embedding to the _unknown staging area."""
        UNKNOWN_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"{speaker_label}_{job_id}.npy"
        np.save(str(UNKNOWN_DIR / filename), embedding)
        logger.info("Saved unknown embedding: %s", filename)

    def get_unknown_embedding(self, speaker_label: str, job_id: str) -> Optional[np.ndarray]:
        """Load an unknown speaker's embedding from the staging area."""
        filename = f"{speaker_label}_{job_id}.npy"
        path = UNKNOWN_DIR / filename
        if path.exists():
            return np.load(str(path))
        return None

    def _ids_to_names(self, speaker_ids: Optional[List[str]]) -> Optional[List[str]]:
        """Resolve a list of speaker_ids to their names via speaker_store.

        Unknown / deleted ids are silently dropped. Empty input returns None.
        """
        if not speaker_ids:
            return None
        names: List[str] = []
        for sid in speaker_ids:
            if not sid:
                continue
            try:
                sp = state.speaker_store.get(sid)
            except Exception:
                sp = None
            if sp and sp.get("name"):
                names.append(sp["name"])
        return names or None

    def auto_identify_speakers(
        self,
        audio_path: str,
        speaker_turns: List[dict],
        job_id: str,
        restrict_to_ids: Optional[List[str]] = None,
        prefer_ids: Optional[List[str]] = None,
    ) -> Dict[str, dict]:
        """Full auto-identification pipeline.

        1. Extract embeddings for each diarization label
        2. Match each against known speakers (optionally scoped / biased)
        3. Save unmatched embeddings to _unknown staging
        4. Return mapping with confidence scores

        Args:
            audio_path: Path to the audio file.
            speaker_turns: Diarization output [{start, end, speaker}].
            job_id: Job ID for staging unknown embeddings.
            restrict_to_ids: hard-scope to these speaker_ids when provided
                (typically passed when the user pre-picked exactly the
                number of speakers they expect).
            prefer_ids: tiebreaker bias toward these speaker_ids when the
                global-best is within PREFER_GAP cosine points.

        Returns:
            Dict: {
                "SPEAKER_00": {"name": "David", "confidence": 0.89,
                               "speaker_id": "...", "matched": True,
                               "source": "pick"|"registry"},
                "SPEAKER_01": {"name": None, "confidence": 0.0,
                               "speaker_id": None, "matched": False}
            }
        """
        restrict_names = self._ids_to_names(restrict_to_ids)
        prefer_names = self._ids_to_names(prefer_ids)

        embeddings = self.extract_speaker_embeddings(audio_path, speaker_turns)

        results = {}
        for label, emb in embeddings.items():
            matched_name, confidence, runner_up = self.match_speaker(
                emb,
                restrict_to_names=restrict_names,
                prefer_names=prefer_names,
            )

            if matched_name:
                speaker = state.speaker_store.get_by_name(matched_name)
                speaker_id = speaker["speaker_id"] if speaker else None
                from_pick = bool(
                    (restrict_names and matched_name in restrict_names)
                    or (prefer_names and matched_name in prefer_names)
                )
                results[label] = {
                    "name": matched_name,
                    "confidence": round(confidence, 3),
                    "speaker_id": speaker_id,
                    "matched": True,
                    "source": "pick" if from_pick else "registry",
                    "runner_up": runner_up,
                }
            else:
                # Save to unknown staging for later manual identification
                self.save_unknown_embedding(label, job_id, emb)
                results[label] = {
                    "name": None,
                    "confidence": round(confidence, 3),
                    "speaker_id": None,
                    "matched": False,
                    "source": None,
                    "runner_up": runner_up,
                }

        # Also include speakers that had segments too short for embedding
        speaker_labels = {t["speaker"] for t in speaker_turns}
        for label in speaker_labels:
            if label not in results:
                results[label] = {
                    "name": None,
                    "confidence": 0.0,
                    "speaker_id": None,
                    "matched": False,
                    "source": None,
                    "runner_up": None,
                    "note": "Segment too short for voice embedding",
                }

        return results
