import React from 'react';
import { X } from 'lucide-react';

function YouTubeInput({
  url,
  onUrlChange,
  onClear,
  disabled = false,
}) {
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
        className="w-full px-4 py-4 bg-slate-700 border border-slate-600 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400 disabled:opacity-50"
      />
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
