import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Upload, Link, FileAudio, Clock, Globe, Loader2, CheckCircle, AlertCircle, Copy, Download, X, Users, Languages, FileText, FileType } from 'lucide-react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Supported languages
const LANGUAGES = {
  auto: 'Auto-detect',
  en: 'English',
  fr: 'French',
};

// Export formats
const EXPORT_FORMATS = {
  txt: { label: 'Plain Text', ext: '.txt', icon: FileText },
  md: { label: 'Markdown', ext: '.md', icon: FileType },
  srt: { label: 'SRT Subtitles', ext: '.srt', icon: FileText },
  pdf: { label: 'PDF Document', ext: '.pdf', icon: FileType },
  docx: { label: 'Word Document', ext: '.docx', icon: FileType },
};

// Format timestamp for display
const formatTime = (seconds) => {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 100);

  if (hrs > 0) {
    return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
  }
  return `${mins}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
};

// Input mode tabs
const InputMode = {
  FILE: 'file',
  YOUTUBE: 'youtube',
};

function App() {
  const [inputMode, setInputMode] = useState(InputMode.FILE);
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [file, setFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [showTimestamps, setShowTimestamps] = useState(true);
  const [showSpeakers, setShowSpeakers] = useState(true);
  const [exportFormat, setExportFormat] = useState('txt');
  const [showExportMenu, setShowExportMenu] = useState(false);

  // Settings
  const [language, setLanguage] = useState('auto');
  const [enableDiarization, setEnableDiarization] = useState(true);

  const fileInputRef = useRef(null);
  const pollIntervalRef = useRef(null);
  const exportMenuRef = useRef(null);

  // Close export menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(event.target)) {
        setShowExportMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  // Poll for job status
  const pollJobStatus = useCallback(async (id) => {
    try {
      const response = await fetch(`${API_URL}/job/${id}`);
      const data = await response.json();

      setProgress(data.progress || 0);
      setProgressMessage(data.progress_message || '');

      if (data.status === 'completed') {
        setResult(data);
        setIsTranscribing(false);
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
      } else if (data.status === 'failed') {
        setError(data.error || 'Transcription failed');
        setIsTranscribing(false);
        setJobId(null);
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
      }
    } catch (err) {
      console.error('Error polling job status:', err);
    }
  }, []);

  // Start polling when job is created
  useEffect(() => {
    if (jobId && isTranscribing) {
      pollIntervalRef.current = setInterval(() => {
        pollJobStatus(jobId);
      }, 1000);

      // Initial poll
      pollJobStatus(jobId);
    }

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [jobId, isTranscribing, pollJobStatus]);

  // Handle file drop
  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);

    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      setFile(droppedFile);
      setError(null);
      setResult(null);
    }
  }, []);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  // Handle file selection
  const handleFileSelect = useCallback((e) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setError(null);
      setResult(null);
    }
  }, []);

  // Start transcription
  const startTranscription = async () => {
    setError(null);
    setResult(null);
    setIsTranscribing(true);
    setProgress(0);
    setProgressMessage('Starting...');

    try {
      let response;
      const params = new URLSearchParams({
        language,
        enable_diarization: enableDiarization,
      });

      if (inputMode === InputMode.FILE && file) {
        const formData = new FormData();
        formData.append('file', file);

        response = await fetch(`${API_URL}/transcribe/file?${params}`, {
          method: 'POST',
          body: formData,
        });
      } else if (inputMode === InputMode.YOUTUBE && youtubeUrl) {
        response = await fetch(`${API_URL}/transcribe/youtube?${params}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            url: youtubeUrl,
            language,
            enable_diarization: enableDiarization,
          }),
        });
      } else {
        throw new Error('Please select a file or enter a YouTube URL');
      }

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Transcription request failed');
      }

      const data = await response.json();
      setJobId(data.job_id);

    } catch (err) {
      setError(err.message || 'Failed to start transcription');
      setIsTranscribing(false);
    }
  };

  // Copy result to clipboard
  const copyToClipboard = async () => {
    if (!result?.result) return;

    try {
      await navigator.clipboard.writeText(result.result);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  // Download transcript in selected format
  const downloadTranscript = async (format) => {
    if (!jobId) return;

    try {
      const response = await fetch(`${API_URL}/job/${jobId}/export?format=${format}`);

      if (!response.ok) {
        throw new Error('Export failed');
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `transcript${EXPORT_FORMATS[format].ext}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setShowExportMenu(false);
    } catch (err) {
      console.error('Export error:', err);
      setError('Failed to export transcript');
    }
  };

  // Clear current selection
  const clearSelection = () => {
    setFile(null);
    setYoutubeUrl('');
    setResult(null);
    setError(null);
    setJobId(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const canStart = (inputMode === InputMode.FILE && file) ||
                   (inputMode === InputMode.YOUTUBE && youtubeUrl.trim());

  // Get unique speakers from result
  const speakers = result?.speakers || [];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Header */}
        <header className="text-center mb-12">
          <div className="flex items-center justify-center gap-3 mb-4">
            <FileAudio className="w-10 h-10 text-blue-400" />
            <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500">
              Whisper Transcription
            </h1>
          </div>
          <p className="text-slate-400 text-lg">
            High-quality transcription with speaker recognition
          </p>
        </header>

        {/* Input Section */}
        <div className="bg-slate-800/50 backdrop-blur rounded-2xl p-6 mb-8 border border-slate-700">
          {/* Mode Tabs */}
          <div className="flex gap-2 mb-6">
            <button
              onClick={() => setInputMode(InputMode.FILE)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                inputMode === InputMode.FILE
                  ? 'bg-blue-500 text-white'
                  : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
              }`}
            >
              <Upload className="w-4 h-4" />
              Upload File
            </button>
            <button
              onClick={() => setInputMode(InputMode.YOUTUBE)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                inputMode === InputMode.YOUTUBE
                  ? 'bg-blue-500 text-white'
                  : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
              }`}
            >
              <Link className="w-4 h-4" />
              YouTube URL
            </button>
          </div>

          {/* File Upload */}
          {inputMode === InputMode.FILE && (
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={() => fileInputRef.current?.click()}
              className={`relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
                isDragging
                  ? 'border-blue-400 bg-blue-500/10'
                  : file
                  ? 'border-green-400 bg-green-500/10'
                  : 'border-slate-600 hover:border-slate-500 hover:bg-slate-700/30'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="audio/*,video/*,.mp3,.wav,.mp4,.mkv,.avi,.webm,.m4a,.flac,.ogg"
                onChange={handleFileSelect}
                className="hidden"
              />

              {file ? (
                <div className="flex items-center justify-center gap-3">
                  <CheckCircle className="w-6 h-6 text-green-400" />
                  <span className="text-lg">{file.name}</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      clearSelection();
                    }}
                    className="ml-2 p-1 rounded-full hover:bg-slate-600"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <>
                  <Upload className="w-12 h-12 mx-auto mb-4 text-slate-400" />
                  <p className="text-lg mb-2">
                    Drag & drop your audio or video file here
                  </p>
                  <p className="text-sm text-slate-500">
                    Supports MP3, WAV, MP4, MKV, AVI, WebM, M4A, FLAC, OGG
                  </p>
                </>
              )}
            </div>
          )}

          {/* YouTube URL Input */}
          {inputMode === InputMode.YOUTUBE && (
            <div className="relative">
              <input
                type="url"
                value={youtubeUrl}
                onChange={(e) => {
                  setYoutubeUrl(e.target.value);
                  setError(null);
                  setResult(null);
                }}
                placeholder="https://www.youtube.com/watch?v=..."
                className="w-full px-4 py-4 bg-slate-700 border border-slate-600 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400"
              />
              {youtubeUrl && (
                <button
                  onClick={clearSelection}
                  className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded-full hover:bg-slate-600"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
          )}

          {/* Settings */}
          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Language Selection */}
            <div>
              <label className="flex items-center gap-2 text-sm text-slate-400 mb-2">
                <Languages className="w-4 h-4" />
                Language
              </label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-400"
              >
                {Object.entries(LANGUAGES).map(([code, name]) => (
                  <option key={code} value={code}>
                    {name}
                  </option>
                ))}
              </select>
            </div>

            {/* Speaker Diarization Toggle */}
            <div>
              <label className="flex items-center gap-2 text-sm text-slate-400 mb-2">
                <Users className="w-4 h-4" />
                Speaker Recognition
              </label>
              <button
                onClick={() => setEnableDiarization(!enableDiarization)}
                className={`w-full px-4 py-3 rounded-lg font-medium transition-all flex items-center justify-center gap-2 ${
                  enableDiarization
                    ? 'bg-blue-500 text-white'
                    : 'bg-slate-700 text-slate-300 border border-slate-600'
                }`}
              >
                <Users className="w-4 h-4" />
                {enableDiarization ? 'Enabled' : 'Disabled'}
              </button>
            </div>
          </div>

          {/* Transcribe Button */}
          <button
            onClick={startTranscription}
            disabled={!canStart || isTranscribing}
            className={`w-full mt-6 py-4 rounded-xl font-semibold text-lg transition-all ${
              canStart && !isTranscribing
                ? 'bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 text-white'
                : 'bg-slate-700 text-slate-400 cursor-not-allowed'
            }`}
          >
            {isTranscribing ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 className="w-5 h-5 animate-spin" />
                Transcribing... {progress}%
              </span>
            ) : (
              'Start Transcription'
            )}
          </button>
        </div>

        {/* Progress Bar */}
        {isTranscribing && (
          <div className="bg-slate-800/50 backdrop-blur rounded-2xl p-6 mb-8 border border-slate-700">
            <div className="flex items-center gap-3 mb-4">
              <Loader2 className="w-5 h-5 animate-spin text-blue-400" />
              <span className="font-medium">{progressMessage || 'Processing your audio...'}</span>
            </div>
            <div className="w-full bg-slate-700 rounded-full h-3">
              <div
                className="bg-gradient-to-r from-blue-500 to-purple-500 h-3 rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-sm text-slate-400 mt-2">
              Quality-focused transcription may take a few minutes
            </p>
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/50 rounded-2xl p-6 mb-8">
            <div className="flex items-center gap-3 text-red-400">
              <AlertCircle className="w-5 h-5" />
              <span className="font-medium">Error</span>
            </div>
            <p className="mt-2 text-red-300">{error}</p>
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="bg-slate-800/50 backdrop-blur rounded-2xl p-6 border border-slate-700">
            {/* Results Header */}
            <div className="flex items-center justify-between mb-6 flex-wrap gap-4">
              <div className="flex items-center gap-3">
                <CheckCircle className="w-6 h-6 text-green-400" />
                <h2 className="text-xl font-semibold">Transcription Complete</h2>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={copyToClipboard}
                  className="flex items-center gap-2 px-3 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors"
                >
                  <Copy className="w-4 h-4" />
                  Copy
                </button>

                {/* Export Dropdown */}
                <div className="relative" ref={exportMenuRef}>
                  <button
                    onClick={() => setShowExportMenu(!showExportMenu)}
                    className="flex items-center gap-2 px-3 py-2 bg-blue-500 hover:bg-blue-600 rounded-lg transition-colors"
                  >
                    <Download className="w-4 h-4" />
                    Export
                  </button>

                  {showExportMenu && (
                    <div className="absolute right-0 mt-2 w-48 bg-slate-700 rounded-lg shadow-xl border border-slate-600 py-2 z-10">
                      {Object.entries(EXPORT_FORMATS).map(([format, { label, ext, icon: Icon }]) => (
                        <button
                          key={format}
                          onClick={() => downloadTranscript(format)}
                          className="w-full px-4 py-2 text-left hover:bg-slate-600 flex items-center gap-3 transition-colors"
                        >
                          <Icon className="w-4 h-4 text-slate-400" />
                          <span>{label}</span>
                          <span className="text-slate-500 text-sm ml-auto">{ext}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Language & Speakers Info */}
            <div className="flex flex-wrap items-center gap-4 mb-6 p-3 bg-slate-700/50 rounded-lg">
              {result.language && (
                <div className="flex items-center gap-2">
                  <Globe className="w-4 h-4 text-blue-400" />
                  <span className="text-slate-300">Language:</span>
                  <span className="font-medium">{LANGUAGES[result.language] || result.language.toUpperCase()}</span>
                  {result.language_probability && (
                    <span className="text-slate-400 text-sm">
                      ({(result.language_probability * 100).toFixed(1)}%)
                    </span>
                  )}
                </div>
              )}
              {speakers.length > 0 && (
                <div className="flex items-center gap-2">
                  <Users className="w-4 h-4 text-purple-400" />
                  <span className="text-slate-300">Speakers:</span>
                  <span className="font-medium">{speakers.length}</span>
                </div>
              )}
            </div>

            {/* View Toggles */}
            <div className="flex items-center gap-2 mb-4 flex-wrap">
              <button
                onClick={() => setShowTimestamps(!showTimestamps)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
                  showTimestamps ? 'bg-blue-500 text-white' : 'bg-slate-700 text-slate-300'
                }`}
              >
                <Clock className="w-4 h-4" />
                Timestamps
              </button>
              {speakers.length > 0 && (
                <button
                  onClick={() => setShowSpeakers(!showSpeakers)}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
                    showSpeakers ? 'bg-purple-500 text-white' : 'bg-slate-700 text-slate-300'
                  }`}
                >
                  <Users className="w-4 h-4" />
                  Speakers
                </button>
              )}
            </div>

            {/* Transcription Text */}
            <div className="bg-slate-900/50 rounded-xl p-4 max-h-[32rem] overflow-y-auto">
              {(showTimestamps || showSpeakers) && result.segments ? (
                <div className="space-y-3">
                  {result.segments.map((segment, index) => (
                    <div key={index} className="flex gap-3">
                      {showTimestamps && (
                        <span className="text-blue-400 font-mono text-sm whitespace-nowrap pt-1">
                          [{formatTime(segment.start)}]
                        </span>
                      )}
                      {showSpeakers && segment.speaker && (
                        <span className="text-purple-400 font-medium text-sm whitespace-nowrap pt-1">
                          {segment.speaker}:
                        </span>
                      )}
                      <p className="text-slate-200 leading-relaxed">{segment.text}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-slate-200 leading-relaxed whitespace-pre-wrap">
                  {result.result}
                </p>
              )}
            </div>
          </div>
        )}

        {/* Footer */}
        <footer className="text-center mt-12 text-slate-500 text-sm">
          <p>Powered by OpenAI Whisper Large-V3 with speaker diarization</p>
          <p className="mt-1">Optimized for Apple Silicon</p>
        </footer>
      </div>
    </div>
  );
}

export default App;
