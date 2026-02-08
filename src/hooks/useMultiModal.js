import { useState, useCallback, useRef, useEffect } from 'react';
import { fetchJobStatus, submitMultiModalProcessing } from '../utils/api';

export function useMultiModal() {
  const [isProcessing, setIsProcessing] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const pollIntervalRef = useRef(null);
  const pollCountRef = useRef(0);

  const getPollInterval = () => {
    const count = pollCountRef.current;
    if (count < 10) return 1000;
    if (count < 30) return 2000;
    return 5000;
  };

  // Poll for job status
  const pollJobStatus = useCallback(async (id) => {
    try {
      const data = await fetchJobStatus(id, true); // isMultiModal = true

      setProgress(data.progress || 0);
      setProgressMessage(data.progress_message || '');

      if (data.status === 'completed') {
        setResult(data);
        setIsProcessing(false);
        if (pollIntervalRef.current) {
          clearTimeout(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
      } else if (data.status === 'failed') {
        setError(data.error || 'Processing failed');
        setIsProcessing(false);
        setJobId(null);
        if (pollIntervalRef.current) {
          clearTimeout(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
      }
    } catch (err) {
      console.error('Error polling multi-modal job status:', err);
    }
  }, []);

  // Start polling when job is created (with backoff)
  useEffect(() => {
    if (jobId && isProcessing) {
      pollCountRef.current = 0;

      const schedulePoll = () => {
        pollIntervalRef.current = setTimeout(async () => {
          await pollJobStatus(jobId);
          pollCountRef.current += 1;
          if (pollIntervalRef.current !== null) {
            schedulePoll();
          }
        }, getPollInterval());
      };

      pollJobStatus(jobId);
      schedulePoll();
    }

    return () => {
      if (pollIntervalRef.current) {
        clearTimeout(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, [jobId, isProcessing, pollJobStatus]);

  // Submit document for processing
  const processDocument = useCallback(async (file, options = {}) => {
    setError(null);
    setResult(null);
    setIsProcessing(true);
    setProgress(0);
    setProgressMessage('Starting document processing...');

    try {
      const data = await submitMultiModalProcessing(file, options);
      setJobId(data.job_id);
    } catch (err) {
      setError(err.message || 'Failed to start document processing');
      setIsProcessing(false);
    }
  }, []);

  // Reset state
  const reset = useCallback(() => {
    if (pollIntervalRef.current) {
      clearTimeout(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    setIsProcessing(false);
    setJobId(null);
    setProgress(0);
    setProgressMessage('');
    setResult(null);
    setError(null);
  }, []);

  // Update result (for edits)
  const updateResult = useCallback((newResult) => {
    setResult(newResult);
  }, []);

  return {
    // State
    isProcessing,
    jobId,
    progress,
    progressMessage,
    result,
    error,

    // Actions
    processDocument,
    reset,
    updateResult,
  };
}

export default useMultiModal;
