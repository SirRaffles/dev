import React, { useState, useRef, useEffect } from 'react';
import { Download, FileText, FileType, Copy, Check } from 'lucide-react';
import { EXPORT_FORMATS, exportTranscript } from '../utils/api';

// Add icons to export formats for display
const FORMAT_ICONS = {
  txt: FileText,
  md: FileType,
  srt: FileText,
  pdf: FileType,
  docx: FileType,
  json: FileText,
};

function ExportMenu({
  jobId,
  result,
  isMultiModal = false,
  filename = 'transcript',
  className = '',
}) {
  const [showMenu, setShowMenu] = useState(false);
  const [copied, setCopied] = useState(false);
  const menuRef = useRef(null);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setShowMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

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

  const downloadTranscript = async (format) => {
    if (!jobId) return;

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
    } catch (err) {
      console.error('Export error:', err);
    }
  };

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      {/* Copy Button */}
      <button
        onClick={copyToClipboard}
        className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
          copied ? 'bg-green-600 text-white' : 'bg-slate-700 hover:bg-slate-600'
        }`}
      >
        {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
        {copied ? 'Copied!' : 'Copy'}
      </button>

      {/* Export Dropdown */}
      <div className="relative" ref={menuRef}>
        <button
          onClick={() => setShowMenu(!showMenu)}
          className="flex items-center gap-2 px-3 py-2 bg-blue-500 hover:bg-blue-600 rounded-lg transition-colors"
        >
          <Download className="w-4 h-4" />
          Export
        </button>

        {showMenu && (
          <div className="absolute right-0 mt-2 w-48 bg-slate-700 rounded-lg shadow-xl border border-slate-600 py-2 z-10">
            {Object.entries(EXPORT_FORMATS).map(([format, { label, ext }]) => {
              const Icon = FORMAT_ICONS[format] || FileText;
              return (
                <button
                  key={format}
                  onClick={() => downloadTranscript(format)}
                  className="w-full px-4 py-2 text-left hover:bg-slate-600 flex items-center gap-3 transition-colors"
                >
                  <Icon className="w-4 h-4 text-slate-400" />
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
