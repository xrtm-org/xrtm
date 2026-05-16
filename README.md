# XRTM: AI for event forecasting

[![PyPI](https://img.shields.io/pypi/v/xrtm?style=flat-square)](https://pypi.org/project/xrtm/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square)](LICENSE)

**XRTM** is the product-first shell for running event-forecasting workflows,
inspecting the scored artifacts, and choosing CLI or WebUI for the same
released local product tasks.

## Start here

If you arrived from xrtm.org, PyPI, or this repository, use the authoritative
first-success guide: [docs/getting-started.md](docs/getting-started.md).

That guide walks the released `xrtm==0.8.0` journey in one place:

1. install XRTM
2. choose a CLI-led or WebUI-led first-success path
3. inspect the latest run, report, and exports
4. run a named workflow from the Start or Workflow detail surface
5. use Operations for profiles, monitors, and cleanup
6. use Workbench to clone, safely edit, validate, run, and compare a workflow
7. choose your next path

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
- [Next-release Feature Track](docs/next-release-feature-track.md) for source-only work that is not part of the published `xrtm==0.8.0` package
- [Stack Versioning Policy](https://github.com/xrtm-org/governance/blob/main/policies/stack-versioning-policy.md) for `xrtm` as the product-anchor release and cross-repo version ownership
- Full documentation: [xrtm.org](https://xrtm.org)

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
