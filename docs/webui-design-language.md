# XRTM WebUI design language

This document is the stable design-language reference for the XRTM product UI.
When the WebUI changes, do not reinterpret the style from scratch; start here.

## Required style contract

> **muted and postal, monochromatic-muted plate for colors, neo
> minimalism, card-based design with layered elements when appropriate, the
> design philosophy is approachable sophistication**

## Product intent

XRTM is a forecasting product. The UI should help users:

1. understand a workflow visually
2. run a question and inspect how the graph executed
3. trust the forecast through evidence, uncertainty, calibration, and history

The design should therefore feel:

- calm
- information-first
- trustworthy
- forecasting-native

It should not feel like:

- a generic diagramming app
- a noisy “AI dashboard”
- a betting-themed gimmick
- an enterprise admin console with interchangeable charts

## Surface composition

### Shared shell

- prefer a narrow vertical navigation rail over a large topnav-only shell
- keep a concise utility/title bar
- keep visible version, environment, and trust cues coherent with the visual
  system

### Hub

- card-based entry surface
- template-first and advanced-path choices should be obvious
- recent activity and readiness should read as calm product context, not noisy
  telemetry

### Studio

- center the canvas as the main workspace
- use left palette + central graph + right inspector structure when possible
- node visuals must read as forecasting workflow units, not generic blocks

### Playground

- emphasize single-question execution
- keep graph and live trace visually connected
- the result should feel attached to the execution path, not dropped below it as
  an unrelated metric

### Observatory

- prioritize trust surfaces: calibration, uncertainty, score history,
  workflow/run comparison, drill-down
- analytics should look product-native and legible before they look dense

### Batch / Versions / API-Webhooks

- keep the same visual trust model as the flagship surfaces
- treat provenance, signing, status, and execution state as first-class design
  elements

## Practical design rules

1. Prefer restrained neutrals and low-saturation color.
2. Use cards and document-like panels as the default composition unit.
3. Use spacing, grouping, typography, and surface depth for hierarchy before
   adding ornament.
4. Use layered elements only when they clarify workflow state, analytics, or
   page context.
5. Keep cyan/teal and muted orange accents purposeful: forecast state,
   uncertainty, selection, trace progression.
6. Keep the product polished and sophisticated without becoming cold, flashy, or
   over-branded.

## Engineering implications

- WebUI and CLI behavior must stay aligned through shared product contracts.
- Do not hide arbitrary code execution inside inspector affordances.
- Visual polish is part of the acceptance bar, not a post-release extra.
- Frontend work should be validated with the existing build/test surfaces and
  live preview where applicable.
