"""
Export format generators for multi-modal processing jobs.
"""

from datetime import datetime
from pathlib import Path

from config import SUPPORTED_LANGUAGES
from models.multimodal import MultiModalJob
from utils.export import format_timestamp, format_srt_timestamp


def generate_multimodal_markdown(job: MultiModalJob, include_visuals: bool = True) -> str:
    """Generate enhanced markdown with visual content."""
    lines = [
        f"# Multi-Modal Transcript",
        f"",
        f"**Source:** {Path(job.source_filename).name if job.source_filename else 'Unknown'}",
        f"**Type:** {job.source_type}",
    ]

    if job.duration:
        mins = int(job.duration // 60)
        secs = int(job.duration % 60)
        lines.append(f"**Duration:** {mins}:{secs:02d}")

    if job.detected_language:
        lines.append(f"**Language:** {SUPPORTED_LANGUAGES.get(job.detected_language, job.detected_language)}")

    if job.speakers:
        lines.append(f"**Speakers:** {', '.join(job.speakers)}")

    lines.extend(["", "---", ""])

    # Document content (for PDF/PPTX)
    if job.document_markdown:
        lines.append("## Document Content")
        lines.append("")
        lines.append(job.document_markdown)
        lines.append("")

    # Timeline with visual references (for video)
    if job.merged_timeline:
        lines.append("## Timeline")
        lines.append("")

        current_visual = None

        for segment in job.merged_timeline:
            if include_visuals and segment.visual and segment.visual != current_visual:
                current_visual = segment.visual
                lines.append("---")
                lines.append(f"### Visual: {segment.visual.type.value.title()}")
                lines.append(f"*Timestamp: {format_timestamp(segment.visual.timestamp or 0)}*")
                lines.append("")

                if segment.visual.text_content:
                    lines.append("```")
                    lines.append(segment.visual.text_content)
                    lines.append("```")
                    lines.append("")

                if segment.visual.description:
                    lines.append(f"> {segment.visual.description}")
                    lines.append("")

            if segment.audio:
                speaker = segment.audio.speaker or ""
                timestamp = format_timestamp(segment.audio.start)
                lines.append(f"**[{timestamp}] {speaker}:** {segment.audio.text}")
                lines.append("")

    # Audio-only segments (fallback)
    elif job.audio_segments:
        lines.append("## Transcript")
        lines.append("")

        current_speaker = None
        for segment in job.audio_segments:
            speaker = segment.speaker

            if speaker and speaker != current_speaker:
                lines.append(f"\n### {speaker}\n")
                current_speaker = speaker

            timestamp = format_timestamp(segment.start)
            lines.append(f"**[{timestamp}]** {segment.text}")
            lines.append("")

    # Visual elements list (for documents)
    if include_visuals and job.visual_elements and job.source_type in ["pdf", "pptx"]:
        lines.append("")
        lines.append("## Visual Elements")
        lines.append("")

        for i, elem in enumerate(job.visual_elements, 1):
            location = ""
            if elem.page:
                location = f"Page {elem.page}"
            elif elem.slide:
                location = f"Slide {elem.slide}"

            lines.append(f"### {i}. {elem.type.value.title()} ({location})")

            if elem.description:
                lines.append(f"> {elem.description}")
                lines.append("")

            if elem.text_content:
                lines.append("**Extracted Text:**")
                lines.append("```")
                lines.append(elem.text_content[:500] + ("..." if len(elem.text_content) > 500 else ""))
                lines.append("```")
                lines.append("")

    # Metadata footer
    lines.extend([
        "",
        "---",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        f"*Models used: {', '.join(job.models_used)}*" if job.models_used else "",
        f"*Processing time: {job.processing_time_seconds:.1f}s*" if job.processing_time_seconds else "",
    ])

    return "\n".join(lines)


def generate_multimodal_json(job: MultiModalJob) -> dict:
    """Generate structured JSON export."""
    return {
        "version": "2.0.0",
        "job_id": job.job_id,
        "source": {
            "filename": Path(job.source_filename).name if job.source_filename else None,
            "type": job.source_type,
            "duration": job.duration,
            "page_count": job.page_count,
            "slide_count": job.slide_count,
        },
        "processing": {
            "models_used": job.models_used,
            "processing_time_seconds": job.processing_time_seconds,
            "frames_extracted": job.frames_extracted,
            "frames_analyzed": job.frames_analyzed,
        },
        "audio": {
            "language": job.detected_language,
            "language_probability": job.language_probability,
            "speakers": job.speakers,
            "transcript": job.audio_transcript,
            "segments": [seg.model_dump() for seg in job.audio_segments],
        },
        "visual": {
            "elements": [elem.model_dump() for elem in job.visual_elements],
        },
        "document": {
            "markdown": job.document_markdown,
            "sections": [sec.model_dump() for sec in job.document_sections],
        },
        "multimodal": {
            "merged_timeline": [seg.model_dump() for seg in job.merged_timeline],
        },
    }
