import { useEffect, RefObject } from 'react';
import { AudioPlayerHandle } from '../components/AudioPlayer';

interface UseGlobalKeyboardOptions {
  audioRef: RefObject<AudioPlayerHandle | null>;
  enabled: boolean;
}

export default function useGlobalKeyboard({ audioRef, enabled }: UseGlobalKeyboardOptions) {
  useEffect(() => {
    if (!enabled) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      if ((e.target as HTMLElement)?.isContentEditable) return;

      const audio = audioRef.current;
      if (!audio) return;

      switch (e.code) {
        case 'Space':
          e.preventDefault();
          audio.togglePlayPause();
          break;
        case 'ArrowLeft':
          e.preventDefault();
          audio.seekToTime(Math.max(0, audio.getCurrentTime() - 5));
          break;
        case 'ArrowRight':
          e.preventDefault();
          audio.seekToTime(Math.min(audio.getDuration(), audio.getCurrentTime() + 5));
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [audioRef, enabled]);
}
