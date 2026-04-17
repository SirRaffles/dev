import { useState, useRef, useEffect, useCallback } from 'react';
import { isMediaFile } from '../utils/api';

export default function useAudioPlayback() {
  const [audioUrl, setAudioUrl] = useState(null);
  const [currentTime, setCurrentTime] = useState(0);
  const audioRef = useRef(null);
  const urlRef = useRef(null);

  const setFileAudio = useCallback((file) => {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    if (file && isMediaFile(file.name)) {
      const next = URL.createObjectURL(file);
      urlRef.current = next;
      setAudioUrl(next);
    } else {
      urlRef.current = null;
      setAudioUrl(null);
    }
  }, []);

  const clearAudio = useCallback(() => {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    urlRef.current = null;
    setAudioUrl(null);
    setCurrentTime(0);
  }, []);

  const seekToTime = useCallback((time) => {
    if (audioRef.current) {
      audioRef.current.seekToTime(time);
    }
  }, []);

  const handleTimeUpdate = useCallback((time) => {
    setCurrentTime(time);
  }, []);

  useEffect(() => {
    return () => {
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    };
  }, []);

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
