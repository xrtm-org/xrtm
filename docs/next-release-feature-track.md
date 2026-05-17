# Next-release feature track

> The published baseline remains `xrtm==0.8.3`: guided onboarding helpers,
> latest-run shortcuts, CSV export, the shared CLI/WebUI workflow-authoring loop,
> the guided local WebUI workbench, the WebUI/CLI parity shell, and the bounded
> interactive sandbox/playground are already on the released surface.
>
> The approved next `0.8.x` UX train, practically `0.8.4`, is the first slice of
> one unified local-first product spine: **Hub → Studio → Playground →
> Observatory**. That spine is implemented in the current source tree and remains
> a next-release claim until packaging, docs, and release gates move together.

Use this together with the governance repo's [Feature Status and Graduation Policy](https://github.com/xrtm-org/governance/blob/main/policies/feature-status-and-graduation-policy.md), [Release Readiness Policy](https://github.com/xrtm-org/governance/blob/main/policies/release-readiness-policy.md), [Stack Versioning Policy](https://github.com/xrtm-org/governance/blob/main/policies/stack-versioning-policy.md), and [Interface Parity and Claim Ownership Policy](https://github.com/xrtm-org/governance/blob/main/policies/interface-parity-and-claim-ownership-policy.md).

For the current command-by-command CLI/WebUI map, see [Interface Parity Matrix](interface-parity.md).

## Approved source-complete 0.8.4-ish UX train

This train makes XRTM feel like one local-first product, not separate
B2C/B2B apps or disconnected feature demos. Use progressive disclosure:
newcomers start with the Hub and templates; advanced users can enter Studio,
run through Playground, and inspect evidence in Observatory.

### Product spine

| Surface | Current source role | Boundary |
| --- | --- | --- |
| Hub | First-run home at `/` and `/hub`, template gallery, recent work, provider/readiness status, and entry points into the rest of the product. | Local product shell only; no cloud account or separate marketing app assumption. |
| Studio | Primary `/studio` route for a true drag-drop graph IDE over XRTM workflows, backed by `/api/studio` wrappers, graph snapshots, the node palette/catalog, and safe draft validate/save/run actions. | Bounded to the existing workflow schema, built-in node catalog, and safe workflow-authoring service. It is not arbitrary code/plugin editing and not a generic diagramming app. |
| Playground | Graph-linked exploratory run loop for quick forecasts and iterative runs, with graph/canvas preview, ordered node trace, executed-node highlighting, and an honest fallback when no graph trace artifact exists. | Playground executes and traces selected workflow states; Studio remains the primary graph authoring surface. |
| Observatory | `/observatory` alias for the run inspector, with clearer probability/result/score/trace/export/compare review and an honest uncertainty empty state. | Inspect released run/artifact data honestly; do not imply a shipped calibration dashboard, webhook system, provider/runtime expansion, or persistent collaborative canvas layout beyond validated evidence. |

### Blessed user paths

- **Quick forecast path:** template gallery in Hub → Playground run → optional
  Studio inspect/edit if the user wants to understand or adjust the graph.
- **Advanced authoring path:** Studio drag-drop workflow authoring → Playground
  execution/trace → Observatory drill-down.

### Route compatibility decision

`/studio` is the primary authoring route for the new graph IDE. The old
`/workbench` surface remains a compatibility route so existing docs, links, and
local workflows do not break while the product language moves to Studio.

### Required gates for this train

- **Gate 1 is required for every PR:** docs/claim checks, lint/build/test slices
  relevant to touched files, and targeted route/API smoke where implementation
  changes land.
- **Gate 2 is required before release:** a fresh-environment new-user proof must
  cover first-run Hub, template-to-Playground, Studio drag-drop authoring with
  validate/save, Studio-to-Playground trace, Observatory drill-down, and the
  provider-free baseline.
- Add a real OpenAI-compatible or coding-agent-CLI runtime proof only if release
  claims widen beyond the provider-free product-shell baseline. If cloud/API
  support is advertised, include a commercial OpenAI-compatible profile.

## Locked WebUI design language for the 0.8.x UX train

The WebUI style contract for this train is:

> **muted and postal, monochromatic muted plate, neo minimalism, card-based
> design with layered elements when appropriate, approachable sophistication**

Implementation guidance:

- prefer restrained, low-saturation neutrals over bright dashboard accents
- treat cards and document-like panels as the main composition unit
- use spacing, grouping, and surface depth for hierarchy before adding ornament
- add layered elements only when they clarify state, context, or workflow steps
- keep the UI polished and trustworthy without becoming cold, flashy, or overly
  enterprise-heavy
- keep version/release trust cues visible and stylistically coherent in the app

## Status legend

- **`shipped`** — already part of the current published surface
- **`next-release`** — implemented or approved candidate for the next coordinated release once package/docs/smoke gates move together
- **`advanced/experimental`** — keep available in source or advanced docs, but off the default released surface for now
- **`redesign-required`** — implementation exists, but the public contract or semantics should change before release marketing/docs adopt it

## Current feature decisions

| Feature family | Current source surface | Canonical status | Target train | Why | Graduation or follow-up requirements |
| --- | --- | --- | --- | --- | --- |
| Unified Hub / Studio / Playground / Observatory spine | `/`, `/hub`, `/studio`, `/playground`, `/observatory`, `/runs/<run-id>`, `/api/app-shell`, `/api/studio*`, `/api/drafts`, `/api/playground*`, and run/artifact read APIs | **`next-release`** | `0.8.4-ish` | Implemented first slice of the local-first product: Hub for first-run/templates, Studio for bounded drag-drop graph authoring, Playground for graph-linked execution and trace review, and Observatory for run inspection. This is one progressively disclosed product, not separate B2C/B2B apps. | Keep release-pinned docs as next-release/source-only wording until package/docs/gates move together. Preserve `/workbench` as a compatibility route, prove Gate 1 on PRs, and require release Gate 2 for first-run Hub, template-to-Playground, Studio validate/save, Studio-to-Playground trace, Observatory drill-down, and provider-free baseline. |
| Shared workflow authoring loop | `xrtm workflow create scratch`, `xrtm workflow create template`, `xrtm workflow create clone`, `xrtm workflow edit ...`, `xrtm workflow list`, `xrtm workflow show`, `xrtm workflow explain`, `xrtm workflow validate`, `xrtm workflow run --workflows-dir ...` | **`shipped`** | `0.8.1` | The released local workflow loop now uses one shared authoring layer across CLI and WebUI: start from scratch/template/clone, edit shared core workflow fields, make safe node/edge/entry mutations inside the built-in node catalog, and then validate/explain/run through the same authored-workflow services. | Keep clean-room authoring evidence in release validation and keep the released docs explicit that this is safe workflow authoring inside the product schema/node library, not arbitrary JSON or code editing. |
| WebUI/CLI parity shell | `/start`, `/workflows/<name>`, `/operations`, `/advanced`, `/api/start`, `/api/runs`, `/api/profiles`, `/api/monitors`, `/api/artifacts/*` | **`shipped`** | `0.8.0` | The released product now exposes the missing parity surfaces for first-success runs, named workflow execution, report/export actions, operator profiles, monitor lifecycle, artifact cleanup preview/confirm, and honest advanced-lane visibility. These surfaces are wired through shared Python product services so the WebUI and CLI do not fork their mutating behavior. | Keep Gate 1 plus fresh-install Gate 2 evidence for the WebUI-only first-success path and selective operator proof on both wheelhouse and PyPI installs. |
| Interactive workflow sandbox / playground | `xrtm playground`, `xrtm web --workflows-dir .xrtm/workflows`, `/playground`, `GET/PATCH /api/playground`, `POST /api/playground/run`, `POST /api/playground/runs/<run-id>/save-workflow`, `POST /api/playground/runs/<run-id>/save-profile` | **`shipped`** for the 0.8.2 baseline; graph-linked UI is **`next-release`** | `0.8.2` baseline plus `0.8.4-ish` UI train | The released package ships the shared sandbox layer behind both interfaces: one custom question first, bounded exploratory reruns, artifact-backed read-only step inspection, and explicit workflow/profile save-back through shared validation and persistence wiring. The current source also links Playground to Studio graphs with graph/canvas preview, ordered node trace, graph trace artifact state, executed-node highlighting, and an honest fallback when no graph trace artifact exists. | Keep the locked public contract intact in release docs and claims: one custom question first, optional tiny batch capped at 5, read-only step inspection, explicit save-back only, and persistent exploratory labeling distinct from benchmark/release evidence. Until dedicated Gate 2 proof exists for a real runtime, keep the released playground runtime story provider-free and do not widen it to commercial OpenAI-compatible claims. |
| Competition dry-run packs | `xrtm competition list`, `xrtm competition dry-run <pack>` | **`advanced/experimental`** | After the flagship workflow and policy guardrails are stable | Dry-run competition packs are intentionally conservative: they prepare review bundles and never submit. This is valuable for proving the live-workflow shape, but the policy, human-review expectations, and target-competition semantics need more runtime evidence before public release docs adopt them. | Keep the surface off release-pinned docs, require redaction tests and dry-run artifact validation, and add at least one real policy-reviewed rehearsal before promoting it beyond advanced docs. |
| Thin benchmark shell | `xrtm benchmark list-corpora`, `xrtm benchmark cache-corpus`, `xrtm benchmark run`, `xrtm benchmark compare`, `xrtm benchmark stress` | **`advanced/experimental`** | After corpus registry and scorecard/report flows mature further | This is the preferred product-facing benchmark entrypoint because it delegates to the lower data/eval/train stack instead of rebuilding benchmark logic in `xrtm`. It is intentionally thin and should stay advanced until the external-corpus and public-scorecard story is more settled. Typed source-level artifacts now separate reproducible internal stress suites from public human baselines, public leaderboards, and inspectable competitor outputs, but the product shell should stay conservative until that ingestion/reporting UX is proven end to end. | Keep the implementation as a delegation shell over validation/registry primitives, route public baseline ingestion/reporting through the dedicated external lane instead of the stress runner, document it only in advanced/internal surfaces for now, and do not market it as a default newcomer path until the larger corpus and scorecard program is stable. |
| Corpus validation workflows | `xrtm validate run`, `xrtm validate list-corpora` | **`advanced/experimental`** | After corpus policy and released-stack validation mature further | These flows depend on corpus tiers, release-gate corpora, caching, and governance decisions that are more specialized than the honest default product path. They fit release engineering and advanced operator/research workflows better than newcomer docs. | Keep them in advanced or release-gate guidance until corpus policy, released upstream package compatibility, and larger-scale validation evidence are stable enough for public promotion. |
| Corpus preparation UX | `xrtm validate prepare-corpus` | **`redesign-required`** | Not on the current release train | The current command is useful, but the public contract still mixes cache preparation, dataset policy, preview semantics, and release-gate expectations. The workflow deserves clearer naming and framing before it becomes a public release promise. | Redesign the user-facing command/story first (for example, make cache/setup semantics explicit), then re-evaluate whether it belongs with `validate` or a separate corpus-management surface. |
| Run attribution flags | `--user` on run-producing commands and saved profiles | **`redesign-required`** | Not on the current release train | A free-form attribution flag is technically useful, but the released product story still says team usage relies on conventions rather than built-in identity management. Shipping the current flag as-is risks overselling multi-user semantics and privacy expectations. | Define the public semantics first: what the field means, where it appears, privacy/storage expectations, and whether it is run metadata, analyst labeling, or team workflow state. Update team docs and exports only after that contract is explicit. |
| Editable workflow workbench / Studio graph IDE | `xrtm web --workflows-dir .xrtm/workflows`, `/`, `/hub`, `/runs`, `/studio`, `/workbench`, `/api/app-shell`, `/api/authoring/catalog`, `/api/studio*`, `/api/runs`, `/api/drafts`, `/api/runs/<run-id>/compare/<baseline-run-id>` | `/workbench` **`shipped`**; `/studio` graph IDE **`next-release`** | `0.8.1` baseline plus `0.8.4-ish` UI train | The released local WebUI is a React/TypeScript app shell backed by the local Python API and SQLite app-state. It can inspect runs, resume recent work, start from scratch/template/clone, author shared workflow fields, make safe node/edge/entry changes inside the built-in node catalog, validate, run, and compare against a selected baseline run. The current source promotes `/studio` as the primary bounded graph IDE with local node dragging, palette click/drag-to-canvas add-node, node/edge/workflow selection, edge create/remove, entry setting, contextual inspector, and validation/save/run through Studio APIs; `/workbench` remains compatibility. | Keep provider-free clean-room evidence covering WebUI smoke plus authoring → validate → run → compare, and keep release docs precise about remaining parallel-group/conditional-route limits. Do not break existing `/workbench` links while moving product language to Studio. |
| Managed local live WebUI dev path | released `xrtm web`, reserved `./workspace.sh live-webui <start\|stop\|restart\|status\|logs>` | **`advanced/experimental`** | Workspace/internal first | The recurring stale `http://127.0.0.1:8765` problem is a local-dev lifecycle issue, not a release-docs gap. The released `xrtm web` entrypoint is still a plain local server over built static assets, so the honest fix is a managed current-checkout workspace helper rather than prematurely promising `xrtm web --reload` or `xrtm web --dev`. | Lock the workspace-helper contract first: manager-owned PID/log/state under `.xrtm/live-webui/`, rebuilt packaged assets before start/restart, current-checkout launch semantics, default `127.0.0.1:8765`, and release docs that continue to describe only plain `xrtm web` until a separate graduation intentionally widens the public CLI. |

## 0.8.2 interactive sandbox contract (released)

### 0.8.1 baseline this extends

The sandbox contract starts from the already released `0.8.1` product surfaces:

- CLI safe authoring and run flow: `xrtm workflow create ...`,
  `xrtm workflow edit ...`, `xrtm workflow validate ...`,
  `xrtm workflow explain ...`, and `xrtm workflow run ...`
- WebUI local shell and authoring flow: `/start`, `/runs`,
  `/workflows/<name>`, `/workbench`, `/api/runs`, `/api/workflows`,
  `/api/authoring/catalog`, and `/api/drafts`
- shared safety boundary: released schema, built-in node catalog, safe graph
  edits only, and no arbitrary JSON/code/implementation editing claim

`0.8.2` adds an exploratory layer between authoring and larger-scale runs,
not replace the released workbench/authoring contract.

### Released 0.8.2 snapshot

The current branch already contains the shared sandbox wiring that the `0.8.2`
docs need to describe truthfully:

- shared sandbox/session services write `sandbox_session.json` with explicit
  exploratory labeling, ordered read-only inspection steps, and save-back
  readiness metadata
- `xrtm playground` can seed the loop from a workflow or starter template, ask
  one custom question first, rerun quickly, and change context without dropping
  into arbitrary JSON/code editing
- `xrtm web` now exposes `/playground` plus sandbox-specific `/api/playground*`
  routes for session state, exploratory runs, and explicit save-back actions
- save-back to workflow/profile reuses the normal authored-workflow validation
  path and profile store; it does not silently relabel prior exploratory runs as
  benchmark or release evidence

That shipped state is enough to support honest release-pinned docs, provided the
package, release claims, and provider-free Gate 2 evidence move together.

### Locked public contract for `0.8.2`

| Area | Locked contract | Must not drift into |
| --- | --- | --- |
| CLI surface name/shape | The primary CLI entrypoint is `xrtm playground`. It should launch the sandbox loop directly and may accept seed flags such as `--workflow`, `--template`, `--question`, `--workflows-dir`, and `--runs-dir`, but the released promise is the interactive exploratory loop, not a large new flag matrix. It should reuse the same workflow registry and safe authored-workflow services already used by `xrtm workflow ...`. | A separate unbounded graph/code editing CLI, raw JSON/code editing, or a benchmark-first command family. |
| WebUI route/surface | The primary browser surface is `/playground` inside the existing `xrtm web` shell. Any new JSON/state routes should stay sandbox-specific under `/api/playground*` instead of overloading `/workbench` or pretending the feature already lives on `/start`. `/workbench` remains the released safe authoring surface; in the next train `/studio` becomes the primary bounded graph IDE. | Folding the feature into `/workbench` in a way that blurs authoring versus exploratory execution, or treating `/playground` as the primary graph editing canvas. |
| Custom-question scope | The released minimum is **one custom question**. A tiny exploratory batch is optional, but if it ships in `0.8.2` it must stay explicitly bounded to **5 questions or fewer**, reuse the same exploratory labeling, and remain secondary to the single-question loop. Batch support may slip without blocking the core release contract. | Unbounded question sets, dataset/corpus management, or reframing the feature as a benchmark runner. |
| Exploratory labeling vs benchmark/release evidence | Every sandbox session and run should carry explicit exploratory/playground labeling in UI text and persisted metadata. Sandbox outputs may still be inspectable, comparable, and exportable for local analysis, but they are **not benchmark-grade or release-grade evidence by default**. Saving back a workflow/profile must not silently relabel prior exploratory runs as benchmark or release evidence. | Treating playground runs as benchmark submissions, release proof, or public scorecard evidence without a separate explicit flow. |
| Step/node output inspection | The sandbox must expose an ordered, read-only inspection view for executed steps/nodes. The stable promise is: node identity (`id`/label/type), execution status/order, a human-readable output preview, and access to normalized artifact-backed payloads when present. This is enough to understand workflow behavior and rerun decisions without promising raw engine internals, arbitrary debug traces, or implementation-private state. | A full debugger promise, unrestricted internal state dumps, or a commitment to expose every transient runtime detail. |
| Save as workflow | “Save as workflow” writes the current safe workflow state into the normal reusable workflow store (for example `.xrtm/workflows`) and must pass the same authored-workflow validation contract as `0.8.1`. It persists supported workflow fields and safe graph edits, but **not** transient step outputs, exploratory labels on prior runs, or hidden runtime-only blobs. | Auto-saving on every rerun, embedding run artifacts into workflows, or bypassing workflow validation. |
| Save as profile | “Save as profile” stores repeatable launch/runtime preferences in the normal profile store (for example `.xrtm/profiles`) and references a workflow explicitly. Profiles must not silently embed unsaved graph mutations. If the sandbox includes graph changes, the product should require saving a workflow first (or keep the original workflow reference) before saving the profile. | A profile format that hides unsaved workflow snapshots or mixes workflow persistence with run evidence implicitly. |
| Runtime promise boundaries for Gate 2 | The release minimum for the playground story is the provider-free product-shell baseline. If `0.8.2` release docs claim playground support for a real OpenAI-compatible endpoint or coding-agent CLI runtime, Gate 2 must prove at least one such end-to-end playground path in a fresh environment. If the released playground docs advertise cloud/API support, Gate 2 must also include at least one **commercial OpenAI-compatible** playground profile. Until that proof exists, release-pinned docs must keep playground runtime wording narrower. | Releasing a playground promise that implies real/commercial runtime support without matching clean-room proof. |
| Product framing and safety boundary | The feature is a **safe sandbox / playground** for bounded workflow experimentation. It stays inside the released schema, built-in node catalog, supported runtime/provider taxonomy, and explicit save flows. The next train can link it to Studio, but Playground itself remains the execution loop. | Unbounded code/plugin editing, unrestricted implementation editing, or bypassing the safe workflow-authoring service. |

## Locked local live WebUI contract (unreleased / local-dev only)

The current source tree has two different concerns:

- released/public `xrtm web`, which is a plain local HTTP server
- local current-checkout iteration, which is where the stale detached-process
  problem lives today

Lock the dev contract around those realities instead of pretending the released
CLI already has a clean reload story.

| Area | Locked contract | Must not drift into |
| --- | --- | --- |
| Supported surface | The supported current-code live/dev path is `./workspace.sh live-webui <start\|stop\|restart\|status\|logs>`. The released `xrtm web` command stays the plain server entrypoint with `--runs-dir`, `--workflows-dir`, `--host`, `--port`, and `--smoke` only. No `xrtm web --reload` or `xrtm web --dev` promise is locked right now. | Sneaking reload/dev semantics into the released CLI before the Python + packaged-frontend story is intentionally designed and validated. |
| Frontend asset model | The browser shell continues to be served from built assets in `src/xrtm/product/webui_static/`. The live manager is responsible for rebuilding those packaged assets from `webui/src/**` before `start`/`restart`. Automatic watch/rebuild may exist later as an implementation detail, but the stable promise is rebuilt packaged assets, not direct source serving or HMR. | Promising instant hot reload for every TS/CSS edit, or serving unpublished assets from outside the packaged static path. |
| Backend update path | Python changes are picked up by restarting the manager-owned `xrtm web` process from the current checkout. Automatic restart may be added later, but the locked contract only requires an explicit managed restart path that developers can trust. | Claiming fully automatic in-process reload semantics across all backend paths, providers, and long-running sessions. |
| PID / log / port ownership | `workspace.sh live-webui` now has one **shared** instance reserved for `0.0.0.0:8765` under `.xrtm/live-webui/`, plus optional **isolated** instances under `.xrtm/live-webui-instances/<name>/` for validation and test runs. Port `8765` is reserved for the shared instance only. `status` reports the targeted instance URL plus PID/log path, and isolated instances must use a non-`8765` port. | Detached orphan processes, validation runs mutating the shared state directory, or ambiguous ownership of port `8765`. |
| How the live URL tracks current code | Shared live commands must acknowledge `--shared-live` before they can mutate the canonical instance, while validation/test runs should use `--instance <name>` and an isolated port/state directory. After the manager finishes its rebuild/start step, the targeted instance reflects the current checkout's Python code plus the freshly rebuilt packaged WebUI assets. | Calling the URL "live" while it still serves an old wheel, stale static bundle, or allowing validation flows to stop/restart the shared instance by accident. |
| Doc boundary | Developer/local workspace docs may describe `workspace.sh live-webui` as the managed current-code path. Release/new-user docs, `docs/release-command-contract.json`, and packaged CLI help continue to describe only plain `xrtm web` until a later graduation intentionally broadens the public CLI surface. | Adding `live-webui`, `xrtm web --reload`, or `xrtm web --dev` to release-pinned docs before implementation and matching validation land. |

### Current source-only helper usage

Use the workspace helper when iterating on current checkout code:

```bash
./workspace.sh live-webui start --shared-live
./workspace.sh live-webui status
./workspace.sh live-webui restart --shared-live
./workspace.sh live-webui logs --lines 100
./workspace.sh live-webui stop --shared-live

# Isolated validation instance
./workspace.sh live-webui start --instance gate2-smoke --host 127.0.0.1 --port 8876
./workspace.sh live-webui stop --instance gate2-smoke
```

Operational notes:

- `start` and `restart` rebuild the packaged WebUI assets from `xrtm/webui/`
  before launching the current checkout.
- The shared instance keeps `state.json`, `server.pid`, and `server.log` under
  `.xrtm/live-webui/`; isolated instances use `.xrtm/live-webui-instances/<name>/`.
- If `0.0.0.0:8765` is already active from an unmanaged process, the shared helper
  refuses to take ownership silently; stop the old process first.
- Shared `start`/`restart`/`stop` now require `--shared-live` so validation/test
  flows do not mutate the canonical instance accidentally.

## Rules for contributors

1. If a convenience is implemented but intentionally unreleased, add or update its row here with the exact governance status label, target train, and blocking validations.
2. Do **not** move the feature into `README.md`, `docs/getting-started.md`, `docs/operator-runbook.md`, or `xrtm.org` release-pinned pages until the published package and `docs/release-command-contract.json` are updated together.
3. Graduation evidence for released docs must include the command-claim check plus provider-free clean-room acceptance from release artifacts (wheelhouse before publish, PyPI after publish). If the change touches local-model behavior, also require local-LLM clean-room evidence or an explicit defer note. Local-LLM release evidence should include the clean-room summary, benchmark artifacts, competition dry-run bundle, and GPU telemetry summary rather than a bare demo log.
4. If a target train slips or the blocking evidence is not ready, keep the feature unreleased or downgrade the status. Do not partially update the release-pinned docs first.
5. If a feature is promising but still semantically muddy, mark it **`redesign-required`** rather than teasing it in release docs.
6. Release-train labels here are coordination labels, not forced shared version numbers; record the exact package versions or refs that the train depends on.
7. Use `xrtm.org/docs/next-release.md` for the public summary and keep this page as the command-level source of truth.

## Current UI train implementation notes

- Entry point in source: `xrtm web`, with `--runs-dir`, `--workflows-dir`, `--host`, `--port`, and `--smoke`.
- Default local URL: `http://127.0.0.1:8765`; Hub lives at `/` and `/hub`, `/studio` is the primary bounded graph authoring route, and `/workbench` remains compatibility.
- App routes: `/`, `/hub`, `/start`, `/runs`, `/observatory`, `/operations`, `/advanced`, `/workflows/<name>`, `/studio`, `/workbench`, `/playground`, `/runs/<run-id>`, and `/runs/<candidate-run-id>/compare/<baseline-run-id>`.
- JSON routes: `/api/app-shell`, `/api/health`, `/api/providers/status`, `/api/start`, `/api/runs`, `/api/workflows`, `/api/studio*`, `/api/authoring/catalog`, `/api/drafts`, `/api/playground*`, `/api/profiles`, `/api/monitors`, `/api/artifacts/*`, and `/api/runs/<run-id>/compare/<baseline-run-id>`.
- The shell serves a local React/TypeScript frontend, keeps reusable workflows on disk, and stores draft values, validation snapshots, compare cache, and resume state in a local SQLite app database.
- Safe workflow authoring covers scratch/template/clone draft creation, shared metadata/questions/runtime/artifact/scoring fields, and node/edge/entry changes inside the built-in product node catalog.
- Studio is a real drag-drop workflow graph IDE over that safe authoring contract; it is not an arbitrary code/plugin graph editor.
- Observatory is the run-inspection lane, not a calibration dashboard or webhook/control-plane promise.
- Parallel-group and conditional-route editing remain thin/read-only, and this still should not be described as arbitrary workflow/JSON/code editing until the implementation and policy intentionally change.
