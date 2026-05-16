"""
Transcript refinement service.

Post-processes Whisper transcripts to:
- Identify speakers by name (replacing SPEAKER_00, SPEAKER_01, etc.)
- Correct misspelled proper nouns, names, and technical terms
- Verify uncertain terms via web search

Uses Claude CLI (Max subscription) for analysis and DuckDuckGo for verification.
"""

import json
import logging
import re
import shutil
import subprocess
from typing import List, Optional

logger = logging.getLogger(__name__)

# JSON schema for Claude's analysis response
ANALYSIS_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "language": {
            "type": "string",
            "description": "ISO 639-1 language code of the transcript"
        },
        "domain": {
            "type": "string",
            "description": "Brief description of the conversation domain/topic"
        },
        "summary": {
            "type": "string",
            "description": "1-2 sentence summary of the conversation"
        },
        "speakers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description": "Original speaker label (e.g. SPEAKER_00)"},
                    "name": {"type": "string", "description": "Identified name or descriptive label"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "reasoning": {"type": "string", "description": "Why this identification was made"}
                },
                "required": ["label", "name", "confidence", "reasoning"]
            }
        },
        "corrections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "original": {"type": "string", "description": "The misspelled or incorrect term"},
                    "corrected": {"type": "string", "description": "The corrected term"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]}
                },
                "required": ["original", "corrected", "confidence"]
            }
        },
        "uncertain_terms": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Terms that may be misspelled but need web verification"
        }
    },
    "required": ["language", "domain", "summary", "speakers", "corrections", "uncertain_terms"]
})

FINALIZE_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "additional_corrections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "original": {"type": "string"},
                    "corrected": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]}
                },
                "required": ["original", "corrected", "confidence"]
            }
        }
    },
    "required": ["additional_corrections"]
})


def _find_claude_cli() -> Optional[str]:
    """Find the claude CLI binary."""
    return shutil.which("claude")


def _run_claude(prompt: str, schema: str, claude_path: str, timeout: int = 120) -> dict:
    """
    Run claude CLI in pipe mode with structured JSON output.

    Returns parsed JSON response.
    Raises RuntimeError on failure.
    """
    cmd = [
        claude_path, "-p",
        "--model", "haiku",
        "--output-format", "json",
        "--max-turns", "1",
        "--no-session-persistence",
        prompt,
    ]

    logger.debug("Running claude CLI: %s", " ".join(cmd[:6]) + " ...")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Claude CLI timed out after {timeout}s")

    if result.returncode != 0:
        stderr = result.stderr[:500] if result.stderr else "(no stderr)"
        raise RuntimeError(f"Claude CLI failed (exit {result.returncode}): {stderr}")

    stdout = result.stdout.strip()
    if not stdout:
        raise RuntimeError("Claude CLI returned empty output")

    # Parse the JSON wrapper from --output-format json
    try:
        wrapper = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Claude CLI returned invalid JSON: {e}\nOutput: {stdout[:300]}")

    # Extract the text content from the response
    text_content = ""
    if isinstance(wrapper, dict):
        # --output-format json returns {"result": "...", ...} or similar
        text_content = wrapper.get("result", "")
        if not text_content:
            # Try content blocks format
            for block in wrapper.get("content", []):
                if isinstance(block, dict) and block.get("type") == "text":
                    text_content = block.get("text", "")
                    break
        if not text_content:
            text_content = json.dumps(wrapper)
    elif isinstance(wrapper, str):
        text_content = wrapper
    else:
        text_content = str(wrapper)

    # Try to extract JSON from the text content
    # Claude may wrap the JSON in markdown code blocks
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text_content, re.DOTALL)
    if json_match:
        text_content = json_match.group(1).strip()

    # Try parsing as JSON directly
    try:
        return json.loads(text_content)
    except json.JSONDecodeError:
        pass

    # If the wrapper itself matches our schema, use it
    if isinstance(wrapper, dict) and any(k in wrapper for k in ("language", "speakers", "corrections", "additional_corrections")):
        return wrapper

    raise RuntimeError(f"Could not extract structured JSON from Claude response: {text_content[:300]}")


def _build_transcript_text(segments: list) -> str:
    """Build readable transcript text from segments."""
    lines = []
    for seg in segments:
        ts = _format_timestamp(seg.get("start", 0))
        speaker = seg.get("speaker", "")
        text = seg.get("text", "").strip()
        if speaker:
            lines.append(f"[{ts}] {speaker}: {text}")
        else:
            lines.append(f"[{ts}] {text}")
    return "\n".join(lines)


def _format_timestamp(seconds: float) -> str:
    """Format seconds to MM:SS.mm"""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    ms = int((seconds % 1) * 100)
    return f"{mins:02d}:{secs:02d}.{ms:02d}"


class RefinementService:
    """Orchestrates transcript refinement: analyze → web verify → apply."""

    def __init__(self, claude_path: str):
        self.claude_path = claude_path
        self._ddg_available = False
        try:
            from duckduckgo_search import DDGS
            self._ddg_available = True
        except ImportError:
            logger.warning("duckduckgo-search not installed, web verification disabled")

    def analyze(self, segments: list, context_text: Optional[str] = None,
                glossary_terms: Optional[List[str]] = None) -> dict:
        """
        Send transcript to Claude for analysis.

        Optional `context_text` (speaker bios + context doc + global glossary, merged)
        and `glossary_terms` (proper-noun list) are prepended as a `## Known context`
        block that tells Claude these terms are present in the audio's domain.

        Returns structured dict with speakers, corrections, uncertain_terms.
        """
        transcript_text = _build_transcript_text(segments)

        # Truncate very long transcripts to stay within reasonable token limits
        if len(transcript_text) > 50000:
            transcript_text = transcript_text[:50000] + "\n\n[... transcript truncated for analysis ...]"

        known_context_block = ""
        if glossary_terms or context_text:
            parts = ["## Known context\n"]
            if glossary_terms:
                terms_csv = ", ".join(t.strip() for t in glossary_terms if t and t.strip())
                if terms_csv:
                    parts.append(
                        "The following terms ARE present in the audio's domain. "
                        "If you find any misspelling of these in the transcript, "
                        "correct it with confidence=high:\n\n"
                        f"[{terms_csv}]\n"
                    )
            if context_text:
                parts.append(f"\nSpeaker context:\n{context_text.strip()}\n")
            known_context_block = "\n".join(parts) + "\n---\n\n"

        prompt = f"""{known_context_block}Analyze this transcript and return a JSON object with the following structure:
{{
  "language": "ISO 639-1 code",
  "domain": "brief topic description",
  "summary": "1-2 sentence summary",
  "speakers": [
    {{"label": "SPEAKER_00", "name": "identified name", "confidence": "high|medium|low", "reasoning": "why"}}
  ],
  "corrections": [
    {{"original": "misspelled term", "corrected": "correct spelling", "confidence": "high|medium|low"}}
  ],
  "uncertain_terms": ["terms needing web verification"]
}}

Rules:
- For speakers: Look for self-introductions, how others address them, context clues. Only assign names with medium+ confidence.
- For corrections: Fix proper nouns, company names, technical terms, medication names, place names. Only include high/medium confidence fixes.
- For uncertain_terms: List terms that look wrong but you're not sure of the correct spelling. These will be verified via web search.
- Keep original speaker labels (SPEAKER_00 etc.) in the "label" field.
- If you cannot identify a speaker's name, use a descriptive label like "Interviewer" or "Caller".

Transcript:
{transcript_text}

Return ONLY the JSON object, no other text."""

        return _run_claude(prompt, ANALYSIS_SCHEMA, self.claude_path, timeout=300)

    def web_verify(self, terms: list) -> dict:
        """
        Search DuckDuckGo for uncertain terms to verify spelling/existence.

        Returns dict mapping term -> search context snippets.
        """
        if not terms:
            return {}

        if not self._ddg_available:
            logger.info("Skipping web verification (duckduckgo-search not installed)")
            return {}

        from duckduckgo_search import DDGS

        results = {}
        for term in terms[:10]:  # Limit to 10 terms
            try:
                with DDGS() as ddgs:
                    search_results = list(ddgs.text(term, max_results=3))
                    if search_results:
                        snippets = []
                        for r in search_results:
                            title = r.get("title", "")
                            body = r.get("body", "")
                            snippets.append(f"{title}: {body[:200]}")
                        results[term] = "\n".join(snippets)
                    else:
                        results[term] = "(no results)"
            except Exception as e:
                logger.warning("Web search failed for '%s': %s", term, e)
                results[term] = f"(search error: {e})"

        return results

    def finalize(self, analysis: dict, web_context: dict) -> dict:
        """
        Send web search results back to Claude for final corrections.

        Only called if there are uncertain terms with web results.
        Returns dict with additional_corrections list.
        """
        if not web_context:
            return {"additional_corrections": []}

        # Filter out error/empty results
        useful_context = {k: v for k, v in web_context.items()
                         if not v.startswith("(") and v.strip()}
        if not useful_context:
            return {"additional_corrections": []}

        context_text = "\n\n".join(
            f"Term: {term}\nSearch results:\n{snippets}"
            for term, snippets in useful_context.items()
        )

        prompt = f"""Based on web search results, determine if these uncertain terms from a transcript should be corrected.

Return a JSON object:
{{
  "additional_corrections": [
    {{"original": "term from transcript", "corrected": "verified correct spelling", "confidence": "high|medium|low"}}
  ]
}}

Only include corrections where the web results clearly indicate the correct spelling. If unsure, omit the term.

Web search results for uncertain terms:
{context_text}

Return ONLY the JSON object, no other text."""

        return _run_claude(prompt, FINALIZE_SCHEMA, self.claude_path, timeout=60)

    def apply_corrections(self, segments: list, analysis: dict) -> tuple:
        """
        Apply corrections deterministically via string replacement.

        Returns (refined_segments, speaker_mapping, corrections_count).
        """
        import copy
        refined = copy.deepcopy(segments)

        # Build speaker mapping
        speaker_mapping = {}
        for speaker_info in analysis.get("speakers", []):
            label = speaker_info.get("label", "")
            name = speaker_info.get("name", "")
            confidence = speaker_info.get("confidence", "low")
            if label and name and confidence in ("high", "medium"):
                speaker_mapping[label] = name

        # Build corrections list (high + medium confidence only)
        all_corrections = []
        for c in analysis.get("corrections", []):
            if c.get("confidence") in ("high", "medium"):
                all_corrections.append((c["original"], c["corrected"]))

        # Apply to segments
        corrections_applied = 0
        for seg in refined:
            text = seg.get("text", "")
            original_text = text

            # Apply text corrections
            for original, corrected in all_corrections:
                if original in text:
                    text = text.replace(original, corrected)

            if text != original_text:
                corrections_applied += 1
            seg["text"] = text

            # Apply speaker mapping
            speaker = seg.get("speaker", "")
            if speaker in speaker_mapping:
                seg["speaker"] = speaker_mapping[speaker]

        return refined, speaker_mapping, corrections_applied

    def refine(self, segments: list, context_text: Optional[str] = None,
               glossary_terms: Optional[List[str]] = None) -> dict:
        """
        Full refinement pipeline: analyze → web verify → finalize → apply.

        Returns dict with all refinement results.
        """
        logger.info("Starting transcript refinement (%d segments)", len(segments))

        # Phase 1: Analyze
        logger.info("Phase 1: Analyzing transcript with Claude...")
        analysis = self.analyze(segments, context_text=context_text, glossary_terms=glossary_terms)
        logger.info(
            "Analysis complete: %d speakers, %d corrections, %d uncertain terms",
            len(analysis.get("speakers", [])),
            len(analysis.get("corrections", [])),
            len(analysis.get("uncertain_terms", [])),
        )

        # Phase 2: Web verify uncertain terms
        web_context = {}
        web_searches = 0
        uncertain = analysis.get("uncertain_terms", [])
        if uncertain:
            logger.info("Phase 2: Verifying %d uncertain terms via web search...", len(uncertain))
            web_context = self.web_verify(uncertain)
            web_searches = len(web_context)
            logger.info("Web verification complete: %d searches performed", web_searches)

            # Phase 2.5: Finalize with web context
            if web_context:
                logger.info("Phase 2.5: Finalizing corrections with web context...")
                finalized = self.finalize(analysis, web_context)
                extra = finalized.get("additional_corrections", [])
                if extra:
                    analysis.setdefault("corrections", []).extend(extra)
                    logger.info("Added %d corrections from web verification", len(extra))
        else:
            logger.info("Phase 2: No uncertain terms, skipping web verification")

        # Phase 3: Apply corrections
        logger.info("Phase 3: Applying corrections...")
        refined_segments, speaker_mapping, corrections_count = self.apply_corrections(
            segments, analysis
        )

        result = {
            "analysis": analysis,
            "refined_segments": refined_segments,
            "speaker_mapping": speaker_mapping,
            "corrections_applied": corrections_count,
            "speakers_identified": len(speaker_mapping),
            "web_searches_performed": web_searches,
        }

        logger.info(
            "Refinement complete: %d speakers identified, %d corrections applied, %d web searches",
            len(speaker_mapping), corrections_count, web_searches,
        )

        return result
