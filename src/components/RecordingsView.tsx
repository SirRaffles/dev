import React, { useState, useMemo } from 'react';
import {
  Mic, CheckCircle, Clock, AlertCircle, Loader2, RefreshCw,
  Search, Edit3, FileText, X, Check, Users, ArrowUpDown,
  Upload, Link as LinkIcon,
} from 'lucide-react';
import useRecordings, { RecordingsStatus, RecordingsSort } from '../hooks/useRecordings';
import {
  JPRRecording, JPRTranscript, Segment, fetchJPRTranscript, fetchJobStatus, renameJPRRecording,
} from '../utils/api';

const STATUS_FILTERS: { key: RecordingsStatus; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'unprocessed', label: 'Unprocessed' },
  { key: 'processed', label: 'Processed' },
  { key: 'processing', label: 'Processing' },
  { key: 'failed', label: 'Failed' },
];

function StatusIcon({ status }: { status: string }) {
  const className = 'w-5 h-5';
  switch (status) {
    case 'completed':
      return <CheckCircle className={`${className} text-green-500 dark:text-green-400`} aria-label="Processed" />;
    case 'processing':
    case 'pending_submission':
      return <Loader2 className={`${className} text-blue-500 dark:text-blue-400 animate-spin`} aria-label="Processing" />;
    case 'failed':
    case 'permanently_failed':
      return <AlertCircle className={`${className} text-red-500 dark:text-red-400`} aria-label="Failed" />;
    default:
      return <Clock className={`${className} text-slate-500 dark:text-slate-400`} aria-label="Unprocessed" />;
  }
}

/**
 * Small badge showing where the recording came from. JPR-sourced rows are
 * the default and intentionally render no badge (would just add noise) —
 * we badge the non-JPR cases so they're scannable.
 */
function SourceBadge({ source }: { source?: string }) {
  const common = 'inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded font-medium';
  if (source === 'upload') {
    return (
      <span
        className={`${common} bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300`}
        title="Direct upload"
      >
        <Upload className="w-3 h-3" aria-hidden="true" />
        Upload
      </span>
    );
  }
  if (source === 'youtube') {
    return (
      <span
        className={`${common} bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300`}
        title="YouTube ingest"
      >
        <LinkIcon className="w-3 h-3" aria-hidden="true" />
        YouTube
      </span>
    );
  }
  return null;
}

function StatusBadge({ status }: { status: string }) {
  const common = 'text-xs px-2 py-1 rounded-full font-medium';
  if (status === 'completed') {
    return <span className={`${common} bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400`}>Processed</span>;
  }
  if (status === 'processing' || status === 'pending_submission') {
    return <span className={`${common} bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400`}>Processing</span>;
  }
  if (status === 'failed' || status === 'permanently_failed') {
    return <span className={`${common} bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400`}>Failed</span>;
  }
  return <span className={`${common} bg-slate-100 text-slate-600 dark:bg-slate-600 dark:text-slate-300`}>Unprocessed</span>;
}

function formatDate(iso?: string | null) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function RenameInline({
  rec, onDone,
}: { rec: JPRRecording; onDone: (newPath?: string) => void }) {
  const stem = rec.filename.replace(/\.m4a$/i, '');
  const [value, setValue] = useState(stem);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const handleSave = async () => {
    const trimmed = value.trim();
    if (!trimmed || trimmed === stem) {
      onDone();
      return;
    }
    setSaving(true);
    setErr(null);
    try {
      const res = await renameJPRRecording(rec.path, trimmed);
      onDone(res.new_path);
    } catch (e: any) {
      setErr(e?.message || 'Rename failed');
      setSaving(false);
    }
  };

  return (
    <div className="flex-1 min-w-0">
      <div className="flex items-center gap-1">
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          autoFocus
          disabled={saving}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSave();
            if (e.key === 'Escape') onDone();
          }}
          aria-label="New recording name"
          className="flex-1 min-w-0 px-2 py-1 text-sm rounded border border-blue-400 bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <span className="text-xs text-slate-500">.m4a</span>
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          aria-label="Save name"
          className="p-2 min-w-[40px] min-h-[40px] rounded text-green-600 hover:bg-green-50 dark:hover:bg-green-900/20 disabled:opacity-50 flex items-center justify-center"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" aria-hidden="true" />}
        </button>
        <button
          type="button"
          onClick={() => onDone()}
          disabled={saving}
          aria-label="Cancel rename"
          className="p-2 min-w-[40px] min-h-[40px] rounded text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 disabled:opacity-50 flex items-center justify-center"
        >
          <X className="w-4 h-4" aria-hidden="true" />
        </button>
      </div>
      {err && <p role="alert" className="text-xs text-red-500 mt-1">{err}</p>}
    </div>
  );
}

function TranscriptModal({
  rec, onClose,
}: { rec: JPRRecording; onClose: () => void }) {
  const [data, setData] = useState<JPRTranscript | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // Upload-sourced rows have an absolute temp path (e.g.
        // /var/folders/.../whisper-upload-XXXX/audio.wav) that the JPR
        // transcript endpoint rejects as path-traversal. For those rows
        // we fetch the job result directly instead.
        if (rec.source === 'upload' && rec.job_id) {
          const job = await fetchJobStatus(rec.job_id);
          // Backend's /job/{id} returns segments/language/speakers at the
          // TOP level for completed jobs (not nested under .result). The
          // JobStatus TS type is loose here, so coerce via `any` to read
          // the runtime shape used everywhere else (see App.tsx + the
          // backend route in routes/transcription.py:541).
          const jobAny = job as any;
          const segments = (jobAny.segments as Segment[] | undefined) || [];
          const speakers: string[] = Array.isArray(jobAny.speakers)
            ? jobAny.speakers.filter((s: unknown): s is string => Boolean(s))
            : Array.from(
                new Set(
                  segments
                    .map((s) => s.speaker)
                    .filter((s): s is string => Boolean(s))
                )
              );
          const transcriptText: string | null =
            (typeof jobAny.text === 'string' && jobAny.text) ||
            segments.map((s) => s.text).join(' ').trim() ||
            null;
          if (!cancelled) {
            setData({
              path: rec.path,
              filename: rec.filename,
              transcript_text: transcriptText,
              segments,
              speakers,
              language: (jobAny.language as string | null) ?? null,
              job_id: job.job_id,
              status: job.status,
            });
          }
        } else {
          const t = await fetchJPRTranscript(rec.path);
          if (!cancelled) setData(t);
        }
      } catch (e: any) {
        if (!cancelled) setErr(e?.message || 'Failed to load transcript');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [rec.path, rec.source, rec.job_id, rec.filename]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Transcript for ${rec.filename}`}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-3xl max-h-[85vh] bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl shadow-xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-700">
          <div className="flex items-center gap-2 min-w-0">
            <FileText className="w-5 h-5 text-blue-500 flex-shrink-0" aria-hidden="true" />
            <h2 className="text-lg font-semibold truncate">{rec.filename}</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close transcript"
            className="p-2 min-w-[40px] min-h-[40px] rounded hover:bg-slate-100 dark:hover:bg-slate-700 flex items-center justify-center"
          >
            <X className="w-5 h-5" aria-hidden="true" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {loading && (
            <div className="flex items-center justify-center py-12 text-slate-500 dark:text-slate-400">
              <Loader2 className="w-5 h-5 animate-spin mr-2" aria-hidden="true" /> Loading transcript…
            </div>
          )}
          {err && (
            <div role="alert" className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-300 p-3 rounded text-sm">
              {err}
            </div>
          )}
          {data && !loading && (
            <>
              {(data.speakers && data.speakers.length > 0) && (
                <div className="mb-3 flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                  <Users className="w-4 h-4" aria-hidden="true" />
                  <span>Speakers: {data.speakers.join(', ')}</span>
                </div>
              )}
              {data.segments && data.segments.length > 0 ? (
                <div className="space-y-3">
                  {data.segments.map((seg: any, i: number) => (
                    <div key={i} className="flex gap-3 text-sm">
                      <span className="text-slate-500 dark:text-slate-400 font-mono flex-shrink-0 w-20">
                        {typeof seg.start === 'number' ? new Date(seg.start * 1000).toISOString().substring(14, 19) : ''}
                      </span>
                      <div className="flex-1">
                        {seg.speaker && (
                          <span className="text-purple-600 dark:text-purple-400 font-medium mr-2">
                            {seg.speaker}:
                          </span>
                        )}
                        <span className="text-slate-700 dark:text-slate-200">{seg.text}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : data.transcript_text ? (
                <pre className="whitespace-pre-wrap text-sm text-slate-700 dark:text-slate-200 font-sans">
                  {data.transcript_text}
                </pre>
              ) : (
                <p className="text-slate-500 dark:text-slate-400 text-sm">No transcript available yet.</p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function RecordingsView() {
  const [status, setStatus] = useState<RecordingsStatus>('all');
  const [sortBy, setSortBy] = useState<RecordingsSort>('date');
  const [query, setQuery] = useState('');
  const [renamingPath, setRenamingPath] = useState<string | null>(null);
  const [viewingTranscript, setViewingTranscript] = useState<JPRRecording | null>(null);

  const { recordings, total, loading, error, refresh } = useRecordings({
    status, sortBy, q: query,
  });

  // "completed_at" only makes sense for processed rows — clamp back to
  // "date" when the current filter isn't Processed.
  const effectiveSortBy: RecordingsSort = useMemo(
    () => (status === 'processed' ? sortBy : 'date'),
    [status, sortBy]
  );

  const hitRename = (r: JPRRecording) => setRenamingPath(r.path);
  const onRenameDone = (newPath?: string) => {
    setRenamingPath(null);
    if (newPath) refresh();
  };

  return (
    <div className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-4 sm:p-6 border border-slate-200 dark:border-slate-700 shadow-sm dark:shadow-none">
      <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <Mic className="w-6 h-6 text-blue-500 dark:text-blue-400" aria-hidden="true" />
          <h2 className="text-xl font-semibold">Recordings</h2>
          <span className="text-sm text-slate-500 dark:text-slate-400">({total} {total === 1 ? 'recording' : 'recordings'})</span>
        </div>
        <button
          type="button"
          onClick={refresh}
          aria-label="Refresh recordings"
          className="p-2.5 min-w-[44px] min-h-[44px] rounded-lg text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors flex items-center justify-center"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} aria-hidden="true" />
        </button>
      </div>

      {/* Filter pills */}
      <div
        role="tablist"
        aria-label="Recordings status filter"
        className="flex flex-wrap gap-2 mb-3"
      >
        {STATUS_FILTERS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={status === key}
            onClick={() => setStatus(key)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              status === key
                ? 'bg-blue-500 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Search + sort row */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search filenames, transcripts, speakers…"
            aria-label="Search recordings"
            className="w-full pl-10 pr-3 py-2 text-sm rounded-lg border border-slate-300 bg-white text-slate-900 placeholder-slate-400 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400 dark:border-slate-600 dark:bg-slate-700 dark:text-white dark:placeholder-slate-500"
          />
        </div>
        <label className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
          <ArrowUpDown className="w-4 h-4" aria-hidden="true" />
          <span>Sort by</span>
          <select
            value={effectiveSortBy}
            onChange={(e) => setSortBy(e.target.value as RecordingsSort)}
            className="px-2 py-1.5 text-sm rounded border border-slate-300 bg-white text-slate-900 focus:outline-none focus:border-blue-400 dark:border-slate-600 dark:bg-slate-700 dark:text-white"
          >
            <option value="date">Recording date</option>
            {status === 'processed' && <option value="completed_at">Processing date</option>}
          </select>
        </label>
      </div>

      {/* Error banner */}
      {error && (
        <div role="alert" className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-3 mb-3 text-red-600 dark:text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* List */}
      {loading && recordings.length === 0 ? (
        <div className="flex items-center justify-center py-12 text-slate-500 dark:text-slate-400">
          <Loader2 className="w-6 h-6 animate-spin mr-2" aria-hidden="true" />
          Loading recordings…
        </div>
      ) : recordings.length === 0 ? (
        <div className="text-center py-12 text-slate-500 dark:text-slate-400">
          <Mic className="w-12 h-12 mx-auto mb-3 opacity-50" aria-hidden="true" />
          <p>No recordings match this filter.</p>
          {query && <p className="text-sm mt-1">Try a different search term.</p>}
        </div>
      ) : (
        <div className="space-y-2">
          {/* Column header (desktop only) */}
          <div className="hidden sm:flex items-center gap-3 px-3 pb-2 text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-700">
            <div className="w-5 flex-shrink-0" aria-hidden="true" />
            <div className="flex-1 min-w-0">File</div>
            <div className="flex-shrink-0 w-36 text-right">
              {effectiveSortBy === 'completed_at' ? 'Processed' : 'Recorded'}
            </div>
            <div className="flex-shrink-0 w-16 text-right">Size</div>
            <div className="flex-shrink-0 w-[112px] text-right" aria-hidden="true" />
          </div>
          {recordings.map((rec) => {
            const isRenaming = renamingPath === rec.path;
            const canOpenTranscript = rec.transcript_exists;
            const effectiveStatus = rec.effective_status || rec.status;
            const whenShown = effectiveSortBy === 'completed_at' ? rec.completed_at : rec.date;
            return (
              <div
                key={rec.path}
                className="flex items-center gap-3 p-3 rounded-xl bg-slate-50 dark:bg-slate-700/50 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
              >
                <div className="flex-shrink-0"><StatusIcon status={effectiveStatus} /></div>

                {isRenaming ? (
                  <RenameInline rec={rec} onDone={onRenameDone} />
                ) : (
                  <button
                    type="button"
                    onClick={() => canOpenTranscript && setViewingTranscript(rec)}
                    disabled={!canOpenTranscript}
                    title={canOpenTranscript ? 'Open transcript' : 'No transcript yet'}
                    className={`flex-1 min-w-0 text-left ${canOpenTranscript ? 'cursor-pointer hover:underline' : 'cursor-default'}`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <p className="text-sm font-medium truncate">{rec.filename}</p>
                      <SourceBadge source={rec.source} />
                    </div>
                    <p className="text-xs text-slate-500 dark:text-slate-400 truncate sm:hidden">
                      {formatDate(whenShown)}
                      {' · '}
                      {(rec.size_bytes / 1024 / 1024).toFixed(1)} MB
                    </p>
                    {rec.speakers && rec.speakers.length > 0 && (
                      <p className="text-xs text-purple-600 dark:text-purple-400 truncate">
                        {rec.speakers.length} speaker{rec.speakers.length === 1 ? '' : 's'}
                        {rec.speakers.length <= 4 && `: ${rec.speakers.join(', ')}`}
                      </p>
                    )}
                    {rec.transcript_preview && query && (
                      <p className="text-xs text-slate-600 dark:text-slate-400 mt-1 italic line-clamp-2">
                        “{rec.transcript_preview.replace(/\s+/g, ' ').trim()}”
                      </p>
                    )}
                  </button>
                )}

                {/* Dedicated date + size columns (hidden on narrow screens) */}
                {!isRenaming && (
                  <>
                    <div className="hidden sm:block flex-shrink-0 text-right w-36 text-xs text-slate-500 dark:text-slate-400">
                      {formatDate(whenShown)}
                    </div>
                    <div className="hidden sm:block flex-shrink-0 text-right w-16 text-xs text-slate-500 dark:text-slate-400 tabular-nums">
                      {(rec.size_bytes / 1024 / 1024).toFixed(1)} MB
                    </div>
                  </>
                )}

                <div className="flex items-center gap-1 flex-shrink-0">
                  <StatusBadge status={effectiveStatus} />
                  {!isRenaming && (
                    <>
                      {canOpenTranscript && (
                        <button
                          type="button"
                          onClick={() => setViewingTranscript(rec)}
                          aria-label={`Open transcript for ${rec.filename}`}
                          className="p-2 min-w-[40px] min-h-[40px] rounded-lg text-slate-500 dark:text-slate-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors flex items-center justify-center"
                          title="Open transcript"
                        >
                          <FileText className="w-4 h-4" aria-hidden="true" />
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => hitRename(rec)}
                        aria-label={`Rename ${rec.filename}`}
                        className="p-2 min-w-[40px] min-h-[40px] rounded-lg text-slate-500 dark:text-slate-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors flex items-center justify-center"
                        title="Rename"
                      >
                        <Edit3 className="w-4 h-4" aria-hidden="true" />
                      </button>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {viewingTranscript && (
        <TranscriptModal rec={viewingTranscript} onClose={() => setViewingTranscript(null)} />
      )}
    </div>
  );
}

export default RecordingsView;
