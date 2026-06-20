import { useMemo, useState } from 'react';
import type { Speaker } from '../utils/api';

/**
 * Shared state machine for the expected-speaker combobox.
 *
 * Extracted verbatim from SettingsPanel's inline picker so both the
 * SettingsPanel "Expected Speakers" combobox and (via SpeakerPicker) any
 * other consumer share ONE implementation of: search filtering, the
 * max-speaker cap, exact-match detection, inline-create gating, and the
 * pick / remove / create-and-pick handlers.
 *
 * The hook owns NO data fetching — the candidate list and the inline-create
 * callback are injected by the caller. The candidate shape is the real
 * registry `Speaker` (so consumers keep access to `embedding_path` for the
 * voice badge, etc.).
 */
export type SpeakerCandidate = Speaker;

export interface UseSpeakerComboboxArgs {
  /** Full registry of speakers available to pick from. */
  candidates: SpeakerCandidate[];
  /** Currently picked speaker ids. */
  pickedIds: string[];
  /** Max number of picks; `null`/`undefined` = no cap. */
  cap?: number | null;
  /** Append a pick. */
  onPick: (id: string) => void;
  /** Remove a pick. */
  onRemove: (id: string) => void;
  /**
   * Create a brand-new speaker by name and resolve to its id. The caller
   * owns the API call + any registry refresh; the hook only sequences the
   * "create then pick" interaction and surfaces creating/error state.
   */
  onCreate: (name: string) => Promise<string>;
}

export interface UseSpeakerCombobox {
  search: string;
  setSearch: (s: string) => void;
  menuOpen: boolean;
  setMenuOpen: (b: boolean) => void;
  /** Picked speakers, resolved against `candidates`, in `pickedIds` order. */
  picked: SpeakerCandidate[];
  /** Candidates not yet picked, filtered by the search query. */
  filtered: SpeakerCandidate[];
  capReached: boolean;
  /** A registry speaker whose name exactly matches the trimmed search. */
  exactMatch: SpeakerCandidate | undefined;
  canInlineCreate: boolean;
  creating: boolean;
  createError: string | null;
  pickExisting: (c: SpeakerCandidate) => void;
  removePick: (id: string) => void;
  createAndPick: () => Promise<void>;
}

export function useSpeakerCombobox(args: UseSpeakerComboboxArgs): UseSpeakerCombobox {
  const { candidates, pickedIds, cap, onPick, onRemove, onCreate } = args;

  const [search, setSearch] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const picked = useMemo(
    () => candidates.filter((s) => pickedIds.includes(s.speaker_id)),
    [candidates, pickedIds],
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return candidates
      .filter((s) => !pickedIds.includes(s.speaker_id))
      .filter((s) => !q || s.name.toLowerCase().includes(q));
  }, [candidates, pickedIds, search]);

  const capReached = cap != null && pickedIds.length >= cap;

  const exactMatch = candidates.find(
    (s) => s.name.toLowerCase() === search.trim().toLowerCase(),
  );
  const canInlineCreate = search.trim().length > 0 && !exactMatch && !capReached;

  const pickExisting = (s: SpeakerCandidate) => {
    if (capReached) return;
    onPick(s.speaker_id);
    setSearch('');
    setMenuOpen(false);
  };

  const removePick = (id: string) => {
    onRemove(id);
  };

  const createAndPick = async () => {
    const name = search.trim();
    if (!name || capReached || creating) return;
    setCreating(true);
    setCreateError(null);
    try {
      const createdId = await onCreate(name);
      onPick(createdId);
      setSearch('');
      setMenuOpen(false);
    } catch (e: any) {
      setCreateError(e?.message || 'Could not create speaker');
    } finally {
      setCreating(false);
    }
  };

  return {
    search,
    setSearch,
    menuOpen,
    setMenuOpen,
    picked,
    filtered,
    capReached,
    exactMatch,
    canInlineCreate,
    creating,
    createError,
    pickExisting,
    removePick,
    createAndPick,
  };
}
