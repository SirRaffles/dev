import { useEffect, RefObject } from 'react';
import type { AudioPlayerHandle } from '../components/AudioPlayer';

interface UseGlobalKeyboardOptions {
  audioRef: RefObject<AudioPlayerHandle | null>;
  enabled: boolean;
}

export default function useGlobalKeyboard({ audioRef, enabled }: UseGlobalKeyboardOptions) {
  useEffect(() => {
    if (!enabled) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target?.closest('button, [role="button"], a, [role="tab"], [role="menuitem"], input, textarea, select')) return;
      if (target?.isContentEditable) return;

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
