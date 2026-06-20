import { useState } from 'react';
import type { Segment } from '../utils/transcriptEditOps';
import {
  searchSegments,
  replaceAllInSegments,
  replaceInSegmentText,
} from '../utils/transcriptEditOps';

interface UseTranscriptSearchOptions {
  // The committed segments search/replace operates on (search & replace always
  // works on the persisted transcript directly, not the edit-mode draft).
  segments: Segment[] | undefined;
  // Persists the next segments to the backend, then surfaces them to the parent.
  persist: (next: Segment[]) => Promise<void>;
}

export interface UseTranscriptSearch {
  searchQuery: string;
  setSearchQuery: (s: string) => void;
  replaceText: string;
  setReplaceText: (s: string) => void;
  searchResults: number[];
  isReplacing: boolean;
  replaceError: string | null;
  performSearch: () => void;
  replaceInSegment: (index: number) => Promise<void>;
  // Counts pending occurrences; returns the total so the caller can drive the
  // confirm modal. Pass `confirmed: true` to actually apply + persist.
  replaceAll: (confirmed: boolean) => Promise<number>;
  resetSearch: () => void;
}

export function useTranscriptSearch({
  segments,
  persist,
}: UseTranscriptSearchOptions): UseTranscriptSearch {
  const [searchQuery, setSearchQuery] = useState('');
  const [replaceText, setReplaceText] = useState('');
  const [searchResults, setSearchResults] = useState<number[]>([]);
  const [isReplacing, setIsReplacing] = useState(false);
  const [replaceError, setReplaceError] = useState<string | null>(null);

  const performSearch = () => {
    if (!segments || !searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    setSearchResults(searchSegments(segments, searchQuery));
  };

  const replaceInSegment = async (index: number) => {
    if (!searchQuery || !segments) return;

    setIsReplacing(true);
    setReplaceError(null);

    const segment = segments[index];
    const newText = replaceInSegmentText(segment.text, searchQuery, replaceText);

    // Search & replace operates on the committed segments directly and
    // auto-saves — matching the existing UX where each Replace is a one-shot
    // persist.
    const updatedSegments = segments.map((seg, i) =>
      i === index ? { ...seg, text: newText } : seg,
    );

    try {
      await persist(updatedSegments);
      performSearch();
    } catch (err: any) {
      setReplaceError(err.message || 'Failed to replace text');
    } finally {
      setIsReplacing(false);
    }
  };

  const replaceAll = async (confirmed: boolean): Promise<number> => {
    if (!searchQuery || !segments) return 0;

    const { segments: updatedSegments, count } = replaceAllInSegments(
      segments,
      searchQuery,
      replaceText,
    );

    if (count === 0) return 0;
    if (!confirmed) return count;

    setIsReplacing(true);
    setReplaceError(null);

    try {
      await persist(updatedSegments);
      setSearchResults([]);
      setSearchQuery('');
      setReplaceText('');
    } catch (err: any) {
      setReplaceError(err.message || 'Failed to replace all');
    } finally {
      setIsReplacing(false);
    }
    return count;
  };

  const resetSearch = () => {
    setSearchQuery('');
    setReplaceText('');
    setSearchResults([]);
    setReplaceError(null);
  };

  return {
    searchQuery,
    setSearchQuery,
    replaceText,
    setReplaceText,
    searchResults,
    isReplacing,
    replaceError,
    performSearch,
    replaceInSegment,
    replaceAll,
    resetSearch,
  };
}
