# Copilot instructions for `xrtm`

- Treat `xrtm` as the user-facing local-first product repo in the XRTM stack.
- Keep the WebUI and CLI aligned through shared workflow/validation/run
  contracts. Do not introduce a WebUI-only arbitrary-code or plugin execution
  path that the CLI cannot inspect, validate, explain, run, and reproduce.
- Keep release/runtime claims honest and tied to validated behavior.
- When changing Hub, Studio, Playground, Observatory, Batch Runner, Versions, or
  API/Webhooks, use the XRTM WebUI design language below as a repo contract, not
  a loose suggestion.

## XRTM WebUI design language

The required style contract is:

> **muted and postal, monochromatic-muted plate for colors, neo
> minimalism, card-based design with layered elements when appropriate, the
> design philosophy is approachable sophistication**

Practical guidance:

1. Prefer restrained, low-saturation neutrals over bright accent-heavy
   dashboards.
2. Use cards, document-like panels, and layered surfaces as the default layout
   units.
3. Build hierarchy through spacing, typography, alignment, and depth before
   adding ornament.
4. Use layered elements only when they clarify workflow state, analytics, or
   page context.
5. Keep the UI forecasting-native: graph nodes, traces, scores, and analytics
   should read like a forecasting product, not a generic canvas app.
6. Keep visible version/release/status cues stylistically coherent because they
   are part of product trust.

For reusable design guidance, see:

- `docs/webui-design-language.md`
- `.github/skills/webui-design/SKILL.md`

## Testing expectations for WebUI changes

When touching WebUI routes, product APIs that back those routes, or WebUI
styling:

1. run the existing WebUI build
2. run the relevant WebUI/product route tests
3. refresh the shared local preview if the work is intended for live review
