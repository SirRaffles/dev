// Diarization emits generic labels like SPEAKER_00 / "Speaker 1". Anything
// that matches this shape is still waiting for a real name.
const ANON_SPEAKER_RE = /^(?:SPEAKER_\d+|Speaker\s*\d+|Unknown)$/i;

export const isAnonymousLabel = (name: string | null | undefined) =>
  !name ? true : ANON_SPEAKER_RE.test(name.trim());
