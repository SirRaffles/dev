import React, { useState } from 'react';
import { FolderOpen, Plus, FileText, Loader2, RefreshCw, ChevronRight, Save, Eye, Edit3 } from 'lucide-react';
import useContexts from '../hooks/useContexts';
import { fetchContextFile, updateContextFile, ContextTree } from '../utils/api';
import GlossaryEditor from './GlossaryEditor';

function ContextBrowser() {
  const { tree, loading, error, refreshTree, addFolder } = useContexts();
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState('');
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [creating, setCreating] = useState(false);
  const [editMode, setEditMode] = useState(false);

  const handleLoadFile = async (path: string, filename: string) => {
    try {
      const content = await fetchContextFile(path, filename);
      setSelectedPath(path);
      setSelectedFile(filename);
      setFileContent(content);
      setDirty(false);
      setEditMode(false);
    } catch (e) {
      console.error('Failed to load file:', e);
    }
  };

  const handleSave = async () => {
    if (!selectedPath || !selectedFile) return;
    setSaving(true);
    try {
      await updateContextFile(selectedPath, selectedFile, fileContent);
      setDirty(false);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) return;
    setCreating(true);
    try {
      await addFolder(newFolderName.trim());
      setNewFolderName('');
      setShowCreate(false);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-4">
      <GlossaryEditor />
      <div className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-4 sm:p-6 border border-slate-200 dark:border-slate-700 shadow-sm dark:shadow-none">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <FolderOpen className="w-6 h-6 text-blue-400" />
            <h2 className="text-xl font-semibold">Contexts</h2>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setShowCreate(!showCreate)} className="p-2 rounded-lg text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors">
              <Plus className="w-5 h-5" />
            </button>
            <button onClick={refreshTree} className="p-2 rounded-lg text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors">
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {showCreate && (
          <div className="mb-4 p-4 rounded-xl bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
            <div className="flex gap-2">
              <input
                type="text"
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
                placeholder="Folder name (e.g., Acme Corp)"
                className="flex-1 px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                onKeyDown={(e) => e.key === 'Enter' && handleCreateFolder()}
                autoFocus
              />
              <button
                onClick={handleCreateFolder}
                disabled={creating || !newFolderName.trim()}
                className="px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 disabled:opacity-50"
              >
                {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create'}
              </button>
            </div>
          </div>
        )}

        {error && (
          <div className="bg-red-500/10 border border-red-500/50 rounded-xl p-4 mb-4 text-red-400 text-sm">{error}</div>
        )}

        {loading && tree.length === 0 ? (
          <div className="flex items-center justify-center py-12 text-slate-400">
            <Loader2 className="w-6 h-6 animate-spin mr-2" /> Loading...
          </div>
        ) : tree.length === 0 ? (
          <div className="text-center py-12 text-slate-400">
            <FolderOpen className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No context folders yet</p>
            <p className="text-sm mt-1">Create folders to organize your call context and insights</p>
          </div>
        ) : (
          <div className="space-y-1">
            {tree.map((node) => (
              <ContextTreeNode key={node.path} node={node} depth={0} onSelectFile={handleLoadFile} />
            ))}
          </div>
        )}
      </div>

      {/* File Editor */}
      {selectedPath && selectedFile && (
        <div className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-4 sm:p-6 border border-slate-200 dark:border-slate-700 shadow-sm dark:shadow-none">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-blue-400" />
              <span className="text-sm font-medium">{selectedPath}/{selectedFile}</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setEditMode(!editMode)}
                className={`p-2 rounded-lg transition-colors ${editMode ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400' : 'text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700'}`}
              >
                {editMode ? <Eye className="w-4 h-4" /> : <Edit3 className="w-4 h-4" />}
              </button>
              {dirty && (
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="flex items-center gap-2 px-3 py-1.5 bg-blue-500 text-white rounded-lg text-sm hover:bg-blue-600 disabled:opacity-50"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  Save
                </button>
              )}
            </div>
          </div>
          {editMode ? (
            <textarea
              value={fileContent}
              onChange={(e) => { setFileContent(e.target.value); setDirty(true); }}
              className="w-full h-80 bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-600 rounded-xl p-4 text-sm font-mono leading-relaxed resize-y focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          ) : (
            <div className="prose prose-sm dark:prose-invert max-w-none bg-slate-50 dark:bg-slate-700/50 rounded-xl p-4 max-h-96 overflow-auto">
              <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">{fileContent || '(empty)'}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ContextTreeNode({ node, depth, onSelectFile }: { node: ContextTree; depth: number; onSelectFile: (path: string, filename: string) => void }) {
  const [expanded, setExpanded] = useState(depth === 0);
  const hasChildren = node.children && node.children.length > 0;

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left flex items-center gap-2 px-3 py-2 rounded-lg text-sm hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
        style={{ paddingLeft: `${depth * 16 + 12}px` }}
      >
        <FolderOpen className="w-4 h-4 text-amber-500" />
        <span className="flex-1 font-medium">{node.name}</span>
        {hasChildren && <ChevronRight className={`w-4 h-4 text-slate-400 transition-transform ${expanded ? 'rotate-90' : ''}`} />}
      </button>
      {expanded && (
        <div>
          <button
            onClick={() => onSelectFile(node.path, 'context.md')}
            className="w-full text-left flex items-center gap-2 px-3 py-1.5 text-xs text-slate-500 hover:text-blue-500 hover:bg-slate-50 dark:hover:bg-slate-700/50 rounded-lg transition-colors"
            style={{ paddingLeft: `${(depth + 1) * 16 + 12}px` }}
          >
            <FileText className="w-3 h-3" /> context.md
          </button>
          <button
            onClick={() => onSelectFile(node.path, 'insights.md')}
            className="w-full text-left flex items-center gap-2 px-3 py-1.5 text-xs text-slate-500 hover:text-blue-500 hover:bg-slate-50 dark:hover:bg-slate-700/50 rounded-lg transition-colors"
            style={{ paddingLeft: `${(depth + 1) * 16 + 12}px` }}
          >
            <FileText className="w-3 h-3" /> insights.md
          </button>
          {hasChildren && node.children!.map((child) => (
            <ContextTreeNode key={child.path} node={child} depth={depth + 1} onSelectFile={onSelectFile} />
          ))}
        </div>
      )}
    </div>
  );
}

export default ContextBrowser;
