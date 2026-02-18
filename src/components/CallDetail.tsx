import React, { useState, useEffect } from 'react';
import { ArrowLeft, CheckCircle, Users, FolderOpen, FileText, Loader2, AlertCircle, Edit3, Plus } from 'lucide-react';
import {
  fetchCall, identifySpeakers, confirmSpeaker, assignContext, setCallTitle,
  generateDeliverables, fetchDeliverables, fetchSpeakers, fetchContextTree,
  CallMetadata, Speaker, ContextTree,
} from '../utils/api';

interface CallDetailProps {
  jobId: string;
  onBack: () => void;
}

function CallDetail({ jobId, onBack }: CallDetailProps) {
  const [call, setCall] = useState<CallMetadata | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [speakers, setSpeakers] = useState<Speaker[]>([]);
  const [contextTree, setContextTree] = useState<ContextTree[]>([]);
  const [deliverables, setDeliverables] = useState<any>(null);
  const [generating, setGenerating] = useState(false);
  const [identifying, setIdentifying] = useState(false);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleInput, setTitleInput] = useState('');

  const refresh = async () => {
    setLoading(true);
    try {
      const data = await fetchCall(jobId);
      setCall(data);
      setTitleInput(data.title || '');
      if (data.deliverables_generated) {
        const del = await fetchDeliverables(jobId);
        setDeliverables(del);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    fetchSpeakers().then(setSpeakers).catch(() => {});
    fetchContextTree().then(setContextTree).catch(() => {});
  }, [jobId]);

  const handleIdentifySpeakers = async () => {
    setIdentifying(true);
    setError(null);
    try {
      await identifySpeakers(jobId);
      await refresh();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIdentifying(false);
    }
  };

  const handleConfirmSpeaker = async (label: string, name: string, createNew: boolean) => {
    try {
      await confirmSpeaker(jobId, label, name, createNew);
      await refresh();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleAssignContext = async (path: string) => {
    try {
      await assignContext(jobId, path);
      await refresh();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleSaveTitle = async () => {
    if (titleInput.trim()) {
      await setCallTitle(jobId, titleInput.trim());
      setEditingTitle(false);
      await refresh();
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      await generateDeliverables(jobId);
      await refresh();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-6 border border-slate-200 dark:border-slate-700">
        <div className="flex items-center justify-center py-12 text-slate-400">
          <Loader2 className="w-6 h-6 animate-spin mr-2" /> Loading call...
        </div>
      </div>
    );
  }

  if (!call) return null;

  const readiness = call.readiness || { ready: false, missing: [] };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-4 sm:p-6 border border-slate-200 dark:border-slate-700 shadow-sm dark:shadow-none">
        <div className="flex items-center gap-3 mb-4">
          <button onClick={onBack} className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors">
            <ArrowLeft className="w-5 h-5" />
          </button>
          {editingTitle ? (
            <div className="flex items-center gap-2 flex-1">
              <input
                type="text"
                value={titleInput}
                onChange={(e) => setTitleInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSaveTitle()}
                className="flex-1 bg-white dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                autoFocus
              />
              <button onClick={handleSaveTitle} className="text-sm px-3 py-1.5 bg-blue-500 text-white rounded-lg hover:bg-blue-600">Save</button>
              <button onClick={() => setEditingTitle(false)} className="text-sm px-3 py-1.5 text-slate-400 hover:text-slate-600">Cancel</button>
            </div>
          ) : (
            <div className="flex items-center gap-2 flex-1">
              <h2 className="text-xl font-semibold">{call.title || `Call ${jobId.slice(0, 8)}`}</h2>
              <button onClick={() => setEditingTitle(true)} className="p-1 rounded text-slate-400 hover:text-slate-600">
                <Edit3 className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
        <p className="text-sm text-slate-400">
          {new Date(call.created_at).toLocaleString()} &middot; {call.source_type}
        </p>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/50 rounded-xl p-4 text-red-400 text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" /> {error}
        </div>
      )}

      {/* Speaker Identification */}
      <div className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-4 sm:p-6 border border-slate-200 dark:border-slate-700 shadow-sm dark:shadow-none">
        <div className="flex items-center gap-3 mb-4">
          <Users className="w-5 h-5 text-blue-400" />
          <h3 className="font-semibold">Speaker Identification</h3>
          {call.speakers_identified ? (
            <CheckCircle className="w-4 h-4 text-green-400" />
          ) : null}
        </div>

        {call.speaker_identifications && call.speaker_identifications.length > 0 ? (
          <div className="space-y-2">
            {call.speaker_identifications.map((si) => (
              <div key={`${si.call_id}-${si.speaker_label}`} className="flex items-center gap-3 p-3 rounded-xl bg-slate-50 dark:bg-slate-700/50">
                <span className="text-xs text-slate-400 font-mono w-24">{si.speaker_label}</span>
                <span className="flex-1 font-medium text-sm">{si.name || 'Unknown'}</span>
                <span className="text-xs text-slate-400">{(si.confidence * 100).toFixed(0)}%</span>
                {si.confirmed ? (
                  <CheckCircle className="w-4 h-4 text-green-400" />
                ) : (
                  <SpeakerConfirmDropdown
                    speakers={speakers}
                    onConfirm={(name, createNew) => handleConfirmSpeaker(si.speaker_label || '', name, createNew)}
                  />
                )}
              </div>
            ))}
          </div>
        ) : (
          <button
            onClick={handleIdentifySpeakers}
            disabled={identifying}
            className="w-full py-3 rounded-xl text-sm font-medium bg-blue-500/10 text-blue-500 hover:bg-blue-500/20 transition-colors disabled:opacity-50"
          >
            {identifying ? (
              <span className="flex items-center justify-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Identifying...</span>
            ) : (
              'Auto-Identify Speakers'
            )}
          </button>
        )}
      </div>

      {/* Context Assignment */}
      <div className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-4 sm:p-6 border border-slate-200 dark:border-slate-700 shadow-sm dark:shadow-none">
        <div className="flex items-center gap-3 mb-4">
          <FolderOpen className="w-5 h-5 text-blue-400" />
          <h3 className="font-semibold">Context</h3>
          {call.context_assigned ? <CheckCircle className="w-4 h-4 text-green-400" /> : null}
        </div>

        {call.context_path ? (
          <div className="flex items-center gap-2 p-3 rounded-xl bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400">
            <FolderOpen className="w-4 h-4" />
            <span className="text-sm font-medium">{call.context_path}</span>
          </div>
        ) : (
          <ContextPicker tree={contextTree} onSelect={handleAssignContext} />
        )}
      </div>

      {/* Generate Deliverables */}
      {readiness.ready && !call.deliverables_generated && (
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="w-full py-4 rounded-xl font-semibold bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 text-white transition-all disabled:opacity-50"
        >
          {generating ? (
            <span className="flex items-center justify-center gap-2"><Loader2 className="w-5 h-5 animate-spin" /> Generating Deliverables...</span>
          ) : (
            <span className="flex items-center justify-center gap-2"><FileText className="w-5 h-5" /> Generate Deliverables</span>
          )}
        </button>
      )}

      {/* Deliverables */}
      {deliverables && deliverables.generated && (
        <DeliverableView deliverables={deliverables} />
      )}
    </div>
  );
}

// Sub-components

function SpeakerConfirmDropdown({ speakers, onConfirm }: { speakers: Speaker[]; onConfirm: (name: string, createNew: boolean) => void }) {
  const [open, setOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [showNew, setShowNew] = useState(false);

  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)} className="text-xs px-2 py-1 bg-blue-500 text-white rounded-lg hover:bg-blue-600">
        Identify
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 z-10 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-lg p-2 min-w-48">
          {speakers.map((s) => (
            <button
              key={s.speaker_id}
              onClick={() => { onConfirm(s.name, false); setOpen(false); }}
              className="w-full text-left text-sm px-3 py-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700"
            >
              {s.name}
            </button>
          ))}
          <hr className="my-1 border-slate-200 dark:border-slate-700" />
          {showNew ? (
            <div className="flex gap-1 p-1">
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="New speaker name"
                className="flex-1 text-sm px-2 py-1 border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && newName.trim()) {
                    onConfirm(newName.trim(), true);
                    setOpen(false);
                  }
                }}
              />
              <button
                onClick={() => { if (newName.trim()) { onConfirm(newName.trim(), true); setOpen(false); } }}
                className="text-xs px-2 py-1 bg-green-500 text-white rounded hover:bg-green-600"
              >
                Add
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowNew(true)}
              className="w-full text-left text-sm px-3 py-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 flex items-center gap-2 text-blue-500"
            >
              <Plus className="w-3 h-3" /> New Speaker
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function ContextPicker({ tree, onSelect }: { tree: ContextTree[]; onSelect: (path: string) => void }) {
  if (tree.length === 0) {
    return <p className="text-sm text-slate-400">No context folders yet. Create one in the Contexts tab.</p>;
  }

  return (
    <div className="space-y-1">
      {tree.map((node) => (
        <ContextNode key={node.path} node={node} onSelect={onSelect} depth={0} />
      ))}
    </div>
  );
}

function ContextNode({ node, onSelect, depth }: { node: ContextTree; onSelect: (path: string) => void; depth: number }) {
  const [expanded, setExpanded] = useState(false);
  const hasChildren = node.children && node.children.length > 0;

  return (
    <div>
      <button
        onClick={() => hasChildren ? setExpanded(!expanded) : onSelect(node.path)}
        className="w-full text-left flex items-center gap-2 px-3 py-2 rounded-lg text-sm hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
        style={{ paddingLeft: `${depth * 16 + 12}px` }}
      >
        <FolderOpen className="w-4 h-4 text-slate-400" />
        <span className="flex-1">{node.name}</span>
        {!hasChildren && (
          <span className="text-xs text-blue-500">Select</span>
        )}
      </button>
      {expanded && hasChildren && (
        <div>
          {node.children!.map((child) => (
            <ContextNode key={child.path} node={child} onSelect={onSelect} depth={depth + 1} />
          ))}
          <button
            onClick={() => onSelect(node.path)}
            className="w-full text-left text-xs text-blue-500 px-3 py-1 hover:underline"
            style={{ paddingLeft: `${(depth + 1) * 16 + 12}px` }}
          >
            Select "{node.name}"
          </button>
        </div>
      )}
    </div>
  );
}

function DeliverableView({ deliverables }: { deliverables: any }) {
  const [tab, setTab] = useState<'summary' | 'analysis'>('summary');

  return (
    <div className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-4 sm:p-6 border border-slate-200 dark:border-slate-700 shadow-sm dark:shadow-none">
      <div className="flex items-center gap-3 mb-4">
        <FileText className="w-5 h-5 text-green-400" />
        <h3 className="font-semibold">Deliverables</h3>
        {deliverables.generated_at && (
          <span className="text-xs text-slate-400">Generated {new Date(deliverables.generated_at).toLocaleDateString()}</span>
        )}
      </div>

      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setTab('summary')}
          className={`text-sm px-4 py-2 rounded-lg font-medium transition-all ${
            tab === 'summary' ? 'bg-blue-500 text-white' : 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
          }`}
        >
          Summary
        </button>
        <button
          onClick={() => setTab('analysis')}
          className={`text-sm px-4 py-2 rounded-lg font-medium transition-all ${
            tab === 'analysis' ? 'bg-blue-500 text-white' : 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
          }`}
        >
          Analysis
        </button>
      </div>

      <div className="prose prose-sm dark:prose-invert max-w-none overflow-auto max-h-96">
        <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">
          {tab === 'summary' ? deliverables.summary_md : deliverables.analysis_md}
        </pre>
      </div>
    </div>
  );
}

export default CallDetail;
