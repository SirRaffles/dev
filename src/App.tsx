import React, { useState, useEffect, useMemo, useRef, useCallback, lazy, Suspense } from 'react';
import { Upload, Link, Loader2, CheckCircle, AlertCircle, Image, FileText, X, RefreshCw, Moon, Sun } from 'lucide-react';

// Components (eagerly loaded - needed immediately)
import Header from './components/Header';
import Navigation, { NavTab } from './components/Navigation';
import FileInput from './components/FileInput';
import YouTubeInput from './components/YouTubeInput';
import SettingsPanel from './components/SettingsPanel';
import ProgressBar from './components/ProgressBar';
import ExportMenu from './components/ExportMenu';
import JobHistory from './components/JobHistory';
import BatchProgress from './components/BatchProgress';
import LearningToast from './components/LearningToast';

// Hooks
import useProcessingState from './hooks/useProcessingState';
import useAudioPlayback from './hooks/useAudioPlayback';
import useWakeOnLan from './hooks/useWakeOnLan';
import useTheme from './hooks/useTheme';
import useGlobalKeyboard from './hooks/useGlobalKeyboard';
import useTranscriptionSession from './hooks/useTranscriptionSession';
import type { TranscriptionSessionSettings } from './hooks/useTranscriptionSession';

// Utils
import { API_URL, JobStatus, cancelJob } from './utils/api';

// Components (lazily loaded - only needed when results are shown)
const AudioPlayer = lazy(() => import('./components/AudioPlayer'));
const TranscriptView = lazy(() => import('./components/TranscriptView'));
const DocumentView = lazy(() => import('./components/DocumentView'));
const VisualElementsPanel = lazy(() => import('./components/VisualElementsPanel'));

// Call intelligence views (lazily loaded - only when navigating to those tabs)
const RecordingsView = lazy(() => import('./components/RecordingsView'));
const CallsView = lazy(() => import('./components/CallsView'));
const SpeakersView = lazy(() => import('./components/SpeakersView'));
const ContextBrowser = lazy(() => import('./components/ContextBrowser'));
const ActivityTimeline = lazy(() => import('./components/ActivityTimeline'));

const InputMode = { FILE: 'file', YOUTUBE: 'youtube' } as const;
const ViewMode = { TRANSCRIPT: 'transcript', DOCUMENT: 'document', VISUAL: 'visual' } as const;

interface WakeProgressBarProps {
  startTime: number;
}

function WakeProgressBar({ startTime }: WakeProgressBarProps) {
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const interval = setInterval(() => {
      const elapsed = (Date.now() - startTime) / 1000;
      setWidth(Math.min(100, (elapsed / 90) * 100));
    }, 1000);
    return () => clearInterval(interval);
  }, [startTime]);
  return (
    <div
      className="bg-amber-400 h-full rounded-full transition-all duration-1000"
      style={{ width: `${width}%` }}
    />
  );
}

function App() {
  // Navigation state
  const [activeTab, setActiveTab] = useState<NavTab>('transcribe');

  // Input state
  const [inputMode, setInputMode] = useState<string>(InputMode.FILE);
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [files, setFiles] = useState<File[]>([]);

  // Settings
  const [settings, setSettings] = useState<Record<string, any>>({
    language: 'auto',
    translateToEnglish: false,
    enableDiarization: true,
    numSpeakers: '',
    enableNoiseReduction: false,
    engine: 'auto-best',
    contextPath: '',
    speakerIds: [] as string[],
    refinementMode: 'auto',
  });

  const [viewMode, setViewMode] = useState<string>(ViewMode.TRANSCRIPT);
  const [dismissedError, setDismissedError] = useState(false);
  const [selectedBatchIndex, setSelectedBatchIndex] = useState(0);

  // Refs for tab keyboard navigation
  const inputTabsRef = useRef<HTMLDivElement>(null);
  const viewTabsRef = useRef<HTMLDivElement>(null);

  // Custom hooks
  const { macState, setMacState, wakeStartTime, detectProxy, triggerWake, queueSubmit, hasPendingSubmit } =
    useWakeOnLan({});

  const { transcription, multiModal, isDocumentMode, sourceType, active, resetAll, updateResult } =
    useProcessingState(file);
  const { audioUrl, currentTime, audioRef, setFileAudio, clearAudio, seekToTime, handleTimeUpdate } =
    useAudioPlayback();
  const { isDark, toggleTheme } = useTheme();

  useGlobalKeyboard({
    audioRef,
    enabled: !!audioUrl && !!active.result && !active.isProcessing,
  });

  // Reset dismissed error when a new error occurs
  useEffect(() => {
    if (active.error) setDismissedError(false);
  }, [active.error]);

  // Keyboard navigation for tablists
  const handleTabKeyDown = useCallback((e: React.KeyboardEvent, tablistRef: React.RefObject<HTMLDivElement | null>) => {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    if (!tablistRef.current) return;
    const tabs = Array.from(tablistRef.current.querySelectorAll('[role="tab"]')) as HTMLElement[];
    const currentIndex = tabs.indexOf(document.activeElement as HTMLElement);
    if (currentIndex === -1) return;
    e.preventDefault();
    const nextIndex = e.key === 'ArrowRight'
      ? (currentIndex + 1) % tabs.length
      : (currentIndex - 1 + tabs.length) % tabs.length;
    tabs[nextIndex].focus();
    tabs[nextIndex].click();
  }, []);

  // Detect wake-proxy on mount. The proxy (if present) drives macState
  // inside useWakeOnLan; direct connections leave macState null and the UI
  // operates as a plain local app. No engine-availability ping needed —
  // the Quality dial owns engine selection now.
  useEffect(() => {
    detectProxy();
  }, [detectProxy]);

  // Handlers
  const handleFileSelect = (selectedFile: File) => {
    setFile(selectedFile);
    setFiles([]);
    setFileAudio(selectedFile);
    resetAll();
  };

  const handleFilesSelect = (selectedFiles: File[]) => {
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

  const loadHistoryJob = async (jobId: string) => {
    try {
      const resp = await fetch(`${API_URL}/job/${jobId}`);
      if (!resp.ok) return;
      const data = await resp.json();
      if (data && data.status === 'completed') {
        clearSelection();
        transcription.updateResult(data);
        setViewMode(ViewMode.TRANSCRIPT);
      }
    } catch (err) {
      console.error('Failed to load job:', err);
    }
  };

  const { canStart, startProcessing } = useTranscriptionSession({
    inputMode,
    file,
    files,
    youtubeUrl,
    // App holds settings loosely (Record) to bridge SettingsPanel's `Settings`
    // type and the session hook's stricter shape; they share the same 9 keys.
    settings: settings as TranscriptionSessionSettings,
    isDocumentMode: Boolean(isDocumentMode),
    macState,
    triggerWake,
    queueSubmit,
    hasPendingSubmit,
    transcription,
    multiModal,
  });

  // Available view modes based on result type
  const availableViewModes = useMemo(() => {
    if (!active.result) return [] as string[];
    const modes: string[] = [isDocumentMode ? ViewMode.DOCUMENT : ViewMode.TRANSCRIPT];
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
    <div className="min-h-screen bg-gradient-to-br from-slate-100 via-slate-50 to-slate-100 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900 text-slate-900 dark:text-white">
      <div className={`${viewMode === ViewMode.VISUAL ? 'max-w-6xl' : 'max-w-4xl'} mx-auto px-3 sm:px-4 py-4 sm:py-8 transition-all`}>
        <div className="relative">
          <Header />
          <button
            onClick={toggleTheme}
            className="absolute top-0 right-0 p-2 rounded-lg text-slate-500 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
            aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {isDark ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
          </button>
        </div>

        <Navigation activeTab={activeTab} onTabChange={setActiveTab} />

        {/* Call Intelligence Views */}
        {activeTab !== 'transcribe' && (
          <Suspense fallback={
            <div className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-6 border border-slate-200 dark:border-slate-700 shadow-sm dark:shadow-none">
              <div className="space-y-4 py-4">
                <div className="h-4 w-3/4 bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
                <div className="h-4 w-full bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
                <div className="h-4 w-5/6 bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
              </div>
            </div>
          }>
            {activeTab === 'recordings' && <RecordingsView />}
            {activeTab === 'calls' && <CallsView />}
            {activeTab === 'speakers' && <SpeakersView />}
            {activeTab === 'contexts' && <ContextBrowser />}
            {activeTab === 'activity' && <ActivityTimeline />}
          </Suspense>
        )}

        {activeTab === 'transcribe' && (<>
        {/* Mac Sleeping Banner */}
        {macState === 'sleeping' && (
          <div className="bg-indigo-500/10 border border-indigo-500/50 rounded-xl p-4 mb-6 flex items-center gap-3">
            <Moon className="w-5 h-5 text-indigo-400 flex-shrink-0" aria-hidden="true" />
            <span className="text-indigo-300 text-sm">
              Mac is sleeping — it will wake automatically when you start a transcription.
            </span>
          </div>
        )}

        {/* Mac Waking Banner */}
        {macState === 'waking' && (
          <div className="bg-amber-500/10 border border-amber-500/50 rounded-xl p-4 mb-6">
            <div className="flex items-center gap-3">
              <Loader2 className="w-5 h-5 text-amber-400 animate-spin flex-shrink-0" aria-hidden="true" />
              <span className="text-amber-300 text-sm">
                Waking Mac and loading AI models... (~90 seconds)
              </span>
            </div>
            {wakeStartTime && (
              <div className="mt-2 bg-amber-500/20 rounded-full h-1.5 overflow-hidden">
                <WakeProgressBar startTime={wakeStartTime} />
              </div>
            )}
          </div>
        )}

        {/* Input Section */}
        <div className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-4 sm:p-6 mb-8 border border-slate-200 dark:border-slate-700 shadow-sm dark:shadow-none">
          {/* Mode Tabs */}
          <div className="flex flex-wrap gap-2 mb-6" role="tablist" aria-label="Input source" ref={inputTabsRef} onKeyDown={(e) => handleTabKeyDown(e, inputTabsRef)}>
            <button
              id="tab-file"
              role="tab"
              aria-selected={inputMode === InputMode.FILE}
              aria-controls="panel-file"
              tabIndex={inputMode === InputMode.FILE ? 0 : -1}
              onClick={() => setInputMode(InputMode.FILE)}
              disabled={active.isProcessing}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                inputMode === InputMode.FILE
                  ? 'bg-blue-500 text-white'
                  : 'bg-slate-200 text-slate-600 hover:bg-slate-300 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600'
              } disabled:opacity-50`}
            >
              <Upload className="w-4 h-4" aria-hidden="true" />
              Upload File
            </button>
            <button
              id="tab-youtube"
              role="tab"
              aria-selected={inputMode === InputMode.YOUTUBE}
              aria-controls="panel-youtube"
              tabIndex={inputMode === InputMode.YOUTUBE ? 0 : -1}
              onClick={() => setInputMode(InputMode.YOUTUBE)}
              disabled={active.isProcessing}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                inputMode === InputMode.YOUTUBE
                  ? 'bg-blue-500 text-white'
                  : 'bg-slate-200 text-slate-600 hover:bg-slate-300 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600'
              } disabled:opacity-50`}
            >
              <Link className="w-4 h-4" aria-hidden="true" />
              YouTube URL
            </button>
          </div>

          {inputMode === InputMode.FILE && (
            <div role="tabpanel" id="panel-file" aria-labelledby="tab-file">
              <FileInput
                file={file}
                files={files}
                onFileSelect={handleFileSelect}
                onFilesSelect={handleFilesSelect}
                onClear={clearSelection}
                disabled={active.isProcessing}
                showDocumentSupport={true}
              />
            </div>
          )}

          {inputMode === InputMode.YOUTUBE && (
            <div role="tabpanel" id="panel-youtube" aria-labelledby="tab-youtube">
              <YouTubeInput
                url={youtubeUrl}
                onUrlChange={(url) => { setYoutubeUrl(url); transcription.reset(); }}
                onClear={clearSelection}
                disabled={active.isProcessing}
              />
            </div>
          )}

          <SettingsPanel
            settings={settings}
            onSettingsChange={setSettings}
            showForDocuments={isDocumentMode}
            disabled={active.isProcessing}
          />

          {/* Start Button */}
          <button
            onClick={startProcessing}
            disabled={!canStart || active.isProcessing || macState === 'waking'}
            title={
              macState === 'waking' ? 'Mac is waking up...'
              : macState === 'sleeping' ? 'Click to wake Mac and start transcription'
              : !canStart ? 'Select a file or enter a YouTube URL first'
              : active.isProcessing ? 'Processing in progress'
              : undefined
            }
            className={`w-full mt-6 py-4 rounded-xl font-semibold text-lg transition-all ${
              canStart && !active.isProcessing && macState !== 'waking'
                ? macState === 'sleeping'
                  ? 'bg-gradient-to-r from-indigo-500 to-blue-500 hover:from-indigo-600 hover:to-blue-600 text-white'
                  : 'bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 text-white'
                : 'bg-slate-200 text-slate-400 cursor-not-allowed dark:bg-slate-700'
            }`}
          >
            {macState === 'waking' ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 className="w-5 h-5 animate-spin" />
                Waking Mac...
              </span>
            ) : active.isProcessing ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 className="w-5 h-5 animate-spin" />
                {isDocumentMode ? 'Processing...' : 'Transcribing...'} {active.progress}%
              </span>
            ) : macState === 'sleeping' ? (
              <span className="flex items-center justify-center gap-2">
                <Moon className="w-5 h-5" />
                {isDocumentMode ? 'Wake Mac & Process' : 'Wake Mac & Transcribe'}
              </span>
            ) : isDocumentMode ? (
              'Process Document'
            ) : files.length > 1 ? (
              `Transcribe ${files.length} Files`
            ) : (
              'Start Transcription'
            )}
          </button>

          {/* Job History */}
          {!active.isProcessing && !active.result && (
            <JobHistory
              onSelectJob={loadHistoryJob}
              onRetryJob={(newJobId) => transcription.trackJob(newJobId)}
            />
          )}
        </div>

        {/* Progress Bar */}
        <div aria-live="polite" aria-atomic="true">
        {active.isProcessing && (
          <div className="space-y-2">
            <ProgressBar
              progress={active.progress}
              progressMessage={active.progressMessage}
              sourceType={sourceType}
              batchProgress={transcription.batchProgress}
              phase={active.phase}
            />
            {active.jobId && (
              <div className="flex justify-end">
                <button
                  onClick={async () => {
                    if (!active.jobId) return;
                    try { await cancelJob(active.jobId); } catch { /* best-effort */ }
                    resetAll();
                  }}
                  className="inline-flex items-center gap-1 px-3 py-1 text-xs rounded border border-rose-300 dark:border-rose-800 text-rose-700 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-900/20"
                  title="Soft-cancel: frees the UI immediately. The backend executor finishes its current chunk (~30s) before fully releasing. For a hard-stop, restart the backend."
                >
                  <X className="w-3 h-3" />
                  Cancel
                </button>
              </div>
            )}
          </div>
        )}
        </div>

        {/* Batch Progress (shown while batch is active, separate from single-file ProgressBar) */}
        {transcription.batchId && files.length > 1 && (
          <BatchProgress
            batchId={transcription.batchId}
            onSelectJob={loadHistoryJob}
          />
        )}

        {/* Error Display */}
        {active.error && !dismissedError && (
          <div role="alert" className="bg-red-500/10 border border-red-500/50 rounded-2xl p-6 mb-8">
            <div className="flex items-center gap-3 text-red-400">
              <AlertCircle className="w-5 h-5 flex-shrink-0" aria-hidden="true" />
              <span className="font-medium flex-1">Error</span>
              <button
                onClick={() => setDismissedError(true)}
                className="text-red-400 hover:text-red-300 transition-colors"
                aria-label="Dismiss error"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <p className="mt-2 text-red-300">{active.error}</p>
            <button
              onClick={startProcessing}
              disabled={!canStart}
              className="mt-3 flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-red-500/20 text-red-300 hover:bg-red-500/30 transition-colors disabled:opacity-50"
            >
              <RefreshCw className="w-4 h-4" aria-hidden="true" />
              Retry
            </button>
          </div>
        )}

        {/* Results */}
        {active.result && (
          <div className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-4 sm:p-6 border border-slate-200 dark:border-slate-700 shadow-sm dark:shadow-none">
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
              <div className="flex flex-wrap gap-2 mb-6" role="tablist" aria-label="Result view" ref={viewTabsRef} onKeyDown={(e) => handleTabKeyDown(e, viewTabsRef)}>
                {availableViewModes.includes(ViewMode.TRANSCRIPT) && (
                  <button
                    id="tab-transcript"
                    role="tab"
                    aria-selected={viewMode === ViewMode.TRANSCRIPT}
                    aria-controls="panel-transcript"
                    tabIndex={viewMode === ViewMode.TRANSCRIPT ? 0 : -1}
                    onClick={() => setViewMode(ViewMode.TRANSCRIPT)}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                      viewMode === ViewMode.TRANSCRIPT
                        ? 'bg-blue-500 text-white'
                        : 'bg-slate-200 text-slate-600 hover:bg-slate-300 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600'
                    }`}
                  >
                    <FileText className="w-4 h-4" aria-hidden="true" />
                    Transcript
                  </button>
                )}
                {availableViewModes.includes(ViewMode.DOCUMENT) && (
                  <button
                    id="tab-document"
                    role="tab"
                    aria-selected={viewMode === ViewMode.DOCUMENT}
                    aria-controls="panel-document"
                    tabIndex={viewMode === ViewMode.DOCUMENT ? 0 : -1}
                    onClick={() => setViewMode(ViewMode.DOCUMENT)}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                      viewMode === ViewMode.DOCUMENT
                        ? 'bg-blue-500 text-white'
                        : 'bg-slate-200 text-slate-600 hover:bg-slate-300 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600'
                    }`}
                  >
                    <FileText className="w-4 h-4" aria-hidden="true" />
                    Document
                  </button>
                )}
                {availableViewModes.includes(ViewMode.VISUAL) && (
                  <button
                    id="tab-visual"
                    role="tab"
                    aria-selected={viewMode === ViewMode.VISUAL}
                    aria-controls="panel-visual"
                    tabIndex={viewMode === ViewMode.VISUAL ? 0 : -1}
                    onClick={() => setViewMode(ViewMode.VISUAL)}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                      viewMode === ViewMode.VISUAL
                        ? 'bg-purple-500 text-white'
                        : 'bg-slate-200 text-slate-600 hover:bg-slate-300 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600'
                    }`}
                  >
                    <Image className="w-4 h-4" aria-hidden="true" />
                    Visual Content
                  </button>
                )}
              </div>
            )}

            {/* Batch Results Selector */}
            {transcription.batchResults.length > 1 && (
              <div className="flex items-center gap-3 mb-4">
                <label htmlFor="batch-select" className="text-sm text-slate-500 dark:text-slate-400">Batch result:</label>
                <select
                  id="batch-select"
                  value={selectedBatchIndex}
                  onChange={(e) => {
                    const idx = Number(e.target.value);
                    setSelectedBatchIndex(idx);
                    transcription.selectBatchResult(idx);
                  }}
                  className="bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-slate-700 dark:border-slate-600 dark:text-white"
                >
                  {transcription.batchResults.map((br: { job_id: string }, i: number) => (
                    <option key={br.job_id} value={i}>
                      File {i + 1} — {br.job_id.slice(0, 8)}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <Suspense fallback={
              <div className="space-y-4 py-4">
                <div className="h-4 w-3/4 bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
                <div className="h-4 w-full bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
                <div className="h-4 w-5/6 bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
                <div className="h-4 w-2/3 bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
              </div>
            }>
              {audioUrl && !isDocumentMode && (
                <AudioPlayer
                  ref={audioRef}
                  audioUrl={audioUrl}
                  onTimeUpdate={handleTimeUpdate}
                  className="mb-6"
                />
              )}

              {viewMode === ViewMode.TRANSCRIPT && active.result.segments && (
                <div role="tabpanel" id="panel-transcript" aria-labelledby="tab-transcript">
                  <TranscriptView
                    result={active.result}
                    jobId={active.jobId}
                    onResultUpdate={updateResult}
                    currentTime={currentTime}
                    onSeekToTime={seekToTime}
                  />
                </div>
              )}

              {viewMode === ViewMode.DOCUMENT && (
                <div role="tabpanel" id="panel-document" aria-labelledby="tab-document">
                  <DocumentView
                    documentMarkdown={active.result.document_markdown}
                    documentSections={active.result.document_sections}
                    speakerNotes={active.result.speaker_notes}
                    sourceType={sourceType}
                    pageCount={active.result.page_count}
                    slideCount={active.result.slide_count}
                  />
                </div>
              )}

              {viewMode === ViewMode.VISUAL && (
                <div role="tabpanel" id="panel-visual" aria-labelledby="tab-visual">
                  <VisualElementsPanel
                    visualElements={active.result.visual_elements || []}
                  />
                </div>
              )}
            </Suspense>

            <button
              onClick={clearSelection}
              className="w-full mt-6 py-3 rounded-lg font-medium bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 transition-colors"
            >
              {isDocumentMode ? 'Process Another Document' : 'Start New Transcription'}
            </button>
          </div>
        )}

        <footer className="text-center mt-12 text-slate-500 dark:text-slate-400 dark:text-slate-500 text-sm">
          <p>Powered by MLX-Whisper with GPU acceleration</p>
          <p className="mt-1">Optimized for Apple Silicon (M1/M2/M3)</p>
        </footer>
        </>)}
      </div>
      <LearningToast
        jobId={active?.jobId || null}
        jobCompleted={!!active?.result && !active?.isProcessing}
        onClickReview={() => setActiveTab('activity')}
      />
    </div>
  );
}

export default App;
