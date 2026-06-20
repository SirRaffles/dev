import React, { useEffect, useMemo, useState } from 'react';
import { Languages, Globe, Users, Volume2, VolumeX, FolderOpen, Shield, Sparkles } from 'lucide-react';
import { LANGUAGES, fetchContextTree, ContextTree, fetchSpeakers, createSpeaker, Speaker } from '../utils/api';
import QualityDial, { QualityMode } from './QualityDial';
import { SpeakerPicker } from './SpeakerPicker';

interface Settings {
  language?: string;
  translateToEnglish?: boolean;
  enableDiarization?: boolean;
  numSpeakers?: string;
  enableNoiseReduction?: boolean;
  engine?: QualityMode;          // 'auto-best' | 'auto-quick'
  contextPath?: string;          // path under CONTEXTS_DIR to a .md file or folder
  speakerIds?: string[];         // expected speakers — their personality.md feeds the prompt
  refinementMode?: 'auto' | 'always' | 'off';
  autoRefine?: boolean | null;   // null/undefined = Auto, true = Always, false = Off
  [key: string]: any;
}

interface SettingsPanelProps {
  settings: Settings;
  onSettingsChange?: (settings: Settings) => void;
  showForDocuments?: boolean;
  disabled?: boolean;
}

function SettingsPanel({
  settings,
  onSettingsChange,
  showForDocuments = false,
  disabled = false,
}: SettingsPanelProps) {
  const {
    language = 'auto',
    translateToEnglish = false,
    enableDiarization = true,
    numSpeakers = '',
    enableNoiseReduction = false,
    engine = 'auto-best',
    contextPath = '',
    speakerIds = [] as string[],
    autoRefine = null,
    refinementMode = autoRefine === true ? 'always' : autoRefine === false ? 'off' : 'auto',
  } = settings;

  const handleChange = (key: string, value: any) => {
    onSettingsChange?.({ ...settings, [key]: value });
  };

  // Lazily fetch the context tree so the dropdown can offer available
  // context folders / files. Errors are silent — the dropdown just stays
  // empty and the user can still submit without a context.
  const [contextOptions, setContextOptions] = useState<{ path: string; label: string }[]>([]);
  useEffect(() => {
    let cancelled = false;
    fetchContextTree()
      .then((tree) => {
        if (cancelled) return;
        const flat: { path: string; label: string }[] = [];
        const walk = (node: ContextTree, depth = 0) => {
          if (node.path) {
            flat.push({ path: node.path, label: `${'· '.repeat(depth - 1)}${node.name}`.trim() });
          }
          (node.children || []).forEach((child) => walk(child, depth + 1));
        };
        tree.forEach((n) => walk(n, 1));
        setContextOptions(flat);
      })
      .catch(() => { /* ignore; dropdown stays empty */ });
    return () => { cancelled = true; };
  }, []);

  // Pull the list of registered speakers once so the "Expected speakers" picker
  // can show who's available to attach pre-transcription context from.
  const [speakersAvailable, setSpeakersAvailable] = useState<Speaker[]>([]);
  useEffect(() => {
    let cancelled = false;
    fetchSpeakers()
      .then((list) => { if (!cancelled) setSpeakersAvailable(list); })
      .catch(() => { /* silent — picker just stays empty */ });
    return () => { cancelled = true; };
  }, []);

  // Integer num_speakers gates the picker (used as the combobox cap).
  const parsedNumSpeakers = useMemo(() => {
    if (numSpeakers === '' || numSpeakers === 'auto') return null;
    const n = parseInt(String(numSpeakers), 10);
    return Number.isFinite(n) && n > 0 ? n : null;
  }, [numSpeakers]);

  // Inline-create: make the speaker, refresh the registry so the picked chip
  // resolves, and hand its id back to the shared combobox to append.
  const handleCreateSpeaker = async (name: string): Promise<string> => {
    const created = await createSpeaker(name);
    const list = await fetchSpeakers();
    setSpeakersAvailable(list);
    return created.speaker_id;
  };

  // For document processing, only show relevant settings
  if (showForDocuments) {
    return (
      <div className="mt-6 p-4 bg-slate-100 dark:bg-slate-700/30 rounded-xl">
        <p className="text-sm text-slate-600 dark:text-slate-400 mb-2">
          Document processing will extract text, images, and visual content.
        </p>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Charts and diagrams will be analyzed using the configured MLX-VLM vision model.
        </p>
      </div>
    );
  }

  const safeEngine: QualityMode = engine === 'auto-quick' ? 'auto-quick' : 'auto-best';

  return (
    <div className="mt-6 space-y-4">
      {/* Quality Dial — replaces engine selector + model dropdown */}
      <QualityDial
        value={safeEngine}
        onChange={(next) => handleChange('engine', next)}
        disabled={disabled}
      />

      {/* Privacy Notice for Refinement */}
      {safeEngine === 'auto-best' && (
        <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-100 dark:border-blue-800/30 flex gap-3">
          <Shield className="w-5 h-5 text-blue-500 flex-shrink-0" />
          <div className="text-xs text-blue-700 dark:text-blue-300">
            <p className="font-semibold mb-1">Privacy Notice: Transcript Refinement</p>
            <p>
              The 'Best' pipeline uses Claude Sonnet to identify speakers and correct technical terms.
              If enabled by your administrator, uncertain terms may be verified via DuckDuckGo search
              to ensure spelling accuracy. No audio data or PII is sent to external search engines.
            </p>
          </div>
        </div>
      )}

      {/* Settings Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Language Selection */}
        <div>
          <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 mb-2">
            <Languages className="w-4 h-4" />
            Language
          </label>
          <select
            value={language}
            onChange={(e) => {
              const newLang = e.target.value;
              const updates: Settings = { language: newLang };
              if (newLang === 'en') {
                updates.translateToEnglish = false;
              }
              onSettingsChange?.({ ...settings, ...updates });
            }}
            disabled={disabled}
            className="w-full px-4 py-3 bg-white border border-slate-300 rounded-lg text-slate-900 dark:bg-slate-700 dark:border-slate-600 dark:text-white focus:outline-none focus:border-blue-400 disabled:opacity-50"
          >
            {Object.entries(LANGUAGES).map(([code, name]) => (
              <option key={code} value={code}>
                {name}
              </option>
            ))}
          </select>
        </div>

        {/* Translate to English Toggle */}
        {language !== 'en' && (
          <div>
            <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 mb-2">
              <Globe className="w-4 h-4" />
              Translate to English
            </label>
            <button
              onClick={() => handleChange('translateToEnglish', !translateToEnglish)}
              disabled={disabled}
              className={`w-full px-4 py-3 rounded-lg font-medium transition-all flex items-center justify-center gap-2 disabled:opacity-50 ${
                translateToEnglish
                  ? 'bg-blue-500 text-white'
                  : 'bg-slate-200 text-slate-600 border border-slate-300 dark:bg-slate-700 dark:text-slate-300 dark:border-slate-600'
              }`}
            >
              <Globe className="w-4 h-4" />
              {translateToEnglish ? 'Yes - Output in English' : 'No - Keep Original'}
            </button>
          </div>
        )}

        {/* Speaker Diarization */}
        <div>
          <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 mb-2">
            <Users className="w-4 h-4" />
            Speaker Recognition
          </label>
          <button
            onClick={() => handleChange('enableDiarization', !enableDiarization)}
            disabled={disabled}
            className={`w-full px-4 py-3 rounded-lg font-medium transition-all flex items-center justify-center gap-2 disabled:opacity-50 ${
              enableDiarization
                ? 'bg-blue-500 text-white'
                : 'bg-slate-200 text-slate-600 border border-slate-300 dark:bg-slate-700 dark:text-slate-300 dark:border-slate-600'
            }`}
          >
            <Users className="w-4 h-4" />
            {enableDiarization ? 'Enabled' : 'Disabled'}
          </button>
        </div>

        {/* Number of Speakers — gated on diarization being on */}
        {enableDiarization && (
          <div>
            <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 mb-2">
              <Users className="w-4 h-4" />
              Number of Speakers
            </label>
            <select
              value={numSpeakers}
              onChange={(e) => handleChange('numSpeakers', e.target.value)}
              disabled={disabled}
              className="w-full px-4 py-3 bg-white border border-slate-300 rounded-lg text-slate-900 dark:bg-slate-700 dark:border-slate-600 dark:text-white focus:outline-none focus:border-blue-400 disabled:opacity-50"
            >
              <option value="">Auto-detect</option>
              <option value="1">1 speaker</option>
              <option value="2">2 speakers</option>
              <option value="3">3 speakers</option>
              <option value="4">4 speakers</option>
              <option value="5">5 speakers</option>
              <option value="6">6+ speakers</option>
            </select>
          </div>
        )}

        {/* Context Document */}
        <div>
          <label
            htmlFor="context-path-select"
            className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 mb-2"
          >
            <FolderOpen className="w-4 h-4" aria-hidden="true" />
            Context
          </label>
          <select
            id="context-path-select"
            value={contextPath}
            onChange={(e) => handleChange('contextPath', e.target.value)}
            disabled={disabled}
            className="w-full px-4 py-3 bg-white border border-slate-300 rounded-lg text-slate-900 dark:bg-slate-700 dark:border-slate-600 dark:text-white focus:outline-none focus:border-violet-400 disabled:opacity-50"
          >
            <option value="">None — no context document</option>
            {contextOptions.map((c) => (
              <option key={c.path} value={c.path}>{c.label || c.path}</option>
            ))}
          </select>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Attach a context document (glossary, acronyms, background) from your Contexts library to bias transcription. Optional.
          </p>
        </div>

        {/* Refinement Mode */}
        <div>
          <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 mb-2">
            <Sparkles className="w-4 h-4" />
            Refinement
          </label>
          <div className="grid grid-cols-3 rounded-lg border border-slate-300 dark:border-slate-600 overflow-hidden">
            {[
              { label: 'Auto', value: null },
              { label: 'Always', value: true },
              { label: 'Off', value: false },
            ].map((option) => {
              const mode = option.value === true ? 'always' : option.value === false ? 'off' : 'auto';
              const active = refinementMode === mode;
              return (
                <button
                  key={option.label}
                  type="button"
                  onClick={() => handleChange('refinementMode', mode)}
                  disabled={disabled}
                  className={`px-2 py-3 text-sm font-medium transition-colors disabled:opacity-50 ${
                    active
                      ? 'bg-blue-500 text-white'
                      : 'bg-white text-slate-600 hover:bg-slate-50 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600'
                  }`}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Noise Reduction (migrated out of removed Advanced block) */}
        <div>
          <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 mb-2">
            {enableNoiseReduction ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
            Noise Reduction
          </label>
          <button
            onClick={() => handleChange('enableNoiseReduction', !enableNoiseReduction)}
            disabled={disabled}
            className={`w-full px-4 py-3 rounded-lg font-medium transition-all flex items-center justify-center gap-2 disabled:opacity-50 ${
              enableNoiseReduction
                ? 'bg-blue-500 text-white'
                : 'bg-slate-200 text-slate-600 border border-slate-300 dark:bg-slate-700 dark:text-slate-300 dark:border-slate-600'
            }`}
          >
            {enableNoiseReduction ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
            {enableNoiseReduction ? 'Enabled' : 'Disabled'}
          </button>
        </div>

        {/* Expected Speakers — searchable combobox with inline-create.
            Only surfaces when diarization is on AND the user set an explicit
            speaker count (so we can cap picks). Each pick seeds the decoder's
            initial_prompt with the speaker's personality.md, AND narrows the
            post-transcription voice auto-match scope. */}
        {enableDiarization && (
          <div>
            <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 mb-2">
              <Users className="w-4 h-4" aria-hidden="true" />
              Expected Speakers
              {parsedNumSpeakers !== null && (
                <span className="text-xs text-slate-400 font-normal">
                  ({speakerIds.length}/{parsedNumSpeakers})
                </span>
              )}
            </label>

            {parsedNumSpeakers === null ? (
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Pick a specific speaker count above to enable pre-selection.
                Voice auto-match will run against your full speaker registry.
              </p>
            ) : (
              <>
                <SpeakerPicker
                  candidates={speakersAvailable}
                  pickedIds={speakerIds}
                  cap={parsedNumSpeakers}
                  disabled={disabled}
                  onPick={(id) => handleChange('speakerIds', [...speakerIds, id])}
                  onRemove={(id) => handleChange('speakerIds', speakerIds.filter((sid) => sid !== id))}
                  onCreate={handleCreateSpeaker}
                />
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">
                  Picks bias the transcription prompt AND narrow post-transcription voice auto-match.
                  {speakerIds.length === parsedNumSpeakers
                    ? ' Auto-match will be scoped to just these picks.'
                    : ' Partial picks: auto-match runs against the full registry with these as tiebreaker.'}
                </p>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default React.memo(SettingsPanel);
