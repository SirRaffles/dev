import React, { useRef, useEffect, useState, useCallback, forwardRef, useImperativeHandle } from 'react';
import { Play, Pause, SkipBack, SkipForward } from 'lucide-react';

// Format timestamp for display
export const formatTime = (seconds: number): string => {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 100);

  if (hrs > 0) {
    return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
  }
  return `${mins}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
};

export interface AudioPlayerHandle {
  seekToTime: (time: number) => void;
  play: () => void;
  pause: () => void;
  getCurrentTime: () => number;
  getDuration: () => number;
}

interface AudioPlayerProps {
  audioUrl: string;
  onTimeUpdate?: (time: number) => void;
  className?: string;
}

const AudioPlayer = forwardRef<AudioPlayerHandle, AudioPlayerProps>(function AudioPlayer({
  audioUrl,
  onTimeUpdate,
  className = ''
}, ref) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

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

  const seekToTime = useCallback((time: number) => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = time;
    if (!isPlaying) {
      audio.play();
      setIsPlaying(true);
    }
  }, [isPlaying]);

  useImperativeHandle(ref, () => ({
    seekToTime,
    play: () => {
      const audio = audioRef.current;
      if (audio) { audio.play(); setIsPlaying(true); }
    },
    pause: () => {
      const audio = audioRef.current;
      if (audio) { audio.pause(); setIsPlaying(false); }
    },
    getCurrentTime: () => currentTime,
    getDuration: () => duration,
  }), [seekToTime, currentTime, duration]);

  const handleSeekChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    seekToTime(parseFloat(e.target.value));
  }, [seekToTime]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === ' ' || e.code === 'Space') {
      e.preventDefault();
      togglePlayPause();
    }
  }, [togglePlayPause]);

  if (!audioUrl) return null;

  return (
    <div
      className={`bg-slate-100 dark:bg-slate-700/50 rounded-xl p-4 ${className}`}
      ref={containerRef}
      tabIndex={0}
      onKeyDown={handleKeyDown}
    >
      <audio ref={audioRef} src={audioUrl} preload="metadata" />

      <div className="flex items-center gap-3 mb-3 flex-wrap">
        <button
          onClick={skipBackward}
          className="p-2.5 bg-slate-200 hover:bg-slate-300 dark:bg-slate-600 dark:hover:bg-slate-500 rounded-lg transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center"
          title="Skip back 5 seconds"
          aria-label="Skip back 5 seconds"
        >
          <SkipBack className="w-5 h-5" />
        </button>
        <button
          onClick={togglePlayPause}
          className="p-3 bg-blue-500 hover:bg-blue-600 rounded-lg transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center"
          title={isPlaying ? 'Pause' : 'Play'}
          aria-label={isPlaying ? 'Pause' : 'Play'}
        >
          {isPlaying ? <Pause className="w-6 h-6" /> : <Play className="w-6 h-6" />}
        </button>
        <button
          onClick={skipForward}
          className="p-2.5 bg-slate-200 hover:bg-slate-300 dark:bg-slate-600 dark:hover:bg-slate-500 rounded-lg transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center"
          title="Skip forward 5 seconds"
          aria-label="Skip forward 5 seconds"
        >
          <SkipForward className="w-5 h-5" />
        </button>
        <div className="flex items-center gap-2 text-sm font-mono ml-1">
          <span>{formatTime(currentTime)}</span>
          <span className="text-slate-400">/</span>
          <span className="text-slate-400">{formatTime(duration)}</span>
        </div>
      </div>

      <input
        type="range"
        min={0}
        max={duration || 0}
        step={0.1}
        value={currentTime}
        onChange={handleSeekChange}
        aria-label="Seek audio position"
        className="w-full h-2 rounded-full appearance-none cursor-pointer bg-slate-300 dark:bg-slate-600
          [&::-webkit-slider-thumb]:appearance-none
          [&::-webkit-slider-thumb]:w-4
          [&::-webkit-slider-thumb]:h-4
          [&::-webkit-slider-thumb]:rounded-full
          [&::-webkit-slider-thumb]:bg-blue-500
          [&::-webkit-slider-thumb]:hover:bg-blue-400
          [&::-webkit-slider-thumb]:shadow-md
          [&::-moz-range-thumb]:w-4
          [&::-moz-range-thumb]:h-4
          [&::-moz-range-thumb]:rounded-full
          [&::-moz-range-thumb]:bg-blue-500
          [&::-moz-range-thumb]:border-0
          [&::-moz-range-thumb]:hover:bg-blue-400
          [&::-webkit-slider-runnable-track]:rounded-full
          [&::-moz-range-track]:rounded-full
          accent-blue-500"
      />
    </div>
  );
});

export default AudioPlayer;
