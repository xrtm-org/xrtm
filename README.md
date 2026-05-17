# XRTM: AI for event forecasting

[![PyPI](https://img.shields.io/pypi/v/xrtm?style=flat-square)](https://pypi.org/project/xrtm/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square)](LICENSE)

**XRTM** is the product-first shell for running event-forecasting workflows,
inspecting the scored artifacts, and choosing CLI or WebUI for the same
released local product tasks.

## Start here

If you arrived from xrtm.org, PyPI, or this repository, use the authoritative
first-success guide: [docs/getting-started.md](docs/getting-started.md).

That guide walks the released `xrtm==0.8.4` journey in one place:

1. install XRTM
2. choose a CLI-led or WebUI-led first-success path
3. inspect the latest run, report, and exports
4. run a named workflow from the Start or Workflow detail surface
5. use Operations for profiles, monitors, and cleanup
6. use Hub at `/` or `/hub` for templates, readiness, recent work, and quick
   entry into the rest of the local product
7. use Studio at `/studio` (with `/workbench` compatibility) or the shared CLI
   authoring layer to create from scratch, template, or clone, then author safe
   workflow fields plus node/edge/entry changes, validate, run, and compare
8. use the released Playground lane for one custom question first, graph/canvas
   trace linkage, read-only step inspection, and explicit save-back to
   workflow/profile on the provider-free release baseline
9. inspect run evidence in Observatory at `/observatory`
10. choose your next path

The `0.8.4` release promotes the bounded local Hub → Studio → Playground →
Observatory product spine. It keeps the release baseline provider-free and does
not claim a calibration dashboard, API/webhook control plane, arbitrary
code/plugin graph editing, full persistent collaborative canvas layout, or
commercial runtime path without separate validation.

This README intentionally stays short so the first-run commands live in one
place.

## After your first successful run

- **Researcher:** use the [researcher workflow on xrtm.org](https://xrtm.org/docs/workflows/researcher-model-eval)
- **Operator:** continue with the [Operator Runbook](docs/operator-runbook.md)
- **Developer:** move to the [Python API Reference](docs/python-api-reference.md) and [integration examples](examples/integration/)

## Documentation

- [Getting Started Guide](docs/getting-started.md)
- [Operator Runbook](docs/operator-runbook.md)
- [Python API Reference](docs/python-api-reference.md)
- [Integration Examples](examples/integration/)
- [Interface Parity Matrix](docs/interface-parity.md) for the current CLI/WebUI capability map and next parity targets
- [0.8.x Feature Track](docs/next-release-feature-track.md) for the released 0.8.4 product spine and future bounded surfaces
- [Stack Versioning Policy](https://github.com/xrtm-org/governance/blob/main/policies/stack-versioning-policy.md) for `xrtm` as the product-anchor release and cross-repo version ownership
- Full documentation: [xrtm.org](https://xrtm.org)

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
