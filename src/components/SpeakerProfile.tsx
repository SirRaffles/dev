import { useRef, useState, useEffect, type ChangeEvent } from 'react';
import {
  ArrowLeft, Save, Loader2, Users, Upload,
  IdCard, Quote, Sparkles, Mic,
} from 'lucide-react';
import {
  fetchSpeaker, SpeakerDetail,
  updateSpeakerProfile, updateSpeakerExplicit, updateSpeakerImplicit,
} from '../utils/api';

interface SpeakerProfileProps {
  speakerId: string;
  onBack: () => void;
}

type SectionKey = 'profile' | 'explicit' | 'implicit';

interface SectionDef {
  key: SectionKey;
  title: string;
  subtitle: string;
  icon: typeof IdCard;
  accent: string;       // tailwind color for header icon
  readOnlyTip?: string; // only the profile accepts upload
}

const SECTIONS: SectionDef[] = [
  {
    key: 'profile',
    title: 'Profile',
    subtitle: 'Factual bio — role, employer, background. You maintain this.',
    icon: IdCard,
    accent: 'text-blue-400',
  },
  {
    key: 'explicit',
    title: 'Explicit insights',
    subtitle: 'Decisions, preferences, facts the speaker said outright. Appended after each call.',
    icon: Quote,
    accent: 'text-emerald-500',
  },
  {
    key: 'implicit',
    title: 'Implicit insights',
    subtitle: 'Inferred style, values, tastes — picked up between the lines. Refined after each call.',
    icon: Sparkles,
    accent: 'text-amber-500',
  },
];

function SpeakerProfile({ speakerId, onBack }: SpeakerProfileProps) {
  const [speaker, setSpeaker] = useState<SpeakerDetail | null>(null);
  const [loading, setLoading] = useState(true);

  // Per-section editable buffers. They're seeded from the server on mount
  // and on explicit Save round-trips, so the user sees their own edits
  // reflected without waiting for a refetch.
  const [buffers, setBuffers] = useState<Record<SectionKey, string>>({
    profile: '', explicit: '', implicit: '',
  });
  const [dirty, setDirty] = useState<Record<SectionKey, boolean>>({
    profile: false, explicit: false, implicit: false,
  });
  const [saving, setSaving] = useState<Record<SectionKey, boolean>>({
    profile: false, explicit: false, implicit: false,
  });
  const [errors, setErrors] = useState<Record<SectionKey, string | null>>({
    profile: null, explicit: null, implicit: null,
  });

  // Upload only applies to Profile (bio) per product spec. Ref shared is fine
  // since we only ever dispatch one file picker at a time.
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    setLoading(true);
    fetchSpeaker(speakerId)
      .then((data) => {
        setSpeaker(data);
        setBuffers({
          profile: data.profile_md || '',
          explicit: data.explicit_insights_md || '',
          implicit: data.implicit_insights_md || data.personality_md || '',
        });
        setDirty({ profile: false, explicit: false, implicit: false });
      })
      .finally(() => setLoading(false));
  }, [speakerId]);

  const onEdit = (key: SectionKey, value: string) => {
    setBuffers((b) => ({ ...b, [key]: value }));
    setDirty((d) => ({ ...d, [key]: true }));
  };

  const saveSection = async (key: SectionKey) => {
    setSaving((s) => ({ ...s, [key]: true }));
    setErrors((e) => ({ ...e, [key]: null }));
    try {
      const writer =
        key === 'profile' ? updateSpeakerProfile
        : key === 'explicit' ? updateSpeakerExplicit
        : updateSpeakerImplicit;
      await writer(speakerId, buffers[key]);
      setDirty((d) => ({ ...d, [key]: false }));
    } catch (err: any) {
      setErrors((e) => ({ ...e, [key]: err?.message || 'Save failed' }));
    } finally {
      setSaving((s) => ({ ...s, [key]: false }));
    }
  };

  const uploadIntoProfile = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (fileInputRef.current) fileInputRef.current.value = '';
    if (!file) return;
    const ext = file.name.toLowerCase().match(/\.[^.]+$/)?.[0] || '';
    if (!['.md', '.txt'].includes(ext)) {
      setErrors((e) => ({ ...e, profile: 'Only .md and .txt files are supported' }));
      return;
    }
    if (file.size > 1_000_000) {
      setErrors((e) => ({ ...e, profile: 'File too large (max 1 MB)' }));
      return;
    }
    setErrors((e) => ({ ...e, profile: null }));
    try {
      const text = await file.text();
      const separator = buffers.profile.trim() ? `\n\n---\n\n` : '';
      setBuffers((b) => ({ ...b, profile: `${b.profile}${separator}${text.trim()}\n` }));
      setDirty((d) => ({ ...d, profile: true }));
    } catch (err: any) {
      setErrors((e) => ({ ...e, profile: err?.message || 'Failed to read file' }));
    }
  };

  if (loading) {
    return (
      <div className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-6 border border-slate-200 dark:border-slate-700">
        <div className="flex items-center justify-center py-12 text-slate-400">
          <Loader2 className="w-6 h-6 animate-spin mr-2" aria-hidden="true" /> Loading…
        </div>
      </div>
    );
  }

  if (!speaker) return null;

  return (
    <div className="space-y-4">
      {/* Header — identity + voice status */}
      <div className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-4 sm:p-6 border border-slate-200 dark:border-slate-700 shadow-sm dark:shadow-none">
        <div className="flex items-center gap-3 mb-4">
          <button
            type="button"
            onClick={onBack}
            aria-label="Back to speakers"
            className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" aria-hidden="true" />
          </button>
          <div className="w-12 h-12 rounded-full bg-blue-500/20 flex items-center justify-center text-blue-500 font-bold text-lg">
            {speaker.name.charAt(0).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-xl font-semibold truncate">{speaker.name}</h2>
            <p className="text-sm text-slate-400 flex items-center gap-2 flex-wrap">
              <span>{speaker.call_count || 0} call{speaker.call_count === 1 ? '' : 's'}</span>
              <span>·</span>
              <span className={`inline-flex items-center gap-1 ${speaker.has_embedding ? 'text-emerald-500' : 'text-amber-500'}`}>
                <Mic className="w-3.5 h-3.5" aria-hidden="true" />
                {speaker.has_embedding ? 'voice registered' : 'no voice sample yet'}
              </span>
            </p>
          </div>
        </div>

        {speaker.calls && speaker.calls.length > 0 && (
          <div className="mt-4">
            <h3 className="text-sm font-medium text-slate-500 mb-2">Recent calls</h3>
            <div className="space-y-1">
              {speaker.calls.slice(0, 5).map((c: any) => (
                <div key={c.call_id} className="text-xs text-slate-400 py-1">
                  {String(c.call_id).slice(0, 8)} · {(Number(c.confidence || 0) * 100).toFixed(0)}% confidence
                  {c.confirmed ? ' \u2713' : ''}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Four cards — one per profile section. Voice is already represented in
          the header badge above (it's read-only here; the embedding is managed
          by the transcription pipeline). */}
      {SECTIONS.map((section) => {
        const Icon = section.icon;
        const showUpload = section.key === 'profile';
        return (
          <div
            key={section.key}
            className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-4 sm:p-6 border border-slate-200 dark:border-slate-700 shadow-sm dark:shadow-none"
          >
            <div className="flex items-center justify-between mb-1 gap-2 flex-wrap">
              <h3 className="font-semibold flex items-center gap-2">
                <Icon className={`w-5 h-5 ${section.accent}`} aria-hidden="true" />
                {section.title}
              </h3>
              <div className="flex items-center gap-2">
                {showUpload && (
                  <>
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      aria-label="Upload .md or .txt into bio"
                      title="Append a .md or .txt file"
                      className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600"
                    >
                      <Upload className="w-4 h-4" aria-hidden="true" />
                      Upload
                    </button>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".md,.txt,text/markdown,text/plain"
                      onChange={uploadIntoProfile}
                      className="hidden"
                    />
                  </>
                )}
                {dirty[section.key] && (
                  <button
                    type="button"
                    onClick={() => saveSection(section.key)}
                    disabled={saving[section.key]}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 disabled:opacity-50"
                  >
                    {saving[section.key]
                      ? <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
                      : <Save className="w-4 h-4" aria-hidden="true" />}
                    Save
                  </button>
                )}
              </div>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">{section.subtitle}</p>
            {errors[section.key] && (
              <div role="alert" className="mb-3 text-xs text-red-500 dark:text-red-400">
                {errors[section.key]}
              </div>
            )}
            <textarea
              value={buffers[section.key]}
              onChange={(e) => onEdit(section.key, e.target.value)}
              aria-label={section.title}
              className="w-full h-56 bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-600 rounded-xl p-4 text-sm font-mono leading-relaxed resize-y focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder={
                section.key === 'profile'
                  ? 'Bio, role, employer, focus areas… type or Upload.'
                  : section.key === 'explicit'
                    ? 'Will populate automatically after calls. You can also curate manually.'
                    : 'Will populate automatically after calls. Feel free to refine.'
              }
            />
          </div>
        );
      })}

      {/* Silence the unused-var warning on the header icon symbol. */}
      <div className="sr-only">
        <Users aria-hidden="true" />
      </div>
    </div>
  );
}

export default SpeakerProfile;
