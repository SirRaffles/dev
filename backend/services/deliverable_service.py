"""
Deliverable generation service using Claude CLI.

Generates structured summaries, detailed analyses, personality updates,
and context insights from call transcripts with speaker and context data.
"""

import json
import logging
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import ICLOUD_BASE_PATH

logger = logging.getLogger(__name__)

CALLS_DIR = ICLOUD_BASE_PATH / "calls"
SPEAKERS_DIR = ICLOUD_BASE_PATH / "speakers"
CONTEXTS_DIR = ICLOUD_BASE_PATH / "contexts"


def _find_claude_cli() -> Optional[str]:
    """Find the claude CLI binary."""
    return shutil.which("claude")


def _run_claude_text(prompt: str, claude_path: str, model: str = "sonnet", timeout: int = 180) -> str:
    """
    Run claude CLI in pipe mode and return raw text output.

    Unlike _run_claude in refinement.py which expects JSON,
    this returns markdown/text directly.
    """
    cmd = [
        claude_path, "-p",
        "--model", model,
        "--output-format", "json",
        "--max-turns", "1",
        "--no-session-persistence",
        prompt,
    ]

    logger.debug("Running claude CLI (model=%s, timeout=%ds)", model, timeout)

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
    except json.JSONDecodeError:
        # If not JSON, return raw text
        return stdout

    # Extract text content from the response
    text_content = ""
    if isinstance(wrapper, dict):
        text_content = wrapper.get("result", "")
        if not text_content:
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

    return text_content


def _build_transcript_text(segments: list) -> str:
    """Build readable transcript text from segments."""
    lines = []
    for seg in segments:
        start = seg.get("start", 0)
        mins = int(start // 60)
        secs = int(start % 60)
        ts = f"{mins:02d}:{secs:02d}"
        speaker = seg.get("speaker", "")
        text = seg.get("text", "").strip()
        if speaker:
            lines.append(f"[{ts}] {speaker}: {text}")
        else:
            lines.append(f"[{ts}] {text}")
    return "\n".join(lines)


class DeliverableService:
    """Generates call deliverables using Claude CLI."""

    def __init__(self, claude_path: str):
        self.claude_path = claude_path

    def generate_summary(
        self,
        transcript: str,
        speaker_profiles: dict,
        context_data: str,
        title: str,
    ) -> str:
        """Generate a structured summary with key points, decisions, action items."""
        profiles_text = ""
        for name, profile in speaker_profiles.items():
            profiles_text += f"- {name}: {profile.get('role', 'participant')}\n"

        prompt = f"""You are analyzing a call transcript. Generate a structured markdown summary.

## Call Title
{title}

## Speakers
{profiles_text or "No speaker profiles available."}

## Context
{context_data or "No additional context provided."}

## Transcript
{transcript[:40000]}

---

Generate a structured summary in markdown with these sections:

# Summary: {title}

## Overview
A 2-3 sentence overview of the call.

## Key Points
Bullet list of the most important topics discussed.

## Decisions Made
Bullet list of any decisions reached during the call. If none, write "No explicit decisions were made."

## Action Items
A table with columns: | Owner | Action | Due/Timeline |
List specific action items with who is responsible. If none are clear, write "No specific action items identified."

## Next Steps
What needs to happen after this call.

---

Return ONLY the markdown content, no code fences or preamble."""

        return _run_claude_text(prompt, self.claude_path, model="sonnet", timeout=180)

    def generate_analysis(
        self,
        transcript: str,
        speaker_profiles: dict,
        context_data: str,
        title: str,
    ) -> str:
        """Generate detailed analysis with insights and recommendations."""
        profiles_text = ""
        for name, profile in speaker_profiles.items():
            personality = profile.get("personality", "")
            if personality:
                profiles_text += f"### {name}\n{personality[:500]}\n\n"
            else:
                profiles_text += f"### {name}\nNo prior personality data.\n\n"

        prompt = f"""You are a senior business analyst reviewing a call transcript. Generate a detailed analysis.

## Call Title
{title}

## Speaker Profiles
{profiles_text or "No speaker profiles available."}

## Context
{context_data or "No additional context provided."}

## Transcript
{transcript[:40000]}

---

Generate a detailed analysis in markdown with these sections:

# Analysis: {title}

## Explicit Insights
What was directly stated — key information, data points, positions expressed.

## Implicit Insights
What was implied but not directly stated — undercurrents, concerns, motivations.

## Relationship Dynamics
How the speakers interacted — power dynamics, alignment, tension points.

## Sentiment per Speaker
For each speaker, their overall tone and emotional state during the call.

## Risks & Concerns
Any risks, blockers, or concerns identified (explicit or implicit).

## Opportunities
Potential opportunities surfaced during the discussion.

## Recommendations
Actionable recommendations based on the call content and context.

---

Return ONLY the markdown content, no code fences or preamble."""

        return _run_claude_text(prompt, self.claude_path, model="sonnet", timeout=180)

    def update_personality(
        self,
        speaker_name: str,
        transcript: str,
        existing_personality: str,
    ) -> str:
        """Legacy — kept so existing callers stay intact. Delegates to
        `update_implicit_insights` since the old prompt produced inferred
        traits, which is what the new "implicit" section represents."""
        return self.update_implicit_insights(speaker_name, transcript, existing_personality)

    def update_explicit_insights(
        self,
        speaker_name: str,
        transcript: str,
        existing_explicit: str,
    ) -> str:
        """Refresh the EXPLICIT-insights markdown for a speaker.

        Explicit = things the speaker said OUTRIGHT in the transcript:
        concrete decisions, named preferences, stated facts (job, family,
        projects), announced hobbies, commitments made. High-confidence,
        verifiable, dated entries. Builds up across calls — we keep priors
        untouched unless a new call contradicts them.
        """
        existing = existing_explicit or (
            f"# Explicit insights\n\n*Concrete observations captured from transcripts will land here.*\n"
        )
        prompt = f"""You maintain the EXPLICIT-insights dossier for "{speaker_name}". Only record things the speaker said OUTRIGHT in the transcript — no inference, no guessing.

## Existing dossier (keep, don't duplicate)
{existing}

## New call transcript (their lines only)
{transcript[:20000]}

---

Add ONLY new, concrete, verifiable items that were spoken aloud. Organize under these buckets (omit any bucket with no new info):

- **Decisions & commitments** — e.g. "Will deliver proposal by March 10", "Chose Supabase for backend"
- **Professional** — employer, role, current projects, responsibilities, tools they use
- **Family & personal** — spouse / children / origin / location explicitly mentioned
- **Hobbies & interests** — things they said they do / enjoy
- **Stated preferences** — "I prefer X over Y", "I hate when …"
- **Named opinions** — direct opinions on companies/products/people

Rules:
- Each item must quote or closely paraphrase something actually said. No embellishment.
- Append to the existing dossier; DO NOT duplicate items already present. If a new detail contradicts an old one, keep the newer item and strike the old with `~~like this~~`.
- Keep the whole dossier under 600 words. Trim vague/old items first if needed.
- Date new items inline with today's date in ISO format (e.g. `· 2026-04-19`).

Start the document with `# Explicit insights` as the header.

Return ONLY the markdown content, no code fences or preamble."""

        return _run_claude_text(prompt, self.claude_path, model="sonnet", timeout=120)

    def update_implicit_insights(
        self,
        speaker_name: str,
        transcript: str,
        existing_implicit: str,
    ) -> str:
        """Refresh the IMPLICIT-insights markdown for a speaker.

        Implicit = traits INFERRED from how they speak, not what they said
        outright: communication style, values, taste, likes/dislikes that
        you pick up between the lines. Lower-confidence, qualitative. Prior
        inferences are refined rather than duplicated.
        """
        existing = existing_implicit or (
            f"# Implicit insights\n\n*Inferred personality, style, and preferences will land here.*\n"
        )
        prompt = f"""You maintain the IMPLICIT-insights dossier for "{speaker_name}" — the inferred personality/style you pick up from how they speak (not what they say outright).

## Existing dossier
{existing}

## New call transcript (their lines only)
{transcript[:20000]}

---

Refine the dossier based on the new transcript. Capture inferences — you're reading between the lines.

Organize under these buckets (omit any with nothing new):

- **Communication style** — tone, verbosity, formality, humor, directness
- **Values & priorities** — what they seem to care about, what lights them up, what drains them
- **Personality traits** — curious / cautious / decisive / reflective / etc. Use short descriptors
- **Likes & affinities** — inferred taste in topics, tools, people, aesthetics
- **Dislikes / friction points** — what visibly frustrates or bores them
- **Notable patterns** — recurring phrases, pet peeves, characteristic turns

Rules:
- These are INFERENCES, not quotes. Frame with verbs like "seems to", "tends to", "likely values".
- Refine prior inferences when new data reinforces or contradicts them. Don't repeat unchanged items — let the prior dossier stand.
- Keep under 500 words total.
- If confidence is low, say so inline (e.g. "— tentative, 1 call").

Start with `# Implicit insights` as the header.

Return ONLY the markdown content, no code fences or preamble."""

        return _run_claude_text(prompt, self.claude_path, model="sonnet", timeout=120)

    def generate_context_insights(
        self,
        transcript: str,
        context_data: str,
        title: str,
    ) -> str:
        """Generate 3-5 bullet point insights to append to context's insights.md."""
        prompt = f"""Based on this call, generate 3-5 concise bullet-point insights that should be recorded in the context folder for future reference.

## Call Title
{title}

## Existing Context
{context_data or "No prior context data."}

## Transcript
{transcript[:20000]}

---

Generate insights in this format (each on a new line, starting with "- "):
- [Insight 1]
- [Insight 2]
- [Insight 3]

Focus on information that would be useful for future calls in this context — decisions, evolving situations, relationship developments, emerging patterns.

Return ONLY the bullet points, no headers or preamble."""

        return _run_claude_text(prompt, self.claude_path, model="sonnet", timeout=90)

    def generate_deliverables(self, job_id: str) -> dict:
        """
        Full deliverable generation pipeline for a call.

        Requires: speakers identified + context assigned.

        Steps:
        1. Gather transcript, speaker profiles, context data
        2. Create call folder on iCloud
        3. Generate summary.md and analysis.md
        4. Update personality.md for each speaker
        5. Append insights to context's insights.md
        6. Update call_metadata

        Returns dict with generation results.
        """
        import state  # Local import to avoid circular dependency

        # Get call metadata
        call = state.call_metadata_store.get(job_id)
        if not call:
            raise ValueError(f"Call not found: {job_id}")

        if not call.get("speakers_identified"):
            raise ValueError("Speakers must be identified before generating deliverables")
        if not call.get("context_assigned"):
            raise ValueError("Context must be assigned before generating deliverables")

        # Get job data
        job = state.job_store.get(job_id)
        if not job or job.status != "completed":
            raise ValueError(f"Job not found or not completed: {job_id}")

        # Build transcript text
        transcript_text = _build_transcript_text(job.segments or [])
        if not transcript_text:
            raise ValueError("No transcript segments available")

        # Get speaker profiles
        call_speakers = state.call_speaker_store.get_for_call(job_id)
        speaker_profiles = {}
        for cs in call_speakers:
            speaker = state.speaker_store.get(cs["speaker_id"])
            if speaker:
                name = speaker["name"]
                speaker_dir = SPEAKERS_DIR / name
                
                # Consolidate all 3 sections for the LLM prompt context
                context_parts = []
                for fname in ("profile.md", "explicit_insights.md", "implicit_insights.md"):
                    fpath = speaker_dir / fname
                    if fpath.exists():
                        try:
                            content = fpath.read_text(encoding="utf-8").strip()
                            if content and "will land here" not in content:
                                context_parts.append(content)
                        except OSError:
                            pass
                
                # Fallback to legacy if no new sections have content
                if not context_parts:
                    legacy_path = speaker_dir / "personality.md"
                    if legacy_path.exists():
                        try:
                            context_parts.append(legacy_path.read_text(encoding="utf-8"))
                        except OSError:
                            pass

                speaker_profiles[name] = {
                    "role": "participant",
                    "personality": "\n\n".join(context_parts),
                    "call_count": speaker.get("call_count", 0),
                }

        # Get context data
        context_path = call.get("context_path", "")
        context_data = ""
        if context_path:
            context_dir = CONTEXTS_DIR / context_path
            context_file = context_dir / "context.md"
            if context_file.exists():
                context_data = context_file.read_text(encoding="utf-8")

        # Call title
        title = call.get("title") or f"Call {job_id[:8]}"

        # Create call folder
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        safe_title = re.sub(r'[^\w\s-]', '', title.lower()).strip()
        safe_title = re.sub(r'[\s]+', '-', safe_title)[:50]
        call_folder_name = f"{date_prefix}_{safe_title}_{job_id[:8]}"
        call_folder = CALLS_DIR / call_folder_name
        call_folder.mkdir(parents=True, exist_ok=True)

        results = {
            "call_folder": str(call_folder_name),
            "generated": [],
            "errors": [],
        }

        # Save transcript.md
        transcript_md = f"# Transcript: {title}\n\n"
        transcript_md += f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        transcript_md += f"**Speakers**: {', '.join(speaker_profiles.keys())}\n\n"
        transcript_md += "---\n\n"
        transcript_md += transcript_text
        (call_folder / "transcript.md").write_text(transcript_md, encoding="utf-8")

        # Save metadata.json
        metadata = {
            "job_id": job_id,
            "title": title,
            "speakers": list(speaker_profiles.keys()),
            "context_path": context_path,
            "generated_at": datetime.now().isoformat(),
        }
        (call_folder / "metadata.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )

        # Generate summary
        try:
            logger.info("Generating summary for call %s", job_id)
            summary = self.generate_summary(
                transcript_text, speaker_profiles, context_data, title
            )
            (call_folder / "summary.md").write_text(summary, encoding="utf-8")
            results["generated"].append("summary")
            logger.info("Summary generated for call %s", job_id)
        except Exception as e:
            logger.error("Failed to generate summary for %s: %s", job_id, e)
            results["errors"].append(f"summary: {e}")

        # Generate analysis
        try:
            logger.info("Generating analysis for call %s", job_id)
            analysis = self.generate_analysis(
                transcript_text, speaker_profiles, context_data, title
            )
            (call_folder / "analysis.md").write_text(analysis, encoding="utf-8")
            results["generated"].append("analysis")
            logger.info("Analysis generated for call %s", job_id)
        except Exception as e:
            logger.error("Failed to generate analysis for %s: %s", job_id, e)
            results["errors"].append(f"analysis: {e}")

        # Append insights to context's insights.md
        if context_path:
            try:
                logger.info("Generating context insights for %s", context_path)
                insights = self.generate_context_insights(
                    transcript_text, context_data, title
                )

                context_dir = CONTEXTS_DIR / context_path
                insights_file = context_dir / "insights.md"
                existing_insights = ""
                if insights_file.exists():
                    existing_insights = insights_file.read_text(encoding="utf-8")

                date_header = f"\n\n## {datetime.now().strftime('%Y-%m-%d')} — {title}\n\n"
                updated_insights = existing_insights + date_header + insights
                insights_file.write_text(updated_insights, encoding="utf-8")
                results["generated"].append("context_insights")
            except Exception as e:
                logger.error("Failed to generate context insights: %s", e)
                results["errors"].append(f"context_insights: {e}")

        # Update call_metadata
        call_folder_path = str(call_folder.relative_to(ICLOUD_BASE_PATH))
        state.call_metadata_store.update(
            job_id,
            call_folder_path=call_folder_path,
            deliverables_generated=1,
            deliverables_generated_at=datetime.now().isoformat(),
        )

        logger.info(
            "Deliverable generation complete for %s: %d generated, %d errors",
            job_id, len(results["generated"]), len(results["errors"]),
        )

        return results
