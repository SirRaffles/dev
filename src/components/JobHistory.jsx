import React, { useState, useEffect, useCallback } from 'react';
import { Clock, ChevronDown, ChevronUp, CheckCircle, AlertCircle, Loader2, FileText, RefreshCw } from 'lucide-react';
import { API_URL } from '../utils/api';

const STATUS_ICONS = {
  completed: <CheckCircle className="w-4 h-4 text-green-400" />,
  failed: <AlertCircle className="w-4 h-4 text-red-400" />,
  processing: <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />,
  pending: <Clock className="w-4 h-4 text-slate-400" />,
};

function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr + 'Z'); // SQLite timestamps are UTC
  const now = new Date();
  const diffMs = now - d;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d ago`;
  return d.toLocaleDateString();
}

export default function JobHistory({ onSelectJob }) {
  const [expanded, setExpanded] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await fetch(`${API_URL}/jobs?limit=20`);
      if (resp.ok) {
        const data = await resp.json();
        setJobs(data.jobs || []);
        setTotal(data.total || 0);
      }
    } catch {
      // Silently fail — history is non-critical
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (expanded && jobs.length === 0) fetchJobs();
  }, [expanded, jobs.length, fetchJobs]);

  return (
    <div className="mt-6">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-slate-400 hover:text-slate-200 transition-colors text-sm font-medium"
      >
        <Clock className="w-4 h-4" />
        Recent Transcriptions {total > 0 && `(${total})`}
        {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>

      {expanded && (
        <div className="mt-3 bg-slate-800/50 rounded-xl border border-slate-700/50 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 border-b border-slate-700/50">
            <span className="text-xs text-slate-500">{total} total jobs</span>
            <button
              onClick={fetchJobs}
              disabled={loading}
              className="text-slate-500 hover:text-slate-300 transition-colors"
              title="Refresh"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {jobs.length === 0 && !loading && (
            <p className="text-sm text-slate-500 text-center py-6">No transcriptions yet</p>
          )}

          {loading && jobs.length === 0 && (
            <div className="flex justify-center py-6">
              <Loader2 className="w-5 h-5 text-slate-500 animate-spin" />
            </div>
          )}

          <div className="max-h-64 overflow-y-auto">
            {jobs.map((job) => (
              <button
                key={job.job_id}
                onClick={() => onSelectJob(job.job_id)}
                className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-slate-700/50 transition-colors text-left border-b border-slate-700/30 last:border-0"
              >
                {STATUS_ICONS[job.status] || <FileText className="w-4 h-4 text-slate-500" />}
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-slate-200 truncate">
                    {job.file_path || job.job_id.slice(0, 8)}
                  </p>
                  <p className="text-xs text-slate-500">
                    {job.language && job.language !== 'auto' && <span className="mr-2">{job.language.toUpperCase()}</span>}
                    {formatDate(job.created_at)}
                  </p>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  job.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                  job.status === 'failed' ? 'bg-red-500/20 text-red-400' :
                  job.status === 'processing' ? 'bg-blue-500/20 text-blue-400' :
                  'bg-slate-500/20 text-slate-400'
                }`}>
                  {job.status}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
