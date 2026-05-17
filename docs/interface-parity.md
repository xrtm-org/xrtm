# Interface parity matrix

This page is the implementation-level source of truth for CLI/WebUI parity in
`xrtm`. It follows the governance
[Interface Parity and Claim Ownership Policy](https://github.com/xrtm-org/governance/blob/main/policies/interface-parity-and-claim-ownership-policy.md).

Current baseline: published `xrtm==0.8.3`.

The current `0.8.3` source line is stability/polish only. Shell copy, visual
refinement, index freshness, and Python 3.13 health fixes should align wording
with the existing released contract, not widen the parity claims below.

## Status legend

| Status | Meaning |
| --- | --- |
| `parity-ready` | CLI and WebUI expose the same released capability through shared product semantics and release evidence. |
| `partial` | WebUI has some of the capability, but not enough to claim peer interface support. |
| `missing` | Released or source-visible CLI capability has no WebUI equivalent yet. |
| `interface-entrypoint` | Command or route launches an interface rather than being a product capability that needs mirroring. |
| `advanced/experimental` | Keep visible only in advanced/next-release contexts until stronger evidence exists. |
| `redesign-required` | Do not promote as a parity claim until the public contract is redesigned. |

## Current WebUI/API surface

| Capability | WebUI route or API | Status | CLI relationship |
| --- | --- | --- | --- |
| Readiness/health | `/start`, `GET /api/health` | `parity-ready` | WebUI Start page renders the shared doctor snapshot and passed clean-room Gate 2 on the release build. |
| Provider status | `/start`, `GET /api/providers/status` | `partial` | WebUI Start page now shows provider-free and local-LLM status from the shared provider snapshot. |
| Overview shell | `/`, `GET /api/app-shell` | `partial` | Local-only shell summary over file-backed run history, workflow index, and resumable workbench state. The `0.8.3` shell/index polish line does not widen this beyond summary/navigation. |
| Run list/search | `/runs`, `GET /api/runs` | `parity-ready` | Covers `xrtm runs list` and the basic searchable view of `xrtm runs search`. |
| Run detail | `/runs/<run-id>`, `GET /api/runs/<id>` | `parity-ready` | Covers the review intent of `xrtm runs show`. |
| Run compare | `/runs/<candidate>/compare/<baseline>`, `GET /api/runs/<candidate>/compare/<baseline>` | `parity-ready` | Covers `xrtm runs compare`. |
| Run export | `/runs/<run-id>`, `GET /api/runs/<run-id>/export?format=json\|csv` | `partial` | Uses the same export service as `xrtm runs export`; run detail now exposes JSON/CSV actions. |
| Report generation/viewing | `/runs/<run-id>`, `POST /api/runs/<run-id>/report`, `/runs/<run-id>/report` | `partial` | Uses the same report renderer as `xrtm report html`; run detail now exposes generate/open actions. |
| Workflow catalog | `/start`, `GET /api/workflows` | `partial` | Start page exposes the catalog for newcomer run setup and workflow selection. |
| Workflow detail | `/workflows/<name>`, `GET /api/workflows/<name>` | `partial` | Dedicated WebUI page now shows workflow metadata and canvas. |
| Workflow explain | `/start`, `/workflows/<name>`, `GET /api/workflows/<name>/explain` | `partial` | Shared explain payload now backs both Start/workflow detail and the authored-workflow CLI inspection path. |
| Workflow validate | `/workflows/<name>`, `POST /api/workflows/<name>/validate` | `partial` | Shared validation now has a dedicated workflow-detail action outside draft flow. |
| First-success run | `/start`, `POST /api/start` | `parity-ready` | WebUI launches the same quickstart service used by `xrtm start` and passed release Gate 2. |
| Demo run setup | `/start`, `POST /api/runs` | `partial` | WebUI now launches bounded demo runs with provider/runtime overrides through shared launch services. |
| Workflow run | `/start`, `/workflows/<name>`, `POST /api/runs` | `partial` | WebUI now launches named workflows through the same shared launch service used by CLI workflow runs. |
| Playground exploratory loop | `/playground`, `GET/PATCH /api/playground`, `POST /api/playground/run`, `POST /api/playground/runs/<run-id>/save-workflow\|save-profile` | `parity-ready` | Shared sandbox state, one-custom-question-first flow, read-only step inspection, and explicit save-back wiring now ship in both interfaces for the released `0.8.3` provider-free sandbox contract. Keep any wider real-runtime or cloud/API wording off the released surface until matching Gate 2 proof exists. |
| Draft authoring | `/workbench`, `GET /api/authoring/catalog`, `POST /api/drafts`, `PATCH /api/drafts/<id>` | `partial` | Covers draft creation from scratch/template/clone plus shared core-field and node/edge/entry authoring inside the released schema and node catalog. Parallel-group and conditional-route editing remain thin/read-only. |
| Draft validate | `/workbench`, `POST /api/drafts/<id>/validate` | `parity-ready` | Shared authored-workflow validation now backs both CLI and WebUI draft flows. |
| Draft run | `/workbench`, `POST /api/drafts/<id>/run` | `parity-ready` | Shared authored-workflow run wiring now backs both CLI and WebUI draft execution. |
| Profiles | `/operations`, `GET/POST /api/profiles`, `GET /api/profiles/<name>`, `POST /api/profiles/<name>/run` | `parity-ready` | Operator page covers starter/custom profile creation, listing, inspection, and run launch with shared services and release proof. |
| Monitors | `/operations`, `GET/POST /api/monitors`, `GET /api/monitors/<run-id>`, `POST /api/monitors/<run-id>/run-once\|pause\|resume\|halt` | `parity-ready` | Operator page exposes monitor lifecycle actions backed by shared monitor services and release proof. |
| Artifact inventory and cleanup | `/operations`, `GET /api/artifacts/<run-id>`, `POST /api/artifacts/cleanup-preview`, `POST /api/artifacts/cleanup` | `parity-ready` | Operator page exposes artifact inventory plus explicit cleanup preview/confirm flow with release proof. |
| Advanced lane visibility | `/advanced` | `advanced/experimental` | Keeps advanced validation, benchmark, perf, and competition lanes visible without promoting them as newcomer defaults. |
| Legacy form workbench | `/workbench/clone`, `/workbench/edit`, `/workbench/validate`, `/workbench/run` | `partial` | Superseded by JSON draft APIs; keep only as compatibility scaffolding. |

## CLI capability matrix

| CLI command | User job | Current WebUI status | Target | Product service owner | Docs/claim owner | Release gate |
| --- | --- | --- | --- | --- | --- | --- |
| `xrtm doctor` | Newcomer readiness | `parity-ready` | released | `xrtm.product.doctor.run_doctor`, `doctor_snapshot` | `xrtm` docs, then `xrtm.org` | Release Gate 1 + Gate 2 complete |
| `xrtm start` | First-success run | `parity-ready` | released | `xrtm.product.launch.run_start_quickstart` | `xrtm` docs, then `xrtm.org` | Release Gate 1 + Gate 2 complete |
| `xrtm demo` | Demo run setup | `partial` | P0 | `xrtm.product.launch.run_demo_workflow` | `xrtm` next-release track | Gate 1 + selective Gate 2 if promoted |
| `xrtm playground` | Run the bounded exploratory sandbox loop | `parity-ready` | released (`0.8.3`) | `xrtm.product.launch.run_sandbox_session`, `save_sandbox_workflow`, `save_sandbox_profile`, WebUI playground state services | `xrtm` docs, then `xrtm.org` | Release Gate 1 + Gate 2 provider-free baseline complete; any real-runtime or cloud/API playground claim still needs matching clean-room proof before promotion |
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
| `xrtm validate prepare-corpus` | Corpus setup | `redesign-required` | P2 decision | `prepare_validation_corpus` | `xrtm` next-release track | Redesign before parity claim |
| `xrtm benchmark run` | Benchmark run | `missing` | P2 | `run_validation` delegation | `xrtm` advanced docs | Gate 3 if promoted |
| `xrtm benchmark list-corpora` | Benchmark corpus discovery | `missing` | P2 | `list_validation_corpora` | `xrtm` advanced docs | Gate 1 |
| `xrtm benchmark cache-corpus` | Benchmark corpus cache | `redesign-required` | P2 decision | `prepare_validation_corpus` | `xrtm` next-release track | Redesign before parity claim |
| `xrtm benchmark compare` | Benchmark comparison | `advanced/experimental` | P2 | `run_benchmark_compare` | `xrtm` advanced docs | Gate 3 |
| `xrtm benchmark stress` | Stress suite | `advanced/experimental` | P2 | `run_benchmark_stress_suite` | `xrtm` advanced docs | Gate 3 |
| `xrtm perf run` | Performance budget check | `advanced/experimental` | P2 | `run_performance_benchmark` | `xrtm` release/advanced docs | Gate 3 or release Gate 2 only when product promise depends on it |
| `xrtm competition list` | Competition pack discovery | `advanced/experimental` | P2 | `CompetitionPackRegistry.list_packs` | `xrtm` advanced docs | Gate 3 if promoted |
| `xrtm competition dry-run` | Competition dry-run bundle | `advanced/experimental` | P2 | `CompetitionPackRegistry.load`, `run_workflow_blueprint` | `xrtm` advanced docs | Gate 3 and policy review |
| `xrtm tui` | Terminal UI entrypoint | `interface-entrypoint` | released | `xrtm.product.tui.run_tui`, `render_tui_once` | `xrtm` docs | No WebUI mirror required |
| `xrtm web` | WebUI entrypoint | `interface-entrypoint` | released | `xrtm.product.web.create_web_server` | `xrtm` docs | Existing released evidence |

## Released parity proof

The `0.8.3` release proof should cover:

1. open WebUI from a fresh install
2. run readiness/doctor from the browser
3. start a provider-free baseline run from the browser
4. inspect run detail
5. create a local authored workflow from scratch, a starter template, or a clone
6. author shared core workflow fields plus node/edge/entry changes inside the built-in node catalog
7. validate, explain, and run the authored workflow through the shared services
8. generate/open reports, export evidence, and compare candidate against baseline
9. run one custom-question-first playground session through CLI and WebUI, verify
   read-only ordered step inspection, and confirm save-back stays explicit and
   exploratory on the provider-free baseline

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
