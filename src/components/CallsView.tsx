import React, { useState } from 'react';
import { Phone, CheckCircle, Clock, AlertCircle, Loader2, RefreshCw, ChevronRight, FileText, Users, FolderOpen } from 'lucide-react';
import useCalls from '../hooks/useCalls';
import CallDetail from './CallDetail';

function CallsView() {
  const { calls, total, loading, error, refresh, statusFilter, setStatusFilter } = useCalls();
  const [selectedCallId, setSelectedCallId] = useState<string | null>(null);

  if (selectedCallId) {
    return <CallDetail jobId={selectedCallId} onBack={() => { setSelectedCallId(null); refresh(); }} />;
  }

  const statusBadge = (call: any) => {
    if (call.deliverables_generated) return { cls: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400', label: 'Delivered', icon: FileText };
    if (call.speakers_identified && call.context_assigned) return { cls: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400', label: 'Ready', icon: CheckCircle };
    if (!call.speakers_identified) return { cls: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400', label: 'Needs Speakers', icon: Users };
    if (!call.context_assigned) return { cls: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400', label: 'Needs Context', icon: FolderOpen };
    return { cls: 'bg-slate-100 text-slate-700 dark:bg-slate-900/30 dark:text-slate-400', label: 'Pending', icon: Clock };
  };

  return (
    <div className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-4 sm:p-6 border border-slate-200 dark:border-slate-700 shadow-sm dark:shadow-none">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Phone className="w-6 h-6 text-blue-400" />
          <h2 className="text-xl font-semibold">Calls</h2>
          <span className="text-sm text-slate-400">({total})</span>
        </div>
        <button onClick={refresh} className="p-2 rounded-lg text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Status filter */}
      <div className="flex gap-2 mb-4 flex-wrap">
        {[undefined, 'pending_speakers', 'pending_context', 'ready', 'delivered'].map((s) => (
          <button
            key={s || 'all'}
            onClick={() => setStatusFilter(s)}
            className={`text-xs px-3 py-1.5 rounded-full transition-colors ${
              statusFilter === s
                ? 'bg-blue-500 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600'
            }`}
          >
            {s ? s.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()) : 'All'}
          </button>
        ))}
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/50 rounded-xl p-4 mb-4 text-red-400 text-sm">{error}</div>
      )}

      {loading && calls.length === 0 ? (
        <div className="flex items-center justify-center py-12 text-slate-400">
          <Loader2 className="w-6 h-6 animate-spin mr-2" /> Loading calls...
        </div>
      ) : calls.length === 0 ? (
        <div className="text-center py-12 text-slate-400">
          <Phone className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>No calls yet</p>
          <p className="text-sm mt-1">Calls are created automatically from transcriptions with diarization</p>
        </div>
      ) : (
        <div className="space-y-2">
          {calls.map((call) => {
            const badge = statusBadge(call);
            const BadgeIcon = badge.icon;
            return (
              <button
                key={call.job_id}
                onClick={() => setSelectedCallId(call.job_id)}
                className="w-full flex items-center gap-3 p-3 rounded-xl bg-slate-50 dark:bg-slate-700/50 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors text-left"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{call.title || `Call ${call.job_id.slice(0, 8)}`}</p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {new Date(call.created_at).toLocaleDateString()} &middot; {call.source_type}
                    {call.speakers?.length ? ` \u00b7 ${call.speakers.length} speakers` : ''}
                  </p>
                </div>
                <span className={`flex items-center gap-1 text-xs px-2 py-1 rounded-full ${badge.cls}`}>
                  <BadgeIcon className="w-3 h-3" />
                  {badge.label}
                </span>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default CallsView;
