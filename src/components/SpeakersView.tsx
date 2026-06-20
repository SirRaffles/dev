import { useMemo, useState } from 'react';
import { Users, Plus, Trash2, Loader2, RefreshCw, ChevronRight, CheckSquare, Square } from 'lucide-react';
import useSpeakers from '../hooks/useSpeakers';
import SpeakerProfile from './SpeakerProfile';
import ConfirmModal from './ConfirmModal';

function SpeakersView() {
  const { speakers, loading, error, refresh, addSpeaker, removeSpeaker, removeMany } = useSpeakers();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  // Bulk selection state
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const [bulkDeleting, setBulkDeleting] = useState(false);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    setCreateError(null);
    try {
      await addSpeaker(newName.trim());
      setNewName('');
      setShowCreate(false);
    } catch (e: any) {
      setCreateError(e.message);
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = (speakerId: string, name: string) => {
    setDeleteTarget({ id: speakerId, name });
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      await removeSpeaker(deleteTarget.id);
      setDeleteError(null);
    } catch (e: any) {
      setDeleteError(e?.message || 'Failed to delete speaker');
    } finally {
      setDeleteTarget(null);
    }
  };

  const toggleOne = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const allSelected = useMemo(
    () => speakers.length > 0 && speakers.every((s) => selectedIds.has(s.speaker_id)),
    [speakers, selectedIds]
  );

  // Early-return AFTER all hooks have run — otherwise React throws
  // "Rendered fewer hooks than expected" when selectedId flips from null to
  // truthy (the useMemo above wouldn't execute on that render).
  if (selectedId) {
    return <SpeakerProfile speakerId={selectedId} onBack={() => { setSelectedId(null); refresh(); }} />;
  }

  const toggleAll = () => {
    setSelectedIds(allSelected ? new Set() : new Set(speakers.map((s) => s.speaker_id)));
  };

  const exitSelectMode = () => {
    setSelectMode(false);
    setSelectedIds(new Set());
  };

  const confirmBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    setBulkDeleting(true);
    try {
      const { ok, failed } = await removeMany(Array.from(selectedIds));
      if (failed.length > 0) {
        setDeleteError(`Deleted ${ok}. ${failed.length} failed: ${failed[0].error}${failed.length > 1 ? '…' : ''}`);
      } else {
        setDeleteError(null);
      }
      exitSelectMode();
    } finally {
      setBulkDeleting(false);
      setBulkDeleteOpen(false);
    }
  };

  const formatTime = (seconds: number) => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${(seconds / 3600).toFixed(1)}h`;
  };

  return (
    <div className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-4 sm:p-6 border border-slate-200 dark:border-slate-700 shadow-sm dark:shadow-none">
      <div className="flex items-center justify-between mb-6 gap-2 flex-wrap">
        <div className="flex items-center gap-3">
          <Users className="w-6 h-6 text-blue-400" aria-hidden="true" />
          <h2 className="text-xl font-semibold">Speakers</h2>
          <span className="text-sm text-slate-400">
            ({speakers.length}{selectMode && selectedIds.size > 0 ? ` · ${selectedIds.size} selected` : ''})
          </span>
        </div>
        <div className="flex items-center gap-2">
          {selectMode ? (
            <>
              <button
                type="button"
                onClick={() => setBulkDeleteOpen(true)}
                disabled={selectedIds.size === 0 || bulkDeleting}
                className="px-3 py-2 rounded-lg bg-red-500 text-white text-sm font-medium hover:bg-red-600 disabled:opacity-50 flex items-center gap-2"
              >
                {bulkDeleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                Delete selected
              </button>
              <button
                type="button"
                onClick={exitSelectMode}
                disabled={bulkDeleting}
                className="px-3 py-2 rounded-lg text-sm bg-slate-200 dark:bg-slate-600 hover:bg-slate-300 dark:hover:bg-slate-500"
              >
                Cancel
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={() => setSelectMode(true)}
                disabled={speakers.length === 0}
                aria-label="Select speakers for bulk actions"
                className="px-3 py-2 rounded-lg text-sm text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-40"
              >
                Select
              </button>
              <button
                type="button"
                onClick={() => setShowCreate(!showCreate)}
                aria-label={showCreate ? 'Close add speaker form' : 'Add speaker'}
                aria-expanded={showCreate}
                className="p-2.5 min-w-[44px] min-h-[44px] rounded-lg text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors flex items-center justify-center"
              >
                <Plus className="w-5 h-5" aria-hidden="true" />
              </button>
              <button
                type="button"
                onClick={refresh}
                aria-label="Refresh speakers"
                className="p-2.5 min-w-[44px] min-h-[44px] rounded-lg text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors flex items-center justify-center"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} aria-hidden="true" />
              </button>
            </>
          )}
        </div>
      </div>

      {deleteError && (
        <div role="alert" className="bg-red-500/10 border border-red-500/50 rounded-xl p-4 mb-4 text-red-400 text-sm">
          {deleteError}
        </div>
      )}

      {showCreate && !selectMode && (
        <div className="mb-4 p-4 rounded-xl bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
          <div className="flex gap-2">
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Speaker name"
              className="flex-1 px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
              autoFocus
            />
            <button
              type="button"
              onClick={handleCreate}
              disabled={creating || !newName.trim()}
              className="px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 disabled:opacity-50"
            >
              {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create'}
            </button>
          </div>
          {createError && <p className="text-red-400 text-xs mt-2">{createError}</p>}
        </div>
      )}

      {error && (
        <div role="alert" className="bg-red-500/10 border border-red-500/50 rounded-xl p-4 mb-4 text-red-400 text-sm">{error}</div>
      )}

      {selectMode && speakers.length > 0 && (
        <button
          type="button"
          onClick={toggleAll}
          className="mb-2 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400 hover:text-blue-500 px-2 py-1 rounded"
        >
          {allSelected ? <CheckSquare className="w-4 h-4" /> : <Square className="w-4 h-4" />}
          {allSelected ? 'Deselect all' : 'Select all'}
        </button>
      )}

      {loading && speakers.length === 0 ? (
        <div className="flex items-center justify-center py-12 text-slate-400">
          <Loader2 className="w-6 h-6 animate-spin mr-2" aria-hidden="true" /> Loading speakers…
        </div>
      ) : speakers.length === 0 ? (
        <div className="text-center py-12 text-slate-500 dark:text-slate-400">
          <Users className="w-12 h-12 mx-auto mb-3 opacity-50" aria-hidden="true" />
          <p>No speakers registered yet</p>
          <p className="text-sm mt-1">Speakers are created automatically during call identification</p>
        </div>
      ) : (
        <div className="space-y-2">
          {speakers.map((speaker) => {
            const checked = selectedIds.has(speaker.speaker_id);
            return (
              <div
                key={speaker.speaker_id}
                className={`flex items-center gap-3 p-3 rounded-xl transition-colors ${checked ? 'bg-blue-50 dark:bg-blue-900/20 ring-1 ring-blue-400' : 'bg-slate-50 dark:bg-slate-700/50 hover:bg-slate-100 dark:hover:bg-slate-700'}`}
              >
                {selectMode && (
                  <button
                    type="button"
                    onClick={() => toggleOne(speaker.speaker_id)}
                    aria-label={checked ? `Deselect ${speaker.name}` : `Select ${speaker.name}`}
                    aria-pressed={checked}
                    className="p-1 rounded text-blue-500 hover:bg-blue-100 dark:hover:bg-blue-900/30"
                  >
                    {checked ? <CheckSquare className="w-5 h-5" aria-hidden="true" /> : <Square className="w-5 h-5" aria-hidden="true" />}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => {
                    if (selectMode) toggleOne(speaker.speaker_id);
                    else setSelectedId(speaker.speaker_id);
                  }}
                  className="flex-1 flex items-center gap-3 text-left"
                >
                  <div className="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center text-blue-500 font-semibold text-sm">
                    {speaker.name.charAt(0).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{speaker.name}</p>
                    <p className="text-xs text-slate-400">
                      {speaker.call_count} calls &middot; {formatTime(speaker.total_speaking_time_seconds)} speaking
                    </p>
                  </div>
                  {!selectMode && <ChevronRight className="w-4 h-4 text-slate-500 dark:text-slate-400" aria-hidden="true" />}
                </button>
                {!selectMode && (
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); handleDelete(speaker.speaker_id, speaker.name); }}
                    aria-label={`Delete speaker ${speaker.name}`}
                    className="p-2 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" aria-hidden="true" />
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      <ConfirmModal
        open={deleteTarget !== null}
        title="Delete Speaker"
        message={deleteTarget ? `Delete speaker "${deleteTarget.name}"? This cannot be undone.` : ''}
        confirmLabel="Delete"
        cancelLabel="Cancel"
        variant="danger"
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />
      <ConfirmModal
        open={bulkDeleteOpen}
        title="Delete selected speakers"
        message={`Delete ${selectedIds.size} speaker${selectedIds.size === 1 ? '' : 's'}? This cannot be undone.`}
        confirmLabel={bulkDeleting ? 'Deleting…' : 'Delete all'}
        cancelLabel="Cancel"
        variant="danger"
        onConfirm={confirmBulkDelete}
        onCancel={() => setBulkDeleteOpen(false)}
      />
    </div>
  );
}

export default SpeakersView;
