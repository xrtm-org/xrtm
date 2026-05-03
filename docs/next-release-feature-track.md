# Next-release feature track

> This page tracks **current-source conveniences that are intentionally not part of the published `xrtm==0.3.0` surface**. Release-pinned docs stay honest; this page is where branch-only value gets an explicit graduation path instead of living in limbo.

Use this together with the governance repo's [Feature Status and Graduation Policy](../../governance/policies/feature-status-and-graduation-policy.md) and [Release Readiness Policy](../../governance/policies/release-readiness-policy.md).

## Status legend

- **Promote soon** — good candidate for the next coordinated release once package/docs/smoke gates move together
- **Advanced longer** — keep available in source or advanced docs, but off the default released surface for now
- **Redesign before shipping** — implementation exists, but the public contract or semantics should change before release marketing/docs adopt it

## Current feature decisions

| Feature family | Current source surface | Decision | Why | Graduation or follow-up requirements |
| --- | --- | --- | --- | --- |
| Guided onboarding helpers | `xrtm start`, `xrtm profile starter` | **Promote soon** | These are wrappers around the already honest provider-free path. They reduce friction without changing the product proof contract. | Validate from a freshly installed release artifact, ensure the success copy only recommends commands released in the same version, then update release-pinned onboarding docs and the release command contract together. |
| Latest-run shortcuts | `latest` run ref plus `--latest` on inspection/report flows | **Promote soon** | This is a low-risk convenience over canonical run directories, not a new product capability. It shortens common operator review commands without changing artifact semantics. | Add clean-install smoke for `runs show latest`, `artifacts inspect --latest`, and `report html --latest`; then move the docs/examples and release contract in the same coordinated release. |
| Spreadsheet export | `xrtm runs export --format csv` | **Promote soon** | CSV export is already implemented and useful for analyst follow-up. It complements the released JSON bundle rather than replacing it. | Keep JSON documented as the full-fidelity export, prove CSV from a built/published artifact with no hidden dependency surprises, and ship the docs/contract change only when the package release is real. |
| Corpus validation workflows | `xrtm validate run`, `xrtm validate list-corpora` | **Advanced longer** | These flows depend on corpus tiers, release-gate corpora, caching, and governance decisions that are more specialized than the honest default product path. They fit release engineering and advanced operator/research workflows better than newcomer docs. | Keep them in advanced/release-gate guidance until corpus policy, released upstream package compatibility, and larger-scale validation evidence are stable enough for public promotion. |
| Corpus preparation UX | `xrtm validate prepare-corpus` | **Redesign before shipping** | The current command is useful, but the public contract still mixes cache preparation, dataset policy, preview semantics, and release-gate expectations. The workflow deserves clearer naming and framing before it becomes a public release promise. | Redesign the user-facing command/story first (for example, make cache/setup semantics explicit), then re-evaluate whether it belongs with `validate` or a separate corpus-management surface. |
| Run attribution flags | `--user` on run-producing commands and saved profiles | **Redesign before shipping** | A free-form attribution flag is technically useful, but the released product story still says team usage relies on conventions rather than built-in identity management. Shipping the current flag as-is risks overselling multi-user semantics and privacy expectations. | Define the public semantics first: what the field means, where it appears, privacy/storage expectations, and whether it is run metadata, analyst labeling, or team workflow state. Update team docs and exports only after that contract is explicit. |

## Rules for contributors

1. If a convenience is implemented but intentionally unreleased, add or update its row here.
2. Do **not** move the feature into `README.md`, `docs/getting-started.md`, `docs/operator-runbook.md`, or `xrtm.org` release-pinned pages until the published package and `docs/release-command-contract.json` are updated together.
3. If a feature is promising but still semantically muddy, mark it **Redesign before shipping** rather than teasing it in release docs.
4. Use `xrtm.org/docs/next-release.md` for the public summary and keep this page as the command-level source of truth.
