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

interface FileInputProps {
  file: File | null;
  files?: File[];
  onFileSelect?: (file: File) => void;
  onFilesSelect?: (files: File[]) => void;
  onClear?: () => void;
  disabled?: boolean;
  showDocumentSupport?: boolean;
}

function FileInput({
  file,
  files = [],
  onFileSelect,
  onFilesSelect,
  onClear,
  disabled = false,
  showDocumentSupport = true,
}: FileInputProps) {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback((e: React.DragEvent) => {
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

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled) {
      setIsDragging(true);
    }
  }, [disabled]);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
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

  const handleRemoveFile = (index: number) => {
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

  const getFileIcon = (filename: string) => {
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

  const hasSelection = Boolean(file) || files.length > 0;

  return (
    <section
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      aria-label="File upload drop zone"
      className={`relative border-2 border-dashed rounded-xl p-4 sm:p-8 text-center transition-all ${
        disabled
          ? 'border-slate-300 bg-slate-100/50 dark:border-slate-700 dark:bg-slate-800/50'
          : isDragging
          ? 'border-blue-400 bg-blue-500/10'
          : hasSelection
          ? 'border-green-400 bg-green-500/10'
          : 'border-slate-300 hover:border-slate-400 hover:bg-slate-100 dark:border-slate-600 dark:hover:border-slate-500 dark:hover:bg-slate-700/30'
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
        <div className="flex items-center justify-center gap-2 sm:gap-3 flex-wrap">
          {getFileIcon(file.name)}
          <CheckCircle className="w-6 h-6 text-green-400 flex-shrink-0" aria-hidden="true" />
          <span className="text-base sm:text-lg truncate max-w-[60vw] sm:max-w-none">{file.name}</span>
          <button
            type="button"
            onClick={() => onClear?.()}
            className="flex-shrink-0 ml-1 p-2.5 min-w-[44px] min-h-[44px] rounded-full hover:bg-slate-200 dark:hover:bg-slate-600 flex items-center justify-center"
            aria-label={`Remove selected file ${file.name}`}
          >
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={handleClick}
            disabled={disabled}
            className="px-3 py-2 text-sm rounded-lg bg-slate-200 hover:bg-slate-300 dark:bg-slate-600 dark:hover:bg-slate-500 min-w-[44px] min-h-[44px]"
          >
            Change file
          </button>
        </div>
      ) : files.length > 0 ? (
        <div className="text-left">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Files className="w-5 h-5 text-green-400" aria-hidden="true" />
              <span className="font-medium">{files.length} files selected</span>
            </div>
            <button
              type="button"
              onClick={onClear}
              aria-label="Clear all selected files"
              className="p-2.5 min-w-[44px] min-h-[44px] rounded-full hover:bg-slate-200 dark:hover:bg-slate-600 flex items-center justify-center"
            >
              <X className="w-4 h-4" aria-hidden="true" />
            </button>
          </div>
          <div className="max-h-40 overflow-y-auto space-y-2">
            {files.map((f, idx) => (
              <div key={idx} className="flex items-center justify-between bg-slate-100 dark:bg-slate-700 rounded p-2">
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  {getFileIcon(f.name)}
                  <span className="text-sm truncate">{f.name}</span>
                </div>
                <button
                  type="button"
                  onClick={() => handleRemoveFile(idx)}
                  className="ml-2 p-2.5 min-w-[44px] min-h-[44px] rounded hover:bg-slate-200 dark:hover:bg-slate-600 flex items-center justify-center"
                  aria-label={`Remove ${f.name}`}
                >
                  <X className="w-3 h-3" aria-hidden="true" />
                </button>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <>
          <Upload className="w-12 h-12 mx-auto mb-4 text-slate-500 dark:text-slate-400" aria-hidden="true" />
          <p className="text-lg mb-2">
            Drag & drop your file here
          </p>
          <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
            {getSupportedFormatsText()}
          </p>
          <button
            type="button"
            onClick={handleClick}
            disabled={disabled}
            className="px-5 py-2.5 text-sm font-medium rounded-lg bg-blue-500 hover:bg-blue-600 text-white disabled:opacity-50 min-h-[44px]"
          >
            Browse files
          </button>
        </>
      )}
    </section>
  );
}

export default React.memo(FileInput);
