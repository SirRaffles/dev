import { useSpeakerCombobox } from '../hooks/useSpeakerCombobox';
import type { UseSpeakerComboboxArgs } from '../hooks/useSpeakerCombobox';

/**
 * Presentation adapter over `useSpeakerCombobox`.
 *
 * Renders the expected-speaker combobox: picked chips, a search input, a
 * dropdown of registry candidates (each with a voice-sample badge) and an
 * inline "create new speaker" affordance. The markup + Tailwind classes are
 * lifted verbatim from SettingsPanel so the visual is unchanged.
 *
 * The surrounding label / count / helper copy stays with each consumer — this
 * component owns only the chips + input + dropdown + create-error, which is
 * exactly the block that used to be duplicated.
 */
export interface SpeakerPickerProps extends UseSpeakerComboboxArgs {
  /** Disable the whole control (e.g. while the parent form is busy). */
  disabled?: boolean;
  /** Placeholder shown when the cap is NOT reached. */
  placeholder?: string;
  /** Placeholder shown when the cap IS reached. */
  capReachedPlaceholder?: string;
  /** aria-label for the search input. */
  searchAriaLabel?: string;
}

export function SpeakerPicker({
  disabled = false,
  placeholder = 'Search or type a new speaker name…',
  capReachedPlaceholder = 'Cap reached — remove one to pick another',
  searchAriaLabel = 'Search expected speakers',
  ...comboboxArgs
}: SpeakerPickerProps) {
  const {
    search,
    setSearch,
    menuOpen,
    setMenuOpen,
    picked,
    filtered,
    capReached,
    canInlineCreate,
    creating,
    createError,
    pickExisting,
    removePick,
    createAndPick,
  } = useSpeakerCombobox(comboboxArgs);

  return (
    <>
      {/* Picked chips */}
      {picked.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2">
          {picked.map((s) => (
            <span
              key={s.speaker_id}
              className="inline-flex items-center gap-1 pl-3 pr-1 py-1 rounded-full text-xs font-medium bg-violet-500 text-white"
            >
              {s.name}
              <button
                type="button"
                onClick={() => removePick(s.speaker_id)}
                aria-label={`Remove ${s.name} from expected speakers`}
                className="w-5 h-5 flex items-center justify-center rounded-full hover:bg-violet-600"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Search + menu */}
      <div className="relative">
        <input
          type="text"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setMenuOpen(true); }}
          onFocus={() => setMenuOpen(true)}
          onBlur={() => setTimeout(() => setMenuOpen(false), 150)}
          disabled={disabled || capReached}
          placeholder={capReached ? capReachedPlaceholder : placeholder}
          aria-label={searchAriaLabel}
          className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm text-slate-900 dark:bg-slate-700 dark:border-slate-600 dark:text-white placeholder-slate-400 focus:outline-none focus:border-violet-400 disabled:opacity-50"
        />
        {menuOpen && !capReached && (filtered.length > 0 || canInlineCreate) && (
          <div className="absolute z-20 left-0 right-0 mt-1 max-h-60 overflow-auto rounded-lg bg-white border border-slate-200 dark:bg-slate-700 dark:border-slate-600 shadow-lg">
            {filtered.map((s) => (
              <button
                key={s.speaker_id}
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => pickExisting(s)}
                className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-600"
              >
                <span className="truncate">{s.name}</span>
                <span
                  className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
                    s.embedding_path
                      ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
                      : 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'
                  }`}
                  title={s.embedding_path ? 'Has a voice sample — will auto-match' : 'No voice sample yet — will be learned from this recording'}
                >
                  {s.embedding_path ? '✓ voice' : '⚠ no voice'}
                </span>
              </button>
            ))}
            {canInlineCreate && (
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={createAndPick}
                disabled={creating}
                className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm border-t border-slate-200 dark:border-slate-600 text-blue-600 dark:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/20 disabled:opacity-60"
              >
                ＋ Create new speaker:&nbsp;<span className="font-medium">{search.trim()}</span>
              </button>
            )}
          </div>
        )}
      </div>

      {createError && (
        <p role="alert" className="text-xs text-red-500 mt-1">{createError}</p>
      )}
    </>
  );
}

export default SpeakerPicker;
