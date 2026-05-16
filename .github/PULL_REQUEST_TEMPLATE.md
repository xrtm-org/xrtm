## Description
Please include a summary of the change and which issue is fixed. Please also include relevant motivation and context.

Fixes # (issue)

## Type of change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] This change requires a documentation update

## How Has This Been Tested?
Please describe the tests that you ran to verify your changes.

- [ ] `python scripts/check_release_claims.py --repo-root . --contract docs/release-command-contract.json --scope xrtm`
- [ ] `uv run pytest tests`
- [ ] `uv run ruff check .`
- [ ] `uv run mypy src/xrtm`
- [ ] `uv run --with build python -m build`
- [ ] Provider-free clean-room evidence recorded when published-surface or release-readiness behavior changed (CI release-validation artifact or stack `acceptance-studies/docker-provider-free/.../summary.json`)
- [ ] Local-LLM clean-room evidence recorded for local-model changes, or an explicit defer note explains why that lane stays manual/not applicable

## Published surface impact

- Release-pinned docs touched: <!-- README / getting-started / operator / xrtm.org mirror, or N/A -->
- Stable surface changed: <!-- CLI / Python API / run artifact / install-version expectation / N/A -->
- Next-release track updated: <!-- row updated in docs/next-release-feature-track.md, N/A, or why not -->

## Cross-repo coordination
Complete this section when the PR changes contracts, packaging/version expectations, CI sibling refs, or release sequencing.

- Coordination record: <!-- issue / PR family / release-train note with anchor xrtm version and explicit sibling refs, or N/A -->
- Release clean-room evidence: <!-- provider-free workflow artifact / summary.json path, local-LLM note if applicable, or N/A -->
- Upstream refs validated:
  - `xrtm-data`: <!-- branch / tag / SHA / PR ref, or N/A -->
  - `xrtm-eval`: <!-- branch / tag / SHA / PR ref, or N/A -->
  - `xrtm-forecast`: <!-- branch / tag / SHA / PR ref, or N/A -->
  - `xrtm-train`: <!-- branch / tag / SHA / PR ref, or N/A -->
- Downstream follow-up:
  - `xrtm.org`: <!-- PR / workflow run / release note, or N/A -->

## Checklist:
- [ ] My code follows the style guidelines of this project
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] Release-pinned docs stay on the published package surface, or the change is explicitly labeled next-release/advanced elsewhere
- [ ] Release-train notes and published-surface claims use explicit package versions or refs per the stack versioning policy
- [ ] Coordinated validation, when needed, uses explicit upstream refs rather than same-name branch fallback
- [ ] Post-merge validation or release-train follow-up is documented when downstream repos or site/docs are affected

---

## Maintainer Triage (for reviewers)
_See [xrtm governance triage docs](https://github.com/xrtm-org/governance/blob/main/policies/triage-matrix.md) for classification guidance._

**Scope**: <!-- Core Schema | Package API | Implementation | Infrastructure | Documentation -->
**Priority**: <!-- Release Blocker | High | Medium | Low -->
**Risk**: <!-- High | Medium | Low -->
**Disposition**: <!-- Accept as-is | Accept with changes | Supersede | Defer | Reject -->

**Review Notes**:
<!-- Brief rationale for disposition. Record full details in governance/policies/pr-disposition-log.md -->
