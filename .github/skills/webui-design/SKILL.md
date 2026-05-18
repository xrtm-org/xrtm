# XRTM WebUI design skill

Use this skill whenever you change the XRTM product surfaces:

- Hub
- Studio
- Playground
- Observatory
- Batch Runner
- Versions
- API/Webhooks

## Core design contract

Always preserve this style language exactly:

> **muted and postal, monochromatic-muted plate for colors, neo
> minimalism, card-based design with layered elements when appropriate, the
> design philosophy is approachable sophistication**

This is not optional polish. It is the product design contract for XRTM.

## What that means in practice

### Visual tone

- dark or muted restrained palettes over flashy dashboard styling
- soft contrast and layered surfaces instead of loud accents
- cyan/teal and muted orange used sparingly for forecast, selection, and
  uncertainty state
- polished and trustworthy, but not luxury, playful, or enterprise-heavy

### Layout

- narrow vertical rail for primary product navigation when appropriate
- strong page title / utility bar
- card and panel composition as the default organizing system
- dominant workspace in the center for graph or analytics
- contextual side panels for input, inspector, live trace, or actions

### Product identity

- Studio must feel like a forecast workflow builder, not a generic diagramming
  app
- Playground must feel like a live forecasting execution surface, not a generic
  form and log dump
- Observatory must feel like a forecasting analytics and trust surface, not only
  a table of run files
- Batch, Versions, and API/Webhooks must inherit the same visual language and
  trust model

### Interaction rules

- use layering to clarify state, not to decorate
- keep graph nodes compact, legible, and forecasting-native
- make version, validation, trace, score, and status cues visible and coherent
- preserve WebUI and CLI alignment; do not invent WebUI-only execution semantics

## Anti-patterns

Do not drift into:

- bright generic SaaS dashboard styling
- toy-like canvas aesthetics
- heavy enterprise chrome
- generic graph-tool language that hides forecasting semantics
- WebUI-only capabilities that bypass shared product contracts

## References

- `.github/copilot-instructions.md`
- `docs/webui-design-language.md`
- `docs/next-release-feature-track.md`
- `CONTRIBUTING.md`
