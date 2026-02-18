import React, { useState, useEffect } from 'react';
import { ArrowLeft, Save, Loader2, Users } from 'lucide-react';
import { fetchSpeaker, updateSpeakerPersonality } from '../utils/api';

interface SpeakerProfileProps {
  speakerId: string;
  onBack: () => void;
}

function SpeakerProfile({ speakerId, onBack }: SpeakerProfileProps) {
  const [speaker, setSpeaker] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [personality, setPersonality] = useState('');
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetchSpeaker(speakerId)
      .then((data) => {
        setSpeaker(data);
        setPersonality(data.personality_md || '');
      })
      .finally(() => setLoading(false));
  }, [speakerId]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateSpeakerPersonality(speakerId, personality);
      setDirty(false);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-6 border border-slate-200 dark:border-slate-700">
        <div className="flex items-center justify-center py-12 text-slate-400">
          <Loader2 className="w-6 h-6 animate-spin mr-2" /> Loading...
        </div>
      </div>
    );
  }

  if (!speaker) return null;

  return (
    <div className="space-y-4">
      <div className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-4 sm:p-6 border border-slate-200 dark:border-slate-700 shadow-sm dark:shadow-none">
        <div className="flex items-center gap-3 mb-4">
          <button onClick={onBack} className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="w-12 h-12 rounded-full bg-blue-500/20 flex items-center justify-center text-blue-500 font-bold text-lg">
            {speaker.name.charAt(0).toUpperCase()}
          </div>
          <div>
            <h2 className="text-xl font-semibold">{speaker.name}</h2>
            <p className="text-sm text-slate-400">
              {speaker.call_count || 0} calls &middot; {speaker.has_embedding ? 'Voice registered' : 'No voice embedding'}
            </p>
          </div>
        </div>

        {speaker.calls && speaker.calls.length > 0 && (
          <div className="mt-4">
            <h3 className="text-sm font-medium text-slate-500 mb-2">Recent Calls</h3>
            <div className="space-y-1">
              {speaker.calls.slice(0, 5).map((c: any) => (
                <div key={c.call_id} className="text-xs text-slate-400 py-1">
                  {c.call_id.slice(0, 8)} &middot; {(c.confidence * 100).toFixed(0)}% confidence
                  {c.confirmed ? ' \u2713' : ''}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-4 sm:p-6 border border-slate-200 dark:border-slate-700 shadow-sm dark:shadow-none">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold flex items-center gap-2">
            <Users className="w-5 h-5 text-blue-400" /> Personality Profile
          </h3>
          {dirty && (
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 disabled:opacity-50"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              Save
            </button>
          )}
        </div>
        <textarea
          value={personality}
          onChange={(e) => { setPersonality(e.target.value); setDirty(true); }}
          className="w-full h-80 bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-600 rounded-xl p-4 text-sm font-mono leading-relaxed resize-y focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="No personality insights yet. These will accrue as calls are analyzed."
        />
      </div>
    </div>
  );
}

export default SpeakerProfile;
