import React from 'react';
import { Loader2 } from 'lucide-react';

interface BatchJob {
  job_id: string;
  progress: number;
  status: string;
}

interface ProgressBarProps {
  progress: number;
  progressMessage?: string;
  batchProgress?: BatchJob[];
  sourceType?: string;
}

function ProgressBar({
  progress,
  progressMessage,
  batchProgress = [],
  sourceType = 'audio'
}: ProgressBarProps) {
  const getMessage = () => {
    if (progressMessage) return progressMessage;

    if (sourceType === 'pdf' || sourceType === 'pptx' || sourceType === 'docx') {
      if (progress < 20) return 'Extracting text...';
      if (progress < 40) return 'Processing images...';
      if (progress < 70) return 'Analyzing visual content...';
      if (progress < 90) return 'Generating output...';
      return 'Finalizing...';
    }

    return 'Processing your audio...';
  };

  return (
    <div className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-6 mb-8 border border-slate-200 dark:border-slate-700 shadow-sm dark:shadow-none">
      <div className="flex items-center gap-3 mb-4">
        <Loader2 className="w-5 h-5 animate-spin text-blue-400" aria-hidden="true" />
        <span className="font-medium" aria-live="polite">{getMessage()}</span>
      </div>
      <div
        className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-3"
        role="progressbar"
        aria-valuenow={progress}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Processing progress"
      >
        <div
          className="bg-gradient-to-r from-blue-500 to-purple-500 h-3 rounded-full transition-all duration-300"
          style={{ width: `${progress}%` }}
        />
      </div>
      <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
        {sourceType === 'pdf' || sourceType === 'pptx' || sourceType === 'docx'
          ? 'Document processing may take a few moments'
          : 'Quality-focused transcription may take a few minutes'}
      </p>

      {batchProgress.length > 1 && (
        <div className="mt-4 space-y-2">
          <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wider">Individual files:</p>
          {batchProgress.map((job, idx) => (
            <div key={job.job_id} className="flex items-center gap-2">
              <span className="text-xs text-slate-500 dark:text-slate-400 w-6">{idx + 1}.</span>
              <div
                className="flex-1 bg-slate-200 dark:bg-slate-600 rounded-full h-2"
                role="progressbar"
                aria-valuenow={job.progress}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <div
                  className={`h-2 rounded-full transition-all duration-300 ${
                    job.status === 'completed' ? 'bg-green-500' :
                    job.status === 'failed' ? 'bg-red-500' :
                    'bg-blue-500'
                  }`}
                  style={{ width: `${job.progress}%` }}
                />
              </div>
              <span className="text-xs text-slate-500 dark:text-slate-400 w-12">{job.progress}%</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default React.memo(ProgressBar);
