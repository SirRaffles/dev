# Backlog — rename recording file with LLM-suggested name

**Status:** Captured, awaiting brainstorm
**Captured:** 2026-05-17
**Trigger:** User feature request during Plan 3 manual validation

## Intent

After a recording is transcribed and refined, the user should be able to rename the underlying audio file itself — not just the in-app display label — and the app should propose a meaningful name derived from the transcription content (call topic, participants, salient terms).

Today, JPR audio files arrive with timestamp-only names like `15-29-21.m4a` and stay that way forever. Finding "the call where Pascal explained Manukai's SAFc partnership" requires opening transcripts. A content-derived filename would make audio files self-describing in Finder, iCloud, Syncthing, etc.

## Why this matters

- **Discoverability outside the app**: timestamps say nothing; the audio files live in iCloud and get backed up, copied, shared. Self-naming makes them legible at every layer.
- **Spec-aligned reuse of existing capabilities**: refinement already extracts `domain` and `summary` fields (`backend/services/refinement.py:35-44` ANALYSIS_SCHEMA). The LLM is already producing the data needed to name the file — we just don't propose it as a filename anywhere.
- **Continues the "self-improving system" arc** of B' v2: B7 surfaces what was learned; this surfaces what the call was about.

## Rough shape (pre-brainstorm — not a spec)

- A "Rename file" action somewhere in the post-job UI (TranscriptView header? Recordings list?) that:
  - Shows the current filename.
  - Shows 1-3 suggested names derived from `analysis.domain` + `analysis.summary` + the speakers list.
  - Lets the user pick a suggestion or edit one.
  - Renames the file on disk (iCloud / JPR folder) AND updates any in-app indexes (job.file_path, RefinementStore audit trail, learning_log entries that reference the old path?).
- Naming convention to brainstorm: `YYYY-MM-DD HH-MM — <topic> with <speakers>.m4a`? Or `<speakers> — <topic>.m4a`?

## Open questions for brainstorm

1. Scope of rename — JPR audio only (`JPR_WATCH_PATH`), or any uploaded file? Direct uploads land in `/tmp` and get deleted; nothing to rename. So this is effectively a JPR-only feature, which is what the user does most of the time anyway.
2. Where in the UI — TranscriptView header (next to RefinementBadge)? Recordings tab list (rename without opening)? Post-job toast ("Refined. Rename this file?")?
3. Automatic vs proposed-only — should refinement-completion AUTO-rename, or only propose? Defaults are sticky; the conservative choice is propose-only.
4. Conflict handling — what if the proposed name already exists? Append `(2)`?
5. Audit trail — does the file's original timestamp-name still matter (e.g. for ordering in JPR's own UI)? If yes, store as a metadata sidecar (`<filename>.original-name`) before renaming.
6. Index propagation — `job.file_path`, `job.settings.original_filename`, JPR state file (`~/.jpr_watcher_state.json`), Recordings tab cache. Audit each consumer before shipping.
7. iCloud sync race — Syncthing-watched dirs. Renaming a file mid-sync can produce duplicates. Probably fine because iCloud detects renames, but worth testing.

## Cross-references

- `backend/services/refinement.py` — `ANALYSIS_SCHEMA` already includes `domain` and `summary`.
- `backend/routes/jpr.py` — JPR file enumeration; rename-target endpoint would live here or in a new `routes/recordings.py`.
- `backend/job_models.py` — `TranscriptionSettings.original_filename` already tracks the source name for JPR jobs.
- `~/Library/Mobile Documents/com~apple~CloudDocs/Davrine Transcription/Just Press Record/` — typical recording location.
- Plan 3's `docs/superpowers/audits/2026-05-15-ux-touchpoints.md` — pattern for next audit when this enters planning.

## Next step

When ready, run `/brainstorm` on this file to produce a spec. Then `/writing-plans` to produce an implementation plan. Likely small — single endpoint + small UI action.
