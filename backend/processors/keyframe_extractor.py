"""
Keyframe extraction from videos using scene detection and interval sampling.

Uses PySceneDetect for scene change detection and OpenCV for frame extraction.
"""
import logging
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import tempfile
import json

logger = logging.getLogger(__name__)


class VideoType(str, Enum):
    """Types of video content for adaptive extraction."""
    PRESENTATION = "presentation"  # Slides, minimal motion
    SCREENCAST = "screencast"  # Code, UI demos
    TALKING_HEAD = "talking_head"  # Face cam
    DOCUMENTARY = "documentary"  # Mixed content
    LECTURE = "lecture"  # Mix of slides and speaker
    UNKNOWN = "unknown"


@dataclass
class ExtractedFrame:
    """Represents an extracted video frame."""
    timestamp: float  # Seconds
    frame_path: Path
    extraction_reason: str  # "scene_change", "interval", "forced"
    frame_number: int
    is_key_frame: bool = True


@dataclass
class ExtractionConfig:
    """Configuration for frame extraction."""
    min_interval: float = 2.0  # Minimum seconds between frames
    max_interval: float = 30.0  # Maximum gap before forcing extraction
    scene_threshold: float = 27.0  # PySceneDetect threshold
    adaptive_threshold: float = 3.0  # For adaptive detector
    force_start_end: bool = True  # Always extract first and last frame
    max_frames: Optional[int] = None  # Maximum frames to extract
    output_format: str = "jpg"  # jpg or png
    output_quality: int = 85  # JPEG quality


class KeyframeExtractor:
    """
    Extracts keyframes from videos using scene detection and interval sampling.

    Combines:
    1. Scene change detection (PySceneDetect)
    2. Interval sampling (fallback/supplement)
    3. Perceptual hashing for deduplication
    """

    # Default configs by video type
    TYPE_CONFIGS = {
        VideoType.PRESENTATION: ExtractionConfig(
            min_interval=5.0,
            max_interval=60.0,
            scene_threshold=30.0,
        ),
        VideoType.SCREENCAST: ExtractionConfig(
            min_interval=2.0,
            max_interval=30.0,
            scene_threshold=40.0,
        ),
        VideoType.TALKING_HEAD: ExtractionConfig(
            min_interval=30.0,
            max_interval=120.0,
            scene_threshold=50.0,
        ),
        VideoType.DOCUMENTARY: ExtractionConfig(
            min_interval=3.0,
            max_interval=20.0,
            scene_threshold=27.0,
        ),
        VideoType.LECTURE: ExtractionConfig(
            min_interval=5.0,
            max_interval=45.0,
            scene_threshold=30.0,
        ),
        VideoType.UNKNOWN: ExtractionConfig(
            min_interval=3.0,
            max_interval=30.0,
            scene_threshold=27.0,
        ),
    }

    def __init__(self, config: Optional[ExtractionConfig] = None):
        self.config = config or ExtractionConfig()
        self._video_duration: float = 0
        self._video_fps: float = 30

    def get_video_info(self, video_path: Path) -> dict:
        """Get video metadata using ffprobe."""
        try:
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(video_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            info = json.loads(result.stdout)

            # Extract duration and fps
            duration = float(info.get("format", {}).get("duration", 0))

            # Get video stream info
            video_stream = None
            for stream in info.get("streams", []):
                if stream.get("codec_type") == "video":
                    video_stream = stream
                    break

            fps = 30.0
            if video_stream:
                # Parse fps from avg_frame_rate (e.g., "30/1")
                fps_str = video_stream.get("avg_frame_rate", "30/1")
                if "/" in fps_str:
                    num, den = fps_str.split("/")
                    fps = float(num) / float(den) if float(den) > 0 else 30.0

            self._video_duration = duration
            self._video_fps = fps

            return {
                "duration": duration,
                "fps": fps,
                "width": video_stream.get("width") if video_stream else None,
                "height": video_stream.get("height") if video_stream else None,
                "codec": video_stream.get("codec_name") if video_stream else None,
            }

        except Exception as e:
            logger.error(f"Failed to get video info: {e}")
            return {"duration": 0, "fps": 30}

    def detect_scenes(self, video_path: Path) -> List[float]:
        """
        Detect scene changes using PySceneDetect.

        Returns list of timestamps (seconds) where scenes change.
        """
        try:
            from scenedetect import detect, ContentDetector, AdaptiveDetector

            logger.info(f"Detecting scenes in {video_path.name}")

            # Use ContentDetector with configured threshold
            detector = ContentDetector(
                threshold=self.config.scene_threshold,
                min_scene_len=int(self._video_fps * self.config.min_interval),
            )

            scene_list = detect(str(video_path), detector, show_progress=False)

            # Extract timestamps (start of each scene)
            timestamps = [scene[0].get_seconds() for scene in scene_list]

            logger.info(f"Detected {len(timestamps)} scene changes")
            return timestamps

        except ImportError:
            logger.warning("scenedetect not installed, using interval sampling only")
            return []
        except Exception as e:
            logger.error(f"Scene detection failed: {e}")
            return []

    def generate_interval_samples(
        self,
        duration: float,
        existing_timestamps: List[float],
    ) -> List[float]:
        """
        Generate interval-based sample timestamps to fill gaps.

        Args:
            duration: Video duration in seconds
            existing_timestamps: Already detected scene timestamps

        Returns:
            Additional timestamps to sample
        """
        additional = []
        existing = sorted(existing_timestamps)

        # Add start if not present
        if self.config.force_start_end and (not existing or existing[0] > 1.0):
            additional.append(0.0)

        # Fill gaps larger than max_interval
        prev_ts = 0.0
        for ts in existing:
            gap = ts - prev_ts
            if gap > self.config.max_interval:
                # Add samples to fill the gap
                num_samples = int(gap / self.config.max_interval)
                interval = gap / (num_samples + 1)
                for i in range(1, num_samples + 1):
                    sample_ts = prev_ts + (i * interval)
                    if sample_ts not in existing:
                        additional.append(sample_ts)
            prev_ts = ts

        # Fill gap after last scene
        if prev_ts < duration - self.config.min_interval:
            gap = duration - prev_ts
            if gap > self.config.max_interval:
                num_samples = int(gap / self.config.max_interval)
                interval = gap / (num_samples + 1)
                for i in range(1, num_samples + 1):
                    sample_ts = prev_ts + (i * interval)
                    additional.append(sample_ts)

        # Add end if not present
        if self.config.force_start_end:
            end_ts = max(0, duration - 1.0)
            if end_ts not in existing and end_ts > prev_ts + self.config.min_interval:
                additional.append(end_ts)

        return additional

    def extract_frames(
        self,
        video_path: Path,
        timestamps: List[float],
        output_dir: Path,
    ) -> List[ExtractedFrame]:
        """
        Extract frames at specified timestamps using ffmpeg.

        Args:
            video_path: Path to video file
            timestamps: List of timestamps (seconds) to extract
            output_dir: Directory to save extracted frames

        Returns:
            List of ExtractedFrame objects
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        extracted = []

        for i, ts in enumerate(sorted(timestamps)):
            output_path = output_dir / f"frame_{i:04d}_{ts:.3f}.{self.config.output_format}"

            try:
                # Use ffmpeg to extract frame
                cmd = [
                    "ffmpeg",
                    "-ss", str(ts),
                    "-i", str(video_path),
                    "-frames:v", "1",
                    "-q:v", str(max(1, min(31, 31 - int(self.config.output_quality / 3.5)))),
                    "-y",  # Overwrite
                    str(output_path),
                ]
                subprocess.run(cmd, capture_output=True, check=True)

                if output_path.exists():
                    extracted.append(ExtractedFrame(
                        timestamp=ts,
                        frame_path=output_path,
                        extraction_reason="scene_change",  # Will be updated
                        frame_number=i,
                    ))

            except subprocess.CalledProcessError as e:
                logger.warning(f"Failed to extract frame at {ts}s: {e}")
            except Exception as e:
                logger.error(f"Frame extraction error at {ts}s: {e}")

        return extracted

    def deduplicate_frames(
        self,
        frames: List[ExtractedFrame],
        hash_threshold: int = 10,
    ) -> List[ExtractedFrame]:
        """
        Remove duplicate frames using perceptual hashing.

        Args:
            frames: List of extracted frames
            hash_threshold: Maximum hamming distance for duplicates

        Returns:
            Deduplicated list of frames
        """
        try:
            from imagehash import phash
            from PIL import Image

            unique_frames = []
            seen_hashes = []

            for frame in frames:
                try:
                    img = Image.open(frame.frame_path)
                    frame_hash = phash(img)

                    # Check against existing hashes
                    is_duplicate = False
                    for existing_hash in seen_hashes:
                        if frame_hash - existing_hash <= hash_threshold:
                            is_duplicate = True
                            break

                    if not is_duplicate:
                        seen_hashes.append(frame_hash)
                        unique_frames.append(frame)
                    else:
                        # Remove duplicate file
                        frame.frame_path.unlink(missing_ok=True)

                except Exception as e:
                    logger.warning(f"Hash computation failed for {frame.frame_path}: {e}")
                    unique_frames.append(frame)  # Keep on error

            logger.info(
                f"Deduplication: {len(frames)} -> {len(unique_frames)} frames "
                f"({len(frames) - len(unique_frames)} duplicates removed)"
            )
            return unique_frames

        except ImportError:
            logger.warning("imagehash not installed, skipping deduplication")
            return frames

    def detect_video_type(self, video_path: Path) -> VideoType:
        """
        Detect the type of video content.

        Uses sampling and heuristics to classify the video.
        """
        try:
            import cv2
            import numpy as np

            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                return VideoType.UNKNOWN

            # Sample 10 evenly spaced frames
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            sample_indices = np.linspace(0, total_frames - 1, 10, dtype=int)

            motion_scores = []
            edge_densities = []
            prev_frame = None

            for idx in sample_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()
                if not ret:
                    continue

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                # Compute edge density
                edges = cv2.Canny(gray, 100, 200)
                edge_density = np.sum(edges > 0) / edges.size
                edge_densities.append(edge_density)

                # Compute motion (difference from previous frame)
                if prev_frame is not None:
                    diff = cv2.absdiff(prev_frame, gray)
                    motion_score = np.mean(diff) / 255.0
                    motion_scores.append(motion_score)

                prev_frame = gray

            cap.release()

            # Analyze metrics
            avg_motion = np.mean(motion_scores) if motion_scores else 0
            avg_edges = np.mean(edge_densities) if edge_densities else 0

            # Classification heuristics
            if avg_motion < 0.02 and avg_edges > 0.1:
                return VideoType.PRESENTATION
            elif avg_motion < 0.05 and avg_edges > 0.15:
                return VideoType.SCREENCAST
            elif avg_motion > 0.1:
                return VideoType.DOCUMENTARY
            elif avg_motion < 0.03:
                return VideoType.LECTURE
            else:
                return VideoType.UNKNOWN

        except ImportError:
            logger.warning("opencv-python not installed")
            return VideoType.UNKNOWN
        except Exception as e:
            logger.error(f"Video type detection failed: {e}")
            return VideoType.UNKNOWN

    def extract(
        self,
        video_path: Path,
        output_dir: Optional[Path] = None,
        auto_detect_type: bool = True,
    ) -> Tuple[List[ExtractedFrame], VideoType]:
        """
        Main extraction method.

        Args:
            video_path: Path to video file
            output_dir: Directory for extracted frames (default: temp dir)
            auto_detect_type: Whether to auto-detect video type

        Returns:
            Tuple of (extracted frames, detected video type)
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        # Create output directory
        if output_dir is None:
            output_dir = Path(tempfile.mkdtemp(prefix="keyframes_"))
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        # Get video info
        info = self.get_video_info(video_path)
        duration = info["duration"]
        if duration <= 0:
            raise ValueError("Could not determine video duration")

        logger.info(f"Processing video: {duration:.1f}s at {info['fps']:.1f}fps")

        # Detect video type and adjust config
        video_type = VideoType.UNKNOWN
        if auto_detect_type:
            video_type = self.detect_video_type(video_path)
            logger.info(f"Detected video type: {video_type.value}")

            # Use type-specific config
            type_config = self.TYPE_CONFIGS[video_type]
            self.config.min_interval = type_config.min_interval
            self.config.max_interval = type_config.max_interval
            self.config.scene_threshold = type_config.scene_threshold

        # Step 1: Detect scenes
        scene_timestamps = self.detect_scenes(video_path)

        # Step 2: Generate interval samples to fill gaps
        interval_timestamps = self.generate_interval_samples(
            duration, scene_timestamps
        )

        # Combine and deduplicate timestamps
        all_timestamps = sorted(set(scene_timestamps + interval_timestamps))

        # Apply max_frames limit if set
        if self.config.max_frames and len(all_timestamps) > self.config.max_frames:
            # Keep evenly distributed subset
            step = len(all_timestamps) / self.config.max_frames
            all_timestamps = [
                all_timestamps[int(i * step)]
                for i in range(self.config.max_frames)
            ]

        logger.info(
            f"Extracting {len(all_timestamps)} frames "
            f"({len(scene_timestamps)} scene changes + {len(interval_timestamps)} interval samples)"
        )

        # Step 3: Extract frames
        frames = self.extract_frames(video_path, all_timestamps, output_dir)

        # Mark extraction reasons
        scene_set = set(scene_timestamps)
        for frame in frames:
            if frame.timestamp in scene_set:
                frame.extraction_reason = "scene_change"
            elif frame.timestamp == 0 or frame.timestamp >= duration - 1:
                frame.extraction_reason = "forced"
            else:
                frame.extraction_reason = "interval"

        # Step 4: Deduplicate
        unique_frames = self.deduplicate_frames(frames)

        logger.info(
            f"Extraction complete: {len(unique_frames)} unique frames from {video_path.name}"
        )

        return unique_frames, video_type
