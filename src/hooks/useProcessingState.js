import { useMemo } from 'react';
import { isDocumentFile, getSourceType } from '../utils/api';
import useTranscription from './useTranscription';
import useMultiModal from './useMultiModal';

/**
 * Coordinates between transcription and multi-modal processing hooks.
 * Provides a unified interface regardless of which processor is active.
 */
export default function useProcessingState(file) {
  const transcription = useTranscription();
  const multiModal = useMultiModal();

  const isDocumentMode = file && isDocumentFile(file.name);
  const sourceType = file ? getSourceType(file.name) : null;

  const active = useMemo(() => ({
    result: isDocumentMode ? multiModal.result : transcription.result,
    error: isDocumentMode ? multiModal.error : transcription.error,
    isProcessing: isDocumentMode ? multiModal.isProcessing : transcription.isTranscribing,
    progress: isDocumentMode ? multiModal.progress : transcription.progress,
    progressMessage: isDocumentMode ? multiModal.progressMessage : transcription.progressMessage,
    jobId: isDocumentMode ? multiModal.jobId : transcription.jobId,
  }), [
    isDocumentMode,
    multiModal.result, multiModal.error, multiModal.isProcessing,
    multiModal.progress, multiModal.progressMessage, multiModal.jobId,
    transcription.result, transcription.error, transcription.isTranscribing,
    transcription.progress, transcription.progressMessage, transcription.jobId,
  ]);

  const resetAll = () => {
    transcription.reset();
    multiModal.reset();
  };

  const updateResult = isDocumentMode ? multiModal.updateResult : transcription.updateResult;

  return {
    transcription,
    multiModal,
    isDocumentMode,
    sourceType,
    active,
    resetAll,
    updateResult,
  };
}
