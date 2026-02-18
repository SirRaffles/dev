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
        """Update a speaker's personality.md with new observations."""
        profile = existing_personality or f"# {speaker_name}\n\n*No personality insights yet.*"
        prompt = f"""You are maintaining a personality profile for "{speaker_name}" based on their appearances in recorded calls.

## Existing Profile
{profile}

## New Call Transcript (relevant segments)
{transcript[:20000]}

---

Update the personality profile. Keep the existing structure and content, adding new observations. The profile should capture:

- **Communication Style**: How they speak, their tone, verbosity, formality
- **Priorities & Interests**: What they focus on, what matters to them
- **Decision-Making**: How they approach decisions, risk tolerance
- **Interpersonal Style**: How they interact with others
- **Notable Patterns**: Recurring themes, phrases, or behaviors

Merge new observations with existing ones. Don't repeat what's already captured unless it's been reinforced. Keep the profile concise (under 500 words).

Start with `# {speaker_name}` as the header.

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
                personality_path = SPEAKERS_DIR / name / "personality.md"
                personality = ""
                if personality_path.exists():
                    personality = personality_path.read_text(encoding="utf-8")
                speaker_profiles[name] = {
                    "role": "participant",
                    "personality": personality,
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

        # Update personality.md for each speaker
        for name, profile in speaker_profiles.items():
            try:
                # Filter transcript to just this speaker's segments
                speaker_lines = [
                    line for line in transcript_text.split("\n")
                    if f"] {name}:" in line
                ]
                if not speaker_lines:
                    continue

                speaker_transcript = "\n".join(speaker_lines[:100])  # Cap at 100 lines
                existing_personality = profile.get("personality", "")

                logger.info("Updating personality for speaker: %s", name)
                updated = self.update_personality(name, speaker_transcript, existing_personality)

                personality_path = SPEAKERS_DIR / name / "personality.md"
                if personality_path.parent.exists():
                    personality_path.write_text(updated, encoding="utf-8")
                    results["generated"].append(f"personality:{name}")
            except Exception as e:
                logger.error("Failed to update personality for %s: %s", name, e)
                results["errors"].append(f"personality:{name}: {e}")

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
