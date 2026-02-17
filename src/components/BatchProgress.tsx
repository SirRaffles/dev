import React, { useState, useEffect, useCallback } from 'react';
import { CheckCircle, AlertCircle, Loader2, Clock, FileText, Layers } from 'lucide-react';
import { API_URL } from '../utils/api';

const API_KEY = import.meta.env.VITE_API_KEY || '';
function authHeaders(): Record<string, string> {
  const h: Record<string, string> = {};
  if (API_KEY) h['X-API-Key'] = API_KEY;
  return h;
}

const STATUS_ICONS: Record<string, React.ReactNode> = {
  completed: <CheckCircle className="w-4 h-4 text-green-400" />,
  failed: <AlertCircle className="w-4 h-4 text-red-400" />,
  processing: <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />,
  pending: <Clock className="w-4 h-4 text-slate-400" />,
};

function basename(filePath: string | null | undefined): string | null {
  if (!filePath) return null;
  return filePath.split('/').pop() || filePath;
}

interface BatchJob {
  job_id: string;
  status: string;
  file_path?: string;
}

interface BatchData {
  total: number;
  completed: number;
  failed: number;
  jobs: BatchJob[];
}

interface BatchProgressProps {
  batchId: string | null;
  onSelectJob?: (jobId: string) => void;
}

export default function BatchProgress({ batchId, onSelectJob }: BatchProgressProps) {
  const [batchData, setBatchData] = useState<BatchData | null>(null);
  const [done, setDone] = useState(false);

  const fetchStatus = useCallback(async () => {
    if (!batchId) return;
    try {
      const resp = await fetch(`${API_URL}/batch/${batchId}`, { headers: authHeaders() });
      if (!resp.ok) return;
      const data = await resp.json();
      setBatchData(data);
      const finished = data.completed + data.failed >= data.total && data.total > 0;
      if (finished) setDone(true);
    } catch {
      // Non-critical — silently fail
    }
  }, [batchId]);

  // Poll every 3 seconds while the batch is active
  useEffect(() => {
    if (!batchId) return;
    setDone(false);
    setBatchData(null);
    fetchStatus();
    const interval = setInterval(() => {
      if (!done) fetchStatus();
    }, 3000);
    return () => clearInterval(interval);
  }, [batchId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Stop polling when done
  useEffect(() => {
    if (done) fetchStatus(); // one final fetch to get the definitive state
  }, [done]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!batchId || !batchData) return null;

  const { total, completed, failed, jobs = [] } = batchData;
  const doneCount = completed + failed;
  const progressPct = total > 0 ? Math.round((doneCount / total) * 100) : 0;

  return (
    <div className="bg-slate-800/50 backdrop-blur rounded-2xl p-4 sm:p-6 mb-8 border border-slate-700/50">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <Layers className="w-5 h-5 text-purple-400 flex-shrink-0" aria-hidden="true" />
        <span className="font-medium text-slate-200">
          Batch Progress
        </span>
        <span className="ml-auto text-sm text-slate-400">
          {doneCount} / {total} files
          {failed > 0 && (
            <span className="ml-2 text-red-400">({failed} failed)</span>
          )}
        </span>
      </div>

      {/* Overall progress bar */}
      <div
        className="w-full bg-slate-700 rounded-full h-2 mb-4"
        role="progressbar"
        aria-valuenow={progressPct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Batch processing progress"
      >
        <div
          className="bg-gradient-to-r from-purple-500 to-blue-500 h-2 rounded-full transition-all duration-300"
          style={{ width: `${progressPct}%` }}
        />
      </div>

      {/* Per-job list */}
      {jobs.length > 0 && (
        <div className="space-y-1 max-h-60 overflow-y-auto">
          {jobs.map((job) => (
            <button
              key={job.job_id}
              onClick={() => job.status === 'completed' && onSelectJob && onSelectJob(job.job_id)}
              disabled={job.status !== 'completed'}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors border border-transparent
                ${job.status === 'completed'
                  ? 'hover:bg-slate-700/50 hover:border-slate-600/50 cursor-pointer'
                  : 'cursor-default'
                }`}
            >
              {STATUS_ICONS[job.status] || <FileText className="w-4 h-4 text-slate-500" />}
              <span className="flex-1 text-sm text-slate-200 truncate">
                {basename(job.file_path) || job.job_id.slice(0, 8)}
              </span>
              <span className={`text-xs px-2 py-0.5 rounded-full ${
                job.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                job.status === 'failed'    ? 'bg-red-500/20 text-red-400' :
                job.status === 'processing'? 'bg-blue-500/20 text-blue-400' :
                'bg-slate-500/20 text-slate-400'
              }`}>
                {job.status}
              </span>
            </button>
          ))}
        </div>
      )}

      {done && (
        <p className="mt-3 text-xs text-slate-500 text-center">
          {failed === 0
            ? 'All files transcribed successfully.'
            : `${completed} succeeded, ${failed} failed.`}
        </p>
      )}
    </div>
  );
}
