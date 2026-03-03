import React, { useState, useRef, useEffect } from 'react';
import { Clock, Users, Edit2, Save, Edit3, Search, Replace, X, Check, Loader2 } from 'lucide-react';
import { LANGUAGES, updateSegments, updateSpeakers, Segment } from '../utils/api';
import { formatTime } from './AudioPlayer';

// Escape special regex characters to prevent ReDoS
const escapeRegExp = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

interface TranscriptResult {
  language?: string;
  language_probability?: number;
  speakers?: string[];
  segments?: Segment[];
  result?: string;
}

interface TranscriptViewProps {
  result: TranscriptResult;
  jobId: string;
  onResultUpdate?: (result: TranscriptResult) => void;
  currentTime?: number;
  onSeekToTime?: (time: number) => void;
  className?: string;
}

function TranscriptView({
  result,
  jobId,
  onResultUpdate,
  currentTime = 0,
  onSeekToTime,
  className = '',
}: TranscriptViewProps) {
  const [showTimestamps, setShowTimestamps] = useState(true);
  const [showSpeakers, setShowSpeakers] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [editedSegments, setEditedSegments] = useState<Record<number, string>>({});
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Speaker renaming
  const [speakerNames, setSpeakerNames] = useState<Record<string, string>>({});
  const [editingSpeaker, setEditingSpeaker] = useState<string | null>(null);
  const [tempSpeakerName, setTempSpeakerName] = useState('');
  const [isSavingSpeaker, setIsSavingSpeaker] = useState(false);
  const [speakerError, setSpeakerError] = useState<string | null>(null);

  // Search & replace
  const [showSearchPanel, setShowSearchPanel] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [replaceText, setReplaceText] = useState('');
  const [searchResults, setSearchResults] = useState<number[]>([]);
  const [isReplacing, setIsReplacing] = useState(false);
  const [replaceError, setReplaceError] = useState<string | null>(null);

  const segmentRefs = useRef<Record<number, HTMLDivElement | null>>({});

  // Get unique speakers from result
  const speakers = result?.speakers || [];

  // Get current playing segment index
  const getCurrentSegmentIndex = () => {
    if (!result?.segments) return -1;
    return result.segments.findIndex(
      segment => currentTime >= segment.start && currentTime <= segment.end
    );
  };

  const currentSegmentIndex = getCurrentSegmentIndex();

  // Auto-scroll to current segment
  useEffect(() => {
    if (!result?.segments || !currentTime) return;

    const currentSegment = result.segments.findIndex(
      segment => currentTime >= segment.start && currentTime <= segment.end
    );

    if (currentSegment >= 0 && segmentRefs.current[currentSegment]) {
      segmentRefs.current[currentSegment]!.scrollIntoView({
        behavior: 'smooth',
        block: 'center'
      });
    }
  }, [currentTime, result]);

  // Handle editing
  const handleEditSegment = (index: number, newText: string) => {
    setEditedSegments(prev => ({
      ...prev,
      [index]: newText
    }));
  };

  const saveEdits = async () => {
    const changeCount = Object.keys(editedSegments).length;
    if (!jobId || changeCount === 0) {
      setIsEditing(false);
      return;
    }

    if (changeCount > 1 && !window.confirm(`Save ${changeCount} changes? This cannot be undone.`)) {
      return;
    }

    setIsSaving(true);
    setSaveError(null);
    try {
      const updatedSegments = result.segments!.map((segment, index) => ({
        ...segment,
        text: editedSegments[index] !== undefined ? editedSegments[index] : segment.text
      }));

      await updateSegments(jobId, updatedSegments);

      onResultUpdate?.({
        ...result,
        segments: updatedSegments
      });

      setIsEditing(false);
      setEditedSegments({});
    } catch (err: any) {
      setSaveError(err.message || 'Failed to save changes');
    } finally {
      setIsSaving(false);
    }
  };

  // Speaker renaming functions
  const startEditingSpeaker = (speaker: string) => {
    setEditingSpeaker(speaker);
    setTempSpeakerName(speakerNames[speaker] || speaker);
  };

  const cancelEditingSpeaker = () => {
    setEditingSpeaker(null);
    setTempSpeakerName('');
  };

  const saveSpeakerName = async () => {
    if (!editingSpeaker || !tempSpeakerName.trim() || !jobId) return;

    setIsSavingSpeaker(true);
    setSpeakerError(null);
    try {
      const mapping = { [editingSpeaker]: tempSpeakerName.trim() };
      const data = await updateSpeakers(jobId, mapping);

      setSpeakerNames(prev => ({ ...prev, [editingSpeaker]: tempSpeakerName.trim() }));
      onResultUpdate?.({ ...result, segments: data.segments, speakers: data.speakers });
      cancelEditingSpeaker();
    } catch (err: any) {
      setSpeakerError(err.message || 'Failed to rename speaker');
    } finally {
      setIsSavingSpeaker(false);
    }
  };

  // Search functions
  const performSearch = () => {
    if (!result?.segments || !searchQuery.trim()) {
      setSearchResults([]);
      return;
    }

    const matches: number[] = [];
    const query = searchQuery.toLowerCase();
    result.segments.forEach((segment, index) => {
      if (segment.text.toLowerCase().includes(query)) {
        matches.push(index);
      }
    });
    setSearchResults(matches);
  };

  const replaceInSegment = async (index: number) => {
    if (!searchQuery || !result?.segments) return;

    setIsReplacing(true);
    setReplaceError(null);

    const segment = result.segments[index];
    const newText = segment.text.replace(new RegExp(escapeRegExp(searchQuery), 'gi'), replaceText);

    setEditedSegments(prev => ({ ...prev, [index]: newText }));

    const updatedSegments = result.segments.map((seg, i) => ({
      ...seg,
      text: i === index ? newText : (editedSegments[i] !== undefined ? editedSegments[i] : seg.text)
    }));

    try {
      await updateSegments(jobId, updatedSegments);
      onResultUpdate?.({ ...result, segments: updatedSegments });
      performSearch();
    } catch (err: any) {
      setReplaceError(err.message || 'Failed to replace text');
    } finally {
      setIsReplacing(false);
    }
  };

  const replaceAll = async () => {
    if (!searchQuery || !result?.segments) return;

    // Count total occurrences across all segments
    const regex = new RegExp(escapeRegExp(searchQuery), 'gi');
    let totalOccurrences = 0;
    result.segments.forEach((segment) => {
      const matches = segment.text.match(regex);
      if (matches) totalOccurrences += matches.length;
    });

    if (totalOccurrences === 0) return;

    if (!window.confirm(`Replace ${totalOccurrences} occurrence${totalOccurrences !== 1 ? 's' : ''} of "${searchQuery}" with "${replaceText}"?`)) {
      return;
    }

    setIsReplacing(true);
    setReplaceError(null);

    const updatedSegments = result.segments.map((segment) => ({
      ...segment,
      text: segment.text.replace(new RegExp(escapeRegExp(searchQuery), 'gi'), replaceText)
    }));

    try {
      await updateSegments(jobId, updatedSegments);
      onResultUpdate?.({ ...result, segments: updatedSegments });
      setSearchResults([]);
      setSearchQuery('');
      setReplaceText('');
    } catch (err: any) {
      setReplaceError(err.message || 'Failed to replace all');
    } finally {
      setIsReplacing(false);
    }
  };

  // Highlight matching text
  const highlightText = (text: string, index: number): React.ReactNode => {
    if (!searchQuery || !searchResults.includes(index)) return text;

    const regex = new RegExp(`(${escapeRegExp(searchQuery)})`, 'gi');
    const parts = text.split(regex);

    return parts.map((part, i) =>
      regex.test(part) ? <mark key={i} className="bg-yellow-400 text-black px-0.5 rounded">{part}</mark> : part
    );
  };

  const handleSeek = (time: number) => {
    onSeekToTime?.(time);
  };

  return (
    <div className={className}>
      {/* Language & Speakers Info */}
      <div className="flex flex-wrap items-center gap-2 sm:gap-4 mb-6 p-3 bg-slate-100 dark:bg-slate-700/50 rounded-lg text-sm sm:text-base">
        {result.language && (
          <div className="flex items-center gap-2">
            <span className="text-slate-500 dark:text-slate-300">Language:</span>
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
            <span className="text-slate-500 dark:text-slate-300">Speakers:</span>
            <span className="font-medium">{speakers.length}</span>
          </div>
        )}
      </div>

      {/* Speaker Renaming */}
      {speakers.length > 0 && (
        <div className="mb-6 p-4 bg-slate-100 dark:bg-slate-700/30 rounded-xl">
          <h3 className="text-sm font-medium text-slate-600 dark:text-slate-300 mb-3 flex items-center gap-2">
            <Edit3 className="w-4 h-4" />
            Rename Speakers
          </h3>
          <div className="flex flex-wrap gap-2">
            {speakers.map((speaker) => (
              <div key={speaker} className="flex items-center gap-1">
                {editingSpeaker === speaker ? (
                  <div className="flex items-center gap-1 bg-slate-200 dark:bg-slate-600 rounded-lg px-2 py-1">
                    <input
                      type="text"
                      value={tempSpeakerName}
                      onChange={(e) => setTempSpeakerName(e.target.value)}
                      className="w-24 bg-white dark:bg-slate-700 text-slate-900 dark:text-white px-2 py-1 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                      autoFocus
                      disabled={isSavingSpeaker}
                      onKeyDown={(e) => e.key === 'Enter' && saveSpeakerName()}
                    />
                    <button
                      onClick={saveSpeakerName}
                      disabled={isSavingSpeaker}
                      className="p-1 text-green-400 hover:text-green-300 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isSavingSpeaker ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                    </button>
                    <button
                      onClick={cancelEditingSpeaker}
                      disabled={isSavingSpeaker}
                      className="p-1 text-red-400 hover:text-red-300 disabled:opacity-50"
                    >
                      <X className="w-4 h-4" />
                    </button>
                    {speakerError && <span className="text-red-400 text-xs ml-1">{speakerError}</span>}
                  </div>
                ) : (
                  <div className="flex items-center gap-1 bg-purple-500/20 text-purple-300 rounded-lg px-3 py-1">
                    <span className="text-sm">{speakerNames[speaker] || speaker}</span>
                    <button
                      onClick={() => startEditingSpeaker(speaker)}
                      className="p-0.5 hover:text-purple-200 transition-colors"
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

      {/* Edit / Search Controls */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        {isEditing ? (
          <button
            onClick={saveEdits}
            disabled={isSaving}
            className="flex items-center gap-2 px-3 py-2 bg-green-600 hover:bg-green-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            {isSaving ? 'Saving...' : 'Save'}
          </button>
        ) : (
          <button
            onClick={() => { setIsEditing(true); setSaveError(null); }}
            className="flex items-center gap-2 px-3 py-2 bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 rounded-lg transition-colors"
          >
            <Edit2 className="w-4 h-4" />
            Edit
          </button>
        )}
        <button
          onClick={() => {
            const next = !showSearchPanel;
            setShowSearchPanel(next);
            if (!next) {
              setSearchQuery('');
              setReplaceText('');
              setSearchResults([]);
              setReplaceError(null);
            }
          }}
          className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
            showSearchPanel ? 'bg-orange-500 text-white' : 'bg-slate-200 text-slate-600 hover:bg-slate-300 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600'
          }`}
        >
          <Search className="w-4 h-4" />
          Search & Replace
        </button>
        {saveError && (
          <span className="text-red-400 text-sm">{saveError}</span>
        )}
      </div>

      {/* Search & Replace Panel */}
      {showSearchPanel && (
        <div className="mb-4 p-4 bg-slate-100 dark:bg-slate-700/30 rounded-xl">
          <div className="flex flex-col sm:flex-row gap-3 mb-3">
            <div className="flex-1 min-w-0">
              <label className="text-xs text-slate-500 dark:text-slate-400 mb-1 block">Search</label>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && performSearch()}
                placeholder="Search text..."
                className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-slate-900 placeholder-slate-400 dark:bg-slate-700 dark:border-slate-600 dark:text-white focus:outline-none focus:border-blue-400"
              />
            </div>
            <div className="flex-1 min-w-0">
              <label className="text-xs text-slate-500 dark:text-slate-400 mb-1 block">Replace with</label>
              <input
                type="text"
                value={replaceText}
                onChange={(e) => setReplaceText(e.target.value)}
                placeholder="Replacement text..."
                className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-slate-900 placeholder-slate-400 dark:bg-slate-700 dark:border-slate-600 dark:text-white focus:outline-none focus:border-blue-400"
              />
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={performSearch}
              disabled={isReplacing}
              className="flex items-center gap-2 px-3 py-2 bg-blue-500 hover:bg-blue-600 rounded-lg text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
                  disabled={isReplacing}
                  className="flex items-center gap-2 px-3 py-2 bg-orange-500 hover:bg-orange-600 rounded-lg text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isReplacing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Replace className="w-4 h-4" />}
                  {isReplacing ? 'Replacing...' : 'Replace All'}
                </button>
              </>
            )}
            {searchQuery && (
              <button
                onClick={() => { setSearchQuery(''); setReplaceText(''); setSearchResults([]); setReplaceError(null); }}
                className="flex items-center gap-1 px-2 py-2 text-slate-400 hover:text-slate-300 transition-colors"
              >
                <X className="w-4 h-4" />
                Clear
              </button>
            )}
            {replaceError && (
              <span className="text-red-400 text-sm">{replaceError}</span>
            )}
          </div>
        </div>
      )}

      {/* View Toggles */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <button
          onClick={() => setShowTimestamps(!showTimestamps)}
          className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
            showTimestamps ? 'bg-blue-500 text-white' : 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
          }`}
        >
          <Clock className="w-4 h-4" />
          Timestamps
        </button>
        {speakers.length > 0 && (
          <button
            onClick={() => setShowSpeakers(!showSpeakers)}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
              showSpeakers ? 'bg-purple-500 text-white' : 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
            }`}
          >
            <Users className="w-4 h-4" />
            Speakers
          </button>
        )}
      </div>

      {/* Transcription Text */}
      <div className="bg-slate-50 dark:bg-slate-900/50 rounded-xl p-4 max-h-[60vh] min-h-[16rem] overflow-y-auto">
        {(showTimestamps || showSpeakers) && result.segments ? (
          <div className="space-y-3">
            {result.segments.map((segment, index) => {
              const isCurrentSegment = index === currentSegmentIndex;
              const isEdited = editedSegments[index] !== undefined;

              return (
                <React.Fragment key={`seg-${segment.start}-${segment.end}`}>
                  {segment.paragraph_break && index > 0 && (
                    <div className="border-t border-slate-200 dark:border-slate-700 my-2" />
                  )}
                  <div
                    ref={el => { segmentRefs.current[index] = el; }}
                    className={`flex gap-2 sm:gap-3 p-2 rounded transition-all ${
                      isCurrentSegment ? 'bg-blue-500/20 border-l-2 border-blue-400' : ''
                    } ${isEdited ? 'bg-yellow-500/10' : ''}`}
                  >
                  {showTimestamps && (
                    <button
                      onClick={() => handleSeek(segment.start)}
                      className="text-blue-400 hover:text-blue-300 font-mono text-xs sm:text-sm whitespace-nowrap pt-1 cursor-pointer transition-colors min-w-[44px] text-left"
                    >
                      [{formatTime(segment.start)}]
                    </button>
                  )}
                  {showSpeakers && segment.speaker && (
                    <span className="text-purple-400 font-medium text-xs sm:text-sm whitespace-nowrap pt-1">
                      {speakerNames[segment.speaker] || segment.speaker}:
                    </span>
                  )}
                  {isEditing ? (
                    <textarea
                      rows={2}
                      value={editedSegments[index] !== undefined ? editedSegments[index] : segment.text}
                      onChange={(e) => handleEditSegment(index, e.target.value)}
                      className="flex-1 bg-white dark:bg-slate-700 text-slate-800 dark:text-slate-200 px-2 py-1 rounded border border-slate-300 dark:border-slate-600 focus:outline-none focus:border-blue-400 resize-y"
                    />
                  ) : (
                    <p className={`text-slate-800 dark:text-slate-200 leading-relaxed flex-1 ${searchResults.includes(index) ? 'bg-yellow-500/10 rounded px-1' : ''}`}>
                      {highlightText(editedSegments[index] !== undefined ? editedSegments[index] : segment.text, index)}
                      {searchResults.includes(index) && replaceText && (
                        <button
                          onClick={() => replaceInSegment(index)}
                          disabled={isReplacing}
                          className="ml-2 text-xs px-2 py-0.5 bg-orange-500 hover:bg-orange-600 rounded text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          Replace
                        </button>
                      )}
                    </p>
                  )}
                  </div>
                </React.Fragment>
              );
            })}
          </div>
        ) : (
          <p className="text-slate-800 dark:text-slate-200 leading-relaxed whitespace-pre-wrap">
            {result.result}
          </p>
        )}
      </div>
    </div>
  );
}

export default React.memo(TranscriptView);
