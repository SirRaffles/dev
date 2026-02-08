import { useState, useCallback, useRef, useEffect } from 'react';
import {
  fetchJobStatus,
  fetchBatchStatus,
  submitTranscription,
  submitYouTubeTranscription,
  submitBatchTranscription,
} from '../utils/api';

export function useTranscription() {
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // Batch state
  const [batchProgress, setBatchProgress] = useState([]);

  const pollIntervalRef = useRef(null);
  const pollCountRef = useRef(0);

  const getPollInterval = () => {
    const count = pollCountRef.current;
    if (count < 10) return 1000;   // First 10s: every 1s
    if (count < 30) return 2000;   // Next 40s: every 2s
    return 5000;                    // After that: every 5s
  };

  // Poll for single job status
  const pollJobStatus = useCallback(async (id) => {
    try {
      const data = await fetchJobStatus(id);

      setProgress(data.progress || 0);
      setProgressMessage(data.progress_message || '');

      if (data.status === 'completed') {
        setResult(data);
        setIsTranscribing(false);
        if (pollIntervalRef.current) {
          clearTimeout(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
      } else if (data.status === 'failed') {
        setError(data.error || 'Transcription failed');
        setIsTranscribing(false);
        setJobId(null);
        if (pollIntervalRef.current) {
          clearTimeout(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
      }
    } catch (err) {
      console.error('Error polling job status:', err);
    }
  }, []);

  // Poll batch job status
  const pollBatchJobStatus = useCallback(async (batchId) => {
    try {
      const data = await fetchBatchStatus(batchId);

      setBatchProgress(data.jobs.map(job => ({
        job_id: job.job_id,
        status: job.status,
        progress: job.progress,
        error: job.error
      })));

      setProgress(data.overall_progress);
      setProgressMessage(`${data.completed}/${data.total} files completed`);

      if (data.overall_status === 'completed') {
        setIsTranscribing(false);
        // Fetch first completed job result to display
        if (data.jobs.length > 0) {
          const firstJobId = data.jobs[0].job_id;
          const resultData = await fetchJobStatus(firstJobId);
          setResult(resultData);
          setJobId(firstJobId);
        }
        if (pollIntervalRef.current) {
          clearTimeout(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
      } else if (data.overall_status === 'failed' && data.completed === 0) {
        setError('All files failed to transcribe');
        setIsTranscribing(false);
        if (pollIntervalRef.current) {
          clearTimeout(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
      }
    } catch (err) {
      console.error('Error polling batch status:', err);
    }
  }, []);

  // Start polling when job is created (with backoff)
  useEffect(() => {
    if (jobId && isTranscribing) {
      pollCountRef.current = 0;

      const schedulePoll = () => {
        pollIntervalRef.current = setTimeout(async () => {
          await pollJobStatus(jobId);
          pollCountRef.current += 1;
          // Only continue if still transcribing (ref check avoids stale closure)
          if (pollIntervalRef.current !== null) {
            schedulePoll();
          }
        }, getPollInterval());
      };

      // Initial poll immediately, then schedule with backoff
      pollJobStatus(jobId);
      schedulePoll();
    }

    return () => {
      if (pollIntervalRef.current) {
        clearTimeout(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, [jobId, isTranscribing, pollJobStatus]);

  // Submit file for transcription
  const transcribeFile = useCallback(async (file, options = {}) => {
    setError(null);
    setResult(null);
    setIsTranscribing(true);
    setProgress(0);
    setProgressMessage('Starting...');

    try {
      const data = await submitTranscription(file, options);
      setJobId(data.job_id);
    } catch (err) {
      setError(err.message || 'Failed to start transcription');
      setIsTranscribing(false);
    }
  }, []);

  // Submit YouTube URL for transcription
  const transcribeYouTube = useCallback(async (url, options = {}) => {
    setError(null);
    setResult(null);
    setIsTranscribing(true);
    setProgress(0);
    setProgressMessage('Downloading video...');

    try {
      const data = await submitYouTubeTranscription(url, options);
      setJobId(data.job_id);
    } catch (err) {
      setError(err.message || 'Failed to start YouTube transcription');
      setIsTranscribing(false);
    }
  }, []);

  // Submit multiple files for batch transcription
  const transcribeBatch = useCallback(async (files, options = {}) => {
    setError(null);
    setResult(null);
    setIsTranscribing(true);
    setProgress(0);
    setProgressMessage('Uploading files...');
    setBatchProgress([]);

    try {
      const data = await submitBatchTranscription(files, options);

      // Initialize progress tracking
      setBatchProgress(data.job_ids.map(id => ({ job_id: id, progress: 0, status: 'pending' })));

      // Start polling batch status
      const batchId = data.batch_id;
      pollIntervalRef.current = setInterval(() => {
        pollBatchJobStatus(batchId);
      }, 2000);
      pollBatchJobStatus(batchId);

    } catch (err) {
      setError(err.message || 'Failed to start batch transcription');
      setIsTranscribing(false);
    }
  }, [pollBatchJobStatus]);

  // Reset state
  const reset = useCallback(() => {
    if (pollIntervalRef.current) {
      clearTimeout(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    setIsTranscribing(false);
    setJobId(null);
    setProgress(0);
    setProgressMessage('');
    setResult(null);
    setError(null);
    setBatchProgress([]);
  }, []);

  // Update result (for edits)
  const updateResult = useCallback((newResult) => {
    setResult(newResult);
  }, []);

  return {
    // State
    isTranscribing,
    jobId,
    progress,
    progressMessage,
    result,
    error,
    batchProgress,

    // Actions
    transcribeFile,
    transcribeYouTube,
    transcribeBatch,
    reset,
    updateResult,
  };
}

export default useTranscription;
