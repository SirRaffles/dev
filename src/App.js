import React, { useState, useRef, useEffect } from 'react';
import { Upload, Link, Loader2, CheckCircle, AlertCircle, Image, FileText } from 'lucide-react';

// Components
import Header from './components/Header';
import FileInput from './components/FileInput';
import YouTubeInput from './components/YouTubeInput';
import SettingsPanel from './components/SettingsPanel';
import ProgressBar from './components/ProgressBar';
import AudioPlayer from './components/AudioPlayer';
import TranscriptView from './components/TranscriptView';
import DocumentView from './components/DocumentView';
import VisualElementsPanel from './components/VisualElementsPanel';
import ExportMenu from './components/ExportMenu';

// Hooks
import useTranscription from './hooks/useTranscription';
import useMultiModal from './hooks/useMultiModal';

// Utils
import { API_URL, isDocumentFile, isMediaFile, getSourceType } from './utils/api';

// Input mode tabs
const InputMode = {
  FILE: 'file',
  YOUTUBE: 'youtube',
};

// View modes for results
const ViewMode = {
  TRANSCRIPT: 'transcript',
  DOCUMENT: 'document',
  VISUAL: 'visual',
};

function App() {
  // Input state
  const [inputMode, setInputMode] = useState(InputMode.FILE);
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [file, setFile] = useState(null);
  const [files, setFiles] = useState([]);

  // Settings state
  const [settings, setSettings] = useState({
    modelSize: 'large-v3-turbo',
    language: 'auto',
    translateToEnglish: false,
    enableDiarization: true,
    numSpeakers: '',
    wordTimestamps: false,
    enableNoiseReduction: false,
    speedPriority: false,
    engine: 'whisper',
    contextTerms: '',
  });

  // Track Voxtral availability from health endpoint
  const [voxtralAvailable, setVoxtralAvailable] = useState(false);

  // Result view state
  const [viewMode, setViewMode] = useState(ViewMode.TRANSCRIPT);

  // Audio playback
  const [audioUrl, setAudioUrl] = useState(null);
  const [currentTime, setCurrentTime] = useState(0);
  const audioRef = useRef(null);

  // Hooks
  const transcription = useTranscription();
  const multiModal = useMultiModal();

  // Check Voxtral availability on mount
  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then(res => res.json())
      .then(data => {
        if (data.voxtral_available) {
          setVoxtralAvailable(true);
        }
      })
      .catch(() => {});
  }, []);

  // Determine which processing mode to use based on file
  const isDocumentMode = file && isDocumentFile(file.name);
  const activeResult = isDocumentMode ? multiModal.result : transcription.result;
  const activeError = isDocumentMode ? multiModal.error : transcription.error;
  const isProcessing = isDocumentMode ? multiModal.isProcessing : transcription.isTranscribing;
  const activeProgress = isDocumentMode ? multiModal.progress : transcription.progress;
  const activeProgressMessage = isDocumentMode ? multiModal.progressMessage : transcription.progressMessage;
  const activeJobId = isDocumentMode ? multiModal.jobId : transcription.jobId;
  const sourceType = file ? getSourceType(file.name) : null;

  // Handle file selection
  const handleFileSelect = (selectedFile) => {
    setFile(selectedFile);
    setFiles([]);

    // Create audio URL for media files (revoke previous to prevent memory leak)
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    if (selectedFile && isMediaFile(selectedFile.name)) {
      const url = URL.createObjectURL(selectedFile);
      setAudioUrl(url);
    } else {
      setAudioUrl(null);
    }

    // Reset results
    transcription.reset();
    multiModal.reset();
  };

  // Handle multiple files selection
  const handleFilesSelect = (selectedFiles) => {
    setFiles(selectedFiles);
    setFile(null);
    setAudioUrl(null);
    transcription.reset();
    multiModal.reset();
  };

  // Clear selection
  const clearSelection = () => {
    setFile(null);
    setFiles([]);
    setYoutubeUrl('');
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
      setAudioUrl(null);
    }
    setCurrentTime(0);
    transcription.reset();
    multiModal.reset();
    setViewMode(ViewMode.TRANSCRIPT);
  };

  // Cleanup audio URL on unmount
  useEffect(() => {
    return () => {
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }
    };
  }, [audioUrl]);

  // Start processing
  const startProcessing = async () => {
    const options = {
      language: settings.language,
      enableDiarization: settings.enableDiarization,
      enableNoiseReduction: settings.enableNoiseReduction,
      modelSize: settings.modelSize,
      wordTimestamps: settings.wordTimestamps,
      numSpeakers: settings.numSpeakers,
      translateToEnglish: settings.translateToEnglish,
      speedPriority: settings.speedPriority,
      engine: settings.engine,
      contextTerms: settings.contextTerms,
    };

    // Batch mode
    if (files.length > 1) {
      await transcription.transcribeBatch(files, options);
      return;
    }

    // Document mode
    if (isDocumentMode) {
      await multiModal.processDocument(file);
      return;
    }

    // Single file transcription
    if (inputMode === InputMode.FILE && file) {
      await transcription.transcribeFile(file, options);
    } else if (inputMode === InputMode.YOUTUBE && youtubeUrl.trim()) {
      await transcription.transcribeYouTube(youtubeUrl, options);
    }
  };

  // Handle seek from transcript
  const handleSeekToTime = (time) => {
    if (audioRef.current) {
      audioRef.current.seekToTime(time);
    }
  };

  // Handle time update from audio player
  const handleTimeUpdate = (time) => {
    setCurrentTime(time);
  };

  // Check if we can start
  const canStart = (inputMode === InputMode.FILE && (file || files.length > 0)) ||
                   (inputMode === InputMode.YOUTUBE && youtubeUrl.trim());

  // Determine available view modes based on result
  const getAvailableViewModes = () => {
    if (!activeResult) return [];

    if (isDocumentMode) {
      const modes = [ViewMode.DOCUMENT];
      if (activeResult.visual_elements?.length > 0) {
        modes.push(ViewMode.VISUAL);
      }
      return modes;
    }

    // Audio/Video mode
    const modes = [ViewMode.TRANSCRIPT];
    if (activeResult.visual_elements?.length > 0) {
      modes.push(ViewMode.VISUAL);
    }
    return modes;
  };

  const availableViewModes = getAvailableViewModes();

  // Set default view mode when result arrives
  useEffect(() => {
    if (activeResult) {
      if (isDocumentMode) {
        setViewMode(ViewMode.DOCUMENT);
      } else {
        setViewMode(ViewMode.TRANSCRIPT);
      }
    }
  }, [activeResult, isDocumentMode]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
      <div className="max-w-4xl mx-auto px-4 py-8">
        <Header />

        {/* Input Section */}
        <div className="bg-slate-800/50 backdrop-blur rounded-2xl p-6 mb-8 border border-slate-700">
          {/* Mode Tabs */}
          <div className="flex gap-2 mb-6">
            <button
              onClick={() => setInputMode(InputMode.FILE)}
              disabled={isProcessing}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                inputMode === InputMode.FILE
                  ? 'bg-blue-500 text-white'
                  : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
              } disabled:opacity-50`}
            >
              <Upload className="w-4 h-4" />
              Upload File
            </button>
            <button
              onClick={() => setInputMode(InputMode.YOUTUBE)}
              disabled={isProcessing}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                inputMode === InputMode.YOUTUBE
                  ? 'bg-blue-500 text-white'
                  : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
              } disabled:opacity-50`}
            >
              <Link className="w-4 h-4" />
              YouTube URL
            </button>
          </div>

          {/* File Input */}
          {inputMode === InputMode.FILE && (
            <FileInput
              file={file}
              files={files}
              onFileSelect={handleFileSelect}
              onFilesSelect={handleFilesSelect}
              onClear={clearSelection}
              disabled={isProcessing}
              showDocumentSupport={true}
            />
          )}

          {/* YouTube Input */}
          {inputMode === InputMode.YOUTUBE && (
            <YouTubeInput
              url={youtubeUrl}
              onUrlChange={(url) => {
                setYoutubeUrl(url);
                transcription.reset();
              }}
              onClear={clearSelection}
              disabled={isProcessing}
            />
          )}

          {/* Settings */}
          <SettingsPanel
            settings={settings}
            onSettingsChange={setSettings}
            showForDocuments={isDocumentMode}
            disabled={isProcessing}
            voxtralAvailable={voxtralAvailable}
          />

          {/* Start Button */}
          <button
            onClick={startProcessing}
            disabled={!canStart || isProcessing}
            className={`w-full mt-6 py-4 rounded-xl font-semibold text-lg transition-all ${
              canStart && !isProcessing
                ? 'bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 text-white'
                : 'bg-slate-700 text-slate-400 cursor-not-allowed'
            }`}
          >
            {isProcessing ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 className="w-5 h-5 animate-spin" />
                {isDocumentMode ? 'Processing...' : 'Transcribing...'} {activeProgress}%
              </span>
            ) : isDocumentMode ? (
              'Process Document'
            ) : files.length > 1 ? (
              `Transcribe ${files.length} Files`
            ) : (
              'Start Transcription'
            )}
          </button>
        </div>

        {/* Progress Bar */}
        {isProcessing && (
          <ProgressBar
            progress={activeProgress}
            progressMessage={activeProgressMessage}
            sourceType={sourceType}
            batchProgress={transcription.batchProgress}
          />
        )}

        {/* Error Display */}
        {activeError && (
          <div className="bg-red-500/10 border border-red-500/50 rounded-2xl p-6 mb-8">
            <div className="flex items-center gap-3 text-red-400">
              <AlertCircle className="w-5 h-5" />
              <span className="font-medium">Error</span>
            </div>
            <p className="mt-2 text-red-300">{activeError}</p>
          </div>
        )}

        {/* Results */}
        {activeResult && (
          <div className="bg-slate-800/50 backdrop-blur rounded-2xl p-6 border border-slate-700">
            {/* Results Header */}
            <div className="flex items-center justify-between mb-6 flex-wrap gap-4">
              <div className="flex items-center gap-3">
                <CheckCircle className="w-6 h-6 text-green-400" />
                <h2 className="text-xl font-semibold">
                  {isDocumentMode ? 'Document Processed' : 'Transcription Complete'}
                </h2>
              </div>
              <ExportMenu
                jobId={activeJobId}
                result={activeResult}
                isMultiModal={isDocumentMode}
                filename={file?.name?.replace(/\.[^/.]+$/, '') || 'transcript'}
              />
            </div>

            {/* View Mode Tabs */}
            {availableViewModes.length > 1 && (
              <div className="flex gap-2 mb-6">
                {availableViewModes.includes(ViewMode.TRANSCRIPT) && (
                  <button
                    onClick={() => setViewMode(ViewMode.TRANSCRIPT)}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                      viewMode === ViewMode.TRANSCRIPT
                        ? 'bg-blue-500 text-white'
                        : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                    }`}
                  >
                    <FileText className="w-4 h-4" />
                    Transcript
                  </button>
                )}
                {availableViewModes.includes(ViewMode.DOCUMENT) && (
                  <button
                    onClick={() => setViewMode(ViewMode.DOCUMENT)}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                      viewMode === ViewMode.DOCUMENT
                        ? 'bg-blue-500 text-white'
                        : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                    }`}
                  >
                    <FileText className="w-4 h-4" />
                    Document
                  </button>
                )}
                {availableViewModes.includes(ViewMode.VISUAL) && (
                  <button
                    onClick={() => setViewMode(ViewMode.VISUAL)}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                      viewMode === ViewMode.VISUAL
                        ? 'bg-purple-500 text-white'
                        : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                    }`}
                  >
                    <Image className="w-4 h-4" />
                    Visual Content
                  </button>
                )}
              </div>
            )}

            {/* Audio Player (only for audio/video) */}
            {audioUrl && !isDocumentMode && (
              <AudioPlayer
                ref={audioRef}
                audioUrl={audioUrl}
                onTimeUpdate={handleTimeUpdate}
                className="mb-6"
              />
            )}

            {/* Content Views */}
            {viewMode === ViewMode.TRANSCRIPT && activeResult.segments && (
              <TranscriptView
                result={activeResult}
                jobId={activeJobId}
                onResultUpdate={isDocumentMode ? multiModal.updateResult : transcription.updateResult}
                currentTime={currentTime}
                onSeekToTime={handleSeekToTime}
              />
            )}

            {viewMode === ViewMode.DOCUMENT && (
              <DocumentView
                documentMarkdown={activeResult.document_markdown}
                documentSections={activeResult.document_sections}
                speakerNotes={activeResult.speaker_notes}
                sourceType={sourceType}
                pageCount={activeResult.page_count}
                slideCount={activeResult.slide_count}
              />
            )}

            {viewMode === ViewMode.VISUAL && (
              <VisualElementsPanel
                visualElements={activeResult.visual_elements || []}
              />
            )}

            {/* New Button */}
            <button
              onClick={clearSelection}
              className="w-full mt-6 py-3 rounded-lg font-medium bg-slate-700 hover:bg-slate-600 transition-colors"
            >
              {isDocumentMode ? 'Process Another Document' : 'Start New Transcription'}
            </button>
          </div>
        )}

        {/* Footer */}
        <footer className="text-center mt-12 text-slate-500 text-sm">
          <p>Powered by MLX-Whisper with GPU acceleration</p>
          <p className="mt-1">Optimized for Apple Silicon (M1/M2/M3)</p>
        </footer>
      </div>
    </div>
  );
}

export default App;
