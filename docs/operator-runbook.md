# Operator Runbook (xrtm 0.10.6)

Operational guide for the released `xrtm` CLI. Claim-pinned to the commands
that exist in this release: `xrtm start`, `xrtm doctor`, `xrtm runs show`,
`xrtm --version`.

## Daily use

```bash
export OPENAI_API_KEY=sk-...
export OPENAI_BASE_URL="https://api.deepseek.com"   # optional
export OPENAI_MODEL="deepseek-v4-flash"              # optional

xrtm doctor                       # readiness check before spending tokens
xrtm start --limit 10             # forecast 10 questions into runs/
xrtm runs show --latest           # inspect the newest run
```

`xrtm start` exits non-zero only on unhandled failures; configuration and
provider errors print a single attributed message (API-key hint for key
problems, input/network hint otherwise) and exit cleanly.

## Scheduling

There is no daemon in this release. Schedule the CLI itself with cron or a
systemd timer, for example:

```bash
# every 6 hours, off-peak for DeepSeek pricing
0 */6 * * * cd /srv/xrtm && .venv/bin/xrtm start --limit 10 >> logs/xrtm.log 2>&1
```

Use distinct `--runs-dir` values if multiple schedules share a host.

## Artifacts and disk

Every run is a directory under `runs/` (override with `--runs-dir`):

- `run.json`, `run_summary.json` — status and aggregates (written atomically)
- `questions.jsonl`, `forecasts.jsonl` — inputs and per-forecast records
- `eval.json`, `train.json`, `provider.json` — scoring/training/provider payloads
- `events.jsonl` — append-only pipeline events

Runs are small (kilobytes to low megabytes). Prune with your filesystem tool of
choice; nothing outside `runs/` is written.

## Troubleshooting

| Symptom | Action |
|---|---|
| `Error: OPENAI_API_KEY not set` | Export the key or add it to `.env` (see the [Getting Started](getting-started.md) `.env` rules). |
| Connection/validation error | Check `OPENAI_BASE_URL`, network reachability, and model id with `xrtm doctor`. |
| `doctor` reports missing deps | Reinstall: `pip install -U xrtm==0.10.6`. |
| Run dir contains no `eval.json` | Ground truth was unavailable for that corpus slice; forecasts are still recorded. |

## Version and upgrade

```bash
xrtm --version
pip install -U xrtm               # always pair with `xrtm doctor`
```

Release notes live in the GitHub releases; every release states the tested
Python range and the commands it claims.
