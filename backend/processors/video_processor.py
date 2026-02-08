"""
Video multi-modal processor.

Combines audio transcription with visual content extraction and timeline merging.
"""
import logging
import subprocess
from pathlib import Path
from typing import Optional, Callable, List
import tempfile
import asyncio

from processors.base import BaseProcessor
from processors.keyframe_extractor import KeyframeExtractor, ExtractionConfig, ExtractedFrame
from models.multimodal import (
    MultiModalJob,
    ProcessingProgress,
    VisualElement,
    VisualContentType,
    AudioSegment,
    MultimodalSegment,
    VideoProcessingSettings,
)
from services.vision_service import VisionService, get_vision_service, ContentType
from services.model_manager import ModelManager, ModelName, get_model_manager

logger = logging.getLogger(__name__)


class VideoProcessor(BaseProcessor):
    """
    Multi-modal video processor.

    Pipeline:
    1. Extract audio → Whisper transcription
    2. Extract keyframes → Scene detection + interval sampling
    3. Analyze frames → OCR + VLM description
    4. Merge timeline → Sync audio segments with visual content
    """

    def __init__(
        self,
        job: MultiModalJob,
        settings: Optional[VideoProcessingSettings] = None,
        model_manager: Optional[ModelManager] = None,
        vision_service: Optional[VisionService] = None,
        progress_callback: Optional[Callable[[ProcessingProgress], None]] = None,
    ):
        super().__init__(job, progress_callback)
        self.settings = settings or VideoProcessingSettings()
        self.model_manager = model_manager or get_model_manager()
        self.vision_service = vision_service or get_vision_service()
        self._temp_dir: Optional[Path] = None
        self._audio_path: Optional[Path] = None
        self._frames_dir: Optional[Path] = None

    def get_supported_extensions(self) -> list[str]:
        return [
            ".mp4", ".MP4",
            ".mov", ".MOV",
            ".mkv", ".MKV",
            ".avi", ".AVI",
            ".webm", ".WEBM",
            ".m4v", ".M4V",
        ]

    async def process(self) -> MultiModalJob:
        """Process a video file with multi-modal extraction."""
        file_path = Path(self.job.source_filename)

        # Create temp directories
        # Note: Don't add to temp_files - this is cleaned up on job deletion
        self._temp_dir = Path(tempfile.mkdtemp(prefix="video_process_"))
        self._frames_dir = self._temp_dir / "frames"
        self._frames_dir.mkdir()
        self.job.image_dir = str(self._temp_dir)

        total_steps = 6
        current_step = 0

        # Step 1: Get video info
        self.update_progress(
            "initialization",
            current_step,
            total_steps,
            message="Analyzing video...",
        )

        video_info = await self._get_video_info(file_path)
        self.job.duration = video_info.get("duration", 0)
        current_step += 1

        # Step 2: Extract audio
        self.update_progress(
            "audio_extraction",
            current_step,
            total_steps,
            message="Extracting audio...",
        )

        self._audio_path = await self._extract_audio(file_path)
        if not self._audio_path:
            self.fail_processing("Failed to extract audio from video")
            return self.job
        current_step += 1

        # Step 3: Extract keyframes (parallel with audio transcription)
        self.update_progress(
            "frame_extraction",
            current_step,
            total_steps,
            message="Extracting keyframes...",
        )

        # Configure keyframe extraction
        extractor = KeyframeExtractor(ExtractionConfig(
            min_interval=2.0,
            max_interval=self.settings.keyframe_interval,
            scene_threshold=self.settings.scene_threshold * 100,  # Convert 0-1 to percentage
        ))

        frames, video_type = await asyncio.to_thread(
            extractor.extract,
            file_path,
            self._frames_dir,
            self.settings.scene_detection,
        )

        self.job.frames_extracted = len(frames)
        logger.info(f"Extracted {len(frames)} frames, video type: {video_type.value}")
        current_step += 1

        # Step 4: Transcribe audio
        self.update_progress(
            "audio_transcription",
            current_step,
            total_steps,
            message="Transcribing audio...",
        )

        await self._transcribe_audio()
        current_step += 1

        # Step 5: Analyze frames with VLM
        if self.settings.enable_visual_analysis and frames:
            self.update_progress(
                "visual_analysis",
                current_step,
                total_steps,
                message="Analyzing visual content...",
            )

            await self._analyze_frames(frames)
            current_step += 1
        else:
            current_step += 1

        # Step 6: Merge timeline
        self.update_progress(
            "timeline_merge",
            current_step,
            total_steps,
            message="Merging audio and visual timeline...",
        )

        self._merge_timeline()
        current_step += 1

        # Mark models used
        self.job.models_used.extend(["whisper"])
        if self.settings.enable_diarization:
            self.job.models_used.append("diarization")
        if self.settings.enable_visual_analysis:
            self.job.models_used.append("vision")

        return self.job

    async def _get_video_info(self, video_path: Path) -> dict:
        """Get video metadata using ffprobe."""
        import json

        try:
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(video_path),
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            info = json.loads(stdout.decode())

            duration = float(info.get("format", {}).get("duration", 0))
            return {"duration": duration, "info": info}

        except Exception as e:
            logger.error(f"Failed to get video info: {e}")
            return {"duration": 0}

    async def _extract_audio(self, video_path: Path) -> Optional[Path]:
        """Extract audio from video to WAV format."""
        output_path = self._temp_dir / "audio.wav"

        try:
            cmd = [
                "ffmpeg",
                "-i", str(video_path),
                "-vn",  # No video
                "-acodec", "pcm_s16le",
                "-ar", "16000",  # 16kHz
                "-ac", "1",  # Mono
                "-y",  # Overwrite
                str(output_path),
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await proc.communicate()

            if proc.returncode == 0 and output_path.exists():
                logger.info(f"Extracted audio: {output_path}")
                return output_path
            else:
                logger.error(f"Audio extraction failed: {stderr.decode()}")
                return None

        except Exception as e:
            logger.error(f"Audio extraction error: {e}")
            return None

    async def _transcribe_audio(self) -> None:
        """Transcribe audio using MLX-Whisper."""
        if not self._audio_path:
            return

        try:
            # Load whisper model
            await self.model_manager.load_whisper(self.settings.model_size)
            whisper = self.model_manager.get_model(ModelName.WHISPER)

            if whisper is None:
                logger.error("Whisper model not available")
                return

            # Run transcription
            logger.info(f"Transcribing audio with model: {self.settings.model_size}")

            result = whisper.transcribe(
                str(self._audio_path),
                language=None if self.settings.language == "auto" else self.settings.language,
                word_timestamps=True,
                fp16=True,
            )

            # Extract segments
            segments = result.get("segments", [])
            self.job.audio_segments = [
                AudioSegment(
                    id=i,
                    start=seg["start"],
                    end=seg["end"],
                    text=seg["text"].strip(),
                    confidence=seg.get("avg_logprob", 0),
                    words=seg.get("words"),
                )
                for i, seg in enumerate(segments)
            ]

            # Build full transcript
            self.job.audio_transcript = " ".join(
                seg.text for seg in self.job.audio_segments
            )

            # Set language info
            self.job.detected_language = result.get("language", "unknown")
            self.job.language_probability = 0.9  # MLX doesn't return this directly

            logger.info(
                f"Transcription complete: {len(self.job.audio_segments)} segments"
            )

            # Run diarization if enabled
            if self.settings.enable_diarization:
                await self._run_diarization()

        except Exception as e:
            logger.error(f"Transcription failed: {e}")

    async def _run_diarization(self) -> None:
        """Run speaker diarization on audio."""
        if not self._audio_path:
            return

        try:
            # Load diarization model
            await self.model_manager.load_diarization()
            pipeline = self.model_manager.get_model(ModelName.DIARIZATION)

            if pipeline is None:
                logger.warning("Diarization model not available")
                return

            logger.info("Running speaker diarization...")

            # Run diarization
            diarization = pipeline(str(self._audio_path))

            # Extract speaker turns
            speaker_turns = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                speaker_turns.append({
                    "start": turn.start,
                    "end": turn.end,
                    "speaker": speaker,
                })

            # Assign speakers to segments
            speakers_seen = set()
            for segment in self.job.audio_segments:
                segment_mid = (segment.start + segment.end) / 2

                # Find speaker at segment midpoint
                for turn in speaker_turns:
                    if turn["start"] <= segment_mid <= turn["end"]:
                        segment.speaker = turn["speaker"]
                        speakers_seen.add(turn["speaker"])
                        break

            self.job.speakers = list(speakers_seen)
            logger.info(f"Diarization complete: {len(self.job.speakers)} speakers")

        except Exception as e:
            logger.error(f"Diarization failed: {e}")

    async def _analyze_frames(self, frames: List[ExtractedFrame]) -> None:
        """Analyze extracted frames with VLM and OCR."""
        # Get vision model if available
        try:
            await self.model_manager.load_vision()
            vision_model = self.model_manager.get_model(ModelName.VISION)
            self.vision_service.set_model(vision_model)
        except Exception as e:
            logger.warning(f"Vision model not available, using OCR only: {e}")

        analyzed = 0
        total = len(frames)

        for frame in frames:
            try:
                # Classify content type
                content_type = await self.vision_service.classify(frame.frame_path)

                # Create visual element
                element = VisualElement(
                    type=self._map_content_type(content_type),
                    timestamp=frame.timestamp,
                    image_path=str(frame.frame_path),
                    is_key_frame=frame.is_key_frame,
                )

                # Skip detailed analysis for person-only frames
                if content_type != ContentType.PERSON:
                    # Get description
                    if self.settings.describe_visuals:
                        description = await self.vision_service.describe(
                            frame.frame_path,
                            content_type=content_type,
                        )
                        element.description = description

                    # Extract text via OCR
                    if self.settings.ocr_enabled:
                        text, confidence = self.vision_service.tesseract_ocr_with_confidence(
                            frame.frame_path
                        )
                        element.text_content = text
                        element.ocr_confidence = confidence

                self.job.visual_elements.append(element)
                analyzed += 1

                self.update_progress(
                    "visual_analysis",
                    analyzed,
                    total,
                    substage=f"frame_{analyzed}",
                    message=f"Analyzed {analyzed}/{total} frames",
                )

            except Exception as e:
                logger.warning(f"Failed to analyze frame at {frame.timestamp}s: {e}")

        self.job.frames_analyzed = analyzed
        logger.info(f"Visual analysis complete: {analyzed}/{total} frames analyzed")

    def _map_content_type(self, content_type: ContentType) -> VisualContentType:
        """Map VisionService ContentType to VisualContentType."""
        mapping = {
            ContentType.SLIDE: VisualContentType.SLIDE,
            ContentType.CODE: VisualContentType.CODE,
            ContentType.DIAGRAM: VisualContentType.DIAGRAM,
            ContentType.CHART: VisualContentType.CHART,
            ContentType.TABLE: VisualContentType.TABLE,
            ContentType.TEXT: VisualContentType.DOCUMENT,
            ContentType.PERSON: VisualContentType.PERSON,
            ContentType.SCREENSHOT: VisualContentType.KEYFRAME,
            ContentType.PHOTO: VisualContentType.IMAGE,
        }
        return mapping.get(content_type, VisualContentType.KEYFRAME)

    def _merge_timeline(self) -> None:
        """Merge audio segments with visual elements into unified timeline."""
        if not self.job.audio_segments and not self.job.visual_elements:
            return

        merged = []
        used_visuals = set()

        # Sort visual elements by timestamp
        visuals_by_time = sorted(
            self.job.visual_elements,
            key=lambda v: v.timestamp or 0,
        )

        # Phase 1: Associate visuals with audio segments
        for audio in self.job.audio_segments:
            segment = MultimodalSegment(
                id=audio.id,
                start=audio.start,
                end=audio.end,
                audio=audio,
                relationship="concurrent",
            )

            # Find visual content within this audio segment's timespan
            for i, visual in enumerate(visuals_by_time):
                if i in used_visuals:
                    continue

                if visual.timestamp is None:
                    continue

                # Visual falls within audio segment (with 1s tolerance)
                if (audio.start - 1.0) <= visual.timestamp <= (audio.end + 1.0):
                    segment.visual = visual
                    used_visuals.add(i)

                    # Add visual reference to audio segment
                    audio.visual_refs.append(visual.element_id)
                    break

            # Generate combined text
            if segment.visual and segment.visual.description:
                segment.combined_text = f"[Visual: {segment.visual.description}] {audio.text}"
            else:
                segment.combined_text = audio.text

            merged.append(segment)

        # Phase 2: Create visual-only segments for unused visuals
        for i, visual in enumerate(visuals_by_time):
            if i in used_visuals:
                continue
            if visual.timestamp is None:
                continue

            # Check if this visual is during a gap in audio
            is_during_gap = True
            for audio in self.job.audio_segments:
                if audio.start <= visual.timestamp <= audio.end:
                    is_during_gap = False
                    break

            if is_during_gap and visual.type != VisualContentType.PERSON:
                segment = MultimodalSegment(
                    id=len(merged),
                    start=visual.timestamp,
                    end=visual.timestamp + 5.0,  # Default 5s duration
                    visual=visual,
                    relationship="visual_only",
                    combined_text=f"[Visual only: {visual.description or 'Content changed'}]",
                )
                merged.append(segment)

        # Sort by start time
        merged.sort(key=lambda s: s.start)

        # Renumber
        for i, segment in enumerate(merged):
            segment.id = i

        self.job.merged_timeline = merged
        logger.info(f"Timeline merged: {len(merged)} segments")
