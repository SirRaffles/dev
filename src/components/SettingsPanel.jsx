import React from 'react';
import { FileAudio, Languages, Globe, Users, Clock, Volume2, VolumeX, Cloud, Cpu, BookOpen, Layers } from 'lucide-react';
import { LANGUAGES, MODEL_SIZES, VOXTRAL_MODELS, VOXTRAL_LOCAL_MODELS } from '../utils/api';

function SettingsPanel({
  settings,
  onSettingsChange,
  showForDocuments = false,
  disabled = false,
  voxtralAvailable = false,
  voxtralLocalAvailable = false,
}) {
  const {
    modelSize = 'large-v3-turbo',
    language = 'auto',
    translateToEnglish = false,
    enableDiarization = true,
    numSpeakers = '',
    wordTimestamps = false,
    enableNoiseReduction = false,
    speedPriority = false,
    engine = 'voxtral-local',
    contextTerms = '',
    twoPass = false,
  } = settings;

  const handleChange = (key, value) => {
    onSettingsChange?.({ ...settings, [key]: value });
  };

  const isVoxtralApi = engine === 'voxtral-api';
  const isVoxtralLocal = engine === 'voxtral-local';
  const isWhisper = engine === 'whisper';

  // For document processing, only show relevant settings
  if (showForDocuments) {
    return (
      <div className="mt-6 p-4 bg-slate-700/30 rounded-xl">
        <p className="text-sm text-slate-400 mb-2">
          Document processing will extract text, images, and visual content.
        </p>
        <p className="text-xs text-slate-400">
          Charts and diagrams will be analyzed using GLM-4.6V vision model.
        </p>
      </div>
    );
  }

  return (
    <div className="mt-6 space-y-4">
      {/* Engine Selector */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => {
            if (!voxtralLocalAvailable) return;
            onSettingsChange?.({ ...settings, engine: 'voxtral-local', modelSize: 'voxtral-mini-3b' });
          }}
          disabled={disabled || !voxtralLocalAvailable}
          title={!voxtralLocalAvailable ? 'Install mlx-audio for local Voxtral transcription' : 'Best accuracy (~4% WER), on-device'}
          className={`flex-1 min-w-[100px] flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-all disabled:opacity-50 ${
            isVoxtralLocal
              ? 'bg-teal-500 text-white'
              : 'bg-slate-700 text-slate-300 border border-slate-600 hover:bg-slate-600'
          } ${!voxtralLocalAvailable ? 'cursor-not-allowed' : ''}`}
        >
          <Cpu className="w-4 h-4" />
          Voxtral Local
        </button>
        <button
          onClick={() => {
            onSettingsChange?.({ ...settings, engine: 'whisper', modelSize: 'large-v3-turbo' });
          }}
          disabled={disabled}
          className={`flex-1 min-w-[100px] flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-all disabled:opacity-50 ${
            isWhisper
              ? 'bg-blue-500 text-white'
              : 'bg-slate-700 text-slate-300 border border-slate-600 hover:bg-slate-600'
          }`}
        >
          <Cpu className="w-4 h-4" />
          Whisper
        </button>
        <button
          onClick={() => {
            if (!voxtralAvailable) return;
            onSettingsChange?.({ ...settings, engine: 'voxtral-api', modelSize: 'voxtral-mini' });
          }}
          disabled={disabled || !voxtralAvailable}
          title={!voxtralAvailable ? 'Set MISTRAL_API_KEY to enable Voxtral cloud transcription' : 'Cloud transcription with Mistral Voxtral'}
          className={`flex-1 min-w-[100px] flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-all disabled:opacity-50 ${
            isVoxtralApi
              ? 'bg-violet-500 text-white'
              : 'bg-slate-700 text-slate-300 border border-slate-600 hover:bg-slate-600'
          } ${!voxtralAvailable ? 'cursor-not-allowed' : ''}`}
        >
          <Cloud className="w-4 h-4" />
          Cloud
          {isVoxtralApi && <span className="text-xs opacity-75">$0.003/min</span>}
        </button>
      </div>

      {/* Settings Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Model Size Selection — different options per engine */}
        <div>
          <label className="flex items-center gap-2 text-sm text-slate-400 mb-2">
            <FileAudio className="w-4 h-4" />
            {isVoxtralApi ? 'Cloud Model' : isVoxtralLocal ? 'Local Model' : 'Model Size'}
          </label>
          {isVoxtralApi ? (
            <select
              value={modelSize}
              onChange={(e) => handleChange('modelSize', e.target.value)}
              disabled={disabled}
              className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-violet-400 disabled:opacity-50"
            >
              {Object.entries(VOXTRAL_MODELS).map(([id, { label, description }]) => (
                <option key={id} value={id}>
                  {label} - {description}
                </option>
              ))}
            </select>
          ) : isVoxtralLocal ? (
            <select
              value={modelSize}
              onChange={(e) => handleChange('modelSize', e.target.value)}
              disabled={disabled}
              className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-teal-400 disabled:opacity-50"
            >
              {Object.entries(VOXTRAL_LOCAL_MODELS).map(([id, { label, description }]) => (
                <option key={id} value={id}>
                  {label} - {description}
                </option>
              ))}
            </select>
          ) : (
            <select
              value={modelSize}
              onChange={(e) => handleChange('modelSize', e.target.value)}
              disabled={disabled}
              className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-400 disabled:opacity-50"
            >
              {Object.entries(MODEL_SIZES).map(([id, { label, description, languageRestriction }]) => {
                const isRestricted = languageRestriction && language !== languageRestriction && language !== 'auto';
                const prefix = id === 'parakeet' ? '\u{1F680} ' : '';
                return (
                  <option key={id} value={id} disabled={isRestricted}>
                    {prefix}{label} - {description}{isRestricted ? ' (English only)' : ''}
                  </option>
                );
              })}
            </select>
          )}
          {isWhisper && modelSize === 'parakeet' && language !== 'en' && language !== 'auto' && (
            <p className="text-xs text-amber-400 mt-1">Parakeet requires English. Please select English or Auto-detect.</p>
          )}
        </div>

        {/* Language Selection */}
        <div>
          <label className="flex items-center gap-2 text-sm text-slate-400 mb-2">
            <Languages className="w-4 h-4" />
            Language
          </label>
          <select
            value={language}
            onChange={(e) => {
              const newLang = e.target.value;
              // Batch all changes into a single update to avoid race condition
              const updates = { language: newLang };

              // Reset translation toggle when switching to English
              if (newLang === 'en') {
                updates.translateToEnglish = false;
              }

              // Reset Parakeet model if switching to non-English
              if (isWhisper && modelSize === 'parakeet' && newLang !== 'en' && newLang !== 'auto') {
                updates.modelSize = 'large-v3-turbo';
              }

              // Single state update with all changes
              onSettingsChange?.({ ...settings, ...updates });
            }}
            disabled={disabled}
            className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-400 disabled:opacity-50"
          >
            {Object.entries(LANGUAGES).map(([code, name]) => (
              <option key={code} value={code}>
                {name}
              </option>
            ))}
          </select>
        </div>

        {/* Translate to English Toggle */}
        {language !== 'en' && !isVoxtralApi && (
          <div>
            <label className="flex items-center gap-2 text-sm text-slate-400 mb-2">
              <Globe className="w-4 h-4" />
              Translate to English
            </label>
            <button
              onClick={() => handleChange('translateToEnglish', !translateToEnglish)}
              disabled={disabled}
              className={`w-full px-4 py-3 rounded-lg font-medium transition-all flex items-center justify-center gap-2 disabled:opacity-50 ${
                translateToEnglish
                  ? 'bg-blue-500 text-white'
                  : 'bg-slate-700 text-slate-300 border border-slate-600'
              }`}
            >
              <Globe className="w-4 h-4" />
              {translateToEnglish ? 'Yes - Output in English' : 'No - Keep Original'}
            </button>
          </div>
        )}

        {/* Speaker Diarization — different display for Voxtral vs Whisper */}
        {isVoxtralApi ? (
          <div>
            <label className="flex items-center gap-2 text-sm text-slate-400 mb-2">
              <Users className="w-4 h-4" />
              Speaker Recognition
            </label>
            <div className="w-full px-4 py-3 rounded-lg font-medium bg-violet-500/20 text-violet-300 border border-violet-500/30 flex items-center justify-center gap-2">
              <Users className="w-4 h-4" />
              Built-in (auto-detected)
            </div>
          </div>
        ) : (
          <div>
            <label className="flex items-center gap-2 text-sm text-slate-400 mb-2">
              <Users className="w-4 h-4" />
              Speaker Recognition
            </label>
            <button
              onClick={() => handleChange('enableDiarization', !enableDiarization)}
              disabled={disabled}
              className={`w-full px-4 py-3 rounded-lg font-medium transition-all flex items-center justify-center gap-2 disabled:opacity-50 ${
                enableDiarization
                  ? 'bg-blue-500 text-white'
                  : 'bg-slate-700 text-slate-300 border border-slate-600'
              }`}
            >
              <Users className="w-4 h-4" />
              {enableDiarization ? 'Enabled' : 'Disabled'}
            </button>
          </div>
        )}

        {/* Number of Speakers — only for local engines with diarization */}
        {!isVoxtralApi && enableDiarization && (
          <div>
            <label className="flex items-center gap-2 text-sm text-slate-400 mb-2">
              <Users className="w-4 h-4" />
              Number of Speakers
            </label>
            <select
              value={numSpeakers}
              onChange={(e) => handleChange('numSpeakers', e.target.value)}
              disabled={disabled}
              className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-400 disabled:opacity-50"
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

        {/* Context Terms — Voxtral Cloud only */}
        {isVoxtralApi && (
          <div>
            <label className="flex items-center gap-2 text-sm text-slate-400 mb-2">
              <BookOpen className="w-4 h-4" />
              Context Terms
            </label>
            <input
              type="text"
              value={contextTerms}
              onChange={(e) => handleChange('contextTerms', e.target.value)}
              disabled={disabled}
              placeholder="e.g. FastAPI, MLX, Voxtral"
              className="w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-violet-400 disabled:opacity-50"
            />
            <p className="text-xs text-slate-400 mt-1">Comma-separated domain terms for better accuracy (max 100)</p>
          </div>
        )}

        {/* Two-Pass Mode — Voxtral Cloud only, when language is set */}
        {isVoxtralApi && language !== 'auto' && (
          <div>
            <label className="flex items-center gap-2 text-sm text-slate-400 mb-2">
              <Layers className="w-4 h-4" />
              Two-Pass Mode
            </label>
            <button
              onClick={() => handleChange('twoPass', !twoPass)}
              disabled={disabled}
              className={`w-full px-4 py-3 rounded-lg font-medium transition-all flex items-center justify-center gap-2 disabled:opacity-50 ${
                twoPass
                  ? 'bg-violet-500 text-white'
                  : 'bg-slate-700 text-slate-300 border border-slate-600'
              }`}
            >
              <Layers className="w-4 h-4" />
              {twoPass ? 'Enabled (2x cost)' : 'Disabled'}
            </button>
            <p className="text-xs text-slate-400 mt-1">Timestamps + language accuracy via two API passes</p>
          </div>
        )}

        {/* Word Timestamps Toggle */}
        <div>
          <label className="flex items-center gap-2 text-sm text-slate-400 mb-2">
            <Clock className="w-4 h-4" />
            Word Timestamps
          </label>
          <button
            onClick={() => handleChange('wordTimestamps', !wordTimestamps)}
            disabled={disabled}
            className={`w-full px-4 py-3 rounded-lg font-medium transition-all flex items-center justify-center gap-2 disabled:opacity-50 ${
              wordTimestamps
                ? 'bg-blue-500 text-white'
                : 'bg-slate-700 text-slate-300 border border-slate-600'
            }`}
          >
            <Clock className="w-4 h-4" />
            {wordTimestamps ? 'Enabled (slower)' : 'Disabled (faster)'}
          </button>
        </div>

        {/* Noise Reduction Toggle */}
        <div>
          <label className="flex items-center gap-2 text-sm text-slate-400 mb-2">
            {enableNoiseReduction ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
            Noise Reduction
          </label>
          <button
            onClick={() => handleChange('enableNoiseReduction', !enableNoiseReduction)}
            disabled={disabled}
            className={`w-full px-4 py-3 rounded-lg font-medium transition-all flex items-center justify-center gap-2 disabled:opacity-50 ${
              enableNoiseReduction
                ? 'bg-blue-500 text-white'
                : 'bg-slate-700 text-slate-300 border border-slate-600'
            }`}
          >
            {enableNoiseReduction ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
            {enableNoiseReduction ? 'Enabled' : 'Disabled'}
          </button>
        </div>

        {/* Speed Priority Toggle — only for Whisper */}
        {isWhisper && (
          <div>
            <label className="flex items-center gap-2 text-sm text-slate-400 mb-2">
              <Clock className="w-4 h-4" />
              Speed Priority
            </label>
            <button
              onClick={() => handleChange('speedPriority', !speedPriority)}
              disabled={disabled}
              className={`w-full px-4 py-3 rounded-lg font-medium transition-all flex items-center justify-center gap-2 disabled:opacity-50 ${
                speedPriority
                  ? 'bg-blue-500 text-white'
                  : 'bg-slate-700 text-slate-300 border border-slate-600'
              }`}
            >
              <Clock className="w-4 h-4" />
              {speedPriority ? (language === 'en' ? '60x Speed (English)' : '6x Speed') : 'Off'}
            </button>
            {speedPriority && language === 'en' && (
              <p className="text-xs text-orange-400 mt-1">Uses Parakeet MLX for maximum speed</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default React.memo(SettingsPanel);
