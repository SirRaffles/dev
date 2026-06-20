import { useRef, useState } from 'react';
import {
  FolderOpen, Plus, FileText, Loader2, RefreshCw, ChevronRight,
  Save, Eye, Edit3, Upload, Trash2, FilePlus,
} from 'lucide-react';
import useContexts from '../hooks/useContexts';
import { fetchContextFile, ContextTree, ContextFile } from '../utils/api';
import GlossaryEditor from './GlossaryEditor';

function ContextBrowser() {
  const {
    tree, loading, error, refreshTree,
    addFolder, removeFolder, removeFile, uploadFile, createFile,
  } = useContexts();
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState('');
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [creating, setCreating] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const handleLoadFile = async (path: string, filename: string) => {
    try {
      setActionError(null);
      const content = await fetchContextFile(path, filename);
      setSelectedPath(path);
      setSelectedFile(filename);
      setFileContent(content);
      setDirty(false);
      setEditMode(false);
    } catch (e: any) {
      setActionError(e?.message || 'Failed to load file');
    }
  };

  const handleSave = async () => {
    if (!selectedPath || !selectedFile) return;
    setSaving(true);
    try {
      await createFile(selectedPath, selectedFile, fileContent);
      setDirty(false);
    } catch (e: any) {
      setActionError(e?.message || 'Failed to save file');
    } finally {
      setSaving(false);
    }
  };

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) return;
    setCreating(true);
    setActionError(null);
    try {
      await addFolder(newFolderName.trim());
      setNewFolderName('');
      setShowCreate(false);
    } catch (e: any) {
      setActionError(e?.message || 'Failed to create folder');
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteFolder = async (path: string) => {
    if (!window.confirm(`Delete folder "${path}" and all its files? This cannot be undone.`)) return;
    try {
      setActionError(null);
      await removeFolder(path);
      if (selectedPath === path || selectedPath?.startsWith(`${path}/`)) {
        setSelectedPath(null);
        setSelectedFile(null);
        setFileContent('');
      }
    } catch (e: any) {
      setActionError(e?.message || 'Failed to delete folder');
    }
  };

  const handleDeleteFile = async (folderPath: string, filename: string) => {
    if (!window.confirm(`Delete "${filename}"? This cannot be undone.`)) return;
    try {
      setActionError(null);
      await removeFile(folderPath, filename);
      if (selectedPath === folderPath && selectedFile === filename) {
        setSelectedPath(null);
        setSelectedFile(null);
        setFileContent('');
      }
    } catch (e: any) {
      setActionError(e?.message || 'Failed to delete file');
    }
  };

  const handleUpload = async (folderPath: string, fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    setActionError(null);
    try {
      for (const f of Array.from(fileList)) {
        await uploadFile(folderPath, f);
      }
    } catch (e: any) {
      setActionError(e?.message || 'Upload failed');
    }
  };

  const handleNewFile = async (folderPath: string, filename: string) => {
    const trimmed = filename.trim();
    if (!trimmed) return;
    const fname = /\.(md|txt)$/i.test(trimmed) ? trimmed : `${trimmed}.md`;
    try {
      setActionError(null);
      await createFile(folderPath, fname, '');
      await handleLoadFile(folderPath, fname);
      setEditMode(true);
    } catch (e: any) {
      setActionError(e?.message || 'Could not create note');
    }
  };

  return (
    <div className="space-y-4">
      <GlossaryEditor />
      <div className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-4 sm:p-6 border border-slate-200 dark:border-slate-700 shadow-sm dark:shadow-none">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <FolderOpen className="w-6 h-6 text-blue-400" aria-hidden="true" />
            <h2 className="text-xl font-semibold">Contexts</h2>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowCreate(!showCreate)}
              aria-label="New folder"
              className="p-2 rounded-lg text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors"
            >
              <Plus className="w-5 h-5" aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={refreshTree}
              aria-label="Refresh"
              className="p-2 rounded-lg text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} aria-hidden="true" />
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
                placeholder="Folder name (e.g., World Models)"
                aria-label="New folder name"
                className="flex-1 px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                onKeyDown={(e) => e.key === 'Enter' && handleCreateFolder()}
                autoFocus
              />
              <button
                type="button"
                onClick={handleCreateFolder}
                disabled={creating || !newFolderName.trim()}
                className="px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 disabled:opacity-50"
              >
                {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create'}
              </button>
            </div>
          </div>
        )}

        {(error || actionError) && (
          <div role="alert" className="bg-red-500/10 border border-red-500/50 rounded-xl p-3 mb-4 text-red-600 dark:text-red-300 text-sm">
            {actionError || error}
          </div>
        )}

        {loading && tree.length === 0 ? (
          <div className="flex items-center justify-center py-12 text-slate-400">
            <Loader2 className="w-6 h-6 animate-spin mr-2" aria-hidden="true" /> Loading…
          </div>
        ) : tree.length === 0 ? (
          <div className="text-center py-12 text-slate-400">
            <FolderOpen className="w-12 h-12 mx-auto mb-3 opacity-50" aria-hidden="true" />
            <p>No context folders yet</p>
            <p className="text-sm mt-1">Create a folder to group context files for transcription.</p>
          </div>
        ) : (
          <div className="space-y-1">
            {tree.map((node) => (
              <ContextTreeNode
                key={node.path}
                node={node}
                depth={0}
                selectedPath={selectedPath}
                selectedFile={selectedFile}
                onSelectFile={handleLoadFile}
                onDeleteFolder={handleDeleteFolder}
                onDeleteFile={handleDeleteFile}
                onUpload={handleUpload}
                onCreateFile={handleNewFile}
              />
            ))}
          </div>
        )}
      </div>

      {selectedPath && selectedFile && (
        <div className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-4 sm:p-6 border border-slate-200 dark:border-slate-700 shadow-sm dark:shadow-none">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2 min-w-0">
              <FileText className="w-5 h-5 text-blue-400 flex-shrink-0" aria-hidden="true" />
              <span className="text-sm font-medium truncate">{selectedPath}/{selectedFile}</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setEditMode(!editMode)}
                aria-label={editMode ? 'Preview' : 'Edit'}
                className={`p-2 rounded-lg transition-colors ${editMode ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400' : 'text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700'}`}
              >
                {editMode ? <Eye className="w-4 h-4" aria-hidden="true" /> : <Edit3 className="w-4 h-4" aria-hidden="true" />}
              </button>
              {dirty && (
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={saving}
                  className="flex items-center gap-2 px-3 py-1.5 bg-blue-500 text-white rounded-lg text-sm hover:bg-blue-600 disabled:opacity-50"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" /> : <Save className="w-4 h-4" aria-hidden="true" />}
                  Save
                </button>
              )}
            </div>
          </div>
          {editMode ? (
            <textarea
              value={fileContent}
              onChange={(e) => { setFileContent(e.target.value); setDirty(true); }}
              aria-label="File content"
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

interface TreeNodeProps {
  node: ContextTree;
  depth: number;
  selectedPath: string | null;
  selectedFile: string | null;
  onSelectFile: (path: string, filename: string) => void;
  onDeleteFolder: (path: string) => void;
  onDeleteFile: (folderPath: string, filename: string) => void;
  onUpload: (folderPath: string, files: FileList | null) => void;
  onCreateFile: (folderPath: string, filename: string) => void;
}

function ContextTreeNode({
  node, depth, selectedPath, selectedFile,
  onSelectFile, onDeleteFolder, onDeleteFile, onUpload, onCreateFile,
}: TreeNodeProps) {
  const [expanded, setExpanded] = useState(depth === 0);
  const [showNewFile, setShowNewFile] = useState(false);
  const [newFileName, setNewFileName] = useState('');
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const hasChildren = !!(node.children && node.children.length > 0);
  const files = node.files || [];
  const indent = depth * 16 + 12;

  return (
    <div>
      <div
        className="group flex items-center gap-1 pr-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
        style={{ paddingLeft: `${indent}px` }}
      >
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          aria-expanded={expanded}
          aria-label={`${expanded ? 'Collapse' : 'Expand'} ${node.name}`}
          className="flex-1 min-w-0 flex items-center gap-2 py-2 text-sm text-left"
        >
          <ChevronRight className={`w-4 h-4 text-slate-400 flex-shrink-0 transition-transform ${expanded ? 'rotate-90' : ''}`} aria-hidden="true" />
          <FolderOpen className="w-4 h-4 text-amber-500 flex-shrink-0" aria-hidden="true" />
          <span className="font-medium truncate">{node.name}</span>
          <span className="text-xs text-slate-400">
            {files.length > 0 ? `${files.length} file${files.length === 1 ? '' : 's'}` : ''}
          </span>
        </button>
        <div className="hidden group-hover:flex items-center gap-1">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            aria-label={`Upload file to ${node.name}`}
            title="Upload .md or .txt"
            className="p-1.5 rounded text-slate-500 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20"
          >
            <Upload className="w-4 h-4" aria-hidden="true" />
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".md,.txt,text/markdown,text/plain"
            multiple
            onChange={(e) => { onUpload(node.path, e.target.files); if (fileInputRef.current) fileInputRef.current.value = ''; }}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => setShowNewFile(true)}
            aria-label={`New note in ${node.name}`}
            title="New note"
            className="p-1.5 rounded text-slate-500 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20"
          >
            <FilePlus className="w-4 h-4" aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={() => onDeleteFolder(node.path)}
            aria-label={`Delete folder ${node.name}`}
            title="Delete folder"
            className="p-1.5 rounded text-slate-500 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20"
          >
            <Trash2 className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>
      </div>

      {expanded && showNewFile && (
        <div className="flex gap-2 py-1" style={{ paddingLeft: `${indent + 24}px` }}>
          <input
            type="text"
            value={newFileName}
            onChange={(e) => setNewFileName(e.target.value)}
            placeholder="filename (e.g., glossary.md)"
            aria-label="New file name"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                onCreateFile(node.path, newFileName);
                setNewFileName('');
                setShowNewFile(false);
              } else if (e.key === 'Escape') {
                setNewFileName('');
                setShowNewFile(false);
              }
            }}
            className="flex-1 px-2 py-1 text-sm rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <button
            type="button"
            onClick={() => { onCreateFile(node.path, newFileName); setNewFileName(''); setShowNewFile(false); }}
            disabled={!newFileName.trim()}
            className="px-2 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
          >
            Create
          </button>
          <button
            type="button"
            onClick={() => { setNewFileName(''); setShowNewFile(false); }}
            className="px-2 py-1 text-xs bg-slate-200 dark:bg-slate-600 rounded hover:bg-slate-300 dark:hover:bg-slate-500"
          >
            Cancel
          </button>
        </div>
      )}

      {expanded && (
        <div>
          {files.map((f: ContextFile) => {
            const isSel = selectedPath === node.path && selectedFile === f.name;
            return (
              <div
                key={f.path}
                className={`group flex items-center gap-1 pr-2 rounded-lg transition-colors ${isSel ? 'bg-blue-50 dark:bg-blue-900/20' : 'hover:bg-slate-50 dark:hover:bg-slate-700/50'}`}
                style={{ paddingLeft: `${indent + 24}px` }}
              >
                <button
                  type="button"
                  onClick={() => onSelectFile(node.path, f.name)}
                  className={`flex-1 min-w-0 flex items-center gap-2 py-1.5 text-xs text-left ${isSel ? 'text-blue-600 dark:text-blue-300 font-medium' : 'text-slate-600 dark:text-slate-400 hover:text-blue-500'}`}
                >
                  <FileText className="w-3 h-3 flex-shrink-0" aria-hidden="true" />
                  <span className="truncate">{f.name}</span>
                </button>
                <button
                  type="button"
                  onClick={() => onDeleteFile(node.path, f.name)}
                  aria-label={`Delete ${f.name}`}
                  title="Delete file"
                  className="hidden group-hover:block p-1 rounded text-slate-500 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20"
                >
                  <Trash2 className="w-3.5 h-3.5" aria-hidden="true" />
                </button>
              </div>
            );
          })}
          {hasChildren && node.children!.map((child) => (
            <ContextTreeNode
              key={child.path}
              node={child}
              depth={depth + 1}
              selectedPath={selectedPath}
              selectedFile={selectedFile}
              onSelectFile={onSelectFile}
              onDeleteFolder={onDeleteFolder}
              onDeleteFile={onDeleteFile}
              onUpload={onUpload}
              onCreateFile={onCreateFile}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default ContextBrowser;
