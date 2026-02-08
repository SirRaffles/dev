import { useState, useRef, useEffect, useCallback } from 'react';
import { isMediaFile } from '../utils/api';

/**
 * Manages audio playback state: URL lifecycle, seek, time tracking.
 */
export default function useAudioPlayback() {
  const [audioUrl, setAudioUrl] = useState(null);
  const [currentTime, setCurrentTime] = useState(0);
  const audioRef = useRef(null);

  const setFileAudio = useCallback((file) => {
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    if (file && isMediaFile(file.name)) {
      setAudioUrl(URL.createObjectURL(file));
    } else {
      setAudioUrl(null);
    }
  }, [audioUrl]);

  const clearAudio = useCallback(() => {
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioUrl(null);
    setCurrentTime(0);
  }, [audioUrl]);

  const seekToTime = useCallback((time) => {
    if (audioRef.current) {
      audioRef.current.seekToTime(time);
    }
  }, []);

  const handleTimeUpdate = useCallback((time) => {
    setCurrentTime(time);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  return {
    audioUrl,
    currentTime,
    audioRef,
    setFileAudio,
    clearAudio,
    seekToTime,
    handleTimeUpdate,
  };
}
