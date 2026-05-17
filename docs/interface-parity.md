# Interface parity matrix

This page is the implementation-level source of truth for CLI/WebUI parity in
`xrtm`. It follows the governance
[Interface Parity and Claim Ownership Policy](https://github.com/xrtm-org/governance/blob/main/policies/interface-parity-and-claim-ownership-policy.md).

Current baseline: published `xrtm==0.8.4`.

The `0.8.4` release promotes the unified Hub → Studio → Playground →
Observatory spine on the provider-free local product-shell baseline. The release
may claim Hub at `/` and `/hub`, Studio at `/studio`, graph-linked Playground
trace review, Observatory at `/observatory`, and `/workbench` compatibility
without implying a calibration dashboard, API/webhook control plane, arbitrary
code/plugin graph editing, full persistent collaborative canvas layout, or
commercial runtime path.

## Status legend

| Status | Meaning |
| --- | --- |
| `parity-ready` | CLI and WebUI expose the same released capability through shared product semantics and release evidence. |
| `partial` | WebUI has some of the capability, but not enough to claim peer interface support. |
| `missing` | Released or source-visible CLI capability has no WebUI equivalent yet. |
| `future-release` | Implemented or approved for a later train, but must stay out of released claims until package/docs/gates land. |
| `interface-entrypoint` | Command or route launches an interface rather than being a product capability that needs mirroring. |
| `advanced/experimental` | Keep visible only in advanced or future-release contexts until stronger evidence exists. |
| `redesign-required` | Do not promote as a parity claim until the public contract is redesigned. |

## Current WebUI/API surface

| Capability | WebUI route or API | Product/service owner | Status | CLI relationship |
| --- | --- | --- | --- | --- |
| Hub shell | `/`, `/hub`, `GET /api/app-shell`, `GET /api/health`, `GET /api/workflows`, `GET /api/providers/status` | Hub composition over app-shell, doctor, workflow catalog, and provider snapshot services | `parity-ready` | Owns first-run home, template gallery, recent work, and quick entry into Playground/Studio without creating a separate app. |
| Readiness/health | `/start`, `GET /api/health` | `xrtm.product.doctor.run_doctor`, `doctor_snapshot` | `parity-ready` | WebUI Start page renders the shared doctor snapshot and passed clean-room Gate 2 on the release build. |
| Provider status | `/start`, `GET /api/providers/status` | `xrtm.product.providers.local_llm_status`, provider snapshot service | `partial` | WebUI Start page shows provider-free and local-LLM status from the shared provider snapshot. |
| Overview shell | `/`, `GET /api/app-shell` | WebUI app-shell read model over runs, workflows, and resumable draft state | `partial` | Shared local shell summary over file-backed run history, workflow index, and resumable workbench state. |
| Run list/search | `/runs`, `GET /api/runs` | `xrtm.product.history.list_runs`, WebUI run read models | `parity-ready` | Covers `xrtm runs list` and the basic searchable view of `xrtm runs search`. |
| Run detail | `/runs/<run-id>`, `GET /api/runs/<id>` | `resolve_run_dir`, run-detail read model, `ArtifactStore` | `parity-ready` | Covers the review intent of `xrtm runs show`. |
| Run compare | `/runs/<candidate>/compare/<baseline>`, `GET /api/runs/<candidate>/compare/<baseline>` | `compare_runs`, WebUI compare snapshots | `parity-ready` | Covers `xrtm runs compare`. |
| Run export | `/runs/<run-id>`, `GET /api/runs/<run-id>/export?format=json\|csv` | `xrtm.product.history.export_run` | `partial` | Uses the same export service as `xrtm runs export`; run detail exposes JSON/CSV actions. |
| Report generation/viewing | `/runs/<run-id>`, `POST /api/runs/<run-id>/report`, `/runs/<run-id>/report` | `xrtm.product.reports.render_html_report` | `partial` | Uses the same report renderer as `xrtm report html`; run detail exposes generate/open actions. |
| Observatory inspector | `/observatory`, run inspector aliases, `/runs/<run-id>`, and run/artifact APIs | Run-detail read model, `ArtifactStore`, compare/export/report services | `parity-ready` | Drill-down inspector for Studio/Playground runs with clearer probability/result/score/trace/export/compare review and an honest uncertainty empty state. This is not a shipped calibration dashboard, webhook/control-plane, or broader runtime promise. |
| Workflow catalog | `/start`, Hub template gallery, `GET /api/workflows` | `WorkflowRegistry.list_workflows` | `partial` | Start page exposes the catalog for newcomer run setup; Hub makes template-to-Playground the quick forecast path. |
| Workflow detail | `/workflows/<name>`, `GET /api/workflows/<name>` | `WorkflowRegistry.load`, WebUI workflow read model | `partial` | Dedicated WebUI page shows workflow metadata and canvas. |
| Workflow explain | `/start`, `/workflows/<name>`, `GET /api/workflows/<name>/explain` | `xrtm.product.launch.explain_registered_workflow`, `WorkflowRegistry.explain` | `partial` | Shared explain payload backs Start/workflow detail and authored-workflow CLI inspection. |
| Workflow validate | `/workflows/<name>`, `POST /api/workflows/<name>/validate` | `xrtm.product.launch.validate_registered_workflow`, `WorkflowRegistry.validate` | `partial` | Shared validation has a dedicated workflow-detail action outside draft flow. |
| First-success run | `/start`, Hub primary action, `POST /api/start` | `xrtm.product.launch.run_start_quickstart` | `parity-ready` | WebUI launches the same quickstart service used by `xrtm start` and passed release Gate 2. |
| Demo run setup | `/start`, `POST /api/runs` | `xrtm.product.launch.run_demo_workflow` | `partial` | WebUI launches bounded demo runs with provider/runtime overrides through shared launch services. |
| Workflow run | `/start`, `/workflows/<name>`, `POST /api/runs` | `xrtm.product.launch.run_registered_workflow` | `partial` | WebUI launches named workflows through the same shared launch service used by CLI workflow runs. |
| Playground exploratory loop | `/playground`, `GET/PATCH /api/playground`, `POST /api/playground/run`, `POST /api/playground/runs/<run-id>/save-workflow\|save-profile` | `xrtm.product.launch.run_sandbox_session`, `save_sandbox_workflow`, `save_sandbox_profile`, WebUI playground state services | `parity-ready` | Shared sandbox state, one-custom-question-first flow, read-only step inspection, and explicit save-back wiring ship in both interfaces for the released provider-free sandbox contract. |
| Playground graph trace | `/playground` trace panel and links from `/studio` to `/playground` runs | Sandbox session/run services plus trace read model linking workflow/draft node IDs to run steps/artifacts when graph trace artifacts exist | `parity-ready` | Released graph/canvas preview, ordered node trace, graph trace artifact state, executed-node highlighting, and an honest fallback when no graph trace artifact exists. |
| Studio graph IDE | `/studio`, `GET /api/studio*` wrappers, graph snapshots, draft APIs, `GET /api/authoring/catalog` | `WorkflowAuthoringService`, draft services, built-in node catalog, validation/persistence services | `parity-ready` | Primary bounded drag-drop graph IDE over the existing workflow schema/node catalog. Supports local node dragging, palette click/drag-to-canvas add-node, node/edge/workflow selection, edge create/remove, entry setting, contextual inspector, and validate/save/run through Studio APIs. It is not arbitrary code/plugin editing or a generic diagramming app. |
| Workbench compatibility | `/workbench`, `GET /api/authoring/catalog`, `POST /api/drafts`, `PATCH /api/drafts/<id>` | Same `WorkflowAuthoringService` and draft services as Studio | `parity-ready` | Preserved as the compatibility route while `/studio` is the primary authoring route. |
| Draft validate | `/workbench`, `/studio`, `POST /api/drafts/<id>/validate` and Studio API wrappers | Shared authored-workflow validation service | `parity-ready` | Shared authored-workflow validation backs CLI and WebUI draft flows. |
| Draft run | `/workbench`, `/studio`, `POST /api/drafts/<id>/run` and Studio API wrappers | Shared authored-workflow run wiring | `parity-ready` | Shared authored-workflow run wiring backs CLI and WebUI draft execution. |
| Profiles | `/operations`, `GET/POST /api/profiles`, `GET /api/profiles/<name>`, `POST /api/profiles/<name>/run` | `starter_profile`, `ProfileStore`, `xrtm.product.launch.run_saved_profile` | `parity-ready` | Operator page covers starter/custom profile creation, listing, inspection, and run launch with shared services and release proof. |
| Monitors | `/operations`, `GET/POST /api/monitors`, `GET /api/monitors/<run-id>`, `POST /api/monitors/<run-id>/run-once\|pause\|resume\|halt` | `xrtm.product.monitoring.*`, monitor store/read models | `parity-ready` | Operator page exposes monitor lifecycle actions backed by shared monitor services and release proof. |
| Artifact inventory and cleanup | `/operations`, `GET /api/artifacts/<run-id>`, `POST /api/artifacts/cleanup-preview`, `POST /api/artifacts/cleanup` | `ArtifactStore`, cleanup preview/confirm helpers | `parity-ready` | Operator page exposes artifact inventory plus explicit cleanup preview/confirm flow with release proof. |
| Advanced lane visibility | `/advanced` | Advanced validation/benchmark/perf/competition command delegates | `advanced/experimental` | Keeps advanced lanes visible without promoting them as newcomer defaults. |
| Legacy form workbench | `/workbench/clone`, `/workbench/edit`, `/workbench/validate`, `/workbench/run` | Legacy form handlers over draft services | `partial` | Superseded by JSON draft APIs; keep only as compatibility scaffolding. |

## CLI capability matrix

| CLI command | User job | Current WebUI status | Target | Product service owner | Docs/claim owner | Release gate |
| --- | --- | --- | --- | --- | --- | --- |
| `xrtm doctor` | Newcomer readiness | `parity-ready` | released | `xrtm.product.doctor.run_doctor`, `doctor_snapshot` | `xrtm` docs, then `xrtm.org` | Release Gate 1 + Gate 2 complete |
| `xrtm start` | First-success run | `parity-ready` | released | `xrtm.product.launch.run_start_quickstart` | `xrtm` docs, then `xrtm.org` | Release Gate 1 + Gate 2 complete |
| `xrtm demo` | Demo run setup | `partial` | P0 | `xrtm.product.launch.run_demo_workflow` | `xrtm` future-release track | Gate 1 + selective Gate 2 if promoted |
| `xrtm playground` | Run the bounded exploratory sandbox loop | `parity-ready` | released (`0.8.4`) | `xrtm.product.launch.run_sandbox_session`, `save_sandbox_workflow`, `save_sandbox_profile`, WebUI playground state services | `xrtm` docs, then `xrtm.org` | Release Gate 1 + Gate 2 provider-free baseline complete; any real-runtime or cloud/API playground claim still needs matching clean-room proof before promotion |
| `xrtm workflow list` | Workflow discovery | `partial` | P0 | `WorkflowRegistry.list_workflows` | `xrtm` docs | Gate 1 |
| `xrtm workflow show` | Workflow inspection | `partial` | P0 | `xrtm.product.launch.load_registered_workflow`, `WorkflowRegistry.load` | `xrtm` docs | Gate 1 |
| `xrtm workflow validate` | Workflow validation | `partial` | P0 | `xrtm.product.launch.validate_registered_workflow`, `WorkflowRegistry.validate` | `xrtm` docs | Gate 1 + WebUI route/API smoke |
| `xrtm workflow create scratch` | Start a new local workflow | `partial` | P0 | `WorkflowAuthoringService.create_workflow_from_scratch`, workbench draft services | `xrtm` docs | Gate 1 + CLI/WebUI authoring smoke |
| `xrtm workflow create template` | Start from a starter template | `partial` | P0 | `WorkflowAuthoringService.create_workflow_from_template`, workbench draft services | `xrtm` docs | Gate 1 + CLI/WebUI authoring smoke |
| `xrtm workflow clone` / `xrtm workflow create clone` | Clone a workflow into a local authoring draft | `partial` | P0 | `WorkflowAuthoringService.clone_workflow`, workbench draft services | `xrtm` docs | Gate 1 + CLI/WebUI authoring smoke |
| `xrtm workflow edit metadata/questions/runtime/artifacts/scoring` | Update shared core workflow fields | `partial` | P0 | `WorkflowAuthoringService.update_*`, workbench draft services | `xrtm` docs | Gate 1 + CLI/WebUI authoring smoke |
| `xrtm workflow edit node/edge/entry` | Safe graph authoring inside the released node library | `partial` | P0 | `WorkflowAuthoringService.add_node/update_node/remove_node/add_edge/remove_edge/set_entry`, workbench draft services | `xrtm` docs | Gate 1 + CLI/WebUI authoring smoke |
| `xrtm workflow explain` | Workflow explanation | `partial` | P0 | `xrtm.product.launch.explain_registered_workflow`, `WorkflowRegistry.explain` | `xrtm` docs | Gate 1 |
| `xrtm workflow run` | Run selected workflow | `partial` | P0 | `xrtm.product.launch.run_registered_workflow` | `xrtm` docs | Gate 1 + WebUI-only Gate 2 |
| `xrtm profile starter` | Starter profile creation | `parity-ready` | released | `starter_profile`, `ProfileStore.create` | `xrtm` operator docs | Release Gate 1 + Gate 2 complete |
| `xrtm profile create` | Profile creation | `parity-ready` | released | `ProfileStore.create` | `xrtm` operator docs | Release Gate 1 + Gate 2 complete |
| `xrtm profile list` | Profile discovery | `parity-ready` | released | `ProfileStore.list_profiles` | `xrtm` operator docs | Release Gate 1 + Gate 2 complete |
| `xrtm profile show` | Profile inspection | `parity-ready` | released | `ProfileStore.load` | `xrtm` operator docs | Release Gate 1 + Gate 2 complete |
| `xrtm run profile` | Run a profile | `parity-ready` | released | `xrtm.product.launch.run_saved_profile` | `xrtm` operator docs | Release Gate 1 + Gate 2 complete |
| `xrtm run pipeline` | Direct pipeline execution | `missing` | P2 decision | `xrtm.product.pipeline.run_pipeline` | `xrtm` advanced docs | Gate 3 if promoted as advanced |
| `xrtm artifacts inspect` | Artifact review | `parity-ready` | released | `ArtifactStore.read_run`, inventory helpers | `xrtm` operator docs | Release Gate 1 + Gate 2 complete |
| `xrtm artifacts cleanup` | Artifact cleanup | `parity-ready` | released | `ArtifactStore.cleanup_runs` | `xrtm` operator docs | Release Gate 1 + Gate 2 complete |
| `xrtm runs list` | Run history | `parity-ready` | released | `xrtm.product.history.list_runs`, WebUI read models | `xrtm` docs | Existing released evidence |
| `xrtm runs search` | Run search | `parity-ready` | released | `list_runs`, WebUI read models | `xrtm` docs | Existing released evidence |
| `xrtm runs show` | Run detail | `parity-ready` | released | `resolve_run_dir`, `run_detail`, WebUI read models | `xrtm` docs | Existing released evidence |
| `xrtm runs compare` | Run comparison | `parity-ready` | released | `compare_runs`, WebUI compare snapshots | `xrtm` docs | Existing released evidence |
| `xrtm runs export` | Evidence export | `partial` | P0 | `xrtm.product.history.export_run` | `xrtm` docs, then `xrtm.org` | Gate 1 + WebUI-only Gate 2 |
| `xrtm providers doctor` | Provider diagnostics | `partial` | P0 | `xrtm.product.providers.local_llm_status` | `xrtm` docs | Gate 1 + provider smoke if claimed |
| `xrtm local-llm status` | Local model status | `partial` | P0 | `xrtm.product.providers.local_llm_status` | `xrtm` docs | Gate 1 + local-LLM evidence if promoted |
| `xrtm report html` | Generate/open HTML report | `partial` | P0 | `xrtm.product.reports.render_html_report` | `xrtm` docs, then `xrtm.org` | Gate 1 + WebUI-only Gate 2 |
| `xrtm monitor start` | Start monitor | `parity-ready` | released | `xrtm.product.monitoring.start_monitor` | `xrtm` operator docs | Release Gate 1 + Gate 2 complete |
| `xrtm monitor list` | List monitors | `parity-ready` | released | `list_monitors` | `xrtm` operator docs | Release Gate 1 + Gate 2 complete |
| `xrtm monitor show` | Inspect monitor | `parity-ready` | released | `load_monitor` | `xrtm` operator docs | Release Gate 1 + Gate 2 complete |
| `xrtm monitor run-once` | Run monitor once | `parity-ready` | released | `run_monitor_once` | `xrtm` operator docs | Release Gate 1 + Gate 2 complete |
| `xrtm monitor daemon` | Long-running monitor daemon | `missing` | P1/P2 decision | `run_monitor_daemon` | `xrtm` operator/advanced docs | Gate 2 only if default operator claim depends on it |
| `xrtm monitor pause` | Pause monitor | `parity-ready` | released | `set_monitor_status` | `xrtm` operator docs | Release Gate 1 + Gate 2 complete |
| `xrtm monitor resume` | Resume monitor | `parity-ready` | released | `set_monitor_status` | `xrtm` operator docs | Release Gate 1 + Gate 2 complete |
| `xrtm monitor halt` | Halt monitor | `parity-ready` | released | `set_monitor_status` | `xrtm` operator docs | Release Gate 1 + Gate 2 complete |
| `xrtm validate run` | Corpus validation | `missing` | P2 | `xrtm.product.validation.run_validation` | `xrtm` advanced/release docs | Gate 3 unless released path depends on it |
| `xrtm validate list-corpora` | Corpus discovery | `missing` | P2 | `list_validation_corpora` | `xrtm` advanced/release docs | Gate 1 |
| `xrtm validate prepare-corpus` | Corpus setup | `redesign-required` | P2 decision | `prepare_validation_corpus` | `xrtm` future-release track | Redesign before parity claim |
| `xrtm benchmark run` | Benchmark run | `missing` | P2 | `run_validation` delegation | `xrtm` advanced docs | Gate 3 if promoted |
| `xrtm benchmark list-corpora` | Benchmark corpus discovery | `missing` | P2 | `list_validation_corpora` | `xrtm` advanced docs | Gate 1 |
| `xrtm benchmark cache-corpus` | Benchmark corpus cache | `redesign-required` | P2 decision | `prepare_validation_corpus` | `xrtm` future-release track | Redesign before parity claim |
| `xrtm benchmark compare` | Benchmark comparison | `advanced/experimental` | P2 | `run_benchmark_compare` | `xrtm` advanced docs | Gate 3 |
| `xrtm benchmark stress` | Stress suite | `advanced/experimental` | P2 | `run_benchmark_stress_suite` | `xrtm` advanced docs | Gate 3 |
| `xrtm perf run` | Performance budget check | `advanced/experimental` | P2 | `run_performance_benchmark` | `xrtm` release/advanced docs | Gate 3 or release Gate 2 only when product promise depends on it |
| `xrtm competition list` | Competition pack discovery | `advanced/experimental` | P2 | `CompetitionPackRegistry.list_packs` | `xrtm` advanced docs | Gate 3 if promoted |
| `xrtm competition dry-run` | Competition dry-run bundle | `advanced/experimental` | P2 | `CompetitionPackRegistry.load`, `run_workflow_blueprint` | `xrtm` advanced docs | Gate 3 and policy review |
| `xrtm tui` | Terminal UI entrypoint | `interface-entrypoint` | released | `xrtm.product.tui.run_tui`, `render_tui_once` | `xrtm` docs | No WebUI mirror required |
| `xrtm web` | WebUI entrypoint | `interface-entrypoint` | released | `xrtm.product.web.create_web_server` | `xrtm` docs | Existing released evidence |

## Released parity proof

The published `0.8.4` release proof should cover:

1. open WebUI from a fresh install
2. run readiness/doctor from the browser
3. start a provider-free baseline run from the browser
4. inspect run detail
5. create a local authored workflow from scratch, a starter template, or a clone
6. author shared core workflow fields plus node/edge/entry changes inside the built-in node catalog
7. validate, explain, and run the authored workflow through the shared services
8. generate/open reports, export evidence, and compare candidate against baseline
9. run one custom-question-first playground session through CLI and WebUI, verify
   read-only ordered step inspection, graph/canvas trace linkage when graph trace
   artifacts exist, and explicit exploratory save-back on the provider-free baseline
10. first-run Hub with readiness, templates, and recent-work entry points
11. template gallery to Playground quick forecast
12. Studio drag-drop authoring inside the workflow schema/node catalog, then
    validate, save, and run through the safe authoring service
13. Studio-to-Playground graph trace
14. Observatory drill-down into run steps/artifacts/evidence
15. provider-free baseline, with real runtime proof added only if claims widen

## Known decisions for P2

- Validation, benchmark, performance, and competition surfaces remain P2 or
  advanced until the UI contract is intentionally designed. Broad corpus,
  provider, stress, and competition coverage belongs in Gate 3 unless the
  release promise directly depends on it.
- `validate prepare-corpus` and `benchmark cache-corpus` need contract redesign
  before WebUI parity because the current naming mixes cache setup, corpus
  policy, and release-gate expectations.
- `providers doctor` and `local-llm status` should converge on one provider
  health panel in WebUI while preserving the CLI aliases users already have.
