# Onboarding Map Enhancement Plan

## Overview
- Scope focuses on two priorities: richer "講人話" summaries per digest node and a guided onboarding path surfaced in the web UI.
- Execute tasks sequentially; only move to the next item after verifying acceptance criteria for the current one.

## Workstream A — Conversational Summaries
- [ ] Draft narrative schema additions (`narrative.summary`, `narrative.handshake`, `narrative.next_steps`) with sample payloads covering leaf and parent digests.
- [ ] Update `SummaryAggregator` to populate the new narrative fields using existing child digests and direct files metadata; include unit tests capturing edge cases (no children, mixed kinds).
- [ ] Extend analyzer prompt assets (`config/prompt.txt`) to instruct the AI client on desired tone/structure for leaf-level narratives; add regression tests for prompt rendering.
- [ ] Add CLI flag or config toggle to enable/disable narrative generation, defaulting to on; document behavior in `README.md`.
- [ ] Wire the new narrative fields into cache hashing logic to ensure changes invalidate stale digests; verify with targeted cache tests.

## Workstream B — Onboarding Path & Tree Index
- [ ] Define `project_map.json` schema extension to include `tree`, `onboarding_path`, and `recommended_reading` arrays, with validation rules.
- [ ] Implement traversal utility to produce the tree index and onboarding path from existing digest files; cover with unit tests using fixture directories.
- [ ] Expose `/api/project-map` endpoint in `web/server.py` serving the new structure and covering unhappy paths (missing files, malformed JSON) via tests.
- [ ] Update SPA to render the tree index (collapsible list) and highlight the onboarding path; include basic interaction tests (e.g., clicking nodes updates detail view).
- [ ] Add onboarding overlay/CTA in the UI that steps through the recommended path, with copy localized in both zh/eng where applicable.

## Wrap-up
- [ ] Run full quality gates (`black`, `isort`, `flake8`, `mypy`, `pytest`) and capture results in the PR description.
- [ ] Refresh architecture/design docs to reflect the new narrative data and onboarding map flow.
- [ ] Delete this plan file after all tasks are complete and create a PR targeting `main`, ensuring it auto-merges once checks pass.
