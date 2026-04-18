import React, { useMemo } from 'react';
import { X } from 'lucide-react';

// KEEP IN SYNC WITH backend/services/youtube.py YOUTUBE_URL_RE
// Requires an 11-char video id in every variant (current YouTube spec).
const YOUTUBE_URL_RE = /^https?:\/\/(?:www\.)?(?:youtube\.com\/(?:watch\?(?:[^#]*&)?v=[A-Za-z0-9_-]{11}|shorts\/[A-Za-z0-9_-]{11}|live\/[A-Za-z0-9_-]{11}|embed\/[A-Za-z0-9_-]{11})|youtu\.be\/[A-Za-z0-9_-]{11}|music\.youtube\.com\/watch\?(?:[^#]*&)?v=[A-Za-z0-9_-]{11})/;

interface YouTubeInputProps {
  url: string;
  onUrlChange: (url: string) => void;
  onClear: () => void;
  disabled?: boolean;
}

function YouTubeInput({
  url,
  onUrlChange,
  onClear,
  disabled = false,
}: YouTubeInputProps) {
  const isValid = useMemo(() => {
    if (!url) return null;
    return YOUTUBE_URL_RE.test(url);
  }, [url]);

  const borderClass = isValid === null
    ? 'border-slate-300 dark:border-slate-600 focus:border-blue-400 focus:ring-blue-400'
    : isValid
      ? 'border-green-500 focus:border-green-400 focus:ring-green-400'
      : 'border-red-500 focus:border-red-400 focus:ring-red-400';

  return (
    <div className="relative">
      <label htmlFor="youtube-url" className="sr-only">YouTube URL</label>
      <input
        id="youtube-url"
        type="url"
        value={url}
        onChange={(e) => onUrlChange(e.target.value)}
        disabled={disabled}
        placeholder="https://www.youtube.com/watch?v=..."
        aria-label="YouTube video URL"
        aria-invalid={isValid === false ? 'true' : undefined}
        aria-describedby={isValid === false ? 'youtube-url-error' : undefined}
        className={`w-full px-4 py-4 bg-white dark:bg-slate-700 border rounded-xl text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-1 disabled:opacity-50 ${borderClass}`}
      />
      {isValid === false && (
        <p id="youtube-url-error" className="text-xs text-red-400 mt-1">
          Enter a valid YouTube URL (youtube.com/watch, youtu.be/, shorts/, live/, embed/, or music.youtube.com)
        </p>
      )}
      {url && !disabled && (
        <button
          onClick={onClear}
          aria-label="Clear URL"
          className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded-full hover:bg-slate-200 dark:hover:bg-slate-600"
        >
          <X className="w-4 h-4" aria-hidden="true" />
        </button>
      )}
    </div>
  );
}

export default React.memo(YouTubeInput);
