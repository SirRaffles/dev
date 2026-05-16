"""Persistent global glossary helper (B4).

Owns the lifecycle of <ICLOUD_BASE_PATH>/contexts/_global.md — a single
markdown file whose terms are auto-injected into every transcription's
initial_prompt and every refinement run's known-context block.
"""

from __future__ import annotations

import logging
import os
import threading
import unicodedata
from typing import List, Optional

from config import ICLOUD_BASE_PATH
from services.transcription import derive_context_terms

logger = logging.getLogger(__name__)

GLOBAL_GLOSSARY_PATH = ICLOUD_BASE_PATH / "contexts" / "_global.md"
PENDING_SECTION_HEADER = "## Auto-learned (pending review)"

# Serializes read-modify-write on _global.md to prevent races between
# concurrent _run_post_refinement_learning callbacks (Plan 2).
_APPEND_LOCK = threading.Lock()


def load_global_glossary() -> Optional[str]:
    """Return the full contents of _global.md, or None if missing/empty."""
    if not GLOBAL_GLOSSARY_PATH.is_file():
        return None
    try:
        text = GLOBAL_GLOSSARY_PATH.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        logger.warning("Failed to read %s: %s", GLOBAL_GLOSSARY_PATH, exc)
        return None
    return text if text.strip() else None


def load_global_glossary_terms() -> List[str]:
    """Return proper-noun terms extracted from _global.md, or [] if missing."""
    text = load_global_glossary()
    if not text:
        return []
    return derive_context_terms(text, limit=200)


def _normalize_term(term: str) -> str:
    """Case-fold + collapse whitespace + strip trailing punctuation for de-dup."""
    normalized = unicodedata.normalize("NFC", term).strip()
    normalized = " ".join(normalized.split())
    normalized = normalized.rstrip(".,;:!?")
    return normalized.lower()


def _existing_normalized_terms(body: str) -> set[str]:
    """Extract all known-term normalized strings from _global.md body for de-dup.

    Sources of truth:
      (a) bullet leads: ``- TERM (...)`` or ``- TERM`` — take text before ``(``.
      (b) comma-separated prose lines (the seed Active format like
          ``Manukai, DMG Mori, Starrag.``) — split by ``,`` and normalize each.

    Heading lines (starting with ``#``) and blank lines are ignored.
    """
    existing: set[str] = set()
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("- "):
            entry = line[2:]
            head = entry.split("(", 1)[0]
            norm = _normalize_term(head)
            if norm:
                existing.add(norm)
            continue

        # Comma-separated prose under Active (or anywhere): treat each token
        # as a candidate term.
        for chunk in line.split(","):
            norm = _normalize_term(chunk)
            if norm:
                existing.add(norm)
    return existing


def append_auto_learned_term(term: str, source_job_id: str, context_phrase: str) -> None:
    """Append `term` to the pending-review section of _global.md.

    - Creates the file with the standard template if it doesn't exist.
    - Creates the pending-review section if missing.
    - Idempotent: no-op if a case-insensitive normalized match already appears
      as a bullet lead or comma-separated token elsewhere in the file.
    - Atomic write via os.replace + sibling tmp file; serialized via _APPEND_LOCK
      so concurrent jobs cannot lose terms.
    - Never raises — logs and returns on any IO failure.
    """
    canonical = term.strip()
    if not canonical:
        return
    norm = _normalize_term(canonical)
    if not norm:
        return

    with _APPEND_LOCK:
        tmp_path = GLOBAL_GLOSSARY_PATH.with_suffix(GLOBAL_GLOSSARY_PATH.suffix + ".tmp")
        try:
            GLOBAL_GLOSSARY_PATH.parent.mkdir(parents=True, exist_ok=True)
            if GLOBAL_GLOSSARY_PATH.is_file():
                body = GLOBAL_GLOSSARY_PATH.read_text(encoding="utf-8", errors="ignore")
            else:
                body = (
                    "# Global Glossary\n\n"
                    "Terms in this document are auto-injected into every transcription's\n"
                    "initial_prompt and into the refinement LLM's known-context block.\n\n"
                    "## Active\n\n"
                    "(Add domain-specific proper nouns, company names, jargon, etc.)\n\n"
                )

            if norm in _existing_normalized_terms(body):
                return

            if PENDING_SECTION_HEADER not in body:
                if not body.endswith("\n"):
                    body += "\n"
                body += f"\n{PENDING_SECTION_HEADER}\n\n"

            entry = f"- {canonical} (from {source_job_id}: {context_phrase[:120]})\n"
            head, _, tail = body.partition(PENDING_SECTION_HEADER)
            rebuilt = head + PENDING_SECTION_HEADER + "\n" + entry + tail.lstrip("\n")

            tmp_path.write_text(rebuilt, encoding="utf-8")
            os.replace(tmp_path, GLOBAL_GLOSSARY_PATH)
        except OSError as exc:
            logger.warning("Failed to append auto-learned term %r: %s", canonical, exc)
        finally:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
