import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Download, FileText, FileType, Copy, Check, Loader2 } from 'lucide-react';
import { EXPORT_FORMATS, exportTranscript } from '../utils/api';

// Add icons to export formats for display
const FORMAT_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  txt: FileText,
  md: FileType,
  srt: FileText,
  pdf: FileType,
  docx: FileType,
  json: FileText,
};

interface ExportMenuProps {
  jobId: string;
  result: { result?: string } | null;
  isMultiModal?: boolean;
  filename?: string;
  className?: string;
}

function ExportMenu({
  jobId,
  result,
  isMultiModal = false,
  filename = 'transcript',
  className = '',
}: ExportMenuProps) {
  const [showMenu, setShowMenu] = useState(false);
  const [copied, setCopied] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [exportingFormat, setExportingFormat] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const menuItemsRef = useRef<(HTMLButtonElement | null)[]>([]);
  const [focusedIndex, setFocusedIndex] = useState(-1);

  const formatEntries = Object.entries(EXPORT_FORMATS);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowMenu(false);
        setFocusedIndex(-1);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Focus first item when menu opens
  useEffect(() => {
    if (showMenu && menuItemsRef.current.length > 0) {
      setFocusedIndex(0);
      menuItemsRef.current[0]?.focus();
    }
  }, [showMenu]);

  const handleMenuKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (!showMenu) return;

    switch (e.key) {
      case 'ArrowDown': {
        e.preventDefault();
        const nextIndex = focusedIndex < formatEntries.length - 1 ? focusedIndex + 1 : 0;
        setFocusedIndex(nextIndex);
        menuItemsRef.current[nextIndex]?.focus();
        break;
      }
      case 'ArrowUp': {
        e.preventDefault();
        const prevIndex = focusedIndex > 0 ? focusedIndex - 1 : formatEntries.length - 1;
        setFocusedIndex(prevIndex);
        menuItemsRef.current[prevIndex]?.focus();
        break;
      }
      case 'Escape':
        e.preventDefault();
        setShowMenu(false);
        setFocusedIndex(-1);
        break;
      case 'Enter':
      case ' ':
        e.preventDefault();
        if (focusedIndex >= 0 && focusedIndex < formatEntries.length) {
          downloadTranscript(formatEntries[focusedIndex][0]);
        }
        break;
      default:
        break;
    }
  }, [showMenu, focusedIndex, formatEntries]);

  const copyToClipboard = async () => {
    if (!result?.result) return;

    try {
      await navigator.clipboard.writeText(result.result);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const downloadTranscript = async (format: string) => {
    if (!jobId || isExporting) return;

    setIsExporting(true);
    setExportingFormat(format);

    try {
      const blob = await exportTranscript(jobId, format, isMultiModal);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${filename}${EXPORT_FORMATS[format].ext}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setShowMenu(false);
      setFocusedIndex(-1);
    } catch (err) {
      console.error('Export error:', err);
    } finally {
      setIsExporting(false);
      setExportingFormat(null);
    }
  };

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      {/* Copy Button */}
      <button
        onClick={copyToClipboard}
        aria-label={copied ? 'Copied to clipboard' : 'Copy transcript to clipboard'}
        className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-all ${
          copied
            ? 'bg-green-500/20 text-green-400'
            : 'bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600'
        }`}
      >
        {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
        {copied ? 'Copied!' : 'Copy'}
      </button>

      {/* Export Dropdown */}
      <div className="relative" ref={menuRef} onKeyDown={handleMenuKeyDown}>
        <button
          onClick={() => setShowMenu(!showMenu)}
          aria-haspopup="true"
          aria-expanded={showMenu}
          disabled={isExporting}
          className="flex items-center gap-2 px-3 py-2 bg-blue-500 hover:bg-blue-600 rounded-lg transition-colors disabled:opacity-50"
        >
          {isExporting ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Download className="w-4 h-4" />
          )}
          {isExporting ? 'Exporting...' : 'Export'}
        </button>

        {showMenu && (
          <div
            className="absolute right-0 mt-2 w-48 bg-white dark:bg-slate-700 rounded-lg shadow-xl border border-slate-200 dark:border-slate-600 py-2 z-10"
            role="menu"
          >
            {formatEntries.map(([format, { label, ext }], index) => {
              const Icon = FORMAT_ICONS[format] || FileText;
              const isThisExporting = isExporting && exportingFormat === format;
              return (
                <button
                  key={format}
                  ref={(el) => { menuItemsRef.current[index] = el; }}
                  role="menuitem"
                  tabIndex={focusedIndex === index ? 0 : -1}
                  onClick={() => downloadTranscript(format)}
                  disabled={isExporting}
                  className="w-full px-4 py-2 text-left hover:bg-slate-100 focus:bg-slate-100 dark:hover:bg-slate-600 dark:focus:bg-slate-600 focus:outline-none flex items-center gap-3 transition-colors disabled:opacity-50"
                >
                  {isThisExporting ? (
                    <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
                  ) : (
                    <Icon className="w-4 h-4 text-slate-400" />
                  )}
                  <span>{label}</span>
                  <span className="text-slate-500 text-sm ml-auto">{ext}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default React.memo(ExportMenu);
