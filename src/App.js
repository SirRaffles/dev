import React, { useState, useEffect, useMemo, lazy, Suspense } from 'react';
import { Upload, Link, Loader2, CheckCircle, AlertCircle, Image, FileText } from 'lucide-react';

// Components (eagerly loaded - needed immediately)
import Header from './components/Header';
import FileInput from './components/FileInput';
import YouTubeInput from './components/YouTubeInput';
import SettingsPanel from './components/SettingsPanel';
import ProgressBar from './components/ProgressBar';
import ExportMenu from './components/ExportMenu';

// Components (lazily loaded - only needed when results are shown)
const AudioPlayer = lazy(() => import('./components/AudioPlayer'));
const TranscriptView = lazy(() => import('./components/TranscriptView'));
const DocumentView = lazy(() => import('./components/DocumentView'));
const VisualElementsPanel = lazy(() => import('./components/VisualElementsPanel'));

// Hooks
import useProcessingState from './hooks/useProcessingState';
import useAudioPlayback from './hooks/useAudioPlayback';

// Utils
import { API_URL } from './utils/api';

const InputMode = { FILE: 'file', YOUTUBE: 'youtube' };
const ViewMode = { TRANSCRIPT: 'transcript', DOCUMENT: 'document', VISUAL: 'visual' };

function App() {
  // Input state
  const [inputMode, setInputMode] = useState(InputMode.FILE);
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [file, setFile] = useState(null);
  const [files, setFiles] = useState([]);

  // Settings
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

  const [voxtralAvailable, setVoxtralAvailable] = useState(false);
  const [viewMode, setViewMode] = useState(ViewMode.TRANSCRIPT);

  // Custom hooks
  const { transcription, multiModal, isDocumentMode, sourceType, active, resetAll, updateResult } =
    useProcessingState(file);
  const { audioUrl, currentTime, audioRef, setFileAudio, clearAudio, seekToTime, handleTimeUpdate } =
    useAudioPlayback();

  // Check Voxtral availability on mount
  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then(res => res.json())
      .then(data => { if (data.voxtral_available) setVoxtralAvailable(true); })
      .catch(() => {});
  }, []);

  // Handlers
  const handleFileSelect = (selectedFile) => {
    setFile(selectedFile);
    setFiles([]);
    setFileAudio(selectedFile);
    resetAll();
  };

  const handleFilesSelect = (selectedFiles) => {
    setFiles(selectedFiles);
    setFile(null);
    clearAudio();
    resetAll();
  };

  const clearSelection = () => {
    setFile(null);
    setFiles([]);
    setYoutubeUrl('');
    clearAudio();
    resetAll();
    setViewMode(ViewMode.TRANSCRIPT);
  };

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

    if (files.length > 1) {
      await transcription.transcribeBatch(files, options);
    } else if (isDocumentMode) {
      await multiModal.processDocument(file);
    } else if (inputMode === InputMode.FILE && file) {
      await transcription.transcribeFile(file, options);
    } else if (inputMode === InputMode.YOUTUBE && youtubeUrl.trim()) {
      await transcription.transcribeYouTube(youtubeUrl, options);
    }
  };

  const canStart = (inputMode === InputMode.FILE && (file || files.length > 0)) ||
                   (inputMode === InputMode.YOUTUBE && youtubeUrl.trim());

  // Available view modes based on result type
  const availableViewModes = useMemo(() => {
    if (!active.result) return [];
    if (isDocumentMode) {
      const modes = [ViewMode.DOCUMENT];
      if (active.result.visual_elements?.length > 0) modes.push(ViewMode.VISUAL);
      return modes;
    }
    const modes = [ViewMode.TRANSCRIPT];
    if (active.result.visual_elements?.length > 0) modes.push(ViewMode.VISUAL);
    return modes;
  }, [active.result, isDocumentMode]);

  // Set default view mode when result arrives
  useEffect(() => {
    if (active.result) {
      setViewMode(isDocumentMode ? ViewMode.DOCUMENT : ViewMode.TRANSCRIPT);
    }
  }, [active.result, isDocumentMode]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
      <div className="max-w-4xl mx-auto px-4 py-8">
        <Header />

        {/* Input Section */}
        <div className="bg-slate-800/50 backdrop-blur rounded-2xl p-6 mb-8 border border-slate-700">
          {/* Mode Tabs */}
          <div className="flex gap-2 mb-6" role="tablist" aria-label="Input source">
            <button
              role="tab"
              aria-selected={inputMode === InputMode.FILE}
              onClick={() => setInputMode(InputMode.FILE)}
              disabled={active.isProcessing}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                inputMode === InputMode.FILE
                  ? 'bg-blue-500 text-white'
                  : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
              } disabled:opacity-50`}
            >
              <Upload className="w-4 h-4" aria-hidden="true" />
              Upload File
            </button>
            <button
              role="tab"
              aria-selected={inputMode === InputMode.YOUTUBE}
              onClick={() => setInputMode(InputMode.YOUTUBE)}
              disabled={active.isProcessing}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                inputMode === InputMode.YOUTUBE
                  ? 'bg-blue-500 text-white'
                  : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
              } disabled:opacity-50`}
            >
              <Link className="w-4 h-4" aria-hidden="true" />
              YouTube URL
            </button>
          </div>

          {inputMode === InputMode.FILE && (
            <FileInput
              file={file}
              files={files}
              onFileSelect={handleFileSelect}
              onFilesSelect={handleFilesSelect}
              onClear={clearSelection}
              disabled={active.isProcessing}
              showDocumentSupport={true}
            />
          )}

          {inputMode === InputMode.YOUTUBE && (
            <YouTubeInput
              url={youtubeUrl}
              onUrlChange={(url) => { setYoutubeUrl(url); transcription.reset(); }}
              onClear={clearSelection}
              disabled={active.isProcessing}
            />
          )}

          <SettingsPanel
            settings={settings}
            onSettingsChange={setSettings}
            showForDocuments={isDocumentMode}
            disabled={active.isProcessing}
            voxtralAvailable={voxtralAvailable}
          />

          {/* Start Button */}
          <button
            onClick={startProcessing}
            disabled={!canStart || active.isProcessing}
            className={`w-full mt-6 py-4 rounded-xl font-semibold text-lg transition-all ${
              canStart && !active.isProcessing
                ? 'bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 text-white'
                : 'bg-slate-700 text-slate-400 cursor-not-allowed'
            }`}
          >
            {active.isProcessing ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 className="w-5 h-5 animate-spin" />
                {isDocumentMode ? 'Processing...' : 'Transcribing...'} {active.progress}%
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
        {active.isProcessing && (
          <ProgressBar
            progress={active.progress}
            progressMessage={active.progressMessage}
            sourceType={sourceType}
            batchProgress={transcription.batchProgress}
          />
        )}

        {/* Error Display */}
        {active.error && (
          <div role="alert" className="bg-red-500/10 border border-red-500/50 rounded-2xl p-6 mb-8">
            <div className="flex items-center gap-3 text-red-400">
              <AlertCircle className="w-5 h-5" aria-hidden="true" />
              <span className="font-medium">Error</span>
            </div>
            <p className="mt-2 text-red-300">{active.error}</p>
          </div>
        )}

        {/* Results */}
        {active.result && (
          <div className="bg-slate-800/50 backdrop-blur rounded-2xl p-6 border border-slate-700">
            <div className="flex items-center justify-between mb-6 flex-wrap gap-4">
              <div className="flex items-center gap-3">
                <CheckCircle className="w-6 h-6 text-green-400" />
                <h2 className="text-xl font-semibold">
                  {isDocumentMode ? 'Document Processed' : 'Transcription Complete'}
                </h2>
              </div>
              <ExportMenu
                jobId={active.jobId}
                result={active.result}
                isMultiModal={isDocumentMode}
                filename={file?.name?.replace(/\.[^/.]+$/, '') || 'transcript'}
              />
            </div>

            {/* View Mode Tabs */}
            {availableViewModes.length > 1 && (
              <div className="flex gap-2 mb-6" role="tablist" aria-label="Result view">
                {availableViewModes.includes(ViewMode.TRANSCRIPT) && (
                  <button
                    role="tab"
                    aria-selected={viewMode === ViewMode.TRANSCRIPT}
                    onClick={() => setViewMode(ViewMode.TRANSCRIPT)}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                      viewMode === ViewMode.TRANSCRIPT
                        ? 'bg-blue-500 text-white'
                        : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                    }`}
                  >
                    <FileText className="w-4 h-4" aria-hidden="true" />
                    Transcript
                  </button>
                )}
                {availableViewModes.includes(ViewMode.DOCUMENT) && (
                  <button
                    role="tab"
                    aria-selected={viewMode === ViewMode.DOCUMENT}
                    onClick={() => setViewMode(ViewMode.DOCUMENT)}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                      viewMode === ViewMode.DOCUMENT
                        ? 'bg-blue-500 text-white'
                        : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                    }`}
                  >
                    <FileText className="w-4 h-4" aria-hidden="true" />
                    Document
                  </button>
                )}
                {availableViewModes.includes(ViewMode.VISUAL) && (
                  <button
                    role="tab"
                    aria-selected={viewMode === ViewMode.VISUAL}
                    onClick={() => setViewMode(ViewMode.VISUAL)}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                      viewMode === ViewMode.VISUAL
                        ? 'bg-purple-500 text-white'
                        : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                    }`}
                  >
                    <Image className="w-4 h-4" aria-hidden="true" />
                    Visual Content
                  </button>
                )}
              </div>
            )}

            <Suspense fallback={<div className="text-center py-4 text-slate-400"><Loader2 className="w-5 h-5 animate-spin mx-auto" /></div>}>
              {audioUrl && !isDocumentMode && (
                <AudioPlayer
                  ref={audioRef}
                  audioUrl={audioUrl}
                  onTimeUpdate={handleTimeUpdate}
                  className="mb-6"
                />
              )}

              {viewMode === ViewMode.TRANSCRIPT && active.result.segments && (
                <TranscriptView
                  result={active.result}
                  jobId={active.jobId}
                  onResultUpdate={updateResult}
                  currentTime={currentTime}
                  onSeekToTime={seekToTime}
                />
              )}

              {viewMode === ViewMode.DOCUMENT && (
                <DocumentView
                  documentMarkdown={active.result.document_markdown}
                  documentSections={active.result.document_sections}
                  speakerNotes={active.result.speaker_notes}
                  sourceType={sourceType}
                  pageCount={active.result.page_count}
                  slideCount={active.result.slide_count}
                />
              )}

              {viewMode === ViewMode.VISUAL && (
                <VisualElementsPanel
                  visualElements={active.result.visual_elements || []}
                />
              )}
            </Suspense>

            <button
              onClick={clearSelection}
              className="w-full mt-6 py-3 rounded-lg font-medium bg-slate-700 hover:bg-slate-600 transition-colors"
            >
              {isDocumentMode ? 'Process Another Document' : 'Start New Transcription'}
            </button>
          </div>
        )}

        <footer className="text-center mt-12 text-slate-500 text-sm">
          <p>Powered by MLX-Whisper with GPU acceleration</p>
          <p className="mt-1">Optimized for Apple Silicon (M1/M2/M3)</p>
        </footer>
      </div>
    </div>
  );
}

export default App;
