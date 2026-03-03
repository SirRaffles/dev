import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Upload, Link, FileAudio, Clock, Globe, Loader2, CheckCircle, AlertCircle, Copy, Check, Download, X, Users, Languages, FileText, FileType, Play, Pause, SkipBack, SkipForward, Edit2, Save, Search, Replace, Volume2, VolumeX, Files, Edit3 } from 'lucide-react';

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
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [copied, setCopied] = useState(false);

  // Settings
  const [language, setLanguage] = useState('auto');
  const [enableDiarization, setEnableDiarization] = useState(true);
  const [enableNoiseReduction, setEnableNoiseReduction] = useState(false);

  // Batch upload
  const [files, setFiles] = useState([]);
  const [batchJobIds, setBatchJobIds] = useState([]);
  const [batchProgress, setBatchProgress] = useState([]);

  // Speaker renaming
  const [speakerNames, setSpeakerNames] = useState({});
  const [editingSpeaker, setEditingSpeaker] = useState(null);
  const [tempSpeakerName, setTempSpeakerName] = useState('');

  // Search & replace
  const [showSearchPanel, setShowSearchPanel] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [replaceText, setReplaceText] = useState('');
  const [searchResults, setSearchResults] = useState([]);

  // Audio player state
  const [audioUrl, setAudioUrl] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  // Editing state
  const [isEditing, setIsEditing] = useState(false);
  const [editedSegments, setEditedSegments] = useState({});

  const fileInputRef = useRef(null);
  const pollIntervalRef = useRef(null);
  const exportMenuRef = useRef(null);
  const audioRef = useRef(null);
  const segmentRefs = useRef({});

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

  // Cleanup polling and audio URL on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }
    };
  }, [audioUrl]);

  // Audio time update handler
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const handleTimeUpdate = () => {
      setCurrentTime(audio.currentTime);
    };

    const handleLoadedMetadata = () => {
      setDuration(audio.duration);
    };

    const handleEnded = () => {
      setIsPlaying(false);
    };

    audio.addEventListener('timeupdate', handleTimeUpdate);
    audio.addEventListener('loadedmetadata', handleLoadedMetadata);
    audio.addEventListener('ended', handleEnded);

    return () => {
      audio.removeEventListener('timeupdate', handleTimeUpdate);
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
      audio.removeEventListener('ended', handleEnded);
    };
  }, [audioRef.current]);

  // Auto-scroll to current segment
  useEffect(() => {
    if (!result?.segments || !currentTime) return;

    const currentSegment = result.segments.findIndex(
      segment => currentTime >= segment.start && currentTime <= segment.end
    );

    if (currentSegment >= 0 && segmentRefs.current[currentSegment]) {
      segmentRefs.current[currentSegment].scrollIntoView({
        behavior: 'smooth',
        block: 'center'
      });
    }
  }, [currentTime, result]);

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
      // Create audio URL for playback
      const url = URL.createObjectURL(droppedFile);
      setAudioUrl(url);
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
      // Create audio URL for playback
      const url = URL.createObjectURL(selectedFile);
      setAudioUrl(url);
      setError(null);
      setResult(null);
    }
  }, []);

  // Audio player controls
  const togglePlayPause = () => {
    const audio = audioRef.current;
    if (!audio) return;

    if (isPlaying) {
      audio.pause();
    } else {
      audio.play();
    }
    setIsPlaying(!isPlaying);
  };

  const skipBackward = () => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = Math.max(0, audio.currentTime - 5);
  };

  const skipForward = () => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = Math.min(duration, audio.currentTime + 5);
  };

  const seekToTime = (time) => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = time;
    if (!isPlaying) {
      audio.play();
      setIsPlaying(true);
    }
  };

  // Get current playing segment
  const getCurrentSegmentIndex = () => {
    if (!result?.segments) return -1;
    return result.segments.findIndex(
      segment => currentTime >= segment.start && currentTime <= segment.end
    );
  };

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
        enable_noise_reduction: enableNoiseReduction,
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
            enable_noise_reduction: enableNoiseReduction,
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

  // Handle editing
  const handleEditSegment = (index, newText) => {
    setEditedSegments(prev => ({
      ...prev,
      [index]: newText
    }));
  };

  const saveEdits = async () => {
    if (!jobId || Object.keys(editedSegments).length === 0) {
      setIsEditing(false);
      return;
    }

    try {
      // Prepare segments with edits
      const updatedSegments = result.segments.map((segment, index) => ({
        ...segment,
        text: editedSegments[index] !== undefined ? editedSegments[index] : segment.text
      }));

      const response = await fetch(`${API_URL}/job/${jobId}/segments`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ segments: updatedSegments }),
      });

      if (!response.ok) {
        throw new Error('Failed to save edits');
      }

      // Update result with edited segments
      setResult(prev => ({
        ...prev,
        segments: updatedSegments
      }));

      setIsEditing(false);
      setEditedSegments({});
    } catch (err) {
      console.error('Save error:', err);
      setError('Failed to save edits');
    }
  };

  // Speaker renaming functions
  const startEditingSpeaker = (speaker) => {
    setEditingSpeaker(speaker);
    setTempSpeakerName(speakerNames[speaker] || speaker);
  };

  const cancelEditingSpeaker = () => {
    setEditingSpeaker(null);
    setTempSpeakerName('');
  };

  const saveSpeakerName = async () => {
    if (!editingSpeaker || !tempSpeakerName.trim() || !jobId) return;

    try {
      const mapping = { [editingSpeaker]: tempSpeakerName.trim() };
      const response = await fetch(`${API_URL}/job/${jobId}/speakers`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ speaker_mapping: mapping }),
      });

      if (!response.ok) throw new Error('Failed to rename speaker');

      const data = await response.json();
      setSpeakerNames(prev => ({ ...prev, [editingSpeaker]: tempSpeakerName.trim() }));
      setResult(prev => ({ ...prev, segments: data.segments, speakers: data.speakers }));
      cancelEditingSpeaker();
    } catch (err) {
      console.error('Rename error:', err);
      setError('Failed to rename speaker');
    }
  };

  // Search functions
  const performSearch = () => {
    if (!result?.segments || !searchQuery.trim()) {
      setSearchResults([]);
      return;
    }

    const matches = [];
    const query = searchQuery.toLowerCase();
    result.segments.forEach((segment, index) => {
      if (segment.text.toLowerCase().includes(query)) {
        matches.push(index);
      }
    });
    setSearchResults(matches);
  };

  const replaceInSegment = async (index) => {
    if (!searchQuery || !result?.segments) return;

    const segment = result.segments[index];
    const newText = segment.text.replace(new RegExp(searchQuery, 'gi'), replaceText);

    setEditedSegments(prev => ({ ...prev, [index]: newText }));

    // Save immediately
    const updatedSegments = result.segments.map((seg, i) => ({
      ...seg,
      text: i === index ? newText : (editedSegments[i] !== undefined ? editedSegments[i] : seg.text)
    }));

    try {
      const response = await fetch(`${API_URL}/job/${jobId}/segments`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ segments: updatedSegments }),
      });

      if (!response.ok) throw new Error('Failed to save');

      setResult(prev => ({ ...prev, segments: updatedSegments }));
      performSearch(); // Refresh search results
    } catch (err) {
      console.error('Replace error:', err);
    }
  };

  const replaceAll = async () => {
    if (!searchQuery || !result?.segments) return;

    const updatedSegments = result.segments.map((segment, index) => ({
      ...segment,
      text: segment.text.replace(new RegExp(searchQuery, 'gi'), replaceText)
    }));

    try {
      const response = await fetch(`${API_URL}/job/${jobId}/segments`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ segments: updatedSegments }),
      });

      if (!response.ok) throw new Error('Failed to save');

      setResult(prev => ({ ...prev, segments: updatedSegments }));
      setSearchResults([]);
      setSearchQuery('');
      setReplaceText('');
    } catch (err) {
      console.error('Replace all error:', err);
      setError('Failed to replace text');
    }
  };

  // Highlight matching text
  const highlightText = (text, index) => {
    if (!searchQuery || !searchResults.includes(index)) return text;

    const regex = new RegExp(`(${searchQuery})`, 'gi');
    const parts = text.split(regex);

    return parts.map((part, i) =>
      regex.test(part) ? <mark key={i} className="bg-yellow-400 text-black px-0.5 rounded">{part}</mark> : part
    );
  };

  // Copy result to clipboard
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

  // Clear current selection and start fresh
  const clearSelection = () => {
    setFile(null);
    setFiles([]);
    setYoutubeUrl('');
    setResult(null);
    setError(null);
    setJobId(null);
    setCopied(false);
    setProgress(0);
    setProgressMessage('');
    setIsEditing(false);
    setEditedSegments({});
    setBatchJobIds([]);
    setBatchProgress([]);
    setSpeakerNames({});
    setEditingSpeaker(null);
    setTempSpeakerName('');
    setShowSearchPanel(false);
    setSearchQuery('');
    setReplaceText('');
    setSearchResults([]);
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
      setAudioUrl(null);
    }
    setIsPlaying(false);
    setCurrentTime(0);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const canStart = (inputMode === InputMode.FILE && file) ||
                   (inputMode === InputMode.YOUTUBE && youtubeUrl.trim());

  // Get unique speakers from result
  const speakers = result?.speakers || [];
  const currentSegmentIndex = getCurrentSegmentIndex();

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
      <div className="max-w-4xl mx-auto px-3 sm:px-4 py-4 sm:py-8">
        {/* Header */}
        <header className="text-center mb-12">
          <div className="flex items-center justify-center gap-3 mb-4">
            <FileAudio className="w-8 h-8 sm:w-10 sm:h-10 text-blue-400" />
            <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500">
              Whisper Transcription
            </h1>
          </div>
          <p className="text-slate-400 text-base sm:text-lg">
            High-quality transcription with speaker recognition
          </p>
        </header>

        {/* Input Section */}
        <div className="bg-slate-800/50 backdrop-blur rounded-2xl p-4 sm:p-6 mb-6 sm:mb-8 border border-slate-700">
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
          <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
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

            {/* Noise Reduction Toggle */}
            <div>
              <label className="flex items-center gap-2 text-sm text-slate-400 mb-2">
                {enableNoiseReduction ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
                Noise Reduction
              </label>
              <button
                onClick={() => setEnableNoiseReduction(!enableNoiseReduction)}
                className={`w-full px-4 py-3 rounded-lg font-medium transition-all flex items-center justify-center gap-2 ${
                  enableNoiseReduction
                    ? 'bg-green-500 text-white'
                    : 'bg-slate-700 text-slate-300 border border-slate-600'
                }`}
              >
                {enableNoiseReduction ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
                {enableNoiseReduction ? 'Enabled' : 'Disabled'}
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
          <div className="bg-slate-800/50 backdrop-blur rounded-2xl p-4 sm:p-6 border border-slate-700">
            {/* Hidden audio element */}
            {audioUrl && (
              <audio ref={audioRef} src={audioUrl} preload="metadata" />
            )}

            {/* Results Header */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-6 gap-4">
              <div className="flex items-center gap-3">
                <CheckCircle className="w-6 h-6 text-green-400" />
                <h2 className="text-xl font-semibold">Transcription Complete</h2>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                {isEditing ? (
                  <button
                    onClick={saveEdits}
                    className="flex items-center gap-1.5 sm:gap-2 px-2 sm:px-3 py-2 bg-green-600 hover:bg-green-700 rounded-lg transition-colors"
                  >
                    <Save className="w-4 h-4" />
                    Save
                  </button>
                ) : (
                  <button
                    onClick={() => setIsEditing(true)}
                    className="flex items-center gap-1.5 sm:gap-2 px-2 sm:px-3 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors"
                  >
                    <Edit2 className="w-4 h-4" />
                    Edit
                  </button>
                )}
                <button
                  onClick={copyToClipboard}
                  className={`flex items-center gap-1.5 sm:gap-2 px-2 sm:px-3 py-2 rounded-lg transition-colors ${
                    copied ? 'bg-green-600 text-white' : 'bg-slate-700 hover:bg-slate-600'
                  }`}
                >
                  {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                  {copied ? 'Copied!' : 'Copy'}
                </button>

                {/* Export Dropdown */}
                <div className="relative" ref={exportMenuRef}>
                  <button
                    onClick={() => setShowExportMenu(!showExportMenu)}
                    className="flex items-center gap-1.5 sm:gap-2 px-2 sm:px-3 py-2 bg-blue-500 hover:bg-blue-600 rounded-lg transition-colors"
                  >
                    <Download className="w-4 h-4" />
                    Export
                  </button>

                  {showExportMenu && (
                    <div className="absolute right-0 mt-2 w-48 max-w-[calc(100vw-2rem)] bg-slate-700 rounded-lg shadow-xl border border-slate-600 py-2 z-10">
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

            {/* Audio Player */}
            {audioUrl && (
              <div className="mb-6 bg-slate-700/50 rounded-xl p-4">
                <div className="flex items-center gap-2 sm:gap-4 mb-3 flex-wrap">
                  <button
                    onClick={skipBackward}
                    className="p-3 sm:p-2 bg-slate-600 hover:bg-slate-500 rounded-lg transition-colors"
                  >
                    <SkipBack className="w-5 h-5" />
                  </button>
                  <button
                    onClick={togglePlayPause}
                    className="p-3 bg-blue-500 hover:bg-blue-600 rounded-lg transition-colors"
                  >
                    {isPlaying ? <Pause className="w-6 h-6" /> : <Play className="w-6 h-6" />}
                  </button>
                  <button
                    onClick={skipForward}
                    className="p-3 sm:p-2 bg-slate-600 hover:bg-slate-500 rounded-lg transition-colors"
                  >
                    <SkipForward className="w-5 h-5" />
                  </button>
                  <div className="flex items-center gap-3 text-sm font-mono">
                    <span>{formatTime(currentTime)}</span>
                    <span className="text-slate-400">/</span>
                    <span className="text-slate-400">{formatTime(duration)}</span>
                  </div>
                </div>
                <div className="relative h-2 bg-slate-600 rounded-full overflow-hidden cursor-pointer"
                     onClick={(e) => {
                       const rect = e.currentTarget.getBoundingClientRect();
                       const x = e.clientX - rect.left;
                       const percentage = x / rect.width;
                       seekToTime(percentage * duration);
                     }}>
                  <div
                    className="absolute top-0 left-0 h-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all"
                    style={{ width: `${(currentTime / duration) * 100}%` }}
                  />
                </div>
              </div>
            )}

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

            {/* Speaker Renaming */}
            {speakers.length > 0 && (
              <div className="mb-6 p-4 bg-slate-700/30 rounded-xl">
                <h3 className="text-sm font-medium text-slate-300 mb-3 flex items-center gap-2">
                  <Edit3 className="w-4 h-4" />
                  Rename Speakers
                </h3>
                <div className="flex flex-wrap gap-2">
                  {speakers.map((speaker) => (
                    <div key={speaker} className="flex items-center gap-1">
                      {editingSpeaker === speaker ? (
                        <div className="flex items-center gap-1 bg-slate-600 rounded-lg px-2 py-1">
                          <input
                            type="text"
                            value={tempSpeakerName}
                            onChange={(e) => setTempSpeakerName(e.target.value)}
                            className="w-32 sm:w-24 bg-slate-700 text-white px-2 py-1.5 sm:py-1 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                            autoFocus
                            onKeyDown={(e) => e.key === 'Enter' && saveSpeakerName()}
                          />
                          <button
                            onClick={saveSpeakerName}
                            className="p-2 sm:p-1 text-green-400 hover:text-green-300"
                          >
                            <Check className="w-4 h-4" />
                          </button>
                          <button
                            onClick={cancelEditingSpeaker}
                            className="p-2 sm:p-1 text-red-400 hover:text-red-300"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1 bg-purple-500/20 text-purple-300 rounded-lg px-3 py-1">
                          <span className="text-sm">{speakerNames[speaker] || speaker}</span>
                          <button
                            onClick={() => startEditingSpeaker(speaker)}
                            className="p-1.5 sm:p-0.5 hover:text-purple-200 transition-colors"
                          >
                            <Edit3 className="w-3 h-3" />
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Search & Replace Panel */}
            <div className="mb-4">
              <button
                onClick={() => setShowSearchPanel(!showSearchPanel)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
                  showSearchPanel ? 'bg-orange-500 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                <Search className="w-4 h-4" />
                Search & Replace
              </button>

              {showSearchPanel && (
                <div className="mt-3 p-4 bg-slate-700/30 rounded-xl">
                  <div className="flex flex-col sm:flex-row gap-3 mb-3">
                    <div className="flex-1 min-w-0 sm:min-w-[200px]">
                      <label className="text-xs text-slate-400 mb-1 block">Search</label>
                      <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && performSearch()}
                        placeholder="Search text..."
                        className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-400"
                      />
                    </div>
                    <div className="flex-1 min-w-0 sm:min-w-[200px]">
                      <label className="text-xs text-slate-400 mb-1 block">Replace with</label>
                      <input
                        type="text"
                        value={replaceText}
                        onChange={(e) => setReplaceText(e.target.value)}
                        placeholder="Replacement text..."
                        className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-400"
                      />
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <button
                      onClick={performSearch}
                      className="flex items-center gap-2 px-3 py-2 bg-blue-500 hover:bg-blue-600 rounded-lg text-white transition-colors"
                    >
                      <Search className="w-4 h-4" />
                      Find
                    </button>
                    {searchResults.length > 0 && (
                      <>
                        <span className="text-sm text-slate-400">
                          {searchResults.length} match{searchResults.length !== 1 ? 'es' : ''} found
                        </span>
                        <button
                          onClick={replaceAll}
                          className="flex items-center gap-2 px-3 py-2 bg-orange-500 hover:bg-orange-600 rounded-lg text-white transition-colors"
                        >
                          <Replace className="w-4 h-4" />
                          Replace All
                        </button>
                      </>
                    )}
                    {searchQuery && (
                      <button
                        onClick={() => { setSearchQuery(''); setReplaceText(''); setSearchResults([]); }}
                        className="flex items-center gap-1 px-2 py-2 text-slate-400 hover:text-slate-300 transition-colors"
                      >
                        <X className="w-4 h-4" />
                        Clear
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* View Toggles */}
            <div className="flex items-center gap-2 mb-4 flex-wrap">
              <button
                onClick={() => setShowTimestamps(!showTimestamps)}
                className={`flex items-center gap-2 px-3 py-2.5 sm:py-2 rounded-lg transition-colors ${
                  showTimestamps ? 'bg-blue-500 text-white' : 'bg-slate-700 text-slate-300'
                }`}
              >
                <Clock className="w-4 h-4" />
                Timestamps
              </button>
              {speakers.length > 0 && (
                <button
                  onClick={() => setShowSpeakers(!showSpeakers)}
                  className={`flex items-center gap-2 px-3 py-2.5 sm:py-2 rounded-lg transition-colors ${
                    showSpeakers ? 'bg-purple-500 text-white' : 'bg-slate-700 text-slate-300'
                  }`}
                >
                  <Users className="w-4 h-4" />
                  Speakers
                </button>
              )}
            </div>

            {/* Transcription Text */}
            <div className="bg-slate-900/50 rounded-xl p-3 sm:p-4 max-h-[70vh] sm:max-h-[32rem] overflow-y-auto">
              {(showTimestamps || showSpeakers) && result.segments ? (
                <div className="space-y-3">
                  {result.segments.map((segment, index) => {
                    const isCurrentSegment = index === currentSegmentIndex;
                    const isEdited = editedSegments[index] !== undefined;

                    return (
                      <div
                        key={index}
                        ref={el => segmentRefs.current[index] = el}
                        className={`flex flex-col md:flex-row gap-1 md:gap-3 p-2 rounded transition-all ${
                          isCurrentSegment ? 'bg-blue-500/20 border-l-2 border-blue-400' : ''
                        } ${isEdited ? 'bg-yellow-500/10' : ''}`}
                      >
                        {(showTimestamps || (showSpeakers && segment.speaker)) && (
                          <div className="flex items-center gap-2 md:contents">
                            {showTimestamps && (
                              <button
                                onClick={() => seekToTime(segment.start)}
                                className="text-blue-400 hover:text-blue-300 font-mono text-sm whitespace-nowrap pt-1 cursor-pointer transition-colors"
                              >
                                [{formatTime(segment.start)}]
                              </button>
                            )}
                            {showSpeakers && segment.speaker && (
                              <span className="text-purple-400 font-medium text-sm whitespace-nowrap pt-1">
                                {segment.speaker}:
                              </span>
                            )}
                          </div>
                        )}
                        {isEditing ? (
                          <input
                            type="text"
                            value={editedSegments[index] !== undefined ? editedSegments[index] : segment.text}
                            onChange={(e) => handleEditSegment(index, e.target.value)}
                            className="flex-1 min-w-[60%] sm:min-w-0 bg-slate-700 text-slate-200 px-2 py-1 rounded border border-slate-600 focus:outline-none focus:border-blue-400"
                          />
                        ) : (
                          <p className={`text-slate-200 leading-relaxed flex-1 min-w-[60%] sm:min-w-0 ${searchResults.includes(index) ? 'bg-yellow-500/10 rounded px-1' : ''}`}>
                            {highlightText(editedSegments[index] !== undefined ? editedSegments[index] : segment.text, index)}
                            {searchResults.includes(index) && replaceText && (
                              <button
                                onClick={() => replaceInSegment(index)}
                                className="ml-2 text-xs px-2 py-0.5 bg-orange-500 hover:bg-orange-600 rounded text-white transition-colors"
                              >
                                Replace
                              </button>
                            )}
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-slate-200 leading-relaxed whitespace-pre-wrap">
                  {result.result}
                </p>
              )}
            </div>

            {/* New Transcription Button */}
            <button
              onClick={clearSelection}
              className="w-full mt-6 py-3 rounded-lg font-medium bg-slate-700 hover:bg-slate-600 transition-colors"
            >
              Start New Transcription
            </button>
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
