import React, { useRef, useEffect, useState, useCallback, forwardRef, useImperativeHandle } from 'react';
import { Play, Pause, SkipBack, SkipForward } from 'lucide-react';

// Format timestamp for display
const formatTime = (seconds) => {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 100);

  if (hrs > 0) {
    return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
  }
  return `${mins}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
};

const AudioPlayer = forwardRef(function AudioPlayer({
  audioUrl,
  onTimeUpdate,
  className = ''
}, ref) {
  const audioRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  // Audio event handlers
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const handleTimeUpdate = () => {
      setCurrentTime(audio.currentTime);
      onTimeUpdate?.(audio.currentTime);
    };

    const handleLoadedMetadata = () => {
      setDuration(audio.duration);
    };

    const handleEnded = () => {
      setIsPlaying(false);
    };

    audio.addEventListener('timeupdate', handleTimeUpdate);
    audio.addEventListener('loadedmetadata', handleLoadedMetadata);
    audio.addEventListener('ended', handleEnded);

    return () => {
      audio.removeEventListener('timeupdate', handleTimeUpdate);
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
      audio.removeEventListener('ended', handleEnded);
    };
  }, [onTimeUpdate]);

  const togglePlayPause = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;

    if (isPlaying) {
      audio.pause();
    } else {
      audio.play();
    }
    setIsPlaying(!isPlaying);
  }, [isPlaying]);

  const skipBackward = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = Math.max(0, audio.currentTime - 5);
  }, []);

  const skipForward = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = Math.min(duration, audio.currentTime + 5);
  }, [duration]);

  const seekToTime = useCallback((time) => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = time;
    if (!isPlaying) {
      audio.play();
      setIsPlaying(true);
    }
  }, [isPlaying]);

  // Expose methods to parent via ref
  useImperativeHandle(ref, () => ({
    seekToTime,
    play: () => {
      const audio = audioRef.current;
      if (audio) {
        audio.play();
        setIsPlaying(true);
      }
    },
    pause: () => {
      const audio = audioRef.current;
      if (audio) {
        audio.pause();
        setIsPlaying(false);
      }
    },
    getCurrentTime: () => currentTime,
    getDuration: () => duration,
  }), [seekToTime, currentTime, duration]);

  const handleSeekClick = useCallback((e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percentage = x / rect.width;
    seekToTime(percentage * duration);
  }, [duration, seekToTime]);

  if (!audioUrl) return null;

  return (
    <div className={`bg-slate-700/50 rounded-xl p-4 ${className}`}>
      <audio ref={audioRef} src={audioUrl} preload="metadata" />

      <div className="flex items-center gap-4 mb-3">
        <button
          onClick={skipBackward}
          className="p-2 bg-slate-600 hover:bg-slate-500 rounded-lg transition-colors"
          title="Skip back 5 seconds"
        >
          <SkipBack className="w-5 h-5" />
        </button>
        <button
          onClick={togglePlayPause}
          className="p-3 bg-blue-500 hover:bg-blue-600 rounded-lg transition-colors"
          title={isPlaying ? 'Pause' : 'Play'}
        >
          {isPlaying ? <Pause className="w-6 h-6" /> : <Play className="w-6 h-6" />}
        </button>
        <button
          onClick={skipForward}
          className="p-2 bg-slate-600 hover:bg-slate-500 rounded-lg transition-colors"
          title="Skip forward 5 seconds"
        >
          <SkipForward className="w-5 h-5" />
        </button>
        <div className="flex items-center gap-3 text-sm font-mono">
          <span>{formatTime(currentTime)}</span>
          <span className="text-slate-400">/</span>
          <span className="text-slate-400">{formatTime(duration)}</span>
        </div>
      </div>

      {/* Seek bar */}
      <div
        className="relative h-2 bg-slate-600 rounded-full overflow-hidden cursor-pointer"
        onClick={handleSeekClick}
      >
        <div
          className="absolute top-0 left-0 h-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all"
          style={{ width: `${(currentTime / duration) * 100 || 0}%` }}
        />
      </div>
    </div>
  );
});

export { formatTime };
export default AudioPlayer;
