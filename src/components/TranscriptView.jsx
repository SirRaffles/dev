import React, { useState, useRef, useEffect } from 'react';
import { Clock, Users, Edit2, Save, Edit3, Search, Replace, X, Check } from 'lucide-react';
import { LANGUAGES, updateSegments, updateSpeakers } from '../utils/api';

// Escape special regex characters to prevent ReDoS
const escapeRegExp = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// Format timestamp for display
export const formatTime = (seconds) => {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 100);

  if (hrs > 0) {
    return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
  }
  return `${mins}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
};

function TranscriptView({
  result,
  jobId,
  onResultUpdate,
  currentTime = 0,
  onSeekToTime,
  className = '',
}) {
  const [showTimestamps, setShowTimestamps] = useState(true);
  const [showSpeakers, setShowSpeakers] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [editedSegments, setEditedSegments] = useState({});

  // Speaker renaming
  const [speakerNames, setSpeakerNames] = useState({});
  const [editingSpeaker, setEditingSpeaker] = useState(null);
  const [tempSpeakerName, setTempSpeakerName] = useState('');

  // Search & replace
  const [showSearchPanel, setShowSearchPanel] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [replaceText, setReplaceText] = useState('');
  const [searchResults, setSearchResults] = useState([]);

  const segmentRefs = useRef({});

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
      segmentRefs.current[currentSegment].scrollIntoView({
        behavior: 'smooth',
        block: 'center'
      });
    }
  }, [currentTime, result]);

  // Handle editing
  const handleEditSegment = (index, newText) => {
    setEditedSegments(prev => ({
      ...prev,
      [index]: newText
    }));
  };

  const saveEdits = async () => {
    if (!jobId || Object.keys(editedSegments).length === 0) {
      setIsEditing(false);
      return;
    }

    try {
      const updatedSegments = result.segments.map((segment, index) => ({
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
    } catch (err) {
      console.error('Save error:', err);
    }
  };

  // Speaker renaming functions
  const startEditingSpeaker = (speaker) => {
    setEditingSpeaker(speaker);
    setTempSpeakerName(speakerNames[speaker] || speaker);
  };

  const cancelEditingSpeaker = () => {
    setEditingSpeaker(null);
    setTempSpeakerName('');
  };

  const saveSpeakerName = async () => {
    if (!editingSpeaker || !tempSpeakerName.trim() || !jobId) return;

    try {
      const mapping = { [editingSpeaker]: tempSpeakerName.trim() };
      const data = await updateSpeakers(jobId, mapping);

      setSpeakerNames(prev => ({ ...prev, [editingSpeaker]: tempSpeakerName.trim() }));
      onResultUpdate?.({ ...result, segments: data.segments, speakers: data.speakers });
      cancelEditingSpeaker();
    } catch (err) {
      console.error('Rename error:', err);
    }
  };

  // Search functions
  const performSearch = () => {
    if (!result?.segments || !searchQuery.trim()) {
      setSearchResults([]);
      return;
    }

    const matches = [];
    const query = searchQuery.toLowerCase();
    result.segments.forEach((segment, index) => {
      if (segment.text.toLowerCase().includes(query)) {
        matches.push(index);
      }
    });
    setSearchResults(matches);
  };

  const replaceInSegment = async (index) => {
    if (!searchQuery || !result?.segments) return;

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
    } catch (err) {
      console.error('Replace error:', err);
    }
  };

  const replaceAll = async () => {
    if (!searchQuery || !result?.segments) return;

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
    } catch (err) {
      console.error('Replace all error:', err);
    }
  };

  // Highlight matching text
  const highlightText = (text, index) => {
    if (!searchQuery || !searchResults.includes(index)) return text;

    const regex = new RegExp(`(${escapeRegExp(searchQuery)})`, 'gi');
    const parts = text.split(regex);

    return parts.map((part, i) =>
      regex.test(part) ? <mark key={i} className="bg-yellow-400 text-black px-0.5 rounded">{part}</mark> : part
    );
  };

  const handleSeek = (time) => {
    onSeekToTime?.(time);
  };

  return (
    <div className={className}>
      {/* Language & Speakers Info */}
      <div className="flex flex-wrap items-center gap-4 mb-6 p-3 bg-slate-700/50 rounded-lg">
        {result.language && (
          <div className="flex items-center gap-2">
            <span className="text-slate-300">Language:</span>
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
            <span className="text-slate-300">Speakers:</span>
            <span className="font-medium">{speakers.length}</span>
          </div>
        )}
      </div>

      {/* Speaker Renaming */}
      {speakers.length > 0 && (
        <div className="mb-6 p-4 bg-slate-700/30 rounded-xl">
          <h3 className="text-sm font-medium text-slate-300 mb-3 flex items-center gap-2">
            <Edit3 className="w-4 h-4" />
            Rename Speakers
          </h3>
          <div className="flex flex-wrap gap-2">
            {speakers.map((speaker) => (
              <div key={speaker} className="flex items-center gap-1">
                {editingSpeaker === speaker ? (
                  <div className="flex items-center gap-1 bg-slate-600 rounded-lg px-2 py-1">
                    <input
                      type="text"
                      value={tempSpeakerName}
                      onChange={(e) => setTempSpeakerName(e.target.value)}
                      className="w-24 bg-slate-700 text-white px-2 py-1 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                      autoFocus
                      onKeyDown={(e) => e.key === 'Enter' && saveSpeakerName()}
                    />
                    <button
                      onClick={saveSpeakerName}
                      className="p-1 text-green-400 hover:text-green-300"
                    >
                      <Check className="w-4 h-4" />
                    </button>
                    <button
                      onClick={cancelEditingSpeaker}
                      className="p-1 text-red-400 hover:text-red-300"
                    >
                      <X className="w-4 h-4" />
                    </button>
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
            className="flex items-center gap-2 px-3 py-2 bg-green-600 hover:bg-green-700 rounded-lg transition-colors"
          >
            <Save className="w-4 h-4" />
            Save
          </button>
        ) : (
          <button
            onClick={() => setIsEditing(true)}
            className="flex items-center gap-2 px-3 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors"
          >
            <Edit2 className="w-4 h-4" />
            Edit
          </button>
        )}
        <button
          onClick={() => setShowSearchPanel(!showSearchPanel)}
          className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
            showSearchPanel ? 'bg-orange-500 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
          }`}
        >
          <Search className="w-4 h-4" />
          Search & Replace
        </button>
      </div>

      {/* Search & Replace Panel */}
      {showSearchPanel && (
        <div className="mb-4 p-4 bg-slate-700/30 rounded-xl">
          <div className="flex flex-wrap gap-3 mb-3">
            <div className="flex-1 min-w-[200px]">
              <label className="text-xs text-slate-400 mb-1 block">Search</label>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && performSearch()}
                placeholder="Search text..."
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-400"
              />
            </div>
            <div className="flex-1 min-w-[200px]">
              <label className="text-xs text-slate-400 mb-1 block">Replace with</label>
              <input
                type="text"
                value={replaceText}
                onChange={(e) => setReplaceText(e.target.value)}
                placeholder="Replacement text..."
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-400"
              />
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={performSearch}
              className="flex items-center gap-2 px-3 py-2 bg-blue-500 hover:bg-blue-600 rounded-lg text-white transition-colors"
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
                  className="flex items-center gap-2 px-3 py-2 bg-orange-500 hover:bg-orange-600 rounded-lg text-white transition-colors"
                >
                  <Replace className="w-4 h-4" />
                  Replace All
                </button>
              </>
            )}
            {searchQuery && (
              <button
                onClick={() => { setSearchQuery(''); setReplaceText(''); setSearchResults([]); }}
                className="flex items-center gap-1 px-2 py-2 text-slate-400 hover:text-slate-300 transition-colors"
              >
                <X className="w-4 h-4" />
                Clear
              </button>
            )}
          </div>
        </div>
      )}

      {/* View Toggles */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <button
          onClick={() => setShowTimestamps(!showTimestamps)}
          className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
            showTimestamps ? 'bg-blue-500 text-white' : 'bg-slate-700 text-slate-300'
          }`}
        >
          <Clock className="w-4 h-4" />
          Timestamps
        </button>
        {speakers.length > 0 && (
          <button
            onClick={() => setShowSpeakers(!showSpeakers)}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
              showSpeakers ? 'bg-purple-500 text-white' : 'bg-slate-700 text-slate-300'
            }`}
          >
            <Users className="w-4 h-4" />
            Speakers
          </button>
        )}
      </div>

      {/* Transcription Text */}
      <div className="bg-slate-900/50 rounded-xl p-4 max-h-[32rem] overflow-y-auto">
        {(showTimestamps || showSpeakers) && result.segments ? (
          <div className="space-y-3">
            {result.segments.map((segment, index) => {
              const isCurrentSegment = index === currentSegmentIndex;
              const isEdited = editedSegments[index] !== undefined;

              return (
                <div
                  key={index}
                  ref={el => segmentRefs.current[index] = el}
                  className={`flex gap-3 p-2 rounded transition-all ${
                    isCurrentSegment ? 'bg-blue-500/20 border-l-2 border-blue-400' : ''
                  } ${isEdited ? 'bg-yellow-500/10' : ''}`}
                >
                  {showTimestamps && (
                    <button
                      onClick={() => handleSeek(segment.start)}
                      className="text-blue-400 hover:text-blue-300 font-mono text-sm whitespace-nowrap pt-1 cursor-pointer transition-colors"
                    >
                      [{formatTime(segment.start)}]
                    </button>
                  )}
                  {showSpeakers && segment.speaker && (
                    <span className="text-purple-400 font-medium text-sm whitespace-nowrap pt-1">
                      {speakerNames[segment.speaker] || segment.speaker}:
                    </span>
                  )}
                  {isEditing ? (
                    <input
                      type="text"
                      value={editedSegments[index] !== undefined ? editedSegments[index] : segment.text}
                      onChange={(e) => handleEditSegment(index, e.target.value)}
                      className="flex-1 bg-slate-700 text-slate-200 px-2 py-1 rounded border border-slate-600 focus:outline-none focus:border-blue-400"
                    />
                  ) : (
                    <p className={`text-slate-200 leading-relaxed flex-1 ${searchResults.includes(index) ? 'bg-yellow-500/10 rounded px-1' : ''}`}>
                      {highlightText(editedSegments[index] !== undefined ? editedSegments[index] : segment.text, index)}
                      {searchResults.includes(index) && replaceText && (
                        <button
                          onClick={() => replaceInSegment(index)}
                          className="ml-2 text-xs px-2 py-0.5 bg-orange-500 hover:bg-orange-600 rounded text-white transition-colors"
                        >
                          Replace
                        </button>
                      )}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-slate-200 leading-relaxed whitespace-pre-wrap">
            {result.result}
          </p>
        )}
      </div>
    </div>
  );
}

export default TranscriptView;
