import React, { useRef, useCallback, useState } from 'react';
import { Upload, CheckCircle, X, Files, FileText, FileVideo, FileAudio } from 'lucide-react';
import { getFileType, AUDIO_EXTENSIONS, VIDEO_EXTENSIONS, DOCUMENT_EXTENSIONS } from '../utils/api';

// Build accept string from extensions
const ACCEPTED_EXTENSIONS = [
  'audio/*',
  'video/*',
  ...AUDIO_EXTENSIONS.map(e => `.${e}`),
  ...VIDEO_EXTENSIONS.map(e => `.${e}`),
  ...DOCUMENT_EXTENSIONS.map(e => `.${e}`),
].join(',');

function FileInput({
  file,
  files = [],
  onFileSelect,
  onFilesSelect,
  onClear,
  disabled = false,
  showDocumentSupport = true,
}) {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);

    if (disabled) return;

    const droppedFiles = Array.from(e.dataTransfer.files || []);
    if (droppedFiles.length > 0) {
      if (droppedFiles.length === 1) {
        onFileSelect?.(droppedFiles[0]);
      } else {
        onFilesSelect?.(droppedFiles);
      }
    }
  }, [disabled, onFileSelect, onFilesSelect]);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    if (!disabled) {
      setIsDragging(true);
    }
  }, [disabled]);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleFileSelect = useCallback((e) => {
    const selectedFiles = Array.from(e.target.files || []);
    if (selectedFiles.length > 0) {
      if (selectedFiles.length === 1) {
        onFileSelect?.(selectedFiles[0]);
      } else {
        onFilesSelect?.(selectedFiles);
      }
    }
  }, [onFileSelect, onFilesSelect]);

  const handleClick = () => {
    if (!disabled) {
      fileInputRef.current?.click();
    }
  };

  const handleRemoveFile = (index) => {
    if (files.length > 1) {
      const newFiles = files.filter((_, i) => i !== index);
      if (newFiles.length === 1) {
        onFileSelect?.(newFiles[0]);
      } else {
        onFilesSelect?.(newFiles);
      }
    } else {
      onClear?.();
    }
  };

  const getFileIcon = (filename) => {
    const type = getFileType(filename);
    switch (type) {
      case 'audio':
        return <FileAudio className="w-4 h-4 text-blue-400" />;
      case 'video':
        return <FileVideo className="w-4 h-4 text-purple-400" />;
      case 'document':
        return <FileText className="w-4 h-4 text-orange-400" />;
      default:
        return <FileText className="w-4 h-4 text-slate-400" />;
    }
  };

  const getSupportedFormatsText = () => {
    const formats = ['MP3', 'WAV', 'MP4', 'MKV', 'AVI', 'WebM', 'M4A', 'FLAC', 'OGG'];
    if (showDocumentSupport) {
      formats.push('PDF', 'PPTX', 'DOCX');
    }
    return `Supports ${formats.join(', ')}`;
  };

  return (
    <div
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onClick={handleClick}
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-label={file ? `Selected file: ${file.name}. Click to change.` : 'Click or drag and drop files to upload'}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleClick(); } }}
      className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-all ${
        disabled
          ? 'border-slate-700 bg-slate-800/50 cursor-not-allowed'
          : isDragging
          ? 'border-blue-400 bg-blue-500/10 cursor-pointer'
          : file
          ? 'border-green-400 bg-green-500/10 cursor-pointer'
          : 'border-slate-600 hover:border-slate-500 hover:bg-slate-700/30 cursor-pointer'
      }`}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPTED_EXTENSIONS}
        onChange={handleFileSelect}
        multiple
        className="hidden"
        aria-label="File upload"
        disabled={disabled}
      />

      {file ? (
        <div className="flex items-center justify-center gap-3">
          {getFileIcon(file.name)}
          <CheckCircle className="w-6 h-6 text-green-400" />
          <span className="text-lg">{file.name}</span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onClear?.();
            }}
            className="ml-2 p-1 rounded-full hover:bg-slate-600"
            aria-label="Remove selected file"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ) : files.length > 0 ? (
        <div className="text-left" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Files className="w-5 h-5 text-green-400" />
              <span className="font-medium">{files.length} files selected</span>
            </div>
            <button
              onClick={onClear}
              className="p-1 rounded-full hover:bg-slate-600"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="max-h-40 overflow-y-auto space-y-2">
            {files.map((f, idx) => (
              <div key={idx} className="flex items-center justify-between bg-slate-700 rounded p-2">
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  {getFileIcon(f.name)}
                  <span className="text-sm truncate">{f.name}</span>
                </div>
                <button
                  onClick={() => handleRemoveFile(idx)}
                  className="ml-2 p-1 rounded hover:bg-slate-600"
                  aria-label={"Remove " + f.name}
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <>
          <Upload className="w-12 h-12 mx-auto mb-4 text-slate-400" />
          <p className="text-lg mb-2">
            Drag & drop your file here
          </p>
          <p className="text-sm text-slate-400">
            {getSupportedFormatsText()}
          </p>
        </>
      )}
    </div>
  );
}

export default React.memo(FileInput);
