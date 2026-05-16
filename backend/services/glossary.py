"""Persistent global glossary helper (B4).

Owns the lifecycle of <ICLOUD_BASE_PATH>/contexts/_global.md — a single
markdown file whose terms are auto-injected into every transcription's
initial_prompt and every refinement run's known-context block.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from config import ICLOUD_BASE_PATH
from services.transcription import derive_context_terms

logger = logging.getLogger(__name__)

GLOBAL_GLOSSARY_PATH = ICLOUD_BASE_PATH / "contexts" / "_global.md"
PENDING_SECTION_HEADER = "## Auto-learned (pending review)"


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
    import unicodedata
    normalized = unicodedata.normalize("NFC", term).strip()
    normalized = " ".join(normalized.split())
    normalized = normalized.rstrip(".,;:!?")
    return normalized.lower()


def append_auto_learned_term(term: str, source_job_id: str, context_phrase: str) -> None:
    """Append `term` to the pending-review section of _global.md.

    - Creates the file with the standard template if it doesn't exist.
    - Creates the pending-review section if missing.
    - Idempotent: no-op if a case-insensitive normalized match already appears
      anywhere in the file (active or pending).
    - Never raises — logs and returns on any IO failure.
    """
    canonical = term.strip()
    if not canonical:
        return
    norm = _normalize_term(canonical)
    if not norm:
        return

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

        for line in body.splitlines():
            if norm and norm in _normalize_term(line):
                return

        if PENDING_SECTION_HEADER not in body:
            if not body.endswith("\n"):
                body += "\n"
            body += f"\n{PENDING_SECTION_HEADER}\n\n"

        entry = f"- {canonical} (from {source_job_id}: {context_phrase[:120]})\n"
        head, _, tail = body.partition(PENDING_SECTION_HEADER)
        rebuilt = head + PENDING_SECTION_HEADER + "\n" + entry + tail.lstrip("\n")

        GLOBAL_GLOSSARY_PATH.write_text(rebuilt, encoding="utf-8")
    except OSError as exc:
        logger.warning("Failed to append auto-learned term %r: %s", canonical, exc)
