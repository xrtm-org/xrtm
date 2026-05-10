# Next-release feature track

> This page tracks conveniences that are intentionally **not** part of the published `xrtm==0.3.1` surface. Guided onboarding helpers, latest-run shortcuts, and CSV export graduated in `0.3.1`; this page now tracks what remains unreleased.

Use this together with the governance repo's [Feature Status and Graduation Policy](https://github.com/xrtm-org/governance/blob/main/policies/feature-status-and-graduation-policy.md) and [Release Readiness Policy](https://github.com/xrtm-org/governance/blob/main/policies/release-readiness-policy.md).

## Status legend

- **`shipped`** — already part of the current published surface
- **`next-release`** — good candidate for the next coordinated release once package/docs/smoke gates move together
- **`advanced/experimental`** — keep available in source or advanced docs, but off the default released surface for now
- **`redesign-required`** — implementation exists, but the public contract or semantics should change before release marketing/docs adopt it

## Current feature decisions

| Feature family | Current source surface | Canonical status | Target train | Why | Graduation or follow-up requirements |
| --- | --- | --- | --- | --- | --- |
| Guided onboarding helpers | `xrtm start`, `xrtm profile starter` | **`shipped`** | `0.3.1` | These wrappers reduce first-run friction without changing the provider-free proof contract. | Keep success output tied to released commands only and validate from clean released artifacts. |
| Latest-run shortcuts | `latest` run ref plus `--latest` on inspection/report flows | **`shipped`** | `0.3.1` | This is a low-risk convenience over canonical run directories. | Keep clean-install smoke covering `runs show latest`, `artifacts inspect --latest`, and `report html --latest`. |
| Spreadsheet export | `xrtm runs export --format csv` | **`shipped`** | `0.3.1` | CSV export is useful for analyst follow-up and complements JSON. | Keep JSON documented as the full-fidelity export and maintain artifact-level smoke for CSV output. |
| Corpus validation workflows | `xrtm validate run`, `xrtm validate list-corpora` | **`advanced/experimental`** | After corpus policy and released-stack validation mature further | These flows depend on corpus tiers, release-gate corpora, caching, and governance decisions that are more specialized than the honest default product path. They fit release engineering and advanced operator/research workflows better than newcomer docs. | Keep them in advanced or release-gate guidance until corpus policy, released upstream package compatibility, and larger-scale validation evidence are stable enough for public promotion. |
| Corpus preparation UX | `xrtm validate prepare-corpus` | **`redesign-required`** | Not on the current release train | The current command is useful, but the public contract still mixes cache preparation, dataset policy, preview semantics, and release-gate expectations. The workflow deserves clearer naming and framing before it becomes a public release promise. | Redesign the user-facing command/story first (for example, make cache/setup semantics explicit), then re-evaluate whether it belongs with `validate` or a separate corpus-management surface. |
| Run attribution flags | `--user` on run-producing commands and saved profiles | **`redesign-required`** | Not on the current release train | A free-form attribution flag is technically useful, but the released product story still says team usage relies on conventions rather than built-in identity management. Shipping the current flag as-is risks overselling multi-user semantics and privacy expectations. | Define the public semantics first: what the field means, where it appears, privacy/storage expectations, and whether it is run metadata, analyst labeling, or team workflow state. Update team docs and exports only after that contract is explicit. |

## Rules for contributors

1. If a convenience is implemented but intentionally unreleased, add or update its row here with the exact governance status label, target train, and blocking validations.
2. Do **not** move the feature into `README.md`, `docs/getting-started.md`, `docs/operator-runbook.md`, or `xrtm.org` release-pinned pages until the published package and `docs/release-command-contract.json` are updated together.
3. Graduation evidence for released docs must include the command-claim check plus provider-free clean-room acceptance from release artifacts (wheelhouse before publish, PyPI after publish). If the change touches local-model behavior, also require local-LLM clean-room evidence or an explicit defer note.
4. If a target train slips or the blocking evidence is not ready, keep the feature unreleased or downgrade the status. Do not partially update the release-pinned docs first.
5. If a feature is promising but still semantically muddy, mark it **`redesign-required`** rather than teasing it in release docs.
6. Use `xrtm.org/docs/next-release.md` for the public summary and keep this page as the command-level source of truth.
