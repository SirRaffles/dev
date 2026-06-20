# ADR 0001 — Keep `state.jobs` and `state.job_store` as distinct names

**Status:** Accepted (2026-06-20)

## Context

`backend/state.py` defines the job store once and binds two module-level names to
the same object:

```python
job_store = JobStore(DB_PATH)
jobs = job_store  # legacy compatibility alias
```

In production the two names are the *same object*, so reads and writes are
identical. They diverge only under `monkeypatch.setattr`, which rebinds one name
without touching the other. The test suite relies on this: different code paths
were written against different names, and each path's tests patch the name that
path uses. Concretely:

- `state.jobs` is patched by `test_learning_orchestrator.py`, `test_transcription_a1.py`,
  and the refinement-worker tests. The writer-side convention (`_run_transcription_sync`,
  the refinement worker) reads `state.jobs`.
- `state.job_store` is patched by `test_auto_refine_orchestration.py`,
  `test_refinement_context.py`, and parts of `test_orchestrator.py`.

The S6 `app_state` façade had to mirror this split: it exposes BOTH `jobs()`
(→ `state.jobs`) and `job_store()` (→ `state.job_store`), and each migrated call
site uses the accessor matching the name it originally read. A single accessor
collapsing the two broke 6 tests (see the S6 slice).

A periodic architecture review will keep surfacing this as a candidate to
"unify the alias" — it looks like accidental duplication. This ADR records why
we are *not* doing that now.

## Decision

Keep `state.jobs` and `state.job_store` as two distinct names, and keep the
`app_state` façade's `jobs()` / `job_store()` split. Do not collapse them.

## Consequences

- **Positive:** the existing test suite (which is the behaviour spec for the
  refinement / learning / orchestration paths) stays valid without rewrites.
  Each code path keeps reading the name its tests patch.
- **Negative:** the two-name split is a real ambiguity. A newcomer can read
  `state.jobs` in one function and `state.job_store` in another and assume they
  can differ at runtime — they cannot, except under test monkeypatching.
- **If we ever revisit:** unifying is a `state.py`-level change that must land
  *together* with a sweep of every test that patches either name onto a single
  convention (likely `state.job_store`, with `jobs` removed). It is a
  test-migration project, not a one-line rename, and it carries regression risk
  on the refinement/learning paths. Only take it on with that full scope in view.

## References

- S6 slice (`app_state` façade) — the split-accessor fix.
- `backend/app_state.py` `jobs()` / `job_store()`.
- `backend/services/refinement_dispatch.py` — in-code comments documenting the
  `state.jobs` (NOT `state.job_store`) writer-side convention.
