import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Upload, Link, FileAudio, Clock, Globe, Loader2, CheckCircle, AlertCircle, Copy, Download, X } from 'lucide-react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

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
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [showTimestamps, setShowTimestamps] = useState(true);
  const fileInputRef = useRef(null);
  const pollIntervalRef = useRef(null);

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

      if (data.status === 'completed') {
        setResult(data);
        setIsTranscribing(false);
        setJobId(null);
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

    try {
      let response;

      if (inputMode === InputMode.FILE && file) {
        const formData = new FormData();
        formData.append('file', file);

        response = await fetch(`${API_URL}/transcribe/file`, {
          method: 'POST',
          body: formData,
        });
      } else if (inputMode === InputMode.YOUTUBE && youtubeUrl) {
        response = await fetch(`${API_URL}/transcribe/youtube`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ url: youtubeUrl }),
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

  // Download as SRT
  const downloadSRT = () => {
    if (!result?.segments) return;

    let srtContent = '';
    result.segments.forEach((segment, index) => {
      const startTime = formatSRTTime(segment.start);
      const endTime = formatSRTTime(segment.end);
      srtContent += `${index + 1}\n${startTime} --> ${endTime}\n${segment.text}\n\n`;
    });

    const blob = new Blob([srtContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'transcription.srt';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // Format time for SRT format
  const formatSRTTime = (seconds) => {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 1000);
    return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')},${ms.toString().padStart(3, '0')}`;
  };

  // Clear current selection
  const clearSelection = () => {
    setFile(null);
    setYoutubeUrl('');
    setResult(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const canStart = (inputMode === InputMode.FILE && file) ||
                   (inputMode === InputMode.YOUTUBE && youtubeUrl.trim());

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
            High-quality audio & video transcription powered by Whisper Large-V3
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
              <span className="font-medium">Processing your audio...</span>
            </div>
            <div className="w-full bg-slate-700 rounded-full h-3">
              <div
                className="bg-gradient-to-r from-blue-500 to-purple-500 h-3 rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-sm text-slate-400 mt-2">
              This may take a few minutes depending on the audio length
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
            <div className="flex items-center justify-between mb-6">
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
                <button
                  onClick={downloadSRT}
                  className="flex items-center gap-2 px-3 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors"
                >
                  <Download className="w-4 h-4" />
                  SRT
                </button>
              </div>
            </div>

            {/* Language Info */}
            {result.language && (
              <div className="flex items-center gap-4 mb-6 p-3 bg-slate-700/50 rounded-lg">
                <div className="flex items-center gap-2">
                  <Globe className="w-4 h-4 text-blue-400" />
                  <span className="text-slate-300">Language:</span>
                  <span className="font-medium">{result.language.toUpperCase()}</span>
                </div>
                {result.language_probability && (
                  <span className="text-slate-400 text-sm">
                    ({(result.language_probability * 100).toFixed(1)}% confidence)
                  </span>
                )}
              </div>
            )}

            {/* Timestamps Toggle */}
            <div className="flex items-center gap-2 mb-4">
              <button
                onClick={() => setShowTimestamps(!showTimestamps)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
                  showTimestamps ? 'bg-blue-500 text-white' : 'bg-slate-700 text-slate-300'
                }`}
              >
                <Clock className="w-4 h-4" />
                Timestamps
              </button>
            </div>

            {/* Transcription Text */}
            <div className="bg-slate-900/50 rounded-xl p-4 max-h-96 overflow-y-auto">
              {showTimestamps && result.segments ? (
                <div className="space-y-3">
                  {result.segments.map((segment, index) => (
                    <div key={index} className="flex gap-3">
                      <span className="text-blue-400 font-mono text-sm whitespace-nowrap pt-1">
                        [{formatTime(segment.start)}]
                      </span>
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
          <p>Powered by OpenAI Whisper Large-V3 via faster-whisper</p>
        </footer>
      </div>
    </div>
  );
}

export default App;
