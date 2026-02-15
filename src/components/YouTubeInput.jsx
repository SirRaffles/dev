import React, { useMemo } from 'react';
import { X } from 'lucide-react';

const YOUTUBE_PATTERN = /^https?:\/\/(?:www\.)?(?:youtube\.com\/(?:watch\?.*v=|shorts\/|live\/|embed\/)|youtu\.be\/|music\.youtube\.com\/watch\?)/;

function YouTubeInput({
  url,
  onUrlChange,
  onClear,
  disabled = false,
}) {
  const isValid = useMemo(() => {
    if (!url) return null;
    return YOUTUBE_PATTERN.test(url);
  }, [url]);

  const borderClass = isValid === null
    ? 'border-slate-600 focus:border-blue-400 focus:ring-blue-400'
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
        className={`w-full px-4 py-4 bg-slate-700 border rounded-xl text-white placeholder-slate-400 focus:outline-none focus:ring-1 disabled:opacity-50 ${borderClass}`}
      />
      {isValid === false && (
        <p className="text-xs text-red-400 mt-1">
          Enter a valid YouTube URL (youtube.com/watch, youtu.be/, shorts/, live/, embed/, or music.youtube.com)
        </p>
      )}
      {url && !disabled && (
        <button
          onClick={onClear}
          aria-label="Clear URL"
          className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded-full hover:bg-slate-600"
        >
          <X className="w-4 h-4" aria-hidden="true" />
        </button>
      )}
    </div>
  );
}

export default React.memo(YouTubeInput);
