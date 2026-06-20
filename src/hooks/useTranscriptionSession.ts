import { useCallback, useEffect, useMemo, useRef } from 'react';
import { API_URL } from '../utils/api';

interface TranscriptionSessionSettings {
  language: string;
  enableDiarization: boolean;
  enableNoiseReduction: boolean;
  numSpeakers: string;
  translateToEnglish: boolean;
  engine: string;
  contextPath: string;
  speakerIds: string[];
  refinementMode: string;
}

type TranscriptionOptions = TranscriptionSessionSettings;

interface TranscriptionController {
  transcribeBatch: (files: File[], options: TranscriptionOptions) => Promise<void>;
  transcribeFile: (file: File, options: TranscriptionOptions) => Promise<void>;
  transcribeYouTube: (url: string, options: TranscriptionOptions) => Promise<void>;
}

interface MultiModalController {
  processDocument: (file: File) => Promise<void>;
}

interface UseTranscriptionSessionParams {
  inputMode: string;
  file: File | null;
  files: File[];
  youtubeUrl: string;
  settings: TranscriptionSessionSettings;
  isDocumentMode: boolean;
  macState: string | null;
  triggerWake: (apiUrl: string) => void;
  queueSubmit: () => void;
  hasPendingSubmit: () => boolean;
  transcription: TranscriptionController;
  multiModal: MultiModalController;
}

export default function useTranscriptionSession({
  inputMode,
  file,
  files,
  youtubeUrl,
  settings,
  isDocumentMode,
  macState,
  triggerWake,
  queueSubmit,
  hasPendingSubmit,
  transcription,
  multiModal,
}: UseTranscriptionSessionParams) {
  const options = useMemo<TranscriptionOptions>(() => ({
    language: settings.language,
    enableDiarization: settings.enableDiarization,
    enableNoiseReduction: settings.enableNoiseReduction,
    numSpeakers: settings.numSpeakers,
    translateToEnglish: settings.translateToEnglish,
    engine: settings.engine,
    contextPath: settings.contextPath,
    speakerIds: settings.speakerIds,
    refinementMode: settings.refinementMode,
  }), [settings]);

  const startProcessing = useCallback(async () => {
    if (macState === 'sleeping') {
      triggerWake(API_URL);
      return;
    }

    if (macState === 'waking') {
      queueSubmit();
      return;
    }

    if (files.length > 1) {
      await transcription.transcribeBatch(files, options);
    } else if (isDocumentMode && file) {
      await multiModal.processDocument(file);
    } else if (inputMode === 'file' && file) {
      await transcription.transcribeFile(file, options);
    } else if (inputMode === 'youtube' && youtubeUrl.trim()) {
      await transcription.transcribeYouTube(youtubeUrl, options);
    }
  }, [
    file,
    files,
    inputMode,
    isDocumentMode,
    macState,
    multiModal,
    options,
    queueSubmit,
    transcription,
    triggerWake,
    youtubeUrl,
  ]);

  const startProcessingRef = useRef(startProcessing);
  startProcessingRef.current = startProcessing;

  useEffect(() => {
    if (macState === 'awake' && hasPendingSubmit()) {
      startProcessingRef.current();
    }
  }, [macState, hasPendingSubmit]);

  const canStart = useMemo(() => (
    (inputMode === 'file' && (file !== null || files.length > 0)) ||
    (inputMode === 'youtube' && youtubeUrl.trim().length > 0)
  ), [file, files.length, inputMode, youtubeUrl]);

  return {
    canStart,
    startProcessing,
  };
}
