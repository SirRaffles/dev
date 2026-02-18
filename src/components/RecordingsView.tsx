import React from 'react';
import { Mic, CheckCircle, Clock, AlertCircle, Loader2, RefreshCw } from 'lucide-react';
import useRecordings from '../hooks/useRecordings';

function RecordingsView() {
  const { recordings, total, loading, error, refresh } = useRecordings();

  return (
    <div className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-4 sm:p-6 border border-slate-200 dark:border-slate-700 shadow-sm dark:shadow-none">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Mic className="w-6 h-6 text-blue-400" />
          <h2 className="text-xl font-semibold">Just Press Record</h2>
          <span className="text-sm text-slate-400">({total} recordings)</span>
        </div>
        <button
          onClick={refresh}
          className="p-2 rounded-lg text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/50 rounded-xl p-4 mb-4 text-red-400 text-sm">
          {error}
        </div>
      )}

      {loading && recordings.length === 0 ? (
        <div className="flex items-center justify-center py-12 text-slate-400">
          <Loader2 className="w-6 h-6 animate-spin mr-2" />
          Loading recordings...
        </div>
      ) : recordings.length === 0 ? (
        <div className="text-center py-12 text-slate-400">
          <Mic className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>No recordings found</p>
          <p className="text-sm mt-1">New Just Press Record files will appear here automatically</p>
        </div>
      ) : (
        <div className="space-y-2">
          {recordings.map((rec) => (
            <div
              key={rec.path}
              className="flex items-center gap-3 p-3 rounded-xl bg-slate-50 dark:bg-slate-700/50 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
            >
              <div className="flex-shrink-0">
                {rec.status === 'completed' ? (
                  <CheckCircle className="w-5 h-5 text-green-400" />
                ) : rec.status === 'processing' ? (
                  <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />
                ) : rec.status === 'failed' ? (
                  <AlertCircle className="w-5 h-5 text-red-400" />
                ) : (
                  <Clock className="w-5 h-5 text-slate-400" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{rec.filename}</p>
                <p className="text-xs text-slate-400">{rec.date_folder} &middot; {(rec.size_bytes / 1024 / 1024).toFixed(1)} MB</p>
              </div>
              <div className="flex-shrink-0">
                <span className={`text-xs px-2 py-1 rounded-full ${
                  rec.status === 'completed' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                  rec.status === 'processing' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' :
                  rec.status === 'failed' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                  'bg-slate-100 text-slate-600 dark:bg-slate-600 dark:text-slate-300'
                }`}>
                  {rec.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default RecordingsView;
