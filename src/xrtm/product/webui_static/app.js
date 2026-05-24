/* eslint-disable */
"use strict";
(() => {
  // src/index.tsx
  var ReactDOMClient = ReactDOM;
  var { useEffect, useMemo, useState } = React;
  var THEME_STORAGE_KEY = "xrtm.webui.themeMode";
  var SYSTEM_THEME_QUERY = "(prefers-color-scheme: dark)";
  var THEME_MODE_SEQUENCE = ["system", "light", "dark"];
  var bootstrap = window.__XRTM_WEBUI_BOOTSTRAP__ ?? {
    api_root: "/api",
    initial_path: window.location.pathname,
    initial_query: window.location.search.replace(/^\?/, ""),
    initial_error: null
  };
  function isThemeMode(value) {
    return value === "system" || value === "light" || value === "dark";
  }
  function readStoredThemeMode() {
    try {
      const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
      return isThemeMode(stored) ? stored : "system";
    } catch (error) {
      console.warn("Unable to read stored theme mode.", error);
      return "system";
    }
  }
  function systemPrefersDark() {
    return typeof window.matchMedia === "function" && window.matchMedia(SYSTEM_THEME_QUERY).matches;
  }
  function resolveTheme(mode, prefersDark) {
    if (mode === "system") return prefersDark ? "dark" : "light";
    return mode;
  }
  function applyDocumentTheme(mode, theme) {
    document.documentElement.dataset.themeMode = mode;
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
  }
  function nextThemeMode(mode) {
    const index = THEME_MODE_SEQUENCE.indexOf(mode);
    return THEME_MODE_SEQUENCE[(index + 1) % THEME_MODE_SEQUENCE.length];
  }
  function currentRoute() {
    return { path: window.location.pathname, search: window.location.search.replace(/^\?/, "") };
  }
  function observatoryRouteFamily(path) {
    return path === "/observatory" || path.startsWith("/observatory/") ? "/observatory" : "/runs";
  }
  function observatoryUiHref(currentPath, target) {
    if (!target) return observatoryRouteFamily(currentPath);
    return /^\/(?:runs|observatory)(?=\/|\?|$)/.test(target) ? target.replace(/^\/(?:runs|observatory)/, observatoryRouteFamily(currentPath)) : target;
  }
  function parsePositiveIntegerInput(value) {
    const normalized = value.trim();
    if (!normalized) return null;
    const parsed = Number.parseInt(normalized, 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }
  function providerLabel(value) {
    if (value === "local-llm") return "Local runtime (optional)";
    if (value === "deterministic") return "Deterministic baseline";
    return value || "Deterministic baseline";
  }
  function preferredWorkbenchWorkflow(requestedWorkflow, latestRunWorkflowName, workflowsPayload) {
    const items = (workflowsPayload?.items || workflowsPayload?.workflows || []).filter((item) => typeof item?.name === "string" && String(item.name).trim());
    if (!items.length) return null;
    const available = new Set(items.map((item) => String(item.name).trim()));
    const normalizedRequestedWorkflow = requestedWorkflow?.trim() || null;
    if (normalizedRequestedWorkflow && available.has(normalizedRequestedWorkflow)) {
      return normalizedRequestedWorkflow;
    }
    const normalizedLatestRunWorkflowName = latestRunWorkflowName?.trim() || null;
    if (normalizedLatestRunWorkflowName && available.has(normalizedLatestRunWorkflowName)) {
      return normalizedLatestRunWorkflowName;
    }
    if (available.has("demo-deterministic")) return "demo-deterministic";
    const first = String(items[0].name || "").trim();
    return first || null;
  }
  function runWithoutRowSelection(event, action) {
    event.stopPropagation();
    action();
  }
  function isNavItemActive(routePath, href) {
    if (href === "/" || href === "/hub") return routePath === "/" || routePath === "/hub" || routePath === "/start" || /^\/workflows\/[^/]+$/.test(routePath);
    if (href === "/start") return routePath === "/start" || /^\/workflows\/[^/]+$/.test(routePath);
    if (href === "/runs" || href === "/observatory") return routePath === "/runs" || routePath === "/observatory" || /^\/(?:runs|observatory)\/[^/]+(?:\/compare\/[^/]+)?$/.test(routePath);
    if (href === "/studio") return routePath === "/studio" || routePath === "/workbench";
    if (href === "/batch") return routePath === "/batch";
    if (href === "/versions") return routePath === "/versions";
    if (href === "/api") return routePath === "/api";
    return routePath === href;
  }
  function railIcon(label, href) {
    const key = `${label} ${href}`.toLowerCase();
    if (key.includes("hub")) return "Hu";
    if (key.includes("studio")) return "St";
    if (key.includes("playground")) return "Pg";
    if (key.includes("observatory") || key.includes("runs")) return "Ob";
    if (key.includes("batch")) return "Bt";
    if (key.includes("version")) return "Vr";
    if (key.includes("control") || key.includes("setting")) return "Ct";
    if (key.includes("api")) return "Ap";
    if (key.includes("operation")) return "Op";
    if (key.includes("advanced")) return "Ad";
    return label.slice(0, 2).toUpperCase();
  }
  function surfaceTitle(routePath, appChrome) {
    if (routePath === "/" || routePath === "/hub") {
      return {
        title: "Hub",
        eyebrow: "Local entry",
        summary: "Choose quickstart, Playground, Studio, or recent local work."
      };
    }
    if (routePath === "/start") {
      return {
        title: "Start",
        eyebrow: "Quickstart",
        summary: "Run first success, bounded demos, or a named workflow without leaving the WebUI."
      };
    }
    if (/^\/workflows\/[^/]+$/.test(routePath)) {
      return {
        title: "Workflow detail",
        eyebrow: "Inspect + launch",
        summary: "Validate, inspect, and run a reusable workflow from the shared shell."
      };
    }
    if (routePath === "/studio" || routePath === "/workbench") {
      return {
        title: "Studio",
        eyebrow: "Graph IDE",
        summary: "Build, validate, and version forecasting workflows visually."
      };
    }
    if (routePath === "/playground") {
      return {
        title: "Playground",
        eyebrow: "Single question",
        summary: "Run one question through a workflow and inspect the trace."
      };
    }
    if (routePath === "/runs" || routePath === "/observatory" || /^\/(?:runs|observatory)\//.test(routePath)) {
      return {
        title: "Observatory",
        eyebrow: "Analytics",
        summary: "Inspect runs, calibration, uncertainty, and workflow performance."
      };
    }
    if (routePath === "/batch") {
      return {
        title: "Batch Runner",
        eyebrow: "Dataset execution",
        summary: "Map saved workflow versions to tables of forecasting questions."
      };
    }
    if (routePath === "/versions") {
      return {
        title: "Versions",
        eyebrow: "Version lineage",
        summary: "Compare workflow revisions, diffs, defaults, and rollbacks."
      };
    }
    if (routePath === "/api") {
      return {
        title: "Control",
        eyebrow: "Settings + API",
        summary: "Run saved versions, webhooks, and local integration settings."
      };
    }
    if (routePath === "/operations") {
      return {
        title: "Operations",
        eyebrow: "Profiles + retention",
        summary: "Manage repeatable profiles, monitors, and artifact cleanup locally."
      };
    }
    if (routePath === "/advanced") {
      return {
        title: "Advanced",
        eyebrow: "Extended lanes",
        summary: "Review advanced capabilities with explicit readiness and safety labels."
      };
    }
    return {
      title: String(appChrome.name || "XRTM WebUI"),
      eyebrow: "Local cockpit",
      summary: String(appChrome.summary || "File-backed runs, local workflows, and resumable SQLite state.")
    };
  }
  function EnvironmentCardView({ card }) {
    return /* @__PURE__ */ React.createElement("article", { className: "environment-card" }, /* @__PURE__ */ React.createElement("div", { className: "environment-card-head" }, /* @__PURE__ */ React.createElement("strong", null, card.label), card.status ? /* @__PURE__ */ React.createElement(StatusPill, { value: String(card.status) }) : null), /* @__PURE__ */ React.createElement("span", { className: "environment-card-value", title: String(card.value || "\u2014") }, card.value || "\u2014"), card.detail ? /* @__PURE__ */ React.createElement("span", { className: "environment-card-detail", title: String(card.detail) }, card.detail) : null);
  }
  function environmentCardKey(card) {
    return String(card.key || card.label || "environment-card");
  }
  function environmentCardValue(card) {
    const value = card?.value;
    return value === void 0 || value === null || value === "" ? "\u2014" : String(value);
  }
  function EnvironmentDisclosureView({ cards, trustCues, status }) {
    if (!cards.length && !trustCues.length) return null;
    const byKey = new Map(cards.map((card) => [environmentCardKey(card), card]));
    const localLlmCard = byKey.get("local-llm");
    const workflowsCard = byKey.get("workflows");
    const runsCard = byKey.get("runs");
    const appDbCard = byKey.get("app-db");
    const versionCard = byKey.get("version");
    const seenCardKeys = /* @__PURE__ */ new Set();
    const prioritizedCards = [
      localLlmCard,
      workflowsCard,
      runsCard,
      appDbCard,
      versionCard,
      ...cards.filter((card) => !["local-llm", "workflows", "runs", "app-db", "version"].includes(environmentCardKey(card)))
    ].filter((card) => {
      if (!card) return false;
      const key = environmentCardKey(card);
      if (seenCardKeys.has(key)) return false;
      seenCardKeys.add(key);
      return true;
    });
    const drawerSummary = trustCues.join(" \u2022 ") || "Local environment detail";
    const statusLabel = String(status.label || "Open system detail");
    const statusDetail = String(status.detail || drawerSummary);
    const statusTitle = `${statusLabel}. ${statusDetail}`;
    return /* @__PURE__ */ React.createElement("details", { className: "environment-shell system-disclosure", id: "shell-environment" }, /* @__PURE__ */ React.createElement(
      "summary",
      {
        className: `shell-status-button ${String(status.tone || "neutral")}`,
        title: statusTitle,
        "aria-label": statusTitle
      },
      /* @__PURE__ */ React.createElement("span", { className: "shell-status-dot", "aria-hidden": "true" })
    ), /* @__PURE__ */ React.createElement("section", { className: "system-drawer", "aria-label": "System detail" }, /* @__PURE__ */ React.createElement("header", { className: "system-drawer-head" }, /* @__PURE__ */ React.createElement("div", { className: "system-drawer-title-row" }, /* @__PURE__ */ React.createElement("div", { className: "system-drawer-copy" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "System"), /* @__PURE__ */ React.createElement("strong", null, statusLabel)), versionCard ? /* @__PURE__ */ React.createElement("span", { className: "version-pill" }, environmentCardValue(versionCard)) : null), /* @__PURE__ */ React.createElement("p", null, statusDetail), trustCues.length ? /* @__PURE__ */ React.createElement("div", { className: "system-trust-row", "aria-label": "Local shell trust cues" }, trustCues.map((cue) => /* @__PURE__ */ React.createElement("span", { key: cue, className: "system-trust-pill" }, cue))) : null), /* @__PURE__ */ React.createElement("section", { className: "environment-strip system-drawer-grid", "aria-label": "Environment status" }, prioritizedCards.map((card) => /* @__PURE__ */ React.createElement(EnvironmentCardView, { key: environmentCardKey(card), card })))));
  }
  function DensityDisclosure({
    title,
    detail,
    className = "",
    defaultOpen = false,
    children
  }) {
    return /* @__PURE__ */ React.createElement("details", { className: ["density-disclosure", className].filter(Boolean).join(" "), open: defaultOpen || void 0 }, /* @__PURE__ */ React.createElement("summary", null, /* @__PURE__ */ React.createElement("div", { className: "density-disclosure-copy" }, /* @__PURE__ */ React.createElement("strong", null, title), detail ? /* @__PURE__ */ React.createElement("p", null, detail) : null)), /* @__PURE__ */ React.createElement("div", { className: "density-disclosure-body" }, children));
  }
  function RouteIdentityPanel({
    eyebrow,
    title,
    summary,
    items,
    className = ""
  }) {
    return /* @__PURE__ */ React.createElement("section", { className: ["panel", "route-identity-panel", className].filter(Boolean).join(" ") }, /* @__PURE__ */ React.createElement("div", { className: "route-identity-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, eyebrow), /* @__PURE__ */ React.createElement("h3", null, title)), /* @__PURE__ */ React.createElement("p", null, summary)), /* @__PURE__ */ React.createElement("div", { className: "route-identity-grid" }, items.map((item) => /* @__PURE__ */ React.createElement("article", { key: item.label, className: "route-identity-card" }, /* @__PURE__ */ React.createElement("span", null, item.label), /* @__PURE__ */ React.createElement("strong", null, item.title), /* @__PURE__ */ React.createElement("p", null, item.detail)))));
  }
  async function requestJson(url, init) {
    const response = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...init
    });
    const body = await response.text();
    const contentType = response.headers.get("Content-Type") || "";
    let payload = {};
    if (body) {
      if (contentType.includes("application/json")) {
        payload = JSON.parse(body);
      } else if (!response.ok) {
        throw new Error(body);
      } else {
        throw new Error(`Expected JSON response from ${url}, received ${contentType || "unknown content type"}`);
      }
    }
    if (!response.ok) {
      throw new Error(payload.error || `${response.status} ${response.statusText}`);
    }
    return payload;
  }
  function draftFromPayload(payload) {
    if (!payload) return null;
    return payload.draft && typeof payload.draft === "object" ? payload.draft : payload;
  }
  function studioEdgeKey(edge) {
    const from = edge.from || edge.source;
    const to = edge.to || edge.target;
    if (from || to) return `${from || "?"}->${to || "?"}:${edge.label || ""}`;
    return String(edge.id || "edge");
  }
  function suggestNodeName(item, existingNodes) {
    const existing = new Set(existingNodes.map((node) => String(node.name || "").toLowerCase()));
    const raw = String(item.name || item.implementation || "node").split(/[/:.]/).pop() || "node";
    const base = raw.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "node";
    let candidate = base;
    let suffix = 2;
    while (existing.has(candidate.toLowerCase())) {
      candidate = `${base}_${suffix}`;
      suffix += 1;
    }
    return candidate;
  }
  var PALETTE_KIND_LABELS = {
    tool: "Tools",
    model: "Models",
    scorer: "Scorers",
    aggregator: "Aggregators",
    router: "Routers",
    "human-gate": "Human gates"
  };
  var PALETTE_KIND_ORDER = ["tool", "model", "router", "aggregator", "scorer", "human-gate"];
  function paletteGroupLabel(kind) {
    if (PALETTE_KIND_LABELS[kind]) return PALETTE_KIND_LABELS[kind];
    return kind.split(/[^a-z0-9]+/i).filter(Boolean).map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ") || "Other";
  }
  function paletteMatchesQuery(item, query) {
    if (!query) return true;
    const fields = [
      item.label,
      item.name,
      item.kind,
      item.implementation,
      item.summary,
      item.description
    ];
    return fields.some((value) => String(value || "").toLowerCase().includes(query));
  }
  function useJsonResource(url, deps) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(Boolean(url));
    const [error, setError] = useState(null);
    const [token, setToken] = useState(0);
    useEffect(() => {
      if (!url) {
        setData(null);
        setLoading(false);
        setError(null);
        return;
      }
      let cancelled = false;
      setLoading(true);
      setError(null);
      requestJson(url).then((payload) => {
        if (!cancelled) {
          setData(payload);
          setLoading(false);
        }
      }).catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
          setLoading(false);
        }
      });
      return () => {
        cancelled = true;
      };
    }, [url, token, ...deps]);
    return { data, loading, error, reload: () => setToken((value) => value + 1) };
  }
  function ThemeModeSwitch({ mode, resolvedTheme, onChange }) {
    const current = mode === "system" ? { icon: "\u25D0", label: `Theme: system (${resolvedTheme})` } : mode === "light" ? { icon: "\u263C", label: "Theme: light" } : { icon: "\u263E", label: "Theme: dark" };
    const next = nextThemeMode(mode);
    const nextLabel = next === "system" ? "system" : next;
    return /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        className: "theme-icon-button",
        "data-theme-mode": mode,
        title: `${current.label}. Click to switch to ${nextLabel}.`,
        "aria-label": `${current.label}. Click to switch to ${nextLabel}.`,
        onClick: () => onChange(next)
      },
      /* @__PURE__ */ React.createElement("span", { className: "theme-icon", "aria-hidden": "true" }, current.icon)
    );
  }
  function App() {
    const [route, setRoute] = useState({ path: bootstrap.initial_path, search: bootstrap.initial_query });
    const [shellRefresh, setShellRefresh] = useState(0);
    const [themeMode, setThemeMode] = useState(() => readStoredThemeMode());
    const [prefersDark, setPrefersDark] = useState(() => systemPrefersDark());
    const shell = useJsonResource(`${bootstrap.api_root}/app-shell`, [route.path, route.search, shellRefresh]);
    const resolvedTheme = resolveTheme(themeMode, prefersDark);
    useEffect(() => {
      const onPopState = () => setRoute(currentRoute());
      window.addEventListener("popstate", onPopState);
      return () => window.removeEventListener("popstate", onPopState);
    }, []);
    useEffect(() => {
      if (typeof window.matchMedia !== "function") return void 0;
      const query = window.matchMedia(SYSTEM_THEME_QUERY);
      const onChange = (event) => setPrefersDark(event.matches);
      setPrefersDark(query.matches);
      if (typeof query.addEventListener === "function") {
        query.addEventListener("change", onChange);
        return () => query.removeEventListener("change", onChange);
      }
      query.addListener(onChange);
      return () => query.removeListener(onChange);
    }, []);
    useEffect(() => {
      applyDocumentTheme(themeMode, resolvedTheme);
      try {
        window.localStorage.setItem(THEME_STORAGE_KEY, themeMode);
      } catch (error) {
        console.warn("Unable to persist theme mode.", error);
      }
    }, [resolvedTheme, themeMode]);
    const navigate = React.useCallback((path) => {
      window.history.pushState({}, "", path);
      setRoute(currentRoute());
    }, []);
    const refreshShell = React.useCallback(() => setShellRefresh((value) => value + 1), []);
    const appChrome = shell.data?.app || {};
    const nav = appChrome.nav ?? [
      { label: "Hub", href: "/hub" },
      { label: "Studio", href: "/studio" },
      { label: "Playground", href: "/playground" },
      { label: "Observatory", href: "/observatory" },
      { label: "Batch", href: "/batch" },
      { label: "Versions", href: "/versions" },
      { label: "API", href: "/api" },
      { label: "Operations", href: "/operations" },
      { label: "Advanced", href: "/advanced" }
    ];
    const trustCues = appChrome.trust_cues || ["Shared local shell", "File-backed history", "SQLite draft state"];
    const environmentCards = shell.data?.environment?.cards || [
      { key: "version", label: "Version", value: shell.data?.app?.version ? `xrtm ${String(shell.data.app.version)}` : "unknown" },
      { key: "runs", label: "Runs", value: shell.data?.environment?.runs_dir || "\u2014" },
      { key: "workflows", label: "Workflows", value: shell.data?.environment?.workflows_dir || "\u2014" },
      {
        key: "local-llm",
        label: "Local runtime",
        value: shell.data?.environment?.local_llm?.healthy ? "Available" : "Optional",
        status: shell.data?.environment?.local_llm?.healthy ? "available" : "optional",
        detail: shell.data?.environment?.local_llm?.base_url || shell.data?.environment?.local_llm?.error || "Unavailable"
      },
      { key: "app-db", label: "App DB", value: shell.data?.environment?.app_db || "\u2014" }
    ];
    const localLlmCard = environmentCards.find((card) => environmentCardKey(card) === "local-llm");
    const shellStatus = appChrome.system_status || (localLlmCard?.status === "available" ? {
      tone: "healthy",
      label: "Deterministic baseline ready",
      detail: String(localLlmCard.detail || "Optional local runtime is available.")
    } : localLlmCard?.status === "unavailable" || localLlmCard?.status === "optional" ? {
      tone: "healthy",
      label: "Deterministic baseline ready",
      detail: String(localLlmCard.detail || "Optional local runtime is not configured.")
    } : {
      tone: "neutral",
      label: "Open System",
      detail: "View compact local environment detail."
    });
    let page;
    if (route.path === "/" || route.path === "/hub") {
      page = /* @__PURE__ */ React.createElement(HubPage, { shell: shell.data, navigate });
    } else if (route.path === "/start") {
      page = /* @__PURE__ */ React.createElement(StartPage, { shell: shell.data, navigate, onMutate: refreshShell });
    } else if (route.path === "/runs" || route.path === "/observatory") {
      page = /* @__PURE__ */ React.createElement(RunsPage, { route, navigate });
    } else if (route.path === "/playground") {
      page = /* @__PURE__ */ React.createElement(PlaygroundPage, { route, shell: shell.data, navigate, onMutate: refreshShell });
    } else if (route.path === "/batch") {
      page = /* @__PURE__ */ React.createElement(BatchPage, { navigate });
    } else if (route.path === "/versions") {
      page = /* @__PURE__ */ React.createElement(VersionsPage, { navigate });
    } else if (route.path === "/api") {
      page = /* @__PURE__ */ React.createElement(ApiControlPage, { navigate });
    } else if (route.path === "/operations") {
      page = /* @__PURE__ */ React.createElement(OperationsPage, { navigate, onMutate: refreshShell });
    } else if (route.path === "/advanced") {
      page = /* @__PURE__ */ React.createElement(AdvancedPage, null);
    } else if (route.path === "/studio" || route.path === "/workbench") {
      page = /* @__PURE__ */ React.createElement(WorkbenchPage, { route, shell: shell.data, navigate, onMutate: refreshShell });
    } else if (/^\/(?:runs|observatory)\/[^/]+\/compare\/[^/]+$/.test(route.path)) {
      const match = route.path.match(/^\/(?:runs|observatory)\/([^/]+)\/compare\/([^/]+)$/);
      page = /* @__PURE__ */ React.createElement(ComparePage, { routePath: route.path, candidateRunId: match[1], baselineRunId: match[2], navigate });
    } else if (/^\/workflows\/[^/]+$/.test(route.path)) {
      page = /* @__PURE__ */ React.createElement(WorkflowDetailPage, { workflowName: decodeURIComponent(route.path.split("/")[2]), navigate, onMutate: refreshShell });
    } else if (/^\/(?:runs|observatory)\/[^/]+$/.test(route.path)) {
      page = /* @__PURE__ */ React.createElement(RunDetailPage, { routePath: route.path, runId: route.path.split("/")[2], navigate, onMutate: refreshShell });
    } else {
      page = /* @__PURE__ */ React.createElement(WorkbenchPage, { route, shell: shell.data, navigate, onMutate: refreshShell });
    }
    const surface = surfaceTitle(route.path, appChrome);
    return /* @__PURE__ */ React.createElement("div", { className: "app-shell product-shell" }, /* @__PURE__ */ React.createElement("aside", { className: "icon-rail", "aria-label": "Primary product navigation" }, /* @__PURE__ */ React.createElement(
      "a",
      {
        className: "rail-brand",
        href: "/hub",
        onClick: (event) => {
          event.preventDefault();
          navigate("/hub");
        },
        "aria-label": "XRTM Hub"
      },
      "X"
    ), /* @__PURE__ */ React.createElement("nav", { className: "rail-nav", "aria-label": "Primary" }, nav.map((item) => {
      const href = String(item.href || "/");
      const active = isNavItemActive(route.path, href);
      const label = String(item.label || href);
      return /* @__PURE__ */ React.createElement(
        "a",
        {
          key: href,
          className: active ? "rail-link active" : "rail-link",
          href,
          title: label,
          "aria-label": label,
          "aria-current": active ? "page" : void 0,
          onClick: (event) => {
            event.preventDefault();
            navigate(href);
          }
        },
        /* @__PURE__ */ React.createElement("span", null, railIcon(label, href))
      );
    })), /* @__PURE__ */ React.createElement("button", { className: "rail-exit", title: "Local shell", "aria-label": "Local shell" }, "LS")), /* @__PURE__ */ React.createElement("section", { className: "product-main" }, /* @__PURE__ */ React.createElement("header", { className: "product-topbar" }, /* @__PURE__ */ React.createElement("div", { className: "product-title-block" }, /* @__PURE__ */ React.createElement("div", { className: "product-route-line" }, /* @__PURE__ */ React.createElement("h1", null, surface.title), /* @__PURE__ */ React.createElement("span", { className: "product-route-context" }, surface.eyebrow)), /* @__PURE__ */ React.createElement("p", { className: "shell-copy" }, surface.summary)), /* @__PURE__ */ React.createElement("div", { className: "product-action-cluster" }, shell.data?.app?.version ? /* @__PURE__ */ React.createElement("span", { className: "version-pill" }, "v", String(shell.data.app.version)) : null, shell.data ? /* @__PURE__ */ React.createElement(EnvironmentDisclosureView, { cards: environmentCards, trustCues, status: shellStatus }) : null, /* @__PURE__ */ React.createElement(ThemeModeSwitch, { mode: themeMode, resolvedTheme, onChange: setThemeMode }), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        className: "shell-icon-button",
        title: "Open API control",
        "aria-label": "Open API control",
        onClick: () => navigate("/api")
      },
      /* @__PURE__ */ React.createElement("span", { "aria-hidden": "true" }, "\u2699")
    ))), bootstrap.initial_error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Initial error", body: bootstrap.initial_error }) : null, shell.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "App shell error", body: shell.error }) : null, shell.loading && !shell.data ? /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading app shell" }) : null, /* @__PURE__ */ React.createElement("div", { className: "page-stack" }, page)));
  }
  function HubPage({ shell, navigate }) {
    const hub = shell?.hub || shell?.overview;
    if (!hub) {
      return /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading Hub" });
    }
    const hero = hub.hero || shell?.overview?.hero || {};
    const doors = hub.doors || [];
    const templates = hub.templates || [];
    const workflows = hub.workflows || [];
    const readiness = hub.readiness || [];
    const recentRuns = hub.recent_runs || shell?.overview?.recent_runs || [];
    const compatibility = hub.compatibility || shell?.overview?.compatibility || {};
    const counts = hub.counts || shell?.overview?.counts || {};
    const latestRun = hub.latest_run || shell?.overview?.latest_run;
    const resumeTarget = hub.resume_target || shell?.overview?.resume_target || {};
    const playgroundAction = doors[0]?.primary_cta || {};
    const quickstartAction = doors[0]?.secondary_cta || {};
    const studioAction = doors[1]?.primary_cta || {};
    const hasResumeTarget = Boolean(resumeTarget.href) && String(resumeTarget.kind || "") !== "studio";
    const heroMetrics = [
      {
        label: "Templates",
        value: counts.templates ?? templates.length,
        detail: "Starter paths"
      },
      {
        label: "Workflows",
        value: counts.workflows ?? workflows.length,
        detail: "Indexed locally"
      },
      {
        label: "Runs",
        value: counts.runs ?? 0,
        detail: latestRun ? "Latest ready" : "Fresh shell"
      }
    ];
    const heroReadiness = readiness.slice(0, 2);
    const leadTemplates = templates.slice(0, 3);
    const overflowTemplates = templates.slice(3);
    const continuityTitle = hasResumeTarget ? String(resumeTarget.label || "Resume local work") : latestRun ? "Latest local run is ready" : "Fresh local shell";
    const continuitySummary = hasResumeTarget ? "Pick up the latest draft, Playground session, or run without leaving the Hub." : latestRun ? "Inspect the latest run when you want traces, artifacts, or provenance." : "Quickstart, Playground, and Studio are ready when you want a first local run or draft.";
    const workflowDisclosureTitle = `Indexed workflows \xB7 ${workflows.length}`;
    return /* @__PURE__ */ React.createElement("main", { className: "page-grid hub-page" }, /* @__PURE__ */ React.createElement("section", { className: "panel hero-panel hub-hero" }, /* @__PURE__ */ React.createElement("div", { className: "hub-hero-copy" }, /* @__PURE__ */ React.createElement("div", { className: "hub-hero-heading" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, hero.eyebrow || "Entry route"), /* @__PURE__ */ React.createElement("h2", null, hero.title || "Choose a first move"), /* @__PURE__ */ React.createElement("p", null, hero.summary || "Run the first-success quickstart, open Playground for one bounded question, or enter Studio for a draft.")), /* @__PURE__ */ React.createElement("div", { className: "button-row hub-hero-actions" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => navigate(String(playgroundAction.href || "/playground")) }, String(playgroundAction.label || "Open Playground")), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(String(studioAction.href || "/studio")) }, String(studioAction.label || "Open Studio")), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(String(quickstartAction.href || "/start")) }, String(quickstartAction.label || "Run first-success quickstart"))), /* @__PURE__ */ React.createElement("div", { className: "hub-hero-metrics", "aria-label": "Hub overview" }, heroMetrics.map((item) => /* @__PURE__ */ React.createElement("article", { key: item.label, className: "hub-hero-metric" }, /* @__PURE__ */ React.createElement("span", null, item.label), /* @__PURE__ */ React.createElement("strong", null, formatValue(item.value)), /* @__PURE__ */ React.createElement("small", null, item.detail))))), /* @__PURE__ */ React.createElement("aside", { className: "hub-hero-aside" }, /* @__PURE__ */ React.createElement("div", { className: "hub-hero-aside-header" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Continuity"), /* @__PURE__ */ React.createElement("h3", null, continuityTitle), /* @__PURE__ */ React.createElement("p", null, continuitySummary)), hasResumeTarget ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button hub-resume-button", onClick: () => navigate(String(resumeTarget.href)) }, String(resumeTarget.label || "Resume")) : null, heroReadiness.length ? /* @__PURE__ */ React.createElement("div", { className: "hub-hero-readiness", "aria-label": "Hub readiness" }, heroReadiness.map((item) => /* @__PURE__ */ React.createElement("div", { key: String(item.key || item.label), className: "hub-readiness-chip" }, /* @__PURE__ */ React.createElement("span", null, item.label), /* @__PURE__ */ React.createElement("strong", null, item.value)))) : null)), /* @__PURE__ */ React.createElement("section", { className: "hub-content-grid" }, /* @__PURE__ */ React.createElement("div", { className: "hub-main-column" }, /* @__PURE__ */ React.createElement("section", { className: "hub-section hub-door-section", "aria-label": "Hub entry doors" }, /* @__PURE__ */ React.createElement("div", { className: "section-header hub-section-header" }, /* @__PURE__ */ React.createElement("div", { className: "hub-section-intro" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Entry doors"), /* @__PURE__ */ React.createElement("h3", null, "Pick a calm starting lane"), /* @__PURE__ */ React.createElement("p", null, "Keep the template-first path upfront, while the workflow-authoring lane stays available when you need it."))), /* @__PURE__ */ React.createElement("div", { className: "hub-door-grid" }, doors.map((door, index) => /* @__PURE__ */ React.createElement("article", { key: String(door.key || door.label), className: "panel section-stack hub-door-card" }, /* @__PURE__ */ React.createElement("div", { className: "hub-door-topline" }, /* @__PURE__ */ React.createElement("span", { className: "hub-door-path" }, index === 0 ? "Template-first path" : "Authoring path"), /* @__PURE__ */ React.createElement(StatusPill, { value: String(door.status || "local") })), /* @__PURE__ */ React.createElement("div", { className: "hub-door-heading" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, door.label), /* @__PURE__ */ React.createElement("h3", null, door.title)), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, door.summary), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, door.primary_cta ? /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => navigate(String(door.primary_cta.href)) }, String(door.primary_cta.label)) : null, door.secondary_cta ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(String(door.secondary_cta.href)) }, String(door.secondary_cta.label)) : null))))), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack hub-section", id: "workflow-config-fields" }, /* @__PURE__ */ React.createElement("div", { className: "section-header hub-section-header" }, /* @__PURE__ */ React.createElement("div", { className: "hub-section-intro" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Templates"), /* @__PURE__ */ React.createElement("h3", null, "Starter templates"), /* @__PURE__ */ React.createElement("p", null, "Keep the newcomer-default set upfront, then open the broader starter catalog only when you need another path.")), /* @__PURE__ */ React.createElement("span", { className: "section-count" }, templates.length, " starter ", templates.length === 1 ? "path" : "paths")), /* @__PURE__ */ React.createElement("div", { className: "hub-template-grid" }, leadTemplates.map((template) => /* @__PURE__ */ React.createElement("article", { key: String(template.template_id), className: "workflow-tile hub-template-card" }, /* @__PURE__ */ React.createElement("div", { className: "workflow-tile-head" }, /* @__PURE__ */ React.createElement("strong", null, template.title), /* @__PURE__ */ React.createElement(StatusPill, { value: String(template.workflow_kind || "workflow") })), /* @__PURE__ */ React.createElement("p", { className: "workflow-note hub-card-copy" }, template.description), (template.tags || []).length ? /* @__PURE__ */ React.createElement("div", { className: "hub-tag-row" }, (template.tags || []).slice(0, 3).map((tag) => /* @__PURE__ */ React.createElement("span", { key: tag, className: "hub-tag" }, tag))) : null, /* @__PURE__ */ React.createElement("div", { className: "button-row hub-card-actions" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => navigate(String(template.playground_href || `/playground?context=template&template=${template.template_id}`)) }, "Open Playground"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(String(template.studio_href || `/studio?mode=template&template=${template.template_id}`)) }, "Open Studio"))))), overflowTemplates.length ? /* @__PURE__ */ React.createElement(
      DensityDisclosure,
      {
        className: "hub-template-disclosure",
        title: `More starter paths \xB7 ${overflowTemplates.length}`,
        detail: "Keep the broader starter catalog nearby without turning the Hub into a wall of equal-priority cards."
      },
      /* @__PURE__ */ React.createElement("div", { className: "hub-template-grid" }, overflowTemplates.map((template) => /* @__PURE__ */ React.createElement("article", { key: String(template.template_id), className: "workflow-tile hub-template-card" }, /* @__PURE__ */ React.createElement("div", { className: "workflow-tile-head" }, /* @__PURE__ */ React.createElement("strong", null, template.title), /* @__PURE__ */ React.createElement(StatusPill, { value: String(template.workflow_kind || "workflow") })), /* @__PURE__ */ React.createElement("p", { className: "workflow-note hub-card-copy" }, template.description), (template.tags || []).length ? /* @__PURE__ */ React.createElement("div", { className: "hub-tag-row" }, (template.tags || []).slice(0, 3).map((tag) => /* @__PURE__ */ React.createElement("span", { key: tag, className: "hub-tag" }, tag))) : null, /* @__PURE__ */ React.createElement("div", { className: "button-row hub-card-actions" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => navigate(String(template.playground_href || `/playground?context=template&template=${template.template_id}`)) }, "Open Playground"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(String(template.studio_href || `/studio?mode=template&template=${template.template_id}`)) }, "Open Studio")))))
    ) : null, !templates.length ? /* @__PURE__ */ React.createElement(EmptyState, { title: "No starter templates found", body: "The Hub could not load starter templates from the authoring catalog." }) : null), /* @__PURE__ */ React.createElement(
      DensityDisclosure,
      {
        className: "panel hub-workflow-disclosure",
        title: workflowDisclosureTitle,
        detail: "Open the broader workflow catalog only when you want a specific saved workflow or draft path."
      },
      workflows.length ? /* @__PURE__ */ React.createElement("div", { className: "hub-workflow-scroll" }, /* @__PURE__ */ React.createElement("div", { className: "action-list hub-workflow-list" }, workflows.map((workflow) => /* @__PURE__ */ React.createElement("article", { key: String(workflow.name), className: "workflow-tile hub-workflow-card" }, /* @__PURE__ */ React.createElement("div", { className: "hub-workflow-copy" }, /* @__PURE__ */ React.createElement("div", { className: "workflow-tile-head" }, /* @__PURE__ */ React.createElement("strong", null, workflow.title || workflow.name), /* @__PURE__ */ React.createElement(SourceBadge, { source: String(workflow.source || "builtin") })), /* @__PURE__ */ React.createElement("p", { className: "hub-workflow-name" }, workflow.name), /* @__PURE__ */ React.createElement("p", { className: "workflow-note hub-card-copy" }, workflow.description || "Reusable workflow from the registry."), /* @__PURE__ */ React.createElement("div", { className: "hub-workflow-meta" }, /* @__PURE__ */ React.createElement("span", null, "Runtime ", workflow.runtime_provider || "deterministic"), /* @__PURE__ */ React.createElement("span", null, formatValue(workflow.question_limit), " questions"))), /* @__PURE__ */ React.createElement("div", { className: "button-row hub-workflow-actions" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => navigate(String(workflow.playground_href || `/playground?context=workflow&workflow=${workflow.name}`)) }, "Open Playground"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(String(workflow.studio_href || `/studio?workflow=${workflow.name}`)) }, "Open Studio")))))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No workflows indexed", body: "Refresh the local workflow registry or create a draft in Studio." })
    )), /* @__PURE__ */ React.createElement("aside", { className: "hub-side-column" }, /* @__PURE__ */ React.createElement("section", { className: "panel section-stack hub-context-panel" }, /* @__PURE__ */ React.createElement("div", { className: "section-header hub-section-header" }, /* @__PURE__ */ React.createElement("div", { className: "hub-section-intro" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Route context"), /* @__PURE__ */ React.createElement("h3", null, "Recent activity and local posture"), /* @__PURE__ */ React.createElement("p", null, "Keep continuity visible in one calm side rail instead of stacking multiple equal-weight panels."))), /* @__PURE__ */ React.createElement("div", { className: "hub-context-block" }, /* @__PURE__ */ React.createElement("div", { className: "hub-context-header" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Recent activity"), /* @__PURE__ */ React.createElement("h4", null, "Latest local run")), latestRun ? /* @__PURE__ */ React.createElement("article", { className: "hub-run-card" }, /* @__PURE__ */ React.createElement("div", { className: "hub-run-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, latestRun.workflow?.title || latestRun.run_id), /* @__PURE__ */ React.createElement("p", { className: "workflow-note" }, latestRun.workflow?.name || latestRun.provider || "Local run")), /* @__PURE__ */ React.createElement(StatusPill, { value: String(latestRun.status || "ready") })), /* @__PURE__ */ React.createElement("dl", { className: "context-list hub-run-meta" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Updated"), /* @__PURE__ */ React.createElement("dd", null, latestRun.updated_at || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Run ID"), /* @__PURE__ */ React.createElement("dd", null, latestRun.run_id || "\u2014"))), /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => navigate(`/observatory/${latestRun.run_id}`) }, "Inspect latest run")) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No runs yet", body: "Open Playground or the first-success quickstart to create a local run history entry." })), recentRuns.length > 1 ? /* @__PURE__ */ React.createElement("div", { className: "hub-context-block" }, /* @__PURE__ */ React.createElement(
      DensityDisclosure,
      {
        className: "hub-recent-runs-disclosure",
        title: `Recent run shortcuts \xB7 ${recentRuns.length}`,
        detail: "Keep the broader local evidence trail nearby without crowding the lead continuity card."
      },
      /* @__PURE__ */ React.createElement("div", { className: "action-list" }, recentRuns.slice(1).map((item) => /* @__PURE__ */ React.createElement(
        "button",
        {
          key: String(item.run_id),
          className: "secondary-button action-button",
          onClick: () => navigate(String(item.href || `/observatory/${item.run_id}`))
        },
        /* @__PURE__ */ React.createElement("span", null, String(item.label || item.run_id)),
        item.summary ? /* @__PURE__ */ React.createElement("small", null, String(item.summary)) : null
      )))
    )) : null, /* @__PURE__ */ React.createElement("div", { className: "hub-context-block" }, readiness.length ? /* @__PURE__ */ React.createElement(
      DensityDisclosure,
      {
        className: "hub-readiness-disclosure",
        title: `Local readiness \xB7 ${readiness.length}`,
        detail: "System posture stays visible here without competing with the main entry flow."
      },
      /* @__PURE__ */ React.createElement("div", { className: "hub-readiness-list" }, readiness.map((item) => /* @__PURE__ */ React.createElement("article", { key: String(item.key || item.label), className: "info-card hub-readiness-card" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("strong", null, item.label), /* @__PURE__ */ React.createElement(StatusPill, { value: String(item.status || "ready") })), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, item.value), item.detail ? /* @__PURE__ */ React.createElement("span", { className: "workflow-note" }, item.detail) : null)))
    ) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No readiness data", body: "Hub readiness details were not available from the local shell." })), compatibility.summary ? /* @__PURE__ */ React.createElement("div", { className: "hub-context-block" }, /* @__PURE__ */ React.createElement("article", { className: "info-card hub-compatibility-card" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("strong", null, String(compatibility.label || "Workbench compatibility")), /* @__PURE__ */ React.createElement(StatusPill, { value: "compatible" })), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, String(compatibility.summary)), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, compatibility.primary_cta?.href ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(String(compatibility.primary_cta.href)) }, String(compatibility.primary_cta.label || "Open Studio")) : null, compatibility.secondary_cta?.href ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(String(compatibility.secondary_cta.href)) }, String(compatibility.secondary_cta.label || "Open Workbench")) : null))) : null))));
  }
  function BatchPage({ navigate }) {
    const batch = useJsonResource(`${bootstrap.api_root}/batch`, []);
    const versions = useJsonResource(`${bootstrap.api_root}/versions`, []);
    const [workflowName, setWorkflowName] = useState("");
    const [versionId, setVersionId] = useState("");
    const [label, setLabel] = useState("");
    const [rowsText, setRowsText] = useState('Will the batch remain local?\n{"question":"Does JSONL work?"}');
    const [notice, setNotice] = useState(null);
    const [busy, setBusy] = useState(false);
    const [activeBatchId, setActiveBatchId] = useState("");
    const versionItems = versions.data?.items || [];
    const batchItems = batch.data?.items || [];
    const parsedRowsPreview = useMemo(() => previewBatchRows(rowsText), [rowsText]);
    const activeBatch = useMemo(() => {
      if (activeBatchId) return batchItems.find((item) => String(item.id) === activeBatchId) || batchItems[0] || null;
      return batchItems[0] || null;
    }, [activeBatchId, batchItems]);
    useEffect(() => {
      if (!versionId && versionItems[0]?.id) {
        setVersionId(String(versionItems[0].id));
      }
    }, [versionId, versionItems]);
    useEffect(() => {
      if (!activeBatchId && batchItems[0]?.id) {
        setActiveBatchId(String(batchItems[0].id));
      }
    }, [activeBatchId, batchItems]);
    async function createBatchDefinition() {
      setBusy(true);
      setNotice(null);
      try {
        const payload = { rows: rowsText, label: label || void 0 };
        if (versionId) payload.version_id = versionId;
        if (workflowName) payload.workflow_name = workflowName;
        const created = await requestJson(`${bootstrap.api_root}/batch`, { method: "POST", body: JSON.stringify(payload) });
        batch.reload();
        setActiveBatchId(String(created.id || ""));
        setNotice({ tone: "success", title: "Batch staged", body: `${created.row_count || created.rows?.length || 0} rows captured with a local workflow snapshot.` });
      } catch (error) {
        setNotice(buildActionErrorNotice("batch", error));
      } finally {
        setBusy(false);
      }
    }
    async function runBatchAction(item, action) {
      setBusy(true);
      setNotice(null);
      try {
        if (action === "cancel") {
          const updated = await requestJson(String(item.routes?.cancel || `${bootstrap.api_root}/batch/${item.id}`), {
            method: "PATCH",
            body: JSON.stringify({ action: "cancel" })
          });
          setNotice({ tone: "success", title: "Batch cancellation requested", body: `${updated.label || updated.id} will stop after the current row.` });
        } else {
          const href = action === "run" ? String(item.routes?.run) : String(item.routes?.retry);
          const updated = await requestJson(href, { method: "POST", body: JSON.stringify({}) });
          setNotice({
            tone: "success",
            title: action === "run" ? "Batch started" : "Batch retry started",
            body: `${updated.label || updated.id} is now ${updated.status}.`
          });
        }
        batch.reload();
      } catch (error) {
        setNotice(buildActionErrorNotice(`batch ${action}`, error));
      } finally {
        setBusy(false);
      }
    }
    function exportBatch(item, format) {
      const route = format === "csv" ? item.routes?.export_csv : item.routes?.export_json;
      if (!route) return;
      window.location.assign(String(route));
    }
    const batchHeroMetrics = [
      { label: "Staged", value: batch.data?.counts?.staged ?? 0, detail: "ready definitions" },
      { label: "Running", value: batch.data?.counts?.running ?? 0, detail: "live executions" },
      { label: "Completed", value: batch.data?.counts?.completed ?? 0, detail: "finished locally" },
      { label: "Workflow versions", value: versionItems.length, detail: "available snapshots" }
    ];
    const batchFocusItems = [
      {
        label: "Stage",
        title: "Capture rows against one snapshot",
        detail: "Start with a version or workflow fallback, then keep import detail bounded to the composer."
      },
      {
        label: "Queue",
        title: "Scan live batches without row noise",
        detail: "The registry stays open for quick status checks while row-level detail waits below."
      },
      {
        label: "Inspect",
        title: "Open row detail only when needed",
        detail: "Per-row progress and run links stay available, but they no longer dominate the default view."
      }
    ];
    const activeBatchVersion = activeBatch?.version_id || activeBatch?.version?.id || "Workflow fallback";
    return /* @__PURE__ */ React.createElement("main", { className: "page-grid batch-shell operations-route" }, batch.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Batch API unavailable", body: batch.error }) : null, versions.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Versions API unavailable", body: versions.error }) : null, notice ? /* @__PURE__ */ React.createElement(Message, { tone: notice.tone, title: notice.title, body: notice.body }) : null, batch.loading && !batch.data ? /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading batch runner" }) : null, /* @__PURE__ */ React.createElement("section", { className: "panel hero-panel operations-hero" }, /* @__PURE__ */ React.createElement("div", { className: "operations-hero-grid" }, /* @__PURE__ */ React.createElement("div", { className: "operations-hero-copy" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Batch Runner"), /* @__PURE__ */ React.createElement("h2", null, batch.data?.surface?.title || "Run saved workflow snapshots across local question batches"), /* @__PURE__ */ React.createElement("p", null, batch.data?.surface?.summary || "Map saved workflow versions to many forecasting questions, track row-level progress, and feed resolved evidence back into Observatory."), /* @__PURE__ */ React.createElement("div", { className: "button-row operations-hero-actions" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => navigate("/versions") }, "Create/select version"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate("/observatory") }, "Review analytics"))), /* @__PURE__ */ React.createElement("div", { className: "operations-hero-side" }, /* @__PURE__ */ React.createElement("article", { className: "operations-trust-card" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Runtime contract"), /* @__PURE__ */ React.createElement("strong", null, "Local batch state stays aligned with shared workflow snapshots."), /* @__PURE__ */ React.createElement("p", null, batch.data?.execution_policy?.runtime_contract || "Batch executions reuse shared workflow snapshots and stay within the local product contract."), /* @__PURE__ */ React.createElement("div", { className: "operations-pill-row" }, /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Local-first orchestration"), /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Version-aware staging"), activeBatch ? /* @__PURE__ */ React.createElement(StatusPill, { value: String(activeBatch.status || "staged") }) : null)), /* @__PURE__ */ React.createElement("div", { className: "operations-stat-grid" }, batchHeroMetrics.map((metric) => /* @__PURE__ */ React.createElement("article", { key: metric.label, className: "operations-stat-card" }, /* @__PURE__ */ React.createElement("span", null, metric.label), /* @__PURE__ */ React.createElement("strong", null, metric.value), /* @__PURE__ */ React.createElement("small", null, metric.detail))))))), /* @__PURE__ */ React.createElement(
      RouteIdentityPanel,
      {
        className: "batch-identity-panel",
        eyebrow: "Batch flow",
        title: "Stage, queue, then inspect deliberately",
        summary: "Batch now reads as a dataset lane first: composition stays foregrounded, active queues stay scannable, and row detail opens only on demand.",
        items: batchFocusItems
      }
    ), /* @__PURE__ */ React.createElement("section", { className: "split-grid operations-lead-grid" }, /* @__PURE__ */ React.createElement("article", { className: "panel section-stack operations-form-panel" }, /* @__PURE__ */ React.createElement("div", { className: "operations-section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Input mapping"), /* @__PURE__ */ React.createElement("h3", null, "Stage a local batch"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "Paste one question per line or JSONL rows. The batch snapshot stays local, aligned with CLI/WebUI workflow contracts, and can be executed, cancelled, retried, or exported.")), /* @__PURE__ */ React.createElement("div", { className: "operations-pill-row" }, /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Rows preview"), /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Export ready"))), /* @__PURE__ */ React.createElement("div", { className: "operations-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Workflow version"), /* @__PURE__ */ React.createElement("select", { value: versionId, onChange: (event) => setVersionId(event.target.value) }, /* @__PURE__ */ React.createElement("option", { value: "" }, "Use workflow name instead"), versionItems.map((item) => /* @__PURE__ */ React.createElement("option", { key: item.id, value: item.id }, item.label || item.id)))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Workflow name fallback"), /* @__PURE__ */ React.createElement("input", { value: workflowName, onChange: (event) => setWorkflowName(event.target.value), placeholder: "demo-deterministic" })), /* @__PURE__ */ React.createElement("label", { className: "operations-field-span" }, /* @__PURE__ */ React.createElement("span", null, "Batch label"), /* @__PURE__ */ React.createElement("input", { value: label, onChange: (event) => setLabel(event.target.value), placeholder: "Optional local label" }))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Rows"), /* @__PURE__ */ React.createElement("textarea", { className: "text-area-input batch-rows-input", value: rowsText, onChange: (event) => setRowsText(event.target.value) })), /* @__PURE__ */ React.createElement(
      DensityDisclosure,
      {
        className: "operations-subpanel section-stack",
        title: `Parsed row preview \xB7 ${parsedRowsPreview.length} rows`,
        detail: "Questions are mapped immediately into the local row table, but the preview stays collapsed until you need to inspect it."
      },
      parsedRowsPreview.length ? /* @__PURE__ */ React.createElement("div", { className: "parsed-data-grid" }, /* @__PURE__ */ React.createElement("span", null, "Row"), /* @__PURE__ */ React.createElement("span", null, "Question"), /* @__PURE__ */ React.createElement("span", null, "Title"), parsedRowsPreview.slice(0, 6).flatMap((row) => [
        /* @__PURE__ */ React.createElement("span", { key: `row-${row.row_index}` }, row.row_index),
        /* @__PURE__ */ React.createElement("span", { key: `question-${row.row_index}` }, row.question),
        /* @__PURE__ */ React.createElement("span", { key: `title-${row.row_index}` }, row.title || "\u2014")
      ])) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No batch rows parsed yet", body: "Enter one question per line or JSONL rows with question/text/prompt fields." })
    ), /* @__PURE__ */ React.createElement("div", { className: "operations-footer" }, /* @__PURE__ */ React.createElement("div", { className: "operations-inline-note" }, /* @__PURE__ */ React.createElement("strong", null, "Snapshot provenance stays attached."), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "Stage first, then run, retry, or export without changing the shared batch/API surface.")), /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: createBatchDefinition, disabled: busy || !versionId && !workflowName || !rowsText.trim() }, busy ? "Creating batch" : "Stage batch"))), /* @__PURE__ */ React.createElement("article", { className: "panel section-stack operations-summary-panel" }, /* @__PURE__ */ React.createElement("div", { className: "operations-section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Execution"), /* @__PURE__ */ React.createElement("h3", null, "Batch posture"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, batch.data?.execution_policy?.runtime_contract || "Batch executions reuse shared workflow snapshots and do not introduce WebUI-only execution.")), activeBatch ? /* @__PURE__ */ React.createElement(StatusPill, { value: String(activeBatch.status || "staged") }) : /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "No active batch")), /* @__PURE__ */ React.createElement("div", { className: "operations-stat-grid" }, /* @__PURE__ */ React.createElement("article", { className: "operations-stat-card" }, /* @__PURE__ */ React.createElement("span", null, "With errors"), /* @__PURE__ */ React.createElement("strong", null, batch.data?.counts?.with_errors ?? 0), /* @__PURE__ */ React.createElement("small", null, "rows needing review")), /* @__PURE__ */ React.createElement("article", { className: "operations-stat-card" }, /* @__PURE__ */ React.createElement("span", null, "Preview rows"), /* @__PURE__ */ React.createElement("strong", null, parsedRowsPreview.length), /* @__PURE__ */ React.createElement("small", null, "captured instantly")), /* @__PURE__ */ React.createElement("article", { className: "operations-stat-card" }, /* @__PURE__ */ React.createElement("span", null, "Selected version"), /* @__PURE__ */ React.createElement("strong", null, versionId || "fallback"), /* @__PURE__ */ React.createElement("small", null, "used for new stage"))), /* @__PURE__ */ React.createElement("article", { className: "operations-subpanel" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, activeBatch ? activeBatch.label || activeBatch.id : "No batch selected"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, activeBatch ? "Keep detail close without flooding the route with row-level noise." : "Select a staged definition below to inspect version provenance and row posture.")), activeBatch ? /* @__PURE__ */ React.createElement(StatusPill, { value: String(activeBatch.status || "staged") }) : null), /* @__PURE__ */ React.createElement("div", { className: "operations-keyline-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Version"), /* @__PURE__ */ React.createElement("strong", null, activeBatchVersion)), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Rows"), /* @__PURE__ */ React.createElement("strong", null, activeBatch ? formatValue(activeBatch.row_count) : "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Progress"), /* @__PURE__ */ React.createElement("strong", null, activeBatch ? `${formatValue(activeBatch.progress?.percent)}%` : "\u2014")))))), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack operations-table-card" }, /* @__PURE__ */ React.createElement("div", { className: "operations-table-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Local batches"), /* @__PURE__ */ React.createElement("h3", null, "Staged definitions"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "Select a definition to inspect row-level progress, provenance, and export actions.")), /* @__PURE__ */ React.createElement("div", { className: "operations-pill-row" }, /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, batchItems.length, " definitions"), activeBatch ? /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Selected: ", activeBatch.label || activeBatch.id) : null)), batchItems.length ? /* @__PURE__ */ React.createElement("div", { className: "table-wrap operations-table-wrap" }, /* @__PURE__ */ React.createElement("table", { className: "data-table" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", null, /* @__PURE__ */ React.createElement("th", null, "Batch"), /* @__PURE__ */ React.createElement("th", null, "Workflow"), /* @__PURE__ */ React.createElement("th", null, "Status"), /* @__PURE__ */ React.createElement("th", null, "Rows"), /* @__PURE__ */ React.createElement("th", null, "Progress"), /* @__PURE__ */ React.createElement("th", null, "Actions"))), /* @__PURE__ */ React.createElement("tbody", null, batchItems.map((item) => /* @__PURE__ */ React.createElement("tr", { key: item.id, className: String(item.id) === String(activeBatch?.id || "") ? "is-active" : void 0 }, /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement(
      "button",
      {
        className: "table-link-button operations-row-button",
        type: "button",
        "aria-pressed": String(item.id) === String(activeBatch?.id || ""),
        onClick: () => setActiveBatchId(String(item.id))
      },
      /* @__PURE__ */ React.createElement("span", { className: "table-primary" }, item.label || item.id),
      /* @__PURE__ */ React.createElement("span", { className: "table-secondary" }, item.id)
    )), /* @__PURE__ */ React.createElement("td", null, item.workflow_name), /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement(StatusPill, { value: item.status })), /* @__PURE__ */ React.createElement("td", null, formatValue(item.row_count)), /* @__PURE__ */ React.createElement("td", null, formatValue(item.progress?.percent), "%"), /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement("div", { className: "button-row operations-table-actions" }, item.status === "staged" ? /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: (event) => runWithoutRowSelection(event, () => void runBatchAction(item, "run")), disabled: busy }, "Run") : null, item.status === "queued" || item.status === "running" || item.status === "cancel-requested" ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: (event) => runWithoutRowSelection(event, () => void runBatchAction(item, "cancel")), disabled: busy }, "Cancel") : null, item.status === "cancelled" || item.status === "failed" || item.status === "completed-with-errors" ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: (event) => runWithoutRowSelection(event, () => void runBatchAction(item, "retry")), disabled: busy }, "Retry") : null, /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: (event) => runWithoutRowSelection(event, () => exportBatch(item, "csv")) }, "CSV"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: (event) => runWithoutRowSelection(event, () => exportBatch(item, "json")) }, "JSON")))))))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No batch definitions yet", body: "Create a staged batch from a saved workflow version or workflow name." })), activeBatch ? /* @__PURE__ */ React.createElement(
      DensityDisclosure,
      {
        className: "panel section-stack operations-detail-card",
        title: `${activeBatch.label || activeBatch.id} row detail`,
        detail: "Open row-level progress only when you need the staged table and run links."
      },
      /* @__PURE__ */ React.createElement("div", { className: "operations-detail-strip" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Completed"), /* @__PURE__ */ React.createElement("strong", null, activeBatch.summary?.completed_rows ?? 0)), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Failed"), /* @__PURE__ */ React.createElement("strong", null, activeBatch.summary?.failed_rows ?? 0)), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Cancelled"), /* @__PURE__ */ React.createElement("strong", null, activeBatch.summary?.cancelled_rows ?? 0))),
      Array.isArray(activeBatch.rows) && activeBatch.rows.length ? /* @__PURE__ */ React.createElement("div", { className: "table-wrap operations-table-wrap" }, /* @__PURE__ */ React.createElement("table", { className: "data-table" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", null, /* @__PURE__ */ React.createElement("th", null, "Row"), /* @__PURE__ */ React.createElement("th", null, "Status"), /* @__PURE__ */ React.createElement("th", null, "Question"), /* @__PURE__ */ React.createElement("th", null, "Run"), /* @__PURE__ */ React.createElement("th", null, "Result"))), /* @__PURE__ */ React.createElement("tbody", null, activeBatch.rows.map((row) => /* @__PURE__ */ React.createElement("tr", { key: `${activeBatch.id}-${row.row_index}` }, /* @__PURE__ */ React.createElement("td", null, row.row_index), /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement(StatusPill, { value: row.status })), /* @__PURE__ */ React.createElement("td", null, row.input?.question || row.input?.text || row.input?.prompt || "\u2014"), /* @__PURE__ */ React.createElement("td", null, row.run_href ? /* @__PURE__ */ React.createElement("button", { className: "table-link-button", onClick: () => navigate(String(row.run_href)) }, row.run_id || "Open run") : "\u2014"), /* @__PURE__ */ React.createElement("td", null, row.result?.probability_summary?.cards?.[1]?.value != null ? `${formatValue(row.result.probability_summary.cards[1].value)} avg` : row.error || "Pending")))))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No staged rows", body: "Add rows to this batch or select another batch definition." })
    ) : null);
  }
  function VersionsPage({ navigate }) {
    const versions = useJsonResource(`${bootstrap.api_root}/versions`, []);
    const workflows = useJsonResource(`${bootstrap.api_root}/workflows`, []);
    const [workflowName, setWorkflowName] = useState("");
    const [label, setLabel] = useState("");
    const [parentId, setParentId] = useState("");
    const [selectedVersionId, setSelectedVersionId] = useState("");
    const [compareVersionId, setCompareVersionId] = useState("");
    const [diff, setDiff] = useState(null);
    const [notice, setNotice] = useState(null);
    const [busy, setBusy] = useState(false);
    const versionItems = versions.data?.items || [];
    const workflowItems = workflows.data?.items || [];
    const selectedVersion = useMemo(() => {
      if (selectedVersionId) return versionItems.find((item) => String(item.id) === selectedVersionId) || versionItems[0] || null;
      return versionItems[0] || null;
    }, [selectedVersionId, versionItems]);
    const selectVersion = (id) => {
      setSelectedVersionId(id);
      setDiff(null);
    };
    useEffect(() => {
      if (!workflowName && workflowItems[0]?.name) {
        setWorkflowName(String(workflowItems[0].name));
      }
    }, [workflowName, workflowItems]);
    useEffect(() => {
      if (!selectedVersionId && versionItems[0]?.id) {
        setSelectedVersionId(String(versionItems[0].id));
      }
    }, [selectedVersionId, versionItems]);
    useEffect(() => {
      if (!selectedVersion) return;
      if (!compareVersionId || compareVersionId === String(selectedVersion.id)) {
        const alternative = versionItems.find((item) => String(item.id) !== String(selectedVersion.id));
        setCompareVersionId(String(alternative?.id || ""));
      }
    }, [compareVersionId, selectedVersion, versionItems]);
    useEffect(() => {
      setDiff(null);
    }, [selectedVersionId, compareVersionId]);
    async function createVersionSnapshot() {
      setBusy(true);
      setNotice(null);
      try {
        const created = await requestJson(`${bootstrap.api_root}/versions`, {
          method: "POST",
          body: JSON.stringify({ workflow_name: workflowName, label: label || void 0, parent_id: parentId || void 0 })
        });
        versions.reload();
        setParentId(String(created.id || ""));
        selectVersion(String(created.id || ""));
        setNotice({ tone: "success", title: "Version snapshot created", body: `${created.label || created.id} now has immutable local graph provenance.` });
      } catch (error) {
        setNotice(buildActionErrorNotice("version", error));
      } finally {
        setBusy(false);
      }
    }
    async function loadDiff() {
      if (!selectedVersion || !compareVersionId) return;
      setBusy(true);
      setNotice(null);
      try {
        const payload = await requestJson(String(selectedVersion.routes?.diff?.href || `${bootstrap.api_root}/versions/${selectedVersion.id}/diff/${compareVersionId}`).replace("{other_version_id}", compareVersionId));
        setDiff(payload);
      } catch (error) {
        setNotice(buildActionErrorNotice("version diff", error));
      } finally {
        setBusy(false);
      }
    }
    async function runVersionSnapshot(item) {
      setBusy(true);
      setNotice(null);
      try {
        const result = await requestJson(String(item.routes?.run?.href || `${bootstrap.api_root}/versions/${item.id}/run`), {
          method: "POST",
          body: JSON.stringify({ user: "webui-versions" })
        });
        versions.reload();
        setNotice({ tone: "success", title: "Version run completed", body: `${result.run_id} executed from ${item.label || item.id}.` });
      } catch (error) {
        setNotice(buildActionErrorNotice("version run", error));
      } finally {
        setBusy(false);
      }
    }
    async function rollbackVersion(item) {
      setBusy(true);
      setNotice(null);
      try {
        const result = await requestJson(String(item.routes?.rollback?.href || `${bootstrap.api_root}/versions/${item.id}/rollback`), {
          method: "POST",
          body: JSON.stringify({ mode: "version", label: `${item.workflow_name} rollback`, set_default: true })
        });
        versions.reload();
        selectVersion(String(result.version?.id || ""));
        setNotice({ tone: "success", title: "Rollback snapshot created", body: `${result.version?.label || result.version?.id || item.id} is now the default local snapshot.` });
      } catch (error) {
        setNotice(buildActionErrorNotice("version rollback", error));
      } finally {
        setBusy(false);
      }
    }
    async function setDefaultVersion(item) {
      setBusy(true);
      setNotice(null);
      try {
        const result = await requestJson(String(item.routes?.set_default?.href || `${bootstrap.api_root}/versions/${item.id}`), {
          method: "PATCH",
          body: JSON.stringify({ set_default: true })
        });
        versions.reload();
        selectVersion(String(result.id || item.id));
        setNotice({ tone: "success", title: "Default version updated", body: `${result.label || result.id} is now the default snapshot for ${result.workflow_name}.` });
      } catch (error) {
        setNotice(buildActionErrorNotice("version default", error));
      } finally {
        setBusy(false);
      }
    }
    const versionHeroMetrics = [
      { label: "Snapshots", value: versionItems.length, detail: "stored locally" },
      { label: "Workflows", value: versions.data?.workflow_count ?? workflowItems.length, detail: "registered blueprints" },
      {
        label: "Arbitrary code",
        value: versions.data?.guidance?.no_arbitrary_code ? "blocked" : "unknown",
        detail: "safety posture"
      },
      {
        label: "Selected",
        value: selectedVersion?.label || selectedVersion?.id || "\u2014",
        detail: "active comparison target"
      }
    ];
    const versionFocusItems = [
      {
        label: "Freeze",
        title: "Create a reusable lineage anchor",
        detail: "New snapshots stay close to the create form instead of expanding into a permanent provenance wall."
      },
      {
        label: "Select",
        title: "Browse history from one calm registry",
        detail: "Default, rollback, and run actions remain visible while the table keeps the route grounded in lineage."
      },
      {
        label: "Compare",
        title: "Open deeper diffs only when asked",
        detail: "Route metadata, recent runs, and graph/config deltas move behind deliberate disclosure."
      }
    ];
    return /* @__PURE__ */ React.createElement("main", { className: "page-grid versions-shell operations-route" }, versions.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Versions API unavailable", body: versions.error }) : null, workflows.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Workflow catalog unavailable", body: workflows.error }) : null, notice ? /* @__PURE__ */ React.createElement(Message, { tone: notice.tone, title: notice.title, body: notice.body }) : null, versions.loading && !versions.data ? /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading versions" }) : null, /* @__PURE__ */ React.createElement("section", { className: "panel hero-panel operations-hero" }, /* @__PURE__ */ React.createElement("div", { className: "operations-hero-grid" }, /* @__PURE__ */ React.createElement("div", { className: "operations-hero-copy" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Versions"), /* @__PURE__ */ React.createElement("h2", null, versions.data?.surface?.title || "Prompt and graph provenance across Studio, Playground, Batch, and API runs"), /* @__PURE__ */ React.createElement("p", null, versions.data?.surface?.summary || "Versioning becomes the connective tissue for graph snapshots, prompt/config diffs, run provenance, rollback, and workflow score comparisons."), /* @__PURE__ */ React.createElement("div", { className: "button-row operations-hero-actions" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => navigate("/studio") }, "Open Studio"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate("/batch") }, "Use in Batch"))), /* @__PURE__ */ React.createElement("div", { className: "operations-hero-side" }, /* @__PURE__ */ React.createElement("article", { className: "operations-trust-card" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Provenance"), /* @__PURE__ */ React.createElement("strong", null, "Immutable local snapshots keep Batch, Studio, and API on one lineage spine."), /* @__PURE__ */ React.createElement("p", null, selectedVersion?.run_provenance?.execution_linkage?.notes?.[0] || "Snapshots preserve the shared workflow blueprint contract and keep run provenance visible without dominating the page."), /* @__PURE__ */ React.createElement("div", { className: "operations-pill-row" }, /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Immutable history"), /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Rollback ready"), selectedVersion?.is_default ? /* @__PURE__ */ React.createElement(StatusPill, { value: "default" }) : null)), /* @__PURE__ */ React.createElement("div", { className: "operations-stat-grid" }, versionHeroMetrics.map((metric) => /* @__PURE__ */ React.createElement("article", { key: metric.label, className: "operations-stat-card" }, /* @__PURE__ */ React.createElement("span", null, metric.label), /* @__PURE__ */ React.createElement("strong", null, metric.value), /* @__PURE__ */ React.createElement("small", null, metric.detail))))))), /* @__PURE__ */ React.createElement(
      RouteIdentityPanel,
      {
        className: "versions-identity-panel",
        eyebrow: "Lineage rhythm",
        title: "Freeze, select, and compare with less framing noise",
        summary: "Versions now foregrounds snapshot lineage and reusable defaults, while deeper provenance tools stay one click away.",
        items: versionFocusItems
      }
    ), /* @__PURE__ */ React.createElement("section", { className: "split-grid operations-lead-grid" }, /* @__PURE__ */ React.createElement("article", { className: "panel section-stack operations-form-panel" }, /* @__PURE__ */ React.createElement("div", { className: "operations-section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Create snapshot"), /* @__PURE__ */ React.createElement("h3", null, "Freeze a shared workflow blueprint"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "Capture a crisp revision without adding a dense provenance wall to the route.")), /* @__PURE__ */ React.createElement("div", { className: "operations-pill-row" }, /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Shared contract"), /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Diffable state"))), /* @__PURE__ */ React.createElement("div", { className: "operations-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Workflow"), /* @__PURE__ */ React.createElement("select", { value: workflowName, onChange: (event) => setWorkflowName(event.target.value) }, !workflowItems.length ? /* @__PURE__ */ React.createElement("option", { value: "" }, "No workflows registered yet") : null, workflowItems.map((item) => /* @__PURE__ */ React.createElement("option", { key: item.name, value: item.name }, item.title || item.name)))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Label"), /* @__PURE__ */ React.createElement("input", { value: label, onChange: (event) => setLabel(event.target.value), placeholder: "Macro consensus v3" })), /* @__PURE__ */ React.createElement("label", { className: "operations-field-span" }, /* @__PURE__ */ React.createElement("span", null, "Parent version"), /* @__PURE__ */ React.createElement("select", { value: parentId, onChange: (event) => setParentId(event.target.value) }, /* @__PURE__ */ React.createElement("option", { value: "" }, "None"), versionItems.map((item) => /* @__PURE__ */ React.createElement("option", { key: item.id, value: item.id }, item.label || item.id))))), /* @__PURE__ */ React.createElement("div", { className: "operations-footer" }, /* @__PURE__ */ React.createElement("div", { className: "operations-inline-note" }, /* @__PURE__ */ React.createElement("strong", null, "Every snapshot is reusable elsewhere."), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "The same saved version can move straight into Batch or Control with no route-specific branching.")), /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: createVersionSnapshot, disabled: busy || !workflowName }, busy ? "Creating version" : "Create version"))), /* @__PURE__ */ React.createElement("article", { className: "panel section-stack operations-summary-panel" }, /* @__PURE__ */ React.createElement("div", { className: "operations-section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Contract"), /* @__PURE__ */ React.createElement("h3", null, "CLI/WebUI aligned snapshots"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, versions.data?.guidance?.runtime_contract || "Snapshots preserve the shared workflow blueprint contract and do not add WebUI-only code paths.")), selectedVersion?.is_default ? /* @__PURE__ */ React.createElement(StatusPill, { value: "default" }) : /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Local provenance")), /* @__PURE__ */ React.createElement("div", { className: "operations-stat-grid" }, /* @__PURE__ */ React.createElement("article", { className: "operations-stat-card" }, /* @__PURE__ */ React.createElement("span", null, "Recent runs"), /* @__PURE__ */ React.createElement("strong", null, selectedVersion?.run_provenance?.recent_run_ids?.length ?? 0), /* @__PURE__ */ React.createElement("small", null, "linked to selected snapshot")), /* @__PURE__ */ React.createElement("article", { className: "operations-stat-card" }, /* @__PURE__ */ React.createElement("span", null, "Parent lineage"), /* @__PURE__ */ React.createElement("strong", null, selectedVersion?.parent_id || "root"), /* @__PURE__ */ React.createElement("small", null, "rollback anchor")), /* @__PURE__ */ React.createElement("article", { className: "operations-stat-card" }, /* @__PURE__ */ React.createElement("span", null, "Runtime"), /* @__PURE__ */ React.createElement("strong", null, selectedVersion?.config?.runtime?.provider || selectedVersion?.metadata?.runtime_provider || "\u2014"), /* @__PURE__ */ React.createElement("small", null, "execution provider"))), /* @__PURE__ */ React.createElement("article", { className: "operations-subpanel" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, selectedVersion?.label || selectedVersion?.id || "No version selected"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, selectedVersion ? "Keep default, rollback, and run lineage close at hand while the route stays visually quiet." : "Choose a version below to inspect its lineage and route contract.")), selectedVersion?.is_default ? /* @__PURE__ */ React.createElement(StatusPill, { value: "default" }) : null), /* @__PURE__ */ React.createElement("div", { className: "operations-keyline-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Workflow"), /* @__PURE__ */ React.createElement("strong", null, selectedVersion?.workflow_name || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Last run"), /* @__PURE__ */ React.createElement("strong", null, selectedVersion?.run_provenance?.last_run_id || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Created"), /* @__PURE__ */ React.createElement("strong", null, selectedVersion ? formatTimestamp(selectedVersion.created_at) : "\u2014")))))), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack operations-table-card" }, /* @__PURE__ */ React.createElement("div", { className: "operations-table-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Version history"), /* @__PURE__ */ React.createElement("h3", null, "Local snapshots"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "Browse lineage, run, default, and rollback actions without collapsing the route into a dense admin ledger.")), /* @__PURE__ */ React.createElement("div", { className: "operations-pill-row" }, /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, versionItems.length, " snapshots"), selectedVersion ? /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Selected: ", selectedVersion.label || selectedVersion.id) : null)), versionItems.length ? /* @__PURE__ */ React.createElement("div", { className: "table-wrap operations-table-wrap" }, /* @__PURE__ */ React.createElement("table", { className: "data-table" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", null, /* @__PURE__ */ React.createElement("th", null, "Version"), /* @__PURE__ */ React.createElement("th", null, "Workflow"), /* @__PURE__ */ React.createElement("th", null, "Source"), /* @__PURE__ */ React.createElement("th", null, "Parent"), /* @__PURE__ */ React.createElement("th", null, "Created"), /* @__PURE__ */ React.createElement("th", null, "Actions"))), /* @__PURE__ */ React.createElement("tbody", null, versionItems.map((item) => /* @__PURE__ */ React.createElement("tr", { key: item.id, className: String(item.id) === String(selectedVersion?.id || "") ? "is-active" : void 0 }, /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement(
      "button",
      {
        className: "table-link-button operations-row-button",
        type: "button",
        "aria-pressed": String(item.id) === String(selectedVersion?.id || ""),
        onClick: () => selectVersion(String(item.id))
      },
      /* @__PURE__ */ React.createElement("span", { className: "table-primary" }, item.label || item.id),
      /* @__PURE__ */ React.createElement("span", { className: "table-secondary" }, item.id)
    )), /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement("button", { className: "table-link-button", onClick: (event) => runWithoutRowSelection(event, () => navigate(`/studio?workflow=${encodeURIComponent(String(item.workflow_name))}`)) }, item.workflow_name)), /* @__PURE__ */ React.createElement("td", null, item.source), /* @__PURE__ */ React.createElement("td", null, item.parent_id || "\u2014"), /* @__PURE__ */ React.createElement("td", null, formatTimestamp(item.created_at)), /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement("div", { className: "button-row operations-table-actions" }, /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: (event) => runWithoutRowSelection(event, () => void runVersionSnapshot(item)), disabled: busy }, "Run"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: (event) => runWithoutRowSelection(event, () => void setDefaultVersion(item)), disabled: busy || item.is_default }, "Default"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: (event) => runWithoutRowSelection(event, () => void rollbackVersion(item)), disabled: busy }, "Rollback")))))))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No version snapshots yet", body: "Create one from a registered workflow, then use it in Batch or Control." })), selectedVersion ? /* @__PURE__ */ React.createElement(
      DensityDisclosure,
      {
        className: "panel section-stack operations-detail-card versions-detail-panel",
        title: `${selectedVersion.label || selectedVersion.id} lineage detail`,
        detail: "Open recent runs, compare tools, and route metadata only when you need deeper provenance context."
      },
      /* @__PURE__ */ React.createElement("div", { className: "operations-table-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Selected version"), /* @__PURE__ */ React.createElement("h3", null, selectedVersion.label || selectedVersion.id), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, selectedVersion.run_provenance?.execution_linkage?.notes?.[0] || "Version snapshots keep run provenance attached to the shared local workflow contract.")), /* @__PURE__ */ React.createElement("div", { className: "operations-pill-row" }, selectedVersion.is_default ? /* @__PURE__ */ React.createElement(StatusPill, { value: "default" }) : null, /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, selectedVersion.source || "local snapshot"))),
      /* @__PURE__ */ React.createElement("div", { className: "operations-detail-strip" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Workflow"), /* @__PURE__ */ React.createElement("strong", null, selectedVersion.workflow_name)), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Parent"), /* @__PURE__ */ React.createElement("strong", null, selectedVersion.parent_id || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Last run"), /* @__PURE__ */ React.createElement("strong", null, selectedVersion.run_provenance?.last_run_id || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Provider"), /* @__PURE__ */ React.createElement("strong", null, selectedVersion.config?.runtime?.provider || selectedVersion.metadata?.runtime_provider || "\u2014"))),
      Array.isArray(selectedVersion.run_provenance?.recent_run_ids) && selectedVersion.run_provenance.recent_run_ids.length ? /* @__PURE__ */ React.createElement("div", { className: "button-row operations-related-actions" }, selectedVersion.run_provenance.recent_run_ids.map((runId) => /* @__PURE__ */ React.createElement("button", { key: runId, className: "secondary-button", onClick: () => navigate(`/runs/${encodeURIComponent(runId)}`) }, runId))) : null,
      /* @__PURE__ */ React.createElement("div", { className: "operations-card-grid" }, /* @__PURE__ */ React.createElement(
        DensityDisclosure,
        {
          className: "operations-subpanel section-stack",
          title: "Compare snapshots",
          detail: "Open graph and config path diffs only when you need lineage detail."
        },
        /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Compare against"), /* @__PURE__ */ React.createElement("select", { value: compareVersionId, onChange: (event) => setCompareVersionId(event.target.value) }, /* @__PURE__ */ React.createElement("option", { value: "" }, "Select another version"), versionItems.filter((item) => String(item.id) !== String(selectedVersion.id)).map((item) => /* @__PURE__ */ React.createElement("option", { key: item.id, value: item.id }, item.label || item.id)))),
        /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: loadDiff, disabled: busy || !compareVersionId }, "Load diff"),
        diff ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("div", { className: "operations-detail-strip compact-detail-strip" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Changed paths"), /* @__PURE__ */ React.createElement("strong", null, diff.summary?.changed ?? 0)), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Same workflow"), /* @__PURE__ */ React.createElement("strong", null, diff.summary?.same_workflow ? "yes" : "no"))), /* @__PURE__ */ React.createElement("pre", { className: "code-card" }, JSON.stringify(diff.changed_paths || [], null, 2))) : /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "Load a diff to inspect graph/config/canvas path changes between two local snapshots.")
      ), /* @__PURE__ */ React.createElement(
        DensityDisclosure,
        {
          className: "operations-subpanel section-stack",
          title: "Snapshot summary",
          detail: "Keep route metadata and graph counts available without leaving JSON panels open all the time."
        },
        /* @__PURE__ */ React.createElement("div", { className: "operations-detail-strip compact-detail-strip" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Nodes"), /* @__PURE__ */ React.createElement("strong", null, Object.keys(selectedVersion.graph?.nodes || {}).length)), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Edges"), /* @__PURE__ */ React.createElement("strong", null, (selectedVersion.graph?.edges || []).length)), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Provider"), /* @__PURE__ */ React.createElement("strong", null, selectedVersion.config?.runtime?.provider || selectedVersion.metadata?.runtime_provider || "\u2014"))),
        /* @__PURE__ */ React.createElement("pre", { className: "code-card" }, JSON.stringify(selectedVersion.routes || {}, null, 2))
      ))
    ) : null);
  }
  function ApiControlPage({ navigate }) {
    const api = useJsonResource(`${bootstrap.api_root}/api-control`, []);
    const webhooks = useJsonResource(`${bootstrap.api_root}/webhooks`, []);
    const [url, setUrl] = useState("https://example.com/xrtm");
    const [events, setEvents] = useState("run.completed,batch.completed");
    const [secret, setSecret] = useState("");
    const [versionId, setVersionId] = useState("");
    const [notice, setNotice] = useState(null);
    const [busy, setBusy] = useState(null);
    const endpoints = webhooks.data?.items || [];
    const deliveries = webhooks.data?.deliveries || [];
    const versionItems = api.data?.snapshots?.versions?.items || [];
    useEffect(() => {
      if (!versionId && versionItems[0]?.id) {
        setVersionId(String(versionItems[0].id));
      }
    }, [versionId, versionItems]);
    async function createWebhook() {
      setBusy("Creating webhook");
      setNotice(null);
      try {
        const endpoint = await requestJson(`${bootstrap.api_root}/webhooks`, {
          method: "POST",
          body: JSON.stringify({
            url,
            events: events.split(",").map((item) => item.trim()).filter(Boolean),
            secret: secret || void 0
          })
        });
        webhooks.reload();
        api.reload();
        setNotice({ tone: "success", title: "Webhook registered", body: `${endpoint.id} is stored locally with signing metadata.` });
      } catch (error) {
        setNotice(buildActionErrorNotice("webhook", error));
      } finally {
        setBusy(null);
      }
    }
    async function deleteWebhook(id) {
      setBusy(`Deleting ${id}`);
      setNotice(null);
      try {
        await requestJson(`${bootstrap.api_root}/webhooks/${id}`, { method: "DELETE" });
        webhooks.reload();
        api.reload();
        setNotice({ tone: "success", title: "Webhook deleted", body: `${id} was removed from the local registry.` });
      } catch (error) {
        setNotice(buildActionErrorNotice("webhook", error));
      } finally {
        setBusy(null);
      }
    }
    async function testWebhook(id) {
      setBusy(`Testing ${id}`);
      setNotice(null);
      try {
        const result = await requestJson(`${bootstrap.api_root}/webhooks/${id}/test`, {
          method: "POST",
          body: JSON.stringify({ event_type: "run.completed" })
        });
        webhooks.reload();
        api.reload();
        setNotice({
          tone: result.delivery?.status === "delivered" ? "success" : "warning",
          title: "Webhook test sent",
          body: `${id} returned ${result.delivery?.status || "unknown"}.`
        });
      } catch (error) {
        setNotice(buildActionErrorNotice("webhook test", error));
      } finally {
        setBusy(null);
      }
    }
    async function retryDelivery(id) {
      setBusy(`Retrying ${id}`);
      setNotice(null);
      try {
        const delivery = await requestJson(`${bootstrap.api_root}/webhooks/deliveries/${id}/retry`, { method: "POST", body: JSON.stringify({}) });
        webhooks.reload();
        api.reload();
        setNotice({
          tone: delivery.status === "delivered" ? "success" : "warning",
          title: "Delivery retried",
          body: `${id} is now ${delivery.status}.`
        });
      } catch (error) {
        setNotice(buildActionErrorNotice("delivery retry", error));
      } finally {
        setBusy(null);
      }
    }
    async function runVersionSnapshot() {
      if (!versionId) return;
      setBusy(`Running ${versionId}`);
      setNotice(null);
      try {
        const result = await requestJson(`${bootstrap.api_root}/versions/${versionId}/run`, {
          method: "POST",
          body: JSON.stringify({ user: "webui-api" })
        });
        webhooks.reload();
        api.reload();
        setNotice({ tone: "success", title: "Version run started", body: `${result.run_id} executed from ${result.workflow_name}.` });
      } catch (error) {
        setNotice(buildActionErrorNotice("version run", error));
      } finally {
        setBusy(null);
      }
    }
    const apiHeroMetrics = [
      { label: "Versions", value: api.data?.counts?.versions ?? 0, detail: "runnable snapshots" },
      { label: "Batch runs", value: api.data?.counts?.batch_runs ?? 0, detail: "linked executions" },
      { label: "Webhooks", value: api.data?.counts?.webhook_endpoints ?? endpoints.length, detail: "registered endpoints" },
      { label: "Token mode", value: String(api.data?.token_behavior?.mode || "local-no-auth"), detail: "current auth posture" }
    ];
    const apiFocusItems = [
      {
        label: "Run",
        title: "Lead with saved version execution",
        detail: "The default control surface keeps version-backed runs first so newcomers land on the shared contract."
      },
      {
        label: "Integrate",
        title: "Keep webhook setup adjacent, not dominant",
        detail: "Endpoint registration stays visible beside execution without turning the route into a dense admin console."
      },
      {
        label: "Audit",
        title: "Review delivery history on demand",
        detail: "Recent attempts and retries remain available, but signed log detail is tucked behind disclosure."
      }
    ];
    return /* @__PURE__ */ React.createElement("main", { className: "page-grid api-shell operations-route" }, api.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Control unavailable", body: api.error }) : null, webhooks.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Webhook registry unavailable", body: webhooks.error }) : null, notice ? /* @__PURE__ */ React.createElement(Message, { tone: notice.tone, title: notice.title, body: notice.body }) : null, api.loading && !api.data ? /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading Control" }) : null, /* @__PURE__ */ React.createElement("section", { className: "panel hero-panel operations-hero" }, /* @__PURE__ */ React.createElement("div", { className: "operations-hero-grid" }, /* @__PURE__ */ React.createElement("div", { className: "operations-hero-copy" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Control"), /* @__PURE__ */ React.createElement("h2", null, api.data?.surface?.title || "Local control and integration plane"), /* @__PURE__ */ React.createElement("p", null, api.data?.surface?.summary || "Run saved versions, inspect batch and webhook state, and manage local integration settings without leaving the product shell."), /* @__PURE__ */ React.createElement("div", { className: "button-row operations-hero-actions" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => navigate("/versions") }, "Select version"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate("/batch") }, "Create batch"))), /* @__PURE__ */ React.createElement("div", { className: "operations-hero-side" }, /* @__PURE__ */ React.createElement("article", { className: "operations-trust-card" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Trust cues"), /* @__PURE__ */ React.createElement("strong", null, "Token posture, version routing, and webhook signing stay visible without taking over the route."), /* @__PURE__ */ React.createElement("p", null, api.data?.token_behavior?.notes?.[0] || "The control plane is local-only and does not require auth tokens today."), /* @__PURE__ */ React.createElement("div", { className: "operations-pill-row" }, /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Signed deliveries"), /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Local integration plane"), /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Token: ", String(api.data?.token_behavior?.mode || "local-no-auth")))), /* @__PURE__ */ React.createElement("div", { className: "operations-stat-grid" }, apiHeroMetrics.map((metric) => /* @__PURE__ */ React.createElement("article", { key: metric.label, className: "operations-stat-card" }, /* @__PURE__ */ React.createElement("span", null, metric.label), /* @__PURE__ */ React.createElement("strong", null, metric.value), /* @__PURE__ */ React.createElement("small", null, metric.detail))))))), /* @__PURE__ */ React.createElement(
      RouteIdentityPanel,
      {
        className: "api-identity-panel",
        eyebrow: "Control loop",
        title: "Run, integrate, then audit as needed",
        summary: "Control now emphasizes the primary local API workflow first, with endpoint setup and signed delivery history stepping back until needed.",
        items: apiFocusItems
      }
    ), /* @__PURE__ */ React.createElement("section", { className: "split-grid operations-lead-grid" }, /* @__PURE__ */ React.createElement("article", { className: "panel section-stack operations-form-panel" }, /* @__PURE__ */ React.createElement("div", { className: "operations-section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Execution API"), /* @__PURE__ */ React.createElement("h3", null, "Run a saved version snapshot"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, api.data?.execution_policy?.summary || "The API records local state and delegates execution to shared product workflow services.")), /* @__PURE__ */ React.createElement("div", { className: "operations-pill-row" }, /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Version-aware routes"), /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Token: ", String(api.data?.token_behavior?.mode || "local-no-auth")))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Version"), /* @__PURE__ */ React.createElement("select", { value: versionId, onChange: (event) => setVersionId(event.target.value) }, !versionItems.length ? /* @__PURE__ */ React.createElement("option", { value: "" }, "No saved versions yet") : null, versionItems.map((item) => /* @__PURE__ */ React.createElement("option", { key: item.id, value: item.id }, item.label || item.id)))), /* @__PURE__ */ React.createElement("div", { className: "operations-footer" }, /* @__PURE__ */ React.createElement("div", { className: "operations-inline-note" }, /* @__PURE__ */ React.createElement("strong", null, "Published routes stay shared."), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "Use the same saved version from this route, Batch, or Versions without changing the API contract.")), /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: runVersionSnapshot, disabled: Boolean(busy) || !versionId }, busy?.startsWith("Running ") ? busy : "Run version")), /* @__PURE__ */ React.createElement("div", { className: "operations-card-grid" }, /* @__PURE__ */ React.createElement(
      DensityDisclosure,
      {
        className: "operations-subpanel section-stack",
        title: "Route examples",
        detail: "Keep example payloads nearby without leaving long JSON blocks open on the main surface."
      },
      /* @__PURE__ */ React.createElement("pre", { className: "code-card" }, JSON.stringify(api.data?.route_examples || [], null, 2))
    ), /* @__PURE__ */ React.createElement(
      DensityDisclosure,
      {
        className: "operations-subpanel section-stack",
        title: "Shared endpoints",
        detail: "Published route contracts stay available here, but collapsed until you need them."
      },
      /* @__PURE__ */ React.createElement("pre", { className: "code-card" }, JSON.stringify(api.data?.routes || { versions: "/api/versions", batch: "/api/batch", webhooks: "/api/webhooks" }, null, 2))
    ))), /* @__PURE__ */ React.createElement("article", { className: "panel section-stack operations-form-panel" }, /* @__PURE__ */ React.createElement("div", { className: "operations-section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Webhooks"), /* @__PURE__ */ React.createElement("h3", null, "Register a signed lifecycle endpoint"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "Endpoints support signed test deliveries and manual retry from the same muted control surface.")), /* @__PURE__ */ React.createElement("div", { className: "operations-pill-row" }, /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Signed test delivery"), /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Manual retry"))), /* @__PURE__ */ React.createElement("div", { className: "operations-field-grid" }, /* @__PURE__ */ React.createElement("label", { className: "operations-field-span" }, /* @__PURE__ */ React.createElement("span", null, "URL"), /* @__PURE__ */ React.createElement("input", { value: url, onChange: (event) => setUrl(event.target.value) })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Events"), /* @__PURE__ */ React.createElement("input", { value: events, onChange: (event) => setEvents(event.target.value) })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Secret"), /* @__PURE__ */ React.createElement("input", { type: "password", autoComplete: "new-password", value: secret, onChange: (event) => setSecret(event.target.value), placeholder: "Optional signing secret" }))), /* @__PURE__ */ React.createElement("div", { className: "operations-footer" }, /* @__PURE__ */ React.createElement("div", { className: "operations-inline-note" }, /* @__PURE__ */ React.createElement("strong", null, "Signing metadata stays visible."), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "Keep delivery trust cues close without forcing operators into a dense registry wall.")), /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: createWebhook, disabled: Boolean(busy) || !url.trim() }, busy === "Creating webhook" ? busy : "Register webhook")), /* @__PURE__ */ React.createElement("article", { className: "operations-subpanel" }, /* @__PURE__ */ React.createElement("div", { className: "operations-keyline-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Endpoints"), /* @__PURE__ */ React.createElement("strong", null, endpoints.length)), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Deliveries"), /* @__PURE__ */ React.createElement("strong", null, deliveries.length)), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Secret"), /* @__PURE__ */ React.createElement("strong", null, secret.trim() ? "provided" : "optional")))))), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack operations-table-card" }, /* @__PURE__ */ React.createElement("div", { className: "operations-table-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Webhook registry"), /* @__PURE__ */ React.createElement("h3", null, "Endpoints and deliveries"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "Keep endpoint health, signing, and actions visible with more breathing room around each registry row.")), /* @__PURE__ */ React.createElement("div", { className: "operations-pill-row" }, /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, endpoints.length, " endpoints"), /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, deliveries.length, " deliveries"))), endpoints.length ? /* @__PURE__ */ React.createElement("div", { className: "table-wrap operations-table-wrap" }, /* @__PURE__ */ React.createElement("table", { className: "data-table" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", null, /* @__PURE__ */ React.createElement("th", null, "Endpoint"), /* @__PURE__ */ React.createElement("th", null, "Events"), /* @__PURE__ */ React.createElement("th", null, "Signing"), /* @__PURE__ */ React.createElement("th", null, "Status"), /* @__PURE__ */ React.createElement("th", null))), /* @__PURE__ */ React.createElement("tbody", null, endpoints.map((endpoint) => /* @__PURE__ */ React.createElement("tr", { key: endpoint.id }, /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement("div", { className: "table-primary" }, endpoint.url), /* @__PURE__ */ React.createElement("div", { className: "table-secondary" }, endpoint.id)), /* @__PURE__ */ React.createElement("td", null, (endpoint.events || []).join(", ")), /* @__PURE__ */ React.createElement("td", null, endpoint.signing?.secret_set ? endpoint.signing.secret_hint : "not set"), /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement(StatusPill, { value: endpoint.enabled ? "enabled" : "disabled" })), /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement("div", { className: "button-row operations-table-actions" }, /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => void testWebhook(String(endpoint.id)), disabled: Boolean(busy) }, "Test"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => void deleteWebhook(String(endpoint.id)), disabled: Boolean(busy) }, "Delete")))))))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No webhooks registered", body: "Register a local endpoint to prepare for signed lifecycle deliveries." })), /* @__PURE__ */ React.createElement(
      DensityDisclosure,
      {
        className: "panel section-stack operations-table-card operations-log-panel",
        title: `Delivery log \xB7 ${deliveries.length}`,
        detail: "Open signed delivery history only when you need to inspect responses or retry failed attempts."
      },
      deliveries.length ? /* @__PURE__ */ React.createElement("div", { className: "table-wrap operations-table-wrap" }, /* @__PURE__ */ React.createElement("table", { className: "data-table" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", null, /* @__PURE__ */ React.createElement("th", null, "Delivery"), /* @__PURE__ */ React.createElement("th", null, "Event"), /* @__PURE__ */ React.createElement("th", null, "Status"), /* @__PURE__ */ React.createElement("th", null, "Attempts"), /* @__PURE__ */ React.createElement("th", null, "Response"), /* @__PURE__ */ React.createElement("th", null))), /* @__PURE__ */ React.createElement("tbody", null, deliveries.map((delivery) => /* @__PURE__ */ React.createElement("tr", { key: delivery.id }, /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement("div", { className: "table-primary" }, delivery.id), /* @__PURE__ */ React.createElement("div", { className: "table-secondary" }, delivery.endpoint_id)), /* @__PURE__ */ React.createElement("td", null, delivery.event_type), /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement(StatusPill, { value: delivery.status })), /* @__PURE__ */ React.createElement("td", null, delivery.attempts), /* @__PURE__ */ React.createElement("td", null, delivery.response_status || delivery.error || "\u2014"), /* @__PURE__ */ React.createElement("td", null, delivery.status === "failed" ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => void retryDelivery(String(delivery.id)), disabled: Boolean(busy) }, "Retry") : "\u2014")))))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No deliveries yet", body: "Run a saved version, batch, or webhook test to populate the delivery log." })
    ));
  }
  function StartPage({
    shell,
    navigate,
    onMutate
  }) {
    const health = useJsonResource(`${bootstrap.api_root}/health`, []);
    const providers = useJsonResource(`${bootstrap.api_root}/providers/status`, []);
    const workflows = useJsonResource(`${bootstrap.api_root}/workflows`, []);
    const runs = useJsonResource(`${bootstrap.api_root}/runs`, []);
    const [mode, setMode] = useState("start");
    const [provider, setProvider] = useState("deterministic");
    const [limit, setLimit] = useState("2");
    const [user, setUser] = useState("");
    const [baseUrl, setBaseUrl] = useState("");
    const [model, setModel] = useState("");
    const [maxTokens, setMaxTokens] = useState("768");
    const [baselineRunId, setBaselineRunId] = useState("");
    const [selectedWorkflow, setSelectedWorkflow] = useState("");
    const [busy, setBusy] = useState(null);
    const [notice, setNotice] = useState(null);
    const [result, setResult] = useState(null);
    const workflowDetail = useJsonResource(
      selectedWorkflow ? `${bootstrap.api_root}/workflows/${encodeURIComponent(selectedWorkflow)}` : null,
      [selectedWorkflow]
    );
    const workflowExplain = useJsonResource(
      selectedWorkflow ? `${bootstrap.api_root}/workflows/${encodeURIComponent(selectedWorkflow)}/explain` : null,
      [selectedWorkflow]
    );
    const workflowItems = workflows.data?.items || [];
    const providerCards = providers.data?.cards || [];
    const modeCopy = {
      start: {
        title: "First-success quickstart",
        body: "Runs the released deterministic baseline with the same local launch contract as the CLI start path.",
        detail: "Best for a clean first run and release verification."
      },
      demo: {
        title: "Bounded demo setup",
        body: "Keeps the demo local, bounded, and report-ready while preserving deterministic as the default runtime.",
        detail: "Optional local runtime overrides stay explicit but do not widen the release promise."
      },
      workflow: {
        title: "Named workflow launch",
        body: "Select one registered workflow, inspect its metadata, then launch a bounded run with shared services.",
        detail: "Use the workflow catalog below when you need a clearer discovery path than the dropdown."
      }
    }[mode];
    useEffect(() => {
      const items = workflowItems;
      if (!selectedWorkflow && items.length) {
        setSelectedWorkflow(String(items[0].name || ""));
      }
    }, [selectedWorkflow, workflows.data]);
    async function launchRun() {
      setBusy("Running");
      setNotice(null);
      try {
        const payload = { limit: Number(limit), user: user || void 0 };
        if (baselineRunId) {
          payload.baseline_run_id = baselineRunId;
        }
        let response;
        if (mode === "start") {
          response = await requestJson(`${bootstrap.api_root}/start`, { method: "POST", body: JSON.stringify(payload) });
        } else {
          payload.provider = provider;
          payload.write_report = true;
          if (baseUrl) payload.base_url = baseUrl;
          if (model) payload.model = model;
          if (maxTokens) payload.max_tokens = Number(maxTokens);
          if (mode === "workflow" && selectedWorkflow) {
            payload.workflow_name = selectedWorkflow;
          }
          response = await requestJson(`${bootstrap.api_root}/runs`, { method: "POST", body: JSON.stringify(payload) });
        }
        setResult(response);
        onMutate();
        runs.reload();
        setNotice({
          tone: "success",
          title: "Run created",
          body: response.compare?.href ? "The candidate is ready with a baseline comparison link." : "Inspect the new run now, then export or compare it from the run detail page."
        });
      } catch (error) {
        setNotice(buildActionErrorNotice("run", error));
      } finally {
        setBusy(null);
      }
    }
    return /* @__PURE__ */ React.createElement("main", { className: "page-grid" }, /* @__PURE__ */ React.createElement("section", { className: "panel hero-panel" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Start"), /* @__PURE__ */ React.createElement("h2", null, "Run first success without leaving the WebUI"), /* @__PURE__ */ React.createElement("p", null, "Use the deterministic quickstart, launch a bounded demo, or run a named workflow with the same product services used by the CLI."), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: launchRun, disabled: Boolean(busy) || mode === "workflow" && !selectedWorkflow }, busy || (mode === "start" ? "Run quickstart" : mode === "demo" ? "Run demo" : "Run workflow")), selectedWorkflow ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(`/workflows/${encodeURIComponent(selectedWorkflow)}`) }, "Open workflow detail") : null, shell?.overview?.latest_run?.run_id ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(`/runs/${shell.overview.latest_run.run_id}`) }, "Inspect latest run") : null)), notice ? /* @__PURE__ */ React.createElement(Message, { tone: notice.tone, title: notice.title, body: notice.body }) : null, result ? /* @__PURE__ */ React.createElement(RunLaunchResultCard, { result, navigate }) : null, /* @__PURE__ */ React.createElement("div", { className: "split-grid" }, /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Run controls"), /* @__PURE__ */ React.createElement("p", null, "Start small with the released baseline, then move to demo or named workflow execution."))), /* @__PURE__ */ React.createElement("article", { className: "info-card start-mode-card" }, /* @__PURE__ */ React.createElement("h4", null, modeCopy.title), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, modeCopy.body), /* @__PURE__ */ React.createElement("span", { className: "workflow-note" }, modeCopy.detail)), /* @__PURE__ */ React.createElement(
      "form",
      {
        className: "form-grid",
        onSubmit: (event) => {
          event.preventDefault();
          void launchRun();
        }
      },
      /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Mode"), /* @__PURE__ */ React.createElement("select", { value: mode, onChange: (event) => setMode(event.target.value) }, /* @__PURE__ */ React.createElement("option", { value: "start" }, "First-success quickstart"), /* @__PURE__ */ React.createElement("option", { value: "demo" }, "Bounded demo run"), /* @__PURE__ */ React.createElement("option", { value: "workflow" }, "Named workflow run"))),
      mode === "workflow" ? /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Workflow"), /* @__PURE__ */ React.createElement("select", { value: selectedWorkflow, onChange: (event) => setSelectedWorkflow(event.target.value) }, (workflows.data?.items || []).map((item) => /* @__PURE__ */ React.createElement("option", { key: item.name, value: item.name }, item.title || item.name)))) : null,
      mode !== "start" ? /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Provider"), /* @__PURE__ */ React.createElement("select", { value: provider, onChange: (event) => setProvider(event.target.value) }, /* @__PURE__ */ React.createElement("option", { value: "deterministic" }, "Deterministic baseline"), /* @__PURE__ */ React.createElement("option", { value: "local-llm" }, "Local runtime (optional)"))) : null,
      /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Question limit"), /* @__PURE__ */ React.createElement("input", { value: limit, onChange: (event) => setLimit(event.target.value) })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Baseline run"), /* @__PURE__ */ React.createElement("select", { value: baselineRunId, onChange: (event) => setBaselineRunId(event.target.value) }, /* @__PURE__ */ React.createElement("option", { value: "" }, "None"), (runs.data?.items || []).map((run) => /* @__PURE__ */ React.createElement("option", { key: run.run_id, value: run.run_id }, run.run_id))))),
      mode !== "start" && provider === "local-llm" ? /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Base URL"), /* @__PURE__ */ React.createElement("input", { value: baseUrl, placeholder: "http://localhost:8000/v1", onChange: (event) => setBaseUrl(event.target.value) })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Model"), /* @__PURE__ */ React.createElement("input", { value: model, placeholder: "your-model-id", onChange: (event) => setModel(event.target.value) }))) : null,
      mode !== "start" ? /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Max tokens"), /* @__PURE__ */ React.createElement("input", { value: maxTokens, onChange: (event) => setMaxTokens(event.target.value) })) : null,
      /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "User attribution"), /* @__PURE__ */ React.createElement("input", { value: user, placeholder: "Optional analyst or operator name", onChange: (event) => setUser(event.target.value) }))
    )), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Environment health"), /* @__PURE__ */ React.createElement("p", null, String(providers.data?.surface?.summary || "Readiness, provider status, and the currently selected workflow stay visible before you launch anything.")))), /* @__PURE__ */ React.createElement("div", { className: "stats-grid" }, /* @__PURE__ */ React.createElement(MetricCard, { label: "Ready checks passing", value: (health.data?.checks || []).filter((item) => item.ok).length }), /* @__PURE__ */ React.createElement(MetricCard, { label: "Checks total", value: (health.data?.checks || []).length }), /* @__PURE__ */ React.createElement(MetricCard, { label: "Deterministic baseline", value: providers.data?.deterministic?.ready ? "Ready" : "Check" }), /* @__PURE__ */ React.createElement(MetricCard, { label: "Local runtime", value: providers.data?.local_runtime?.healthy ? "Available" : "Optional" })), health.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Health unavailable", body: health.error }) : null, (health.data?.checks || []).length ? /* @__PURE__ */ React.createElement("div", { className: "card-grid" }, (health.data?.checks || []).map((item) => /* @__PURE__ */ React.createElement("article", { key: item.name, className: "info-card" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("strong", null, item.name), /* @__PURE__ */ React.createElement(StatusPill, { value: item.ok ? "ready" : "failed" })), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, item.detail)))) : null, /* @__PURE__ */ React.createElement("div", { className: "provider-status-grid" }, providerCards.length ? providerCards.map((item) => /* @__PURE__ */ React.createElement("article", { key: String(item.key || item.label), className: "info-card" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("strong", null, String(item.label || "Provider status")), /* @__PURE__ */ React.createElement(StatusPill, { value: String(item.status || "ready") })), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, String(item.value || "\u2014")), item.detail ? /* @__PURE__ */ React.createElement("span", { className: "workflow-note" }, String(item.detail)) : null)) : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("article", { className: "info-card" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("strong", null, "Deterministic baseline"), /* @__PURE__ */ React.createElement(StatusPill, { value: "ready" })), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "Ready"), /* @__PURE__ */ React.createElement("span", { className: "workflow-note" }, "Released local baseline for first success, demos, and verification.")), /* @__PURE__ */ React.createElement("article", { className: "info-card" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("strong", null, "Local runtime (optional)"), /* @__PURE__ */ React.createElement(StatusPill, { value: providers.data?.local_llm?.healthy ? "available" : "optional" })), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, providers.data?.local_llm?.healthy ? "Available" : "Optional"), /* @__PURE__ */ React.createElement("span", { className: "workflow-note" }, String(providers.data?.local_llm?.base_url || providers.data?.local_llm?.error || "Optional local runtime not configured."))))))), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Workflow guide"), /* @__PURE__ */ React.createElement("p", null, "Inspect the selected workflow before running it so the graph and expected artifacts stay explicit."))), workflowDetail.loading && !workflowDetail.data ? /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading workflow detail" }) : null, workflowDetail.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Workflow detail unavailable", body: workflowDetail.error }) : null, workflowDetail.data ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("div", { className: "split-grid" }, /* @__PURE__ */ React.createElement("section", { className: "section-stack" }, /* @__PURE__ */ React.createElement("article", { className: "info-card" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, workflowDetail.data.workflow?.title || workflowDetail.data.workflow?.name), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, workflowDetail.data.workflow?.description || "No description available.")), /* @__PURE__ */ React.createElement("span", { className: `source-pill ${workflowDetail.data.workflow?.source || "builtin"}` }, workflowDetail.data.workflow?.source || "builtin")), /* @__PURE__ */ React.createElement("div", { className: "stats-grid compact-stats-grid" }, (workflowDetail.data.summary_cards || []).map((card) => /* @__PURE__ */ React.createElement(MetricCard, { key: card.label, label: card.label, value: card.value })))), /* @__PURE__ */ React.createElement("article", { className: "info-card" }, /* @__PURE__ */ React.createElement("h4", null, "Explain"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, workflowExplain.data?.explanation?.summary || "Choose a workflow to load its explanation."), (workflowExplain.data?.explanation?.runtime_requirements || []).length ? /* @__PURE__ */ React.createElement("ul", { className: "guidance-list" }, (workflowExplain.data?.explanation?.runtime_requirements || []).map((item) => /* @__PURE__ */ React.createElement("li", { key: item }, item))) : null, (workflowExplain.data?.explanation?.expected_artifacts || []).length ? /* @__PURE__ */ React.createElement(
      DensityDisclosure,
      {
        className: "workflow-guide-disclosure",
        title: `Expected artifacts \xB7 ${(workflowExplain.data?.explanation?.expected_artifacts || []).length}`,
        detail: "Keep the shared evidence contract visible before running."
      },
      /* @__PURE__ */ React.createElement("ul", { className: "guidance-list" }, (workflowExplain.data?.explanation?.expected_artifacts || []).map((item) => /* @__PURE__ */ React.createElement("li", { key: item }, item)))
    ) : null)), /* @__PURE__ */ React.createElement("section", { className: "section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "canvas-grid" }, (workflowDetail.data.canvas?.nodes || []).map((node) => /* @__PURE__ */ React.createElement("article", { key: node.name, className: "canvas-node" }, /* @__PURE__ */ React.createElement("strong", null, node.name), /* @__PURE__ */ React.createElement("span", null, node.kind), /* @__PURE__ */ React.createElement("span", null, node.description || node.implementation || "No description"), /* @__PURE__ */ React.createElement(StatusPill, { value: node.status || "ready" })))), workflowDetail.data.compatibility?.summary ? /* @__PURE__ */ React.createElement("article", { className: "info-card" }, /* @__PURE__ */ React.createElement("h4", null, "Authoring posture"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, String(workflowDetail.data.compatibility.summary)), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(String(workflowDetail.data.compatibility.primary_route || `/studio?workflow=${encodeURIComponent(selectedWorkflow)}`)) }, "Open Studio"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(String(workflowDetail.data.compatibility.legacy_route || `/workbench?workflow=${encodeURIComponent(selectedWorkflow)}`)) }, "Open Workbench"))) : null)), /* @__PURE__ */ React.createElement(
      DensityDisclosure,
      {
        className: "workflow-guide-disclosure",
        title: `Workflow catalog \xB7 ${workflowItems.length}`,
        detail: "Browse reusable workflows here before switching the named-run control above."
      },
      workflowItems.length ? /* @__PURE__ */ React.createElement("div", { className: "workflow-list workflow-catalog" }, workflowItems.map((item) => /* @__PURE__ */ React.createElement("article", { key: String(item.name), className: `workflow-tile${selectedWorkflow === item.name ? " active" : ""}` }, /* @__PURE__ */ React.createElement("div", { className: "workflow-tile-head" }, /* @__PURE__ */ React.createElement("strong", null, item.title || item.name), /* @__PURE__ */ React.createElement(SourceBadge, { source: String(item.source || "builtin") })), /* @__PURE__ */ React.createElement("p", { className: "workflow-note" }, item.description || "Reusable workflow from the local registry."), /* @__PURE__ */ React.createElement("div", { className: "meta-row" }, /* @__PURE__ */ React.createElement("span", null, providerLabel(String(item.runtime_provider || "deterministic"))), /* @__PURE__ */ React.createElement("span", null, formatValue(item.question_limit), " questions")), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement(
        "button",
        {
          className: "secondary-button",
          onClick: () => {
            setMode("workflow");
            setSelectedWorkflow(String(item.name || ""));
          }
        },
        "Use for run"
      ), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(`/workflows/${encodeURIComponent(String(item.name || ""))}`) }, "Open detail"))))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No workflows indexed", body: "Refresh the workflow registry or create a local draft in Studio." })
    )) : null));
  }
  function WorkflowDetailPage({
    workflowName,
    navigate,
    onMutate
  }) {
    const detail = useJsonResource(`${bootstrap.api_root}/workflows/${encodeURIComponent(workflowName)}`, [workflowName]);
    const [provider, setProvider] = useState("");
    const [limit, setLimit] = useState("");
    const [baselineRunId, setBaselineRunId] = useState("");
    const [busy, setBusy] = useState(null);
    const [notice, setNotice] = useState(null);
    const workflowSummaryCards = detail.data?.summary_cards || [];
    const recentRuns = detail.data?.recent_runs || [];
    const explanation = detail.data?.explanation || {};
    const workflowActions = detail.data?.actions || {};
    const explainAction = workflowActions.explain || {};
    const validateAction = workflowActions.validate || {};
    const runAction = workflowActions.run || {};
    const baselineOptions = runAction.baseline_options || [];
    const compatibility = detail.data?.compatibility || {};
    useEffect(() => {
      if (!detail.data) return;
      if (!provider) {
        setProvider(String(runAction.default_provider || detail.data.workflow?.runtime_provider || ""));
      }
      if (!limit) {
        const defaultLimit = runAction.default_limit ?? detail.data.workflow?.question_limit;
        if (defaultLimit !== void 0 && defaultLimit !== null && defaultLimit !== "") {
          setLimit(String(defaultLimit));
        }
      }
    }, [detail.data, provider, limit]);
    async function validateWorkflow() {
      setBusy("Validating workflow");
      setNotice(null);
      try {
        const response = await requestJson(`${bootstrap.api_root}/workflows/${encodeURIComponent(workflowName)}/validate`, {
          method: "POST",
          body: JSON.stringify({})
        });
        setNotice({
          tone: "success",
          title: "Workflow valid",
          body: String(validateAction.success_label || `${response.workflow_name} is ready to run.`)
        });
      } catch (error) {
        setNotice(buildActionErrorNotice("validate", error));
      } finally {
        setBusy(null);
      }
    }
    async function openAuthoringSurface() {
      if (detail.data?.workflow?.source === "local") {
        navigate(String(compatibility.primary_route || `/studio?workflow=${encodeURIComponent(workflowName)}`));
        return;
      }
      setBusy("Opening Studio draft");
      setNotice(null);
      try {
        const created = await requestJson(`${bootstrap.api_root}/drafts`, {
          method: "POST",
          body: JSON.stringify({ source_workflow_name: workflowName })
        });
        onMutate();
        navigate(`/studio?draft=${encodeURIComponent(String(created.id || created.draft?.id || ""))}`);
      } catch (error) {
        setNotice(buildActionErrorNotice("open Studio", error));
      } finally {
        setBusy(null);
      }
    }
    async function runWorkflow() {
      setBusy("Running workflow");
      setNotice(null);
      try {
        const payload = {
          write_report: true
        };
        if (provider) payload.provider = provider;
        if (limit) payload.limit = Number(limit);
        if (baselineRunId) payload.baseline_run_id = baselineRunId;
        const response = await requestJson(
          `${bootstrap.api_root}/workflows/${encodeURIComponent(workflowName)}/run`,
          { method: "POST", body: JSON.stringify(payload) }
        );
        onMutate();
        setNotice({
          tone: "success",
          title: "Workflow launched",
          body: response.compare?.href ? "The candidate run is ready with a comparison link." : "Inspect the run detail to review report and exports."
        });
        navigate(response.compare?.href || response.href);
      } catch (error) {
        setNotice(buildActionErrorNotice("run", error));
      } finally {
        setBusy(null);
      }
    }
    if (detail.error) {
      return /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Workflow unavailable", body: detail.error });
    }
    if (detail.loading || !detail.data) {
      return /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading workflow detail" });
    }
    return /* @__PURE__ */ React.createElement("main", { className: "page-grid" }, /* @__PURE__ */ React.createElement("section", { className: "panel hero-panel" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Workflow"), /* @__PURE__ */ React.createElement("h2", null, detail.data.workflow?.title || detail.data.workflow?.name), /* @__PURE__ */ React.createElement("p", null, detail.data.workflow?.description || explanation.summary || "Inspect, validate, and run this workflow from the WebUI."), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: runWorkflow, disabled: Boolean(busy) }, busy === "Running workflow" ? busy : "Run workflow"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: validateWorkflow, disabled: Boolean(busy) }, busy === "Validating workflow" ? busy : "Validate"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => void openAuthoringSurface(), disabled: Boolean(busy) }, busy === "Opening Studio draft" ? busy : detail.data.workflow?.source === "local" ? "Open Studio" : "Clone into Studio"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate("/start") }, "Back to start"))), notice ? /* @__PURE__ */ React.createElement(Message, { tone: notice.tone, title: notice.title, body: notice.body }) : null, workflowSummaryCards.length ? /* @__PURE__ */ React.createElement("section", { className: "stats-grid" }, workflowSummaryCards.map((card) => /* @__PURE__ */ React.createElement(MetricCard, { key: card.label, label: card.label, value: card.value }))) : null, /* @__PURE__ */ React.createElement("div", { className: "split-grid" }, /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Execution settings"), /* @__PURE__ */ React.createElement("p", null, "Keep explain, validate, and run on one route while preserving the same local execution contract as the CLI."))), /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Provider"), /* @__PURE__ */ React.createElement("select", { value: provider, onChange: (event) => setProvider(event.target.value) }, /* @__PURE__ */ React.createElement("option", { value: "deterministic" }, "Deterministic baseline"), /* @__PURE__ */ React.createElement("option", { value: "local-llm" }, "Local runtime (optional)"))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Question limit"), /* @__PURE__ */ React.createElement("input", { value: limit, onChange: (event) => setLimit(event.target.value) }))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Baseline run for compare"), /* @__PURE__ */ React.createElement("select", { value: baselineRunId, onChange: (event) => setBaselineRunId(event.target.value) }, /* @__PURE__ */ React.createElement("option", { value: "" }, "None"), baselineOptions.map((run) => /* @__PURE__ */ React.createElement("option", { key: String(run.run_id), value: String(run.run_id) }, String(run.label || run.run_id))))), /* @__PURE__ */ React.createElement("div", { className: "info-grid workflow-contract-grid" }, /* @__PURE__ */ React.createElement("article", { className: "info-card workflow-contract-card" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h4", null, "Explain"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, String(explainAction.summary || "Plain-language workflow walkthrough shared with the CLI explain command."))), /* @__PURE__ */ React.createElement(StatusPill, { value: "shared explain" })), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, String(explanation.summary || explanation.error || "Workflow explanation unavailable.")), (explanation.runtime_requirements || []).length ? /* @__PURE__ */ React.createElement("ul", { className: "guidance-list" }, (explanation.runtime_requirements || []).map((item) => /* @__PURE__ */ React.createElement("li", { key: item }, item))) : null, /* @__PURE__ */ React.createElement("code", { className: "workflow-command" }, String(explainAction.cli_command || `xrtm workflow explain ${workflowName}`))), /* @__PURE__ */ React.createElement("article", { className: "info-card workflow-contract-card" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h4", null, "Validate"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, String(validateAction.summary || "Shared validation keeps the WebUI honest about what can run locally."))), /* @__PURE__ */ React.createElement(StatusPill, { value: "shared validate" })), /* @__PURE__ */ React.createElement("ul", { className: "guidance-list" }, /* @__PURE__ */ React.createElement("li", null, String(validateAction.success_label || `Workflow valid: ${workflowName}`)), /* @__PURE__ */ React.createElement("li", null, "Validation stays inside the safe product node library and the released workflow schema."), /* @__PURE__ */ React.createElement("li", null, "Failures remain local and explicit so you can fix the workflow before execution.")), /* @__PURE__ */ React.createElement("code", { className: "workflow-command" }, String(validateAction.cli_command || `xrtm workflow validate ${workflowName}`))), /* @__PURE__ */ React.createElement("article", { className: "info-card workflow-contract-card" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h4", null, "Run contract"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, String(runAction.summary || "Run this named workflow through the same shared launch service as the CLI."))), /* @__PURE__ */ React.createElement(StatusPill, { value: String(runAction.default_provider === "local-llm" ? "local optional" : "deterministic default") })), (runAction.trust_cues || []).length ? /* @__PURE__ */ React.createElement("ul", { className: "guidance-list" }, (runAction.trust_cues || []).map((item) => /* @__PURE__ */ React.createElement("li", { key: item }, item))) : null, /* @__PURE__ */ React.createElement("code", { className: "workflow-command" }, String(runAction.cli_command || `xrtm workflow run ${workflowName}`)))), /* @__PURE__ */ React.createElement("article", { className: "info-card workflow-guide-disclosure" }, /* @__PURE__ */ React.createElement("h4", null, "Evidence and node roles"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "Keep the shared runtime and evidence expectations visible before you run."), (explanation.expected_artifacts || []).length ? /* @__PURE__ */ React.createElement(
      DensityDisclosure,
      {
        className: "workflow-guide-disclosure",
        title: `Expected artifacts \xB7 ${(explanation.expected_artifacts || []).length}`,
        detail: "Matches the CLI explain output for this workflow."
      },
      /* @__PURE__ */ React.createElement("ul", { className: "guidance-list" }, (explanation.expected_artifacts || []).map((item) => /* @__PURE__ */ React.createElement("li", { key: item }, item)))
    ) : null, (explanation.nodes || []).length ? /* @__PURE__ */ React.createElement(
      DensityDisclosure,
      {
        className: "workflow-guide-disclosure",
        title: `Plain-language node roles \xB7 ${(explanation.nodes || []).length}`,
        detail: "The same role summary shown by the CLI explain command."
      },
      /* @__PURE__ */ React.createElement("div", { className: "action-stack workflow-node-list" }, (explanation.nodes || []).map((node) => /* @__PURE__ */ React.createElement("article", { key: String(node.name), className: "surface-card workflow-node-card" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("strong", null, String(node.name || "node")), /* @__PURE__ */ React.createElement(StatusPill, { value: String(node.runtime || detail.data.workflow?.runtime_provider || "ready") })), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, String(node.summary || node.kind || "No role summary available.")))))
    ) : null, compatibility.summary || compatibility.primary_route ? /* @__PURE__ */ React.createElement("div", { className: "info-card workflow-compatibility-card" }, /* @__PURE__ */ React.createElement("h4", null, "Authoring posture"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, String(compatibility.summary || "Studio stays primary while Workbench remains available for compatibility.")), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(String(compatibility.primary_route || `/studio?workflow=${encodeURIComponent(workflowName)}`)) }, "Open Studio"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(String(compatibility.legacy_route || `/workbench?workflow=${encodeURIComponent(workflowName)}`)) }, "Open Workbench"))) : null), recentRuns.length ? /* @__PURE__ */ React.createElement(
      DensityDisclosure,
      {
        className: "workflow-guide-disclosure",
        title: `Recent runs \xB7 ${recentRuns.length}`,
        detail: "Open recent evidence for this workflow without leaving the detail route."
      },
      /* @__PURE__ */ React.createElement("div", { className: "action-list" }, recentRuns.map((run) => /* @__PURE__ */ React.createElement("button", { key: String(run.run_id), className: "secondary-button action-button", onClick: () => navigate(String(run.href || `/runs/${run.run_id}`)) }, /* @__PURE__ */ React.createElement("span", null, String(run.label || run.run_id)), run.summary ? /* @__PURE__ */ React.createElement("small", null, String(run.summary)) : null)))
    ) : /* @__PURE__ */ React.createElement(
      EmptyState,
      {
        title: detail.data.recent_runs_empty_state?.title || "No recent runs for this workflow",
        body: detail.data.recent_runs_empty_state?.body || "Launch a bounded run to seed workflow-specific evidence."
      }
    )), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Canvas"), /* @__PURE__ */ React.createElement("p", null, "Graph nodes stay visible so you can inspect the release-safe workflow shape before running it."))), /* @__PURE__ */ React.createElement("div", { className: "canvas-grid" }, (detail.data.canvas?.nodes || []).map((node) => /* @__PURE__ */ React.createElement("article", { key: node.name, className: "canvas-node" }, /* @__PURE__ */ React.createElement("strong", null, node.name), /* @__PURE__ */ React.createElement("span", null, node.kind), /* @__PURE__ */ React.createElement("span", null, node.description || node.implementation || "No description"), /* @__PURE__ */ React.createElement(StatusPill, { value: node.status || "ready" })))))));
  }
  function OperationsPage({ navigate, onMutate }) {
    const profiles = useJsonResource(`${bootstrap.api_root}/profiles`, []);
    const monitors = useJsonResource(`${bootstrap.api_root}/monitors`, []);
    const runs = useJsonResource(`${bootstrap.api_root}/runs`, []);
    const [profileName, setProfileName] = useState("local-default");
    const [profileProvider, setProfileProvider] = useState("deterministic");
    const [profileLimit, setProfileLimit] = useState("5");
    const [selectedProfile, setSelectedProfile] = useState("");
    const [selectedMonitor, setSelectedMonitor] = useState("");
    const [selectedArtifactRun, setSelectedArtifactRun] = useState("");
    const [cleanupKeep, setCleanupKeep] = useState("5");
    const [cleanupPreview, setCleanupPreview] = useState(null);
    const [busy, setBusy] = useState(null);
    const [notice, setNotice] = useState(null);
    const profileDetail = useJsonResource(
      selectedProfile ? `${bootstrap.api_root}/profiles/${encodeURIComponent(selectedProfile)}` : null,
      [selectedProfile]
    );
    const monitorDetail = useJsonResource(selectedMonitor ? `${bootstrap.api_root}/monitors/${selectedMonitor}` : null, [selectedMonitor]);
    const artifactDetail = useJsonResource(
      selectedArtifactRun ? `${bootstrap.api_root}/artifacts/${selectedArtifactRun}` : null,
      [selectedArtifactRun]
    );
    const profileItems = profiles.data?.items || [];
    const monitorItems = monitors.data?.items || [];
    const runItems = runs.data?.items || [];
    const selectedProfileItem = useMemo(() => {
      if (selectedProfile) return profileItems.find((item) => String(item.name) === selectedProfile) || profileItems[0] || null;
      return profileItems[0] || null;
    }, [selectedProfile, profileItems]);
    const selectedMonitorItem = useMemo(() => {
      if (selectedMonitor) return monitorItems.find((item) => String(item.run_id) === selectedMonitor) || monitorItems[0] || null;
      return monitorItems[0] || null;
    }, [selectedMonitor, monitorItems]);
    const selectedProfileSummary = profileDetail.data?.profile || selectedProfileItem || null;
    const selectedMonitorSummary = monitorDetail.data?.monitor || selectedMonitorItem || null;
    const activeMonitorCount = monitorItems.filter((item) => {
      const status = String(item.status || "").toLowerCase();
      return status && !["halted", "completed", "stopped"].includes(status);
    }).length;
    const operationsHeroMetrics = [
      { label: "Profiles", value: profileItems.length, detail: "repeatable presets" },
      { label: "Active monitors", value: activeMonitorCount, detail: "running or resumable" },
      { label: "Run directories", value: runItems.length, detail: "artifact inventory" },
      { label: "Cleanup preview", value: cleanupPreview?.count ?? 0, detail: "pending removals" }
    ];
    const operationsFocusItems = [
      {
        label: "Preset",
        title: "Save one calm local profile first",
        detail: "Profile composition stays up front, while the registry and run actions sit behind bounded disclosure."
      },
      {
        label: "Monitor",
        title: "Operate lifecycle controls from a contained registry",
        detail: "Run, pause, resume, and halt remain visible without forcing full monitor detail to stay open."
      },
      {
        label: "Retain",
        title: "Preview cleanup before delete",
        detail: "Artifacts and retention now read as a deliberate maintenance lane rather than always-on operator chrome."
      }
    ];
    const parsedProfileLimit = parsePositiveIntegerInput(profileLimit);
    const parsedCleanupKeep = parsePositiveIntegerInput(cleanupKeep);
    useEffect(() => {
      if (!selectedProfile && profileItems[0]?.name) {
        setSelectedProfile(String(profileItems[0].name));
      }
    }, [profileItems, selectedProfile]);
    useEffect(() => {
      if (!selectedMonitor && monitorItems[0]?.run_id) {
        setSelectedMonitor(String(monitorItems[0].run_id));
      }
    }, [monitorItems, selectedMonitor]);
    useEffect(() => {
      if (!selectedArtifactRun && runItems.length) {
        setSelectedArtifactRun(String(runItems[0].run_id || ""));
      }
    }, [runItems, selectedArtifactRun]);
    async function createProfile(template) {
      setBusy("Saving profile");
      setNotice(null);
      try {
        await requestJson(`${bootstrap.api_root}/profiles`, {
          method: "POST",
          body: JSON.stringify({
            name: profileName,
            template: template === "starter" ? "starter" : void 0,
            provider: template === "starter" ? void 0 : profileProvider,
            limit: template === "starter" ? void 0 : parsedProfileLimit ?? void 0,
            write_report: true
          })
        });
        profiles.reload();
        setSelectedProfile(profileName);
        setNotice({ tone: "success", title: "Profile saved", body: "Run it from the list when you want a repeatable local configuration." });
      } catch (error) {
        setNotice(buildActionErrorNotice("profile", error));
      } finally {
        setBusy(null);
      }
    }
    async function runProfile(name) {
      setBusy(`Running ${name}`);
      setNotice(null);
      try {
        const result = await requestJson(`${bootstrap.api_root}/profiles/${encodeURIComponent(name)}/run`, {
          method: "POST",
          body: JSON.stringify({})
        });
        onMutate();
        runs.reload();
        setNotice({ tone: "success", title: "Profile run started", body: `Inspect ${result.run_id} to review the new run.` });
        navigate(result.href);
      } catch (error) {
        setNotice(buildActionErrorNotice("run", error));
      } finally {
        setBusy(null);
      }
    }
    async function createMonitor() {
      setBusy("Starting monitor");
      setNotice(null);
      try {
        const result = await requestJson(`${bootstrap.api_root}/monitors`, {
          method: "POST",
          body: JSON.stringify({ limit: parsedProfileLimit, provider: profileProvider })
        });
        monitors.reload();
        setSelectedMonitor(result.run_id);
        setNotice({ tone: "success", title: "Monitor started", body: "Run a cycle, pause, resume, or halt it from this page." });
      } catch (error) {
        setNotice(buildActionErrorNotice("monitor", error));
      } finally {
        setBusy(null);
      }
    }
    async function mutateMonitor(runId, action) {
      setBusy(action);
      setNotice(null);
      try {
        await requestJson(`${bootstrap.api_root}/monitors/${runId}/${action}`, {
          method: "POST",
          body: JSON.stringify({})
        });
        monitors.reload();
        monitorDetail.reload();
        setNotice({ tone: "success", title: "Monitor updated", body: `Monitor ${action} completed.` });
      } catch (error) {
        setNotice(buildActionErrorNotice(action, error));
      } finally {
        setBusy(null);
      }
    }
    async function previewCleanup() {
      setBusy("Previewing cleanup");
      setNotice(null);
      try {
        const preview = await requestJson(`${bootstrap.api_root}/artifacts/cleanup-preview`, {
          method: "POST",
          body: JSON.stringify({ keep: parsedCleanupKeep })
        });
        setCleanupPreview(preview);
      } catch (error) {
        setNotice(buildActionErrorNotice("cleanup-preview", error));
      } finally {
        setBusy(null);
      }
    }
    async function runCleanup() {
      setBusy("Cleaning artifacts");
      setNotice(null);
      try {
        const result = await requestJson(`${bootstrap.api_root}/artifacts/cleanup`, {
          method: "POST",
          body: JSON.stringify({ keep: parsedCleanupKeep, confirm: "delete" })
        });
        setCleanupPreview(result);
        runs.reload();
        onMutate();
        setNotice({ tone: "success", title: "Artifacts cleaned", body: `${result.count || 0} run directories were removed.` });
      } catch (error) {
        setNotice(buildActionErrorNotice("cleanup", error));
      } finally {
        setBusy(null);
      }
    }
    return /* @__PURE__ */ React.createElement("main", { className: "page-grid operations-shell operations-route" }, profiles.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Profiles unavailable", body: profiles.error }) : null, monitors.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Monitors unavailable", body: monitors.error }) : null, runs.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Runs unavailable", body: runs.error }) : null, profiles.loading && monitors.loading && runs.loading && !profileItems.length && !monitorItems.length && !runItems.length ? /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading operations" }) : null, /* @__PURE__ */ React.createElement("section", { className: "panel hero-panel operations-hero" }, /* @__PURE__ */ React.createElement("div", { className: "operations-hero-grid" }, /* @__PURE__ */ React.createElement("div", { className: "operations-hero-copy" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Operations"), /* @__PURE__ */ React.createElement("h2", null, "Operate profiles, monitors, and retention without a sprawling admin wall"), /* @__PURE__ */ React.createElement("p", null, "Keep repeatable profiles, monitor lifecycles, and artifact cleanup visible in calm local surfaces instead of long stacked operator panels."), /* @__PURE__ */ React.createElement("div", { className: "button-row operations-hero-actions" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => navigate("/runs") }, "Inspect recent runs"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate("/api") }, "Open Control"))), /* @__PURE__ */ React.createElement("div", { className: "operations-hero-side" }, /* @__PURE__ */ React.createElement("article", { className: "operations-trust-card" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Operator loop"), /* @__PURE__ */ React.createElement("strong", null, "Profiles, monitor cadence, and retention stay available, but detail only expands when the task needs it."), /* @__PURE__ */ React.createElement("p", null, "Use the same local product services as the CLI while keeping saved presets, live monitor state, and cleanup consequences readable."), /* @__PURE__ */ React.createElement("div", { className: "operations-pill-row" }, /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Profile reuse"), /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Lifecycle controls"), /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Explicit cleanup"))), /* @__PURE__ */ React.createElement("div", { className: "operations-stat-grid" }, operationsHeroMetrics.map((metric) => /* @__PURE__ */ React.createElement("article", { key: metric.label, className: "operations-stat-card" }, /* @__PURE__ */ React.createElement("span", null, metric.label), /* @__PURE__ */ React.createElement("strong", null, metric.value), /* @__PURE__ */ React.createElement("small", null, metric.detail))))))), notice ? /* @__PURE__ */ React.createElement(Message, { tone: notice.tone, title: notice.title, body: notice.body }) : null, /* @__PURE__ */ React.createElement(
      RouteIdentityPanel,
      {
        className: "operations-identity-panel",
        eyebrow: "Operator rhythm",
        title: "Preset, monitor, and retain with calmer defaults",
        summary: "Operations now separates everyday preset work from heavier lifecycle and cleanup detail, while preserving the same local control surface.",
        items: operationsFocusItems
      }
    ), /* @__PURE__ */ React.createElement("section", { className: "split-grid operations-lead-grid" }, /* @__PURE__ */ React.createElement("article", { className: "panel section-stack operations-form-panel" }, /* @__PURE__ */ React.createElement("div", { className: "operations-section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Profiles"), /* @__PURE__ */ React.createElement("h3", null, "Save repeatable local presets"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "Create a starter or custom profile, then keep the saved list contained in a selectable registry instead of a growing action stack.")), /* @__PURE__ */ React.createElement("div", { className: "operations-pill-row" }, /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Starter-safe"), /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Runnable locally"))), /* @__PURE__ */ React.createElement("div", { className: "operations-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Name"), /* @__PURE__ */ React.createElement("input", { value: profileName, onChange: (event) => setProfileName(event.target.value) })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Provider"), /* @__PURE__ */ React.createElement("select", { value: profileProvider, onChange: (event) => setProfileProvider(event.target.value) }, /* @__PURE__ */ React.createElement("option", { value: "deterministic" }, "Deterministic baseline"), /* @__PURE__ */ React.createElement("option", { value: "local-llm" }, "Local runtime (optional)"))), /* @__PURE__ */ React.createElement("label", { className: "operations-field-span" }, /* @__PURE__ */ React.createElement("span", null, "Question limit"), /* @__PURE__ */ React.createElement("input", { type: "number", min: 1, step: 1, inputMode: "numeric", value: profileLimit, onChange: (event) => setProfileLimit(event.target.value) }))), /* @__PURE__ */ React.createElement("div", { className: "operations-footer" }, /* @__PURE__ */ React.createElement("div", { className: "operations-inline-note" }, /* @__PURE__ */ React.createElement("strong", null, "Profiles stay reusable across local operator flows."), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "Save first, then run from here or keep the preset available for later monitor and Control work.")), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => void createProfile("custom"), disabled: Boolean(busy) || parsedProfileLimit == null }, busy === "Saving profile" ? busy : "Save profile"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => void createProfile("starter"), disabled: Boolean(busy) }, "Save starter profile"))), /* @__PURE__ */ React.createElement(
      DensityDisclosure,
      {
        className: "operations-subpanel section-stack",
        title: `Saved profiles \xB7 ${profileItems.length}`,
        detail: "Select a saved preset when you need detail or a run, while the route keeps a bounded table instead of an uncontained stack."
      },
      profileItems.length ? /* @__PURE__ */ React.createElement("div", { className: "table-wrap operations-table-wrap" }, /* @__PURE__ */ React.createElement("table", { className: "data-table" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", null, /* @__PURE__ */ React.createElement("th", null, "Profile"), /* @__PURE__ */ React.createElement("th", null, "Provider"), /* @__PURE__ */ React.createElement("th", null, "Limit"), /* @__PURE__ */ React.createElement("th", null, "Runs dir"), /* @__PURE__ */ React.createElement("th", null, "Actions"))), /* @__PURE__ */ React.createElement("tbody", null, profileItems.map((profile) => /* @__PURE__ */ React.createElement("tr", { key: profile.name, className: String(profile.name) === String(selectedProfileSummary?.name || "") ? "is-active" : void 0 }, /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement(
        "button",
        {
          className: "table-link-button operations-row-button",
          type: "button",
          "aria-pressed": String(profile.name) === String(selectedProfileSummary?.name || ""),
          onClick: () => setSelectedProfile(String(profile.name))
        },
        /* @__PURE__ */ React.createElement("span", { className: "table-primary" }, profile.name),
        /* @__PURE__ */ React.createElement("span", { className: "table-secondary" }, profile.provider || "deterministic")
      )), /* @__PURE__ */ React.createElement("td", null, profile.provider || "deterministic"), /* @__PURE__ */ React.createElement("td", null, formatValue(profile.limit)), /* @__PURE__ */ React.createElement("td", null, profile.runs_dir || "runs"), /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement("div", { className: "button-row operations-table-actions" }, /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: (event) => runWithoutRowSelection(event, () => setSelectedProfile(String(profile.name))) }, "Show"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: (event) => runWithoutRowSelection(event, () => void runProfile(String(profile.name))), disabled: Boolean(busy) }, "Run")))))))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No profiles yet", body: "Save a starter or custom profile to keep a repeatable local preset on hand." })
    )), /* @__PURE__ */ React.createElement("article", { className: "panel section-stack operations-summary-panel" }, /* @__PURE__ */ React.createElement("div", { className: "operations-section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Posture"), /* @__PURE__ */ React.createElement("h3", null, "Selected operator context"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "Keep the current profile, monitor, and cleanup consequences close without making them permanent full-height panels.")), selectedMonitorSummary ? /* @__PURE__ */ React.createElement(StatusPill, { value: String(selectedMonitorSummary.status || "ready") }) : /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "No monitor selected")), /* @__PURE__ */ React.createElement("div", { className: "operations-stat-grid" }, /* @__PURE__ */ React.createElement("article", { className: "operations-stat-card" }, /* @__PURE__ */ React.createElement("span", null, "Profiles"), /* @__PURE__ */ React.createElement("strong", null, profileItems.length), /* @__PURE__ */ React.createElement("small", null, "saved presets")), /* @__PURE__ */ React.createElement("article", { className: "operations-stat-card" }, /* @__PURE__ */ React.createElement("span", null, "Monitors"), /* @__PURE__ */ React.createElement("strong", null, monitorItems.length), /* @__PURE__ */ React.createElement("small", null, "tracked lifecycles")), /* @__PURE__ */ React.createElement("article", { className: "operations-stat-card" }, /* @__PURE__ */ React.createElement("span", null, "Selected run"), /* @__PURE__ */ React.createElement("strong", null, selectedArtifactRun || "\u2014"), /* @__PURE__ */ React.createElement("small", null, "artifact inventory target"))), /* @__PURE__ */ React.createElement("article", { className: "operations-subpanel" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, selectedProfileSummary?.name || "No profile selected"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, selectedProfileSummary ? "Keep the active preset readable while the full list stays tucked into the bounded registry." : "Select a saved preset to inspect its run posture.")), selectedProfileSummary ? /* @__PURE__ */ React.createElement(StatusPill, { value: "ready" }) : null), /* @__PURE__ */ React.createElement("div", { className: "operations-keyline-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Provider"), /* @__PURE__ */ React.createElement("strong", null, selectedProfileSummary?.provider || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Limit"), /* @__PURE__ */ React.createElement("strong", null, selectedProfileSummary?.limit != null ? formatValue(selectedProfileSummary.limit) : "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Runs dir"), /* @__PURE__ */ React.createElement("strong", null, selectedProfileSummary?.runs_dir || "\u2014")))), /* @__PURE__ */ React.createElement(
      DensityDisclosure,
      {
        className: "operations-subpanel section-stack",
        title: selectedMonitorSummary?.run_id ? `Monitor detail \xB7 ${selectedMonitorSummary.run_id}` : "Monitor detail",
        detail: "Lifecycle controls stay available below, while selected state opens only when you need the run cadence and watch count."
      },
      selectedMonitorSummary ? /* @__PURE__ */ React.createElement("div", { className: "operations-keyline-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Status"), /* @__PURE__ */ React.createElement("strong", null, selectedMonitorSummary.status || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Cycles"), /* @__PURE__ */ React.createElement("strong", null, formatValue(selectedMonitorSummary.cycles))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Watches"), /* @__PURE__ */ React.createElement("strong", null, (selectedMonitorSummary.watches || []).length))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No monitor selected", body: "Start or select a monitor to review its lifecycle detail." })
    ), /* @__PURE__ */ React.createElement(
      DensityDisclosure,
      {
        className: "operations-subpanel section-stack",
        title: "Cleanup posture",
        detail: "Preview the deletion boundary before acting so retention stays explicit instead of hidden inside a dense footer."
      },
      /* @__PURE__ */ React.createElement("div", { className: "operations-keyline-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Keep newest"), /* @__PURE__ */ React.createElement("strong", null, cleanupKeep)), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Preview count"), /* @__PURE__ */ React.createElement("strong", null, cleanupPreview?.count ?? 0)), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Available runs"), /* @__PURE__ */ React.createElement("strong", null, runItems.length)))
    ))), /* @__PURE__ */ React.createElement("section", { className: "split-grid operations-control-grid" }, /* @__PURE__ */ React.createElement("article", { className: "panel section-stack operations-table-card" }, /* @__PURE__ */ React.createElement("div", { className: "operations-table-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Monitors"), /* @__PURE__ */ React.createElement("h3", null, "Lifecycle controls"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "Start a monitor, then keep cycle and pause controls in a contained registry instead of an endlessly growing operator list.")), /* @__PURE__ */ React.createElement("div", { className: "operations-pill-row" }, /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, monitorItems.length, " monitors"), /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => void createMonitor(), disabled: Boolean(busy) || parsedProfileLimit == null }, busy === "Starting monitor" ? busy : "Start monitor"))), monitorItems.length ? /* @__PURE__ */ React.createElement("div", { className: "table-wrap operations-table-wrap" }, /* @__PURE__ */ React.createElement("table", { className: "data-table" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", null, /* @__PURE__ */ React.createElement("th", null, "Monitor"), /* @__PURE__ */ React.createElement("th", null, "Status"), /* @__PURE__ */ React.createElement("th", null, "Provider"), /* @__PURE__ */ React.createElement("th", null, "Cycles"), /* @__PURE__ */ React.createElement("th", null, "Watches"), /* @__PURE__ */ React.createElement("th", null, "Actions"))), /* @__PURE__ */ React.createElement("tbody", null, monitorItems.map((monitor) => /* @__PURE__ */ React.createElement("tr", { key: monitor.run_id, className: String(monitor.run_id) === String(selectedMonitorSummary?.run_id || "") ? "is-active" : void 0 }, /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement(
      "button",
      {
        className: "table-link-button operations-row-button",
        type: "button",
        "aria-pressed": String(monitor.run_id) === String(selectedMonitorSummary?.run_id || ""),
        onClick: () => setSelectedMonitor(String(monitor.run_id))
      },
      /* @__PURE__ */ React.createElement("span", { className: "table-primary" }, monitor.run_id),
      /* @__PURE__ */ React.createElement("span", { className: "table-secondary" }, monitor.provider || "deterministic")
    )), /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement(StatusPill, { value: String(monitor.status || "ready") })), /* @__PURE__ */ React.createElement("td", null, monitor.provider || "deterministic"), /* @__PURE__ */ React.createElement("td", null, formatValue(monitor.cycles)), /* @__PURE__ */ React.createElement("td", null, (monitor.watches || []).length), /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement("div", { className: "button-row operations-table-actions" }, /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: (event) => runWithoutRowSelection(event, () => setSelectedMonitor(String(monitor.run_id))) }, "Show"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: (event) => runWithoutRowSelection(event, () => void mutateMonitor(String(monitor.run_id), "run-once")), disabled: Boolean(busy) }, "Run once"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: (event) => runWithoutRowSelection(event, () => void mutateMonitor(String(monitor.run_id), "pause")), disabled: Boolean(busy) }, "Pause"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: (event) => runWithoutRowSelection(event, () => void mutateMonitor(String(monitor.run_id), "resume")), disabled: Boolean(busy) }, "Resume"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: (event) => runWithoutRowSelection(event, () => void mutateMonitor(String(monitor.run_id), "halt")), disabled: Boolean(busy) }, "Halt")))))))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No monitors yet", body: "Start a monitor to keep a resumable local lifecycle on hand." })), /* @__PURE__ */ React.createElement(
      DensityDisclosure,
      {
        className: "panel section-stack operations-detail-card operations-retention-panel",
        title: `Artifacts + retention \xB7 ${cleanupPreview?.count ?? 0} previewed`,
        detail: "Inspect artifact inventory and explicit cleanup controls only when you are intentionally doing maintenance work."
      },
      /* @__PURE__ */ React.createElement("div", { className: "operations-table-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Artifacts + retention"), /* @__PURE__ */ React.createElement("h3", null, "Contained cleanup workflow"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "Inspect one run, preview retention, then confirm deletion from clearly separated subpanels.")), /* @__PURE__ */ React.createElement("div", { className: "operations-pill-row" }, /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, runItems.length, " runs"), /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Explicit delete"))),
      /* @__PURE__ */ React.createElement("div", { className: "three-column-grid operations-retention-grid" }, /* @__PURE__ */ React.createElement("section", { className: "operations-subpanel section-stack operations-retention-column" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, "Artifact inventory"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "Choose one run to inspect packaged artifacts without letting the inventory take over the whole route."))), runItems.length ? /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Run"), /* @__PURE__ */ React.createElement("select", { value: selectedArtifactRun, onChange: (event) => setSelectedArtifactRun(event.target.value) }, runItems.map((run) => /* @__PURE__ */ React.createElement("option", { key: run.run_id, value: run.run_id }, run.run_id)))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No runs available yet", body: "Run a profile or saved version first to populate the local artifact inventory." }), runItems.length && artifactDetail.data ? /* @__PURE__ */ React.createElement("div", { className: "operations-retention-scroll" }, /* @__PURE__ */ React.createElement("ul", { className: "artifact-list" }, (artifactDetail.data.artifacts || []).map((item) => /* @__PURE__ */ React.createElement("li", { key: item.name }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, item.name), /* @__PURE__ */ React.createElement("span", null, item.path)), /* @__PURE__ */ React.createElement("span", { className: `availability-pill ${item.exists ? "available" : "missing"}` }, item.exists ? "Present" : "Missing"))))) : runItems.length ? /* @__PURE__ */ React.createElement(EmptyState, { title: "No artifact detail yet", body: "Select a run with local artifacts to review its inventory." }) : null), /* @__PURE__ */ React.createElement("section", { className: "operations-subpanel section-stack operations-retention-column" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, "Retention boundary"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "Preview the deletion set before you confirm cleanup so removal never feels bundled into another control surface."))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Keep newest run directories"), /* @__PURE__ */ React.createElement("input", { type: "number", min: 1, step: 1, inputMode: "numeric", value: cleanupKeep, onChange: (event) => setCleanupKeep(event.target.value) })), /* @__PURE__ */ React.createElement("div", { className: "operations-keyline-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Current target"), /* @__PURE__ */ React.createElement("strong", null, selectedArtifactRun || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Preview removals"), /* @__PURE__ */ React.createElement("strong", null, cleanupPreview?.count ?? 0))), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => void previewCleanup(), disabled: Boolean(busy) || parsedCleanupKeep == null }, busy === "Previewing cleanup" ? busy : "Preview cleanup"), /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => void runCleanup(), disabled: Boolean(busy) || parsedCleanupKeep == null || !cleanupPreview?.count }, busy === "Cleaning artifacts" ? busy : "Delete previewed runs"))), /* @__PURE__ */ React.createElement("section", { className: "operations-subpanel section-stack operations-retention-column" }, cleanupPreview ? /* @__PURE__ */ React.createElement("article", { className: "operations-retention-preview" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, "Cleanup preview"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, cleanupPreview.count || 0, " run directories would be removed while keeping the newest ", cleanupPreview.keep, "."))), /* @__PURE__ */ React.createElement("div", { className: "operations-retention-scroll" }, /* @__PURE__ */ React.createElement("ul", { className: "guidance-list compact-list" }, (cleanupPreview.items || []).map((item) => /* @__PURE__ */ React.createElement("li", { key: item.run_id }, item.run_id))))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No cleanup preview yet", body: "Preview retention first so deletion stays explicit." })))
    )));
  }
  function AdvancedPage() {
    const cards = [
      {
        title: "Validation and corpora",
        status: "advanced",
        body: "Validation suites, corpora preparation, and release-gate validation remain advanced lanes with explicit safety and runtime rules.",
        emphasis: "Explicit validation before execution",
        detail: "Keep these lanes visible for advanced operators, but collapse the operational burden until a user intentionally enters the workflow."
      },
      {
        title: "Benchmark and stress",
        status: "advanced",
        body: "Benchmark compare, cache, and stress flows need heavier validation and should not be mistaken for first-success paths.",
        emphasis: "Heavier runtime and review cost",
        detail: "This lane belongs behind clear readiness language so performance and stress work do not read like default day-one controls."
      },
      {
        title: "Performance and competition",
        status: "experimental",
        body: "Performance budgets and competition dry-runs are visible here so advanced users can see the lane without overselling it to newcomers.",
        emphasis: "Visible, but not newcomer default",
        detail: "Expose the capability honestly with status labels, then use calm disclosure for the surrounding context instead of keeping the whole lane expanded."
      }
    ];
    const advancedStats = [
      { label: "Visible lanes", value: cards.length, detail: "kept in view" },
      { label: "Default posture", value: "guided", detail: "not first-success" },
      { label: "Safety labels", value: "explicit", detail: "readiness stays honest" },
      { label: "Release frame", value: "0.8.8", detail: "stabilization + hardening" }
    ];
    const advancedFocusItems = [
      {
        label: "Visible",
        title: "Keep advanced lanes in plain sight",
        detail: "Capabilities remain discoverable so experienced operators do not need to hunt through secondary chrome."
      },
      {
        label: "Honest",
        title: "Lead with readiness and safety labels",
        detail: "Advanced and experimental posture stays explicit before any deeper lane detail opens up."
      },
      {
        label: "Calm",
        title: "Use disclosure instead of permanent warning walls",
        detail: "Context waits behind deliberate expansion, keeping the route distinct without overstating danger."
      }
    ];
    return /* @__PURE__ */ React.createElement("main", { className: "page-grid advanced-shell operations-route" }, /* @__PURE__ */ React.createElement("section", { className: "panel hero-panel operations-hero" }, /* @__PURE__ */ React.createElement("div", { className: "operations-hero-grid" }, /* @__PURE__ */ React.createElement("div", { className: "operations-hero-copy" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Advanced"), /* @__PURE__ */ React.createElement("h2", null, "Visible advanced lanes with calm disclosure and honest status labels"), /* @__PURE__ */ React.createElement("p", { className: "section-copy" }, "The product should not hide advanced capabilities, but it also should not present them as newcomer defaults.")), /* @__PURE__ */ React.createElement("div", { className: "operations-hero-side" }, /* @__PURE__ */ React.createElement("article", { className: "operations-trust-card" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Default stance"), /* @__PURE__ */ React.createElement("strong", null, "Advanced capability remains visible, while surrounding detail waits behind deliberate disclosure."), /* @__PURE__ */ React.createElement("p", null, "Keep readiness, safety, and release framing close so users can see what exists without mistaking these lanes for the main entry path."), /* @__PURE__ */ React.createElement("div", { className: "operations-pill-row" }, /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Explicit readiness"), /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Visible, not default"), /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Calm disclosure"))), /* @__PURE__ */ React.createElement("div", { className: "operations-stat-grid" }, advancedStats.map((metric) => /* @__PURE__ */ React.createElement("article", { key: metric.label, className: "operations-stat-card" }, /* @__PURE__ */ React.createElement("span", null, metric.label), /* @__PURE__ */ React.createElement("strong", null, metric.value), /* @__PURE__ */ React.createElement("small", null, metric.detail))))))), /* @__PURE__ */ React.createElement(
      RouteIdentityPanel,
      {
        className: "advanced-identity-panel",
        eyebrow: "Advanced posture",
        title: "Visible lanes, honest labels, calmer defaults",
        summary: "Advanced remains explicit and reachable, but the route now leans on posture and disclosure instead of always-expanded context.",
        items: advancedFocusItems
      }
    ), /* @__PURE__ */ React.createElement("section", { className: "split-grid operations-lead-grid" }, /* @__PURE__ */ React.createElement("article", { className: "panel section-stack operations-form-panel" }, /* @__PURE__ */ React.createElement("div", { className: "operations-section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Lane catalog"), /* @__PURE__ */ React.createElement("h3", null, "Advanced capabilities stay visible"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "Each lane remains discoverable, but the heavier context opens only when an operator intentionally drills in.")), /* @__PURE__ */ React.createElement("div", { className: "operations-pill-row" }, /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "No hidden lanes"), /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Scoped disclosure"))), /* @__PURE__ */ React.createElement("div", { className: "operations-lane-list" }, cards.map((card) => /* @__PURE__ */ React.createElement(
      DensityDisclosure,
      {
        key: card.title,
        className: "operations-subpanel section-stack",
        title: `${card.title} \xB7 ${card.status === "experimental" ? "Experimental" : "Advanced"}`,
        detail: card.body
      },
      /* @__PURE__ */ React.createElement("div", { className: "operations-keyline-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Status"), /* @__PURE__ */ React.createElement("strong", null, card.status)), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Why disclosed"), /* @__PURE__ */ React.createElement("strong", null, card.emphasis))),
      /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, card.detail)
    )))), /* @__PURE__ */ React.createElement("article", { className: "panel section-stack operations-summary-panel" }, /* @__PURE__ */ React.createElement("div", { className: "operations-section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Route posture"), /* @__PURE__ */ React.createElement("h3", null, "Advanced without permanent clutter"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "Keep the page structurally separate from day-one routes by foregrounding posture, labels, and release framing before control density.")), /* @__PURE__ */ React.createElement("span", { className: "shell-trust-pill" }, "Not newcomer default")), /* @__PURE__ */ React.createElement("div", { className: "operations-keyline-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Primary audience"), /* @__PURE__ */ React.createElement("strong", null, "operators who already know the lane")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Interaction model"), /* @__PURE__ */ React.createElement("strong", null, "inspect first, expand deliberately")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", null, "Product promise"), /* @__PURE__ */ React.createElement("strong", null, "deterministic stabilization and hardening, not new feature families"))), /* @__PURE__ */ React.createElement("div", { className: "operations-card-grid advanced-card-grid" }, /* @__PURE__ */ React.createElement("article", { className: "advanced-note-card" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Visibility"), /* @__PURE__ */ React.createElement("strong", null, "Capabilities remain findable"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "The route shows advanced work plainly instead of hiding it behind secondary navigation.")), /* @__PURE__ */ React.createElement("article", { className: "advanced-note-card" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Separation"), /* @__PURE__ */ React.createElement("strong", null, "Status labels do the sorting"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "Advanced and experimental posture stays legible through cards, spacing, and labels rather than dense warning chrome.")), /* @__PURE__ */ React.createElement("article", { className: "advanced-note-card" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Release trust"), /* @__PURE__ */ React.createElement("strong", null, "0.8.8 stays deterministic stabilization work"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "This route clarifies existing lanes while keeping the broader product framing local, calm, and truthful."))))));
  }
  function RunsPage({ route, navigate }) {
    const params = useMemo(() => new URLSearchParams(route.search), [route.search]);
    const resource = useJsonResource(`${bootstrap.api_root}/runs${route.search ? `?${route.search}` : ""}`, [route.search]);
    const [query, setQuery] = useState(params.get("q") || "");
    const [status, setStatus] = useState(params.get("status") || "");
    const [provider, setProvider] = useState(params.get("provider") || "");
    const analytics = resource.data?.analytics || {};
    const summaryCards = resource.data?.summary_cards || [];
    const calibrationBins = analytics.calibration_curve || [];
    const uncertaintyBins = analytics.uncertainty_distribution || [];
    const workflowScoreRows = analytics.workflow_scores || [];
    const versionScoreRows = analytics.version_scores || [];
    const scoreHistoryRows = analytics.score_history || [];
    const runItems = resource.data?.items || [];
    const leadRun = runItems[0] || null;
    const recentRuns = runItems.slice(1, 4);
    const reportReadyCount = runItems.filter((run) => Boolean(run.observatory?.report_available)).length;
    const observatoryBasePath = observatoryRouteFamily(route.path);
    const statusOptions = useMemo(() => {
      const values = new Set(runItems.map((run) => String(run.status || "").trim()).filter(Boolean));
      if (status) values.add(status);
      return Array.from(values).sort((left, right) => left.localeCompare(right));
    }, [runItems, status]);
    const providerOptions = useMemo(() => {
      const values = new Set(runItems.map((run) => String(run.provider || "").trim()).filter(Boolean));
      if (provider) values.add(provider);
      return Array.from(values).sort((left, right) => left.localeCompare(right));
    }, [provider, runItems]);
    const leadRunInspectHref = observatoryUiHref(
      route.path,
      leadRun?.observatory?.inspect_href || (leadRun?.run_id ? `/runs/${leadRun.run_id}` : "")
    );
    const leadRunReportHref = leadRun?.run_id ? `/runs/${leadRun.run_id}/report` : "";
    const hasActiveFilters = Boolean(query || status || provider);
    const leadRunFacts = [
      leadRun?.updated_at ? `Updated ${leadRun.updated_at}` : null,
      leadRun?.observatory?.version_label ? `Version ${leadRun.observatory.version_label}` : null,
      leadRun?.observatory?.score_label != null ? `Lead score ${formatValue(leadRun.observatory.score_label)}` : null
    ].filter(Boolean);
    const controlStats = [
      { label: "Runs", value: formatValue(analytics.summary?.run_count ?? runItems.length) },
      { label: "Resolved", value: formatValue(analytics.summary?.resolved_score_rows ?? analytics.resolved_rows ?? 0) },
      { label: "Reports", value: formatValue(reportReadyCount) }
    ];
    const trustFacts = [
      { label: "Resolved", value: formatValue(analytics.summary?.resolved_score_rows ?? analytics.resolved_rows ?? 0) },
      { label: "Forecasts", value: formatValue(analytics.forecast_rows || 0) },
      { label: "ECE", value: analytics.summary?.ece != null ? formatValue(analytics.summary.ece) : "\u2014" },
      { label: "Log score", value: analytics.summary?.log_score != null ? formatValue(analytics.summary.log_score) : "\u2014" }
    ];
    const leadTrustFacts = trustFacts.slice(0, 2);
    const scoreTrustFacts = trustFacts.slice(2);
    const filterSummary = hasActiveFilters ? [
      query ? `Search: ${query}` : null,
      status ? `Status: ${status}` : null,
      provider ? `Provider: ${provider}` : null
    ].filter(Boolean).join(" \u2022 ") : "Search, status, and provider stay available when you need a narrower slice.";
    useEffect(() => {
      setQuery(params.get("q") || "");
      setStatus(params.get("status") || "");
      setProvider(params.get("provider") || "");
    }, [params]);
    return /* @__PURE__ */ React.createElement("main", { className: "page-grid observatory-page" }, /* @__PURE__ */ React.createElement("section", { className: "observatory-lead-grid" }, /* @__PURE__ */ React.createElement("section", { className: "panel observatory-control-panel" }, /* @__PURE__ */ React.createElement("div", { className: "section-header observatory-control-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Observatory"), /* @__PURE__ */ React.createElement("h2", null, resource.data?.surface?.title || "Observatory run inspector"), /* @__PURE__ */ React.createElement("p", null, "Filter recent runs, check calibration, and jump into trusted analysis without leaving the overview.")), /* @__PURE__ */ React.createElement("dl", { className: "observatory-control-stats" }, controlStats.map((stat) => /* @__PURE__ */ React.createElement("div", { key: stat.label }, /* @__PURE__ */ React.createElement("dt", null, stat.label), /* @__PURE__ */ React.createElement("dd", null, stat.value))))), /* @__PURE__ */ React.createElement(
      DensityDisclosure,
      {
        className: "observatory-filter-disclosure",
        title: hasActiveFilters ? "Filters applied" : "Filter runs",
        detail: filterSummary,
        defaultOpen: hasActiveFilters
      },
      /* @__PURE__ */ React.createElement(
        "form",
        {
          className: "observatory-filter-row",
          onSubmit: (event) => {
            event.preventDefault();
            const next = new URLSearchParams();
            if (query) next.set("q", query);
            if (status) next.set("status", status);
            if (provider) next.set("provider", provider);
            navigate(next.toString() ? observatoryUiHref(route.path, `/runs?${next.toString()}`) : observatoryBasePath);
          }
        },
        /* @__PURE__ */ React.createElement("label", { className: "observatory-filter-field" }, /* @__PURE__ */ React.createElement("span", null, "Search"), /* @__PURE__ */ React.createElement("input", { placeholder: "Run or workflow", value: query, onChange: (event) => setQuery(event.target.value) })),
        /* @__PURE__ */ React.createElement("label", { className: "observatory-filter-field" }, /* @__PURE__ */ React.createElement("span", null, "Status"), /* @__PURE__ */ React.createElement("select", { value: status, onChange: (event) => setStatus(event.target.value) }, /* @__PURE__ */ React.createElement("option", { value: "" }, "Any status"), statusOptions.map((value) => /* @__PURE__ */ React.createElement("option", { key: value, value }, value)))),
        /* @__PURE__ */ React.createElement("label", { className: "observatory-filter-field" }, /* @__PURE__ */ React.createElement("span", null, "Provider"), /* @__PURE__ */ React.createElement("select", { value: provider, onChange: (event) => setProvider(event.target.value) }, /* @__PURE__ */ React.createElement("option", { value: "" }, "Any provider"), providerOptions.map((value) => /* @__PURE__ */ React.createElement("option", { key: value, value }, value)))),
        /* @__PURE__ */ React.createElement("button", { className: "secondary-button", type: "submit" }, "Apply")
      )
    ), /* @__PURE__ */ React.createElement("section", { className: "observatory-run-focus" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Run analysis"), /* @__PURE__ */ React.createElement("h3", null, leadRun?.observatory?.label || "Open the latest run"), /* @__PURE__ */ React.createElement("p", null, leadRun?.observatory?.summary || "Recent run shortcuts appear here once Observatory has indexed local history.")), leadRun?.status ? /* @__PURE__ */ React.createElement(StatusPill, { value: String(leadRun.status) }) : null), leadRunFacts.length ? /* @__PURE__ */ React.createElement("div", { className: "meta-row observatory-run-focus-meta" }, leadRunFacts.map((fact) => /* @__PURE__ */ React.createElement("span", { key: fact }, fact))) : null, /* @__PURE__ */ React.createElement("div", { className: "button-row observatory-run-focus-actions" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        className: "primary-button",
        type: "button",
        disabled: !leadRunInspectHref,
        onClick: () => leadRunInspectHref && navigate(leadRunInspectHref)
      },
      "Inspect latest run"
    ), leadRun?.observatory?.report_available ? /* @__PURE__ */ React.createElement("a", { className: "secondary-link", href: leadRunReportHref, target: "_blank", rel: "noreferrer" }, "Open report") : null), recentRuns.length ? /* @__PURE__ */ React.createElement(
      DensityDisclosure,
      {
        className: "observatory-quick-runs-disclosure",
        title: `Recent shortcuts \xB7 ${recentRuns.length}`,
        detail: "Adjacent runs stay nearby, but collapsed until you want to branch from the lead run."
      },
      /* @__PURE__ */ React.createElement("div", { className: "observatory-quick-runs" }, /* @__PURE__ */ React.createElement("div", { className: "observatory-quick-run-list" }, recentRuns.map((run) => /* @__PURE__ */ React.createElement(
        "button",
        {
          key: String(run.run_id),
          className: "observatory-quick-run",
          type: "button",
          onClick: () => navigate(observatoryUiHref(route.path, run.observatory?.inspect_href || `/runs/${run.run_id}`))
        },
        /* @__PURE__ */ React.createElement("span", { className: "observatory-quick-run-label" }, "Run shortcut"),
        /* @__PURE__ */ React.createElement("span", { className: "table-primary clamp-2", title: String(run.observatory?.label || run.run_id) }, run.observatory?.label || run.run_id),
        /* @__PURE__ */ React.createElement("span", { className: "table-secondary", title: String(run.run_id) }, "Run ID \xB7 ", run.run_id)
      ))))
    ) : null)), /* @__PURE__ */ React.createElement("article", { className: "panel chart-panel observatory-primary-panel" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Calibration Curve"), /* @__PURE__ */ React.createElement("h3", null, "Calibration at a glance"), /* @__PURE__ */ React.createElement("p", null, "See whether forecast confidence tracks observed outcomes before opening a run.")), /* @__PURE__ */ React.createElement("div", { className: "observatory-primary-meta" }, /* @__PURE__ */ React.createElement("span", null, formatValue(analytics.forecast_rows || 0), " forecasts"), /* @__PURE__ */ React.createElement("span", null, analytics.resolved_rows ? `${formatValue(analytics.resolved_rows)} resolved` : "Awaiting outcomes"))), /* @__PURE__ */ React.createElement("div", { className: "observatory-primary-shell" }, /* @__PURE__ */ React.createElement(CalibrationCurveChart, { bins: calibrationBins }), /* @__PURE__ */ React.createElement("aside", { className: "observatory-primary-summary" }, /* @__PURE__ */ React.createElement("div", { className: "brier-summary-card observatory-brier-card" }, /* @__PURE__ */ React.createElement("span", null, "Brier"), /* @__PURE__ */ React.createElement("strong", null, analytics.summary?.brier != null ? formatValue(analytics.summary.brier) : "No score yet"), /* @__PURE__ */ React.createElement("em", null, analytics.resolved_rows ? "Resolved evidence available" : "Needs resolved rows")), /* @__PURE__ */ React.createElement("dl", { className: "observatory-trust-facts observatory-trust-facts-primary" }, leadTrustFacts.map((fact) => /* @__PURE__ */ React.createElement("div", { key: fact.label }, /* @__PURE__ */ React.createElement("dt", null, fact.label), /* @__PURE__ */ React.createElement("dd", null, fact.value)))), scoreTrustFacts.length ? /* @__PURE__ */ React.createElement(
      DensityDisclosure,
      {
        className: "observatory-score-detail-disclosure",
        title: "Scoring detail",
        detail: "ECE and log score stay nearby without expanding the lead trust stack."
      },
      /* @__PURE__ */ React.createElement("dl", { className: "observatory-trust-facts observatory-trust-facts-secondary" }, scoreTrustFacts.map((fact) => /* @__PURE__ */ React.createElement("div", { key: fact.label }, /* @__PURE__ */ React.createElement("dt", null, fact.label), /* @__PURE__ */ React.createElement("dd", null, fact.value))))
    ) : null, /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "Keep trust metrics compact here, then open a run for row-level evidence, reports, and comparisons."))))), resource.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Runs unavailable", body: resource.error }) : null, resource.loading ? /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading runs" }) : null, /* @__PURE__ */ React.createElement("section", { className: "panel section-stack observatory-run-table" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Runs"), /* @__PURE__ */ React.createElement("h3", null, "Recent runs"), /* @__PURE__ */ React.createElement("p", null, "Open a run to inspect artifacts, compare reports, or continue analysis immediately.")), /* @__PURE__ */ React.createElement("span", { className: "section-count" }, formatValue(runItems.length), " shown")), runItems.length ? /* @__PURE__ */ React.createElement("div", { className: "table-wrap observatory-run-table-wrap" }, /* @__PURE__ */ React.createElement("table", { className: "data-table" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", null, /* @__PURE__ */ React.createElement("th", null, "Run"), /* @__PURE__ */ React.createElement("th", null, "Workflow"), /* @__PURE__ */ React.createElement("th", null, "Version"), /* @__PURE__ */ React.createElement("th", null, "Status"), /* @__PURE__ */ React.createElement("th", null, "Provider"), /* @__PURE__ */ React.createElement("th", null, "Updated"))), /* @__PURE__ */ React.createElement("tbody", null, runItems.map((run) => /* @__PURE__ */ React.createElement("tr", { key: run.run_id }, /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement("a", { href: observatoryUiHref(route.path, `/runs/${run.run_id}`), onClick: (event) => {
      event.preventDefault();
      navigate(observatoryUiHref(route.path, `/runs/${run.run_id}`));
    } }, run.run_id)), /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement("div", { className: "table-primary" }, run.observatory?.label || run.workflow?.title || run.workflow?.name || "Unknown workflow"), /* @__PURE__ */ React.createElement("div", { className: "table-secondary" }, run.observatory?.summary || run.workflow?.name || "\u2014")), /* @__PURE__ */ React.createElement("td", null, run.observatory?.version_label || "\u2014"), /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement(StatusPill, { value: run.status })), /* @__PURE__ */ React.createElement("td", null, run.provider), /* @__PURE__ */ React.createElement("td", null, run.updated_at || "\u2014")))))) : null, !resource.loading && !runItems.length ? /* @__PURE__ */ React.createElement(
      EmptyState,
      {
        title: resource.data?.empty_state?.title || "No runs match the current filter",
        body: resource.data?.empty_state?.body || "Clear filters or start a deterministic workflow to create a run for inspection."
      }
    ) : null), /* @__PURE__ */ React.createElement(
      DensityDisclosure,
      {
        className: "panel section-stack observatory-disclosure",
        title: "Secondary analytics",
        detail: "Open the broader run mix, probability spread, and score rollups after the main trust and run-access view."
      },
      summaryCards.length ? /* @__PURE__ */ React.createElement("section", { className: "section-stack observatory-summary-section" }, /* @__PURE__ */ React.createElement("div", { className: "stats-grid observatory-summary-grid" }, summaryCards.map((card) => /* @__PURE__ */ React.createElement(MetricCard, { key: card.label, label: card.label, value: card.value })))) : null,
      /* @__PURE__ */ React.createElement("section", { className: "observatory-dashboard" }, /* @__PURE__ */ React.createElement("article", { className: "panel chart-panel uncertainty-panel observatory-secondary-panel" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Probability spread"), /* @__PURE__ */ React.createElement("h3", null, "Where historic forecasts cluster"), /* @__PURE__ */ React.createElement("p", null, "Use the band view after calibration to spot where certainty stacks up.")), /* @__PURE__ */ React.createElement("span", { className: "section-count" }, formatValue(analytics.forecast_rows || 0), " rows")), /* @__PURE__ */ React.createElement(UncertaintyHistogram, { bins: uncertaintyBins })), /* @__PURE__ */ React.createElement("article", { className: "panel chart-panel observatory-secondary-panel observatory-history-panel" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Trend"), /* @__PURE__ */ React.createElement("h3", null, "Brier score over recent runs"), /* @__PURE__ */ React.createElement("p", null, "Keep the score trend nearby without crowding the main trust surface.")), /* @__PURE__ */ React.createElement("span", { className: "section-count" }, scoreHistoryRows.length, " scored runs")), /* @__PURE__ */ React.createElement(ScoreHistoryChart, { rows: scoreHistoryRows }))),
      /* @__PURE__ */ React.createElement("section", { className: "split-grid observatory-score-grid" }, /* @__PURE__ */ React.createElement("article", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Workflow scores"), /* @__PURE__ */ React.createElement("h3", null, "Workflow rollup"), /* @__PURE__ */ React.createElement("p", null, "Compare scored runs by workflow after scanning the lead trust view."))), /* @__PURE__ */ React.createElement(WorkflowScoreTable, { rows: workflowScoreRows, navigate })), /* @__PURE__ */ React.createElement("article", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Version scores"), /* @__PURE__ */ React.createElement("h3", null, "Saved snapshot rollup"), /* @__PURE__ */ React.createElement("p", null, "Inspect version performance without pulling more tables into the lead area."))), /* @__PURE__ */ React.createElement(VersionScoreTable, { rows: versionScoreRows, navigate, routePath: route.path })))
    ));
  }
  function CalibrationCurveChart({ bins }) {
    const plotted = bins.filter((bin) => typeof bin.mean_probability === "number" && typeof bin.observed_frequency === "number");
    const points = plotted.map((bin) => `${Math.max(0, Math.min(1, Number(bin.mean_probability))) * 100},${100 - Math.max(0, Math.min(1, Number(bin.observed_frequency))) * 100}`).join(" ");
    const summary = plotted.length ? `${plotted.length} calibration bins. ${plotted.map((bin) => `${bin.label || "bin"} mean ${formatProbability(bin.mean_probability)}, observed ${formatProbability(bin.observed_frequency)}`).join(". ")}.` : "Resolved forecast rows are required before the calibration curve can be drawn.";
    return /* @__PURE__ */ React.createElement("div", { className: "calibration-chart", role: "img", "aria-label": "Calibration curve", "aria-describedby": "calibration-chart-summary" }, /* @__PURE__ */ React.createElement("svg", { viewBox: "0 0 100 100", preserveAspectRatio: "none", "aria-hidden": "true" }, /* @__PURE__ */ React.createElement("line", { className: "chart-grid-line", x1: "0", y1: "100", x2: "100", y2: "0" }), points ? /* @__PURE__ */ React.createElement("polyline", { className: "calibration-line primary", points }) : null, plotted.map((bin) => /* @__PURE__ */ React.createElement(
      "circle",
      {
        key: String(bin.label),
        className: "calibration-dot",
        cx: Math.max(0, Math.min(1, Number(bin.mean_probability))) * 100,
        cy: 100 - Math.max(0, Math.min(1, Number(bin.observed_frequency))) * 100,
        r: "1.8"
      }
    ))), /* @__PURE__ */ React.createElement("div", { className: "chart-axis x-axis", "aria-hidden": "true" }, "Forecasted Probability"), /* @__PURE__ */ React.createElement("div", { className: "chart-axis y-axis", "aria-hidden": "true" }, "Observed Frequency"), /* @__PURE__ */ React.createElement("p", { id: "calibration-chart-summary", className: "sr-only" }, summary), !plotted.length ? /* @__PURE__ */ React.createElement(EmptyState, { title: "Calibration pending", body: "Resolved forecast rows are required before the curve can be drawn." }) : null);
  }
  function UncertaintyHistogram({ bins }) {
    const maxCount = Math.max(1, ...bins.map((bin) => Number(bin.count || 0)));
    const summary = bins.length ? `${bins.length} uncertainty bands. ${bins.map((bin) => `${bin.label || "band"} forecast count ${formatValue(bin.count || 0)}, observed true ${formatValue(bin.observed_true || 0)}`).join(". ")}.` : "No forecast rows are available for the uncertainty histogram yet.";
    return /* @__PURE__ */ React.createElement("div", { className: "histogram-chart", role: "img", "aria-label": "Uncertainty distribution", "aria-describedby": "uncertainty-chart-summary" }, bins.map((bin) => {
      const height = Math.max(4, Number(bin.count || 0) / maxCount * 100);
      return /* @__PURE__ */ React.createElement("div", { key: String(bin.label), className: "histogram-bin" }, /* @__PURE__ */ React.createElement("span", { className: "histogram-bar forecast", style: { height: `${height}%` } }), /* @__PURE__ */ React.createElement("span", { className: "histogram-bar observed", style: { height: `${Math.max(3, Number(bin.observed_true || 0) / maxCount * 100)}%` } }), /* @__PURE__ */ React.createElement("small", null, String(bin.label || "").replace("-100%", "%")));
    }), /* @__PURE__ */ React.createElement("p", { id: "uncertainty-chart-summary", className: "sr-only" }, summary));
  }
  function WorkflowScoreTable({ rows, navigate }) {
    if (!rows.length) {
      return /* @__PURE__ */ React.createElement(EmptyState, { title: "No workflow scores yet", body: "Run workflows with scoring artifacts to populate score history." });
    }
    return /* @__PURE__ */ React.createElement("div", { className: "table-wrap score-table-wrap" }, /* @__PURE__ */ React.createElement("table", { className: "data-table" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", null, /* @__PURE__ */ React.createElement("th", null, "Workflow"), /* @__PURE__ */ React.createElement("th", null, "Runs"), /* @__PURE__ */ React.createElement("th", null, "Brier"), /* @__PURE__ */ React.createElement("th", null, "ECE"), /* @__PURE__ */ React.createElement("th", null, "Scoring rule"))), /* @__PURE__ */ React.createElement("tbody", null, rows.map((row) => /* @__PURE__ */ React.createElement("tr", { key: String(row.workflow) }, /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement("button", { className: "table-link-button", onClick: () => navigate(`/studio?workflow=${encodeURIComponent(String(row.workflow))}`) }, row.label || row.workflow)), /* @__PURE__ */ React.createElement("td", null, formatValue(row.runs)), /* @__PURE__ */ React.createElement("td", null, formatValue(row.brier)), /* @__PURE__ */ React.createElement("td", null, formatValue(row.ece)), /* @__PURE__ */ React.createElement("td", null, row.status || "insufficient evidence"))))));
  }
  function VersionScoreTable({
    rows,
    navigate,
    routePath
  }) {
    if (!rows.length) {
      return /* @__PURE__ */ React.createElement(EmptyState, { title: "No version scores yet", body: "Run saved version snapshots or version-backed batches to populate version history." });
    }
    return /* @__PURE__ */ React.createElement("div", { className: "table-wrap score-table-wrap" }, /* @__PURE__ */ React.createElement("table", { className: "data-table" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", null, /* @__PURE__ */ React.createElement("th", null, "Version"), /* @__PURE__ */ React.createElement("th", null, "Workflow"), /* @__PURE__ */ React.createElement("th", null, "Runs"), /* @__PURE__ */ React.createElement("th", null, "Brier"), /* @__PURE__ */ React.createElement("th", null, "ECE"))), /* @__PURE__ */ React.createElement("tbody", null, rows.map((row) => /* @__PURE__ */ React.createElement("tr", { key: String(row.version_id) }, /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement("button", { className: "table-link-button", onClick: () => navigate(observatoryUiHref(routePath, `/runs?q=${encodeURIComponent(String(row.version_id))}`)) }, row.label || row.version_id)), /* @__PURE__ */ React.createElement("td", null, row.workflow_name || "\u2014"), /* @__PURE__ */ React.createElement("td", null, formatValue(row.runs)), /* @__PURE__ */ React.createElement("td", null, formatValue(row.brier)), /* @__PURE__ */ React.createElement("td", null, formatValue(row.ece)))))));
  }
  function ScoreHistoryChart({ rows }) {
    const plotted = rows.filter((row) => typeof row.brier === "number");
    if (!plotted.length) {
      return /* @__PURE__ */ React.createElement(EmptyState, { title: "No score trend yet", body: "Resolved runs with scoring artifacts are required before score history can be plotted." });
    }
    const points = plotted.map((row, index) => {
      const x = plotted.length === 1 ? 50 : index / (plotted.length - 1) * 100;
      const y = 100 - Math.max(0, Math.min(1, Number(row.brier))) * 100;
      return `${x},${y}`;
    }).join(" ");
    const summary = `${plotted.length} scored runs. ${plotted.map((row) => `${row.label || row.workflow || row.run_id}: Brier ${formatValue(row.brier)}`).join(". ")}.`;
    return /* @__PURE__ */ React.createElement("div", { className: "score-history-chart", role: "img", "aria-label": "Brier score history", "aria-describedby": "score-history-summary" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("strong", null, "Brier score history"), /* @__PURE__ */ React.createElement("span", { className: "helper-text" }, plotted.length, " scored runs")), /* @__PURE__ */ React.createElement("svg", { viewBox: "0 0 100 100", preserveAspectRatio: "none", "aria-hidden": "true" }, /* @__PURE__ */ React.createElement("line", { className: "chart-grid-line", x1: "0", y1: "50", x2: "100", y2: "50" }), /* @__PURE__ */ React.createElement("polyline", { className: "calibration-line primary", points }), plotted.map((row, index) => {
      const x = plotted.length === 1 ? 50 : index / (plotted.length - 1) * 100;
      const y = 100 - Math.max(0, Math.min(1, Number(row.brier))) * 100;
      return /* @__PURE__ */ React.createElement("circle", { key: String(row.run_id), className: "calibration-dot", cx: x, cy: y, r: "1.8" });
    })), /* @__PURE__ */ React.createElement("div", { className: "score-history-labels" }, plotted.map((row) => /* @__PURE__ */ React.createElement("div", { key: String(row.run_id) }, /* @__PURE__ */ React.createElement("strong", null, formatValue(row.brier)), /* @__PURE__ */ React.createElement("span", null, row.label || row.workflow || row.run_id)))), /* @__PURE__ */ React.createElement("p", { id: "score-history-summary", className: "sr-only" }, summary));
  }
  function RunDetailPage({
    routePath,
    runId,
    navigate,
    onMutate
  }) {
    const resource = useJsonResource(`${bootstrap.api_root}/runs/${runId}`, [runId]);
    const [busy, setBusy] = useState(null);
    const [notice, setNotice] = useState(null);
    const navigateWithinObservatory = (target) => navigate(observatoryUiHref(routePath, target));
    async function generateReport() {
      setBusy("Generating report");
      setNotice(null);
      try {
        const result = await requestJson(`${bootstrap.api_root}/runs/${runId}/report`, {
          method: "POST",
          body: JSON.stringify({})
        });
        resource.reload();
        onMutate();
        setNotice({ tone: "success", title: "Report ready", body: "The HTML report was regenerated and is ready to open." });
        window.open(result.href, "_blank", "noopener");
      } catch (error) {
        setNotice(buildActionErrorNotice("report", error));
      } finally {
        setBusy(null);
      }
    }
    if (resource.error) {
      return /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Run detail unavailable", body: resource.error });
    }
    if (resource.loading || !resource.data) {
      return /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading run detail" });
    }
    const run = resource.data;
    const report = run.artifacts?.report || {};
    return /* @__PURE__ */ React.createElement("main", { className: "page-grid detail-shell" }, notice ? /* @__PURE__ */ React.createElement(Message, { tone: notice.tone, title: notice.title, body: notice.body }) : null, /* @__PURE__ */ React.createElement("section", { className: "panel hero-panel detail-hero" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Observatory / Run inspector"), /* @__PURE__ */ React.createElement("h2", null, run.hero?.title || run.workflow?.title || run.run_id), /* @__PURE__ */ React.createElement("p", null, run.hero?.summary || run.observatory?.summary || "Inspect the latest run summary, question rows, trace, and artifacts."), /* @__PURE__ */ React.createElement("div", { className: "meta-row" }, /* @__PURE__ */ React.createElement(StatusPill, { value: run.run?.status }), /* @__PURE__ */ React.createElement("span", null, run.run?.provider || "Unknown provider"), /* @__PURE__ */ React.createElement("span", null, run.run?.updated_at || run.run?.completed_at || "\u2014")), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => navigateWithinObservatory(run.observatory?.runs_href || "/runs") }, "Back to Observatory"), run.recommended_compare ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigateWithinObservatory(run.recommended_compare.href) }, "Compare with ", run.recommended_compare.run_id) : null, report.available ? /* @__PURE__ */ React.createElement("a", { className: "secondary-link", href: report.href, target: "_blank", rel: "noreferrer" }, report.open_label || "Open HTML report") : null)), /* @__PURE__ */ React.createElement("section", { className: "stats-grid" }, (run.summary_cards || []).map((card) => /* @__PURE__ */ React.createElement(MetricCard, { key: card.label, label: card.label, value: card.value }))), /* @__PURE__ */ React.createElement("div", { className: "detail-grid" }, /* @__PURE__ */ React.createElement("div", { className: "detail-main" }, /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Readable summary"), /* @__PURE__ */ React.createElement("p", null, "Grouped metadata keeps the run context visible without opening raw JSON."))), /* @__PURE__ */ React.createElement("div", { className: "info-grid" }, (run.metadata_groups || []).map((group) => /* @__PURE__ */ React.createElement(KeyValueGroup, { key: group.title, group })))), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Probability & result summary"), /* @__PURE__ */ React.createElement("p", null, "Forecast probabilities, resolution coverage, and existing run result fields in one Observatory review block."))), (run.probability_summary?.cards || []).length ? /* @__PURE__ */ React.createElement("div", { className: "stats-grid" }, (run.probability_summary?.cards || []).map((card) => /* @__PURE__ */ React.createElement(MetricCard, { key: card.label, label: card.label, value: card.label.toLowerCase().includes("probability") ? formatProbability(card.value) : card.value }))) : null, (run.probability_summary?.groups || []).some((group) => (group.items || []).length) ? /* @__PURE__ */ React.createElement("div", { className: "info-grid" }, (run.probability_summary?.groups || []).filter((group) => (group.items || []).length).map((group) => /* @__PURE__ */ React.createElement(KeyValueGroup, { key: group.title, group }))) : /* @__PURE__ */ React.createElement(EmptyState, { title: run.probability_summary?.empty_state?.title || "No probability rows", body: run.probability_summary?.empty_state?.body || "This run does not include probability rows." })), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Score summary"), /* @__PURE__ */ React.createElement("p", null, "Existing eval/train outputs stay explicit when they are present."))), (run.score_summary?.groups || []).length ? /* @__PURE__ */ React.createElement("div", { className: "info-grid" }, (run.score_summary?.groups || []).map((group) => /* @__PURE__ */ React.createElement(KeyValueGroup, { key: group.title, group }))) : /* @__PURE__ */ React.createElement(EmptyState, { title: run.score_summary?.empty_state?.title || "No score outputs", body: run.score_summary?.empty_state?.body || "This run does not include evaluation or training score fields." })), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Results snapshot"), /* @__PURE__ */ React.createElement("p", null, "Core quality, training, and usage metrics in one place."))), (run.result_groups || []).length ? /* @__PURE__ */ React.createElement("div", { className: "info-grid" }, (run.result_groups || []).map((group) => /* @__PURE__ */ React.createElement(KeyValueGroup, { key: group.title, group }))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No result summary yet", body: "This run does not include evaluation or training summary fields." })), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Forecast table"), /* @__PURE__ */ React.createElement("p", null, "Question titles, forecast values, and scoring context for quick review.")), /* @__PURE__ */ React.createElement("span", { className: "section-count" }, run.forecast_table?.count || 0, " rows")), /* @__PURE__ */ React.createElement(RunForecastTable, { rows: run.forecast_table?.rows || [], emptyState: run.forecast_table?.empty_state }))), /* @__PURE__ */ React.createElement("aside", { className: "detail-sidebar" }, /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Guided actions"), /* @__PURE__ */ React.createElement("p", null, "Jump to the next useful surface from this run."))), /* @__PURE__ */ React.createElement("div", { className: "action-stack" }, (run.guided_actions || []).map((action) => /* @__PURE__ */ React.createElement("button", { key: action.label, className: "secondary-button action-button", onClick: () => navigateWithinObservatory(action.href) }, action.label)))), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Version provenance"), /* @__PURE__ */ React.createElement("p", null, "Keep the exact saved snapshot visible when the run came from Versions or a version-backed batch."))), run.version?.version_id ? /* @__PURE__ */ React.createElement("article", { className: "info-card" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("strong", null, run.version.label || run.version.version_id), /* @__PURE__ */ React.createElement(StatusPill, { value: run.version.source || "version" })), /* @__PURE__ */ React.createElement("dl", { className: "context-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Version ID"), /* @__PURE__ */ React.createElement("dd", null, run.version.version_id)), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Workflow"), /* @__PURE__ */ React.createElement("dd", null, run.version.workflow_name || run.workflow?.name || "\u2014"))), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate("/versions") }, "Open Versions"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigateWithinObservatory(`/runs?q=${encodeURIComponent(String(run.version.version_id))}`) }, "Related runs"))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No saved version linked", body: "This run came from a workflow or surface that did not persist version provenance." })), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Report & artifacts"), /* @__PURE__ */ React.createElement("p", null, "Use the report when available; fall back to raw files when it is not."))), /* @__PURE__ */ React.createElement(ReportCard, { report, onGenerate: generateReport, generating: busy === "Generating report" }), /* @__PURE__ */ React.createElement(ArtifactList, { items: run.artifacts?.items || [] }), (run.artifacts?.exports || []).length ? /* @__PURE__ */ React.createElement("div", { className: "workflow-list export-card-grid" }, (run.artifacts?.exports || []).map((item) => /* @__PURE__ */ React.createElement(ExportCard, { key: String(item.label), item }))) : null, Object.keys(run.artifacts?.raw || {}).length ? /* @__PURE__ */ React.createElement("details", { className: "artifact-preview" }, /* @__PURE__ */ React.createElement("summary", null, "Raw structured payloads"), Object.entries(run.artifacts?.raw || {}).map(([key, value]) => /* @__PURE__ */ React.createElement(ArtifactPreview, { key, label: key, value }))) : null), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Compare next"), /* @__PURE__ */ React.createElement("p", null, "Pick a baseline to understand whether the candidate moved the right metrics."))), (run.baseline_candidates || []).length ? /* @__PURE__ */ React.createElement("div", { className: "action-list" }, (run.baseline_candidates || []).map((item) => /* @__PURE__ */ React.createElement("button", { key: item.run_id, className: "secondary-button action-button", onClick: () => navigateWithinObservatory(item.href) }, item.label || item.run_id))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No comparison candidates", body: "Run another workflow revision to unlock side-by-side comparison." })), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Execution trace"), /* @__PURE__ */ React.createElement("p", null, "Ordered graph trace or sandbox inspection steps where the run persisted them."))), (run.execution_trace?.items || []).length ? /* @__PURE__ */ React.createElement("ul", { className: "timeline-list" }, (run.execution_trace?.items || []).map((item, index) => /* @__PURE__ */ React.createElement("li", { key: `${item.node_id}-${index}` }, /* @__PURE__ */ React.createElement("strong", null, item.order, ". ", item.label || item.node_id), /* @__PURE__ */ React.createElement("span", null, item.node_id, " \xB7 ", item.node_type || "node", " \xB7 ", item.status || "observed"), item.preview ? /* @__PURE__ */ React.createElement("span", { className: "table-secondary" }, item.preview) : null))) : /* @__PURE__ */ React.createElement(EmptyState, { title: run.execution_trace?.empty_state?.title || "No execution trace", body: run.execution_trace?.empty_state?.body || "This run did not persist graph trace rows." })), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Uncertainty"), /* @__PURE__ */ React.createElement("p", null, "Shown only when the artifacts include enough uncertainty or reliability data."))), run.uncertainty_summary?.available ? /* @__PURE__ */ React.createElement("div", { className: "info-grid" }, (run.uncertainty_summary?.groups || []).map((group) => /* @__PURE__ */ React.createElement(KeyValueGroup, { key: group.title, group }))) : /* @__PURE__ */ React.createElement(EmptyState, { title: run.uncertainty_summary?.empty_state?.title || "Uncertainty unavailable", body: run.uncertainty_summary?.empty_state?.body || "No uncertainty fields were present in the current read model." })))));
  }
  function ComparePage({
    routePath,
    candidateRunId,
    baselineRunId,
    navigate
  }) {
    const resource = useJsonResource(`${bootstrap.api_root}/runs/${candidateRunId}/compare/${baselineRunId}`, [candidateRunId, baselineRunId]);
    const navigateWithinObservatory = (target) => navigate(observatoryUiHref(routePath, target));
    if (resource.error) {
      return /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Comparison unavailable", body: resource.error });
    }
    if (resource.loading || !resource.data) {
      return /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading comparison" });
    }
    const compare = resource.data;
    return /* @__PURE__ */ React.createElement("main", { className: "page-grid compare-shell" }, /* @__PURE__ */ React.createElement("section", { className: `panel hero-panel compare-hero ${compare.verdict?.tone || "neutral"}` }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Compare"), /* @__PURE__ */ React.createElement("h2", null, compare.verdict?.headline || compare.verdict?.label || "Comparison ready"), /* @__PURE__ */ React.createElement("p", null, compare.verdict?.summary || "Review grouped metrics and question-level changes before choosing the next step."), /* @__PURE__ */ React.createElement("div", { className: "compare-run-grid" }, /* @__PURE__ */ React.createElement(CompareRunCard, { label: "Candidate", run: compare.run_pair?.candidate }), /* @__PURE__ */ React.createElement(CompareRunCard, { label: "Baseline", run: compare.run_pair?.baseline })), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigateWithinObservatory(`/runs/${candidateRunId}`) }, "Inspect candidate run"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigateWithinObservatory(`/runs/${baselineRunId}`) }, "Inspect baseline run"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate("/workbench") }, "Back to workbench"))), /* @__PURE__ */ React.createElement("section", { className: "stats-grid" }, (compare.summary_cards || []).map((card) => /* @__PURE__ */ React.createElement(MetricCard, { key: card.label, label: card.label, value: card.value }))), /* @__PURE__ */ React.createElement("div", { className: "compare-grid" }, /* @__PURE__ */ React.createElement("div", { className: "compare-main" }, /* @__PURE__ */ React.createElement("section", { className: `panel verdict-panel ${compare.verdict?.tone || "neutral"}` }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Verdict"), /* @__PURE__ */ React.createElement("h3", null, compare.verdict?.label || "No verdict yet"), /* @__PURE__ */ React.createElement("p", null, compare.verdict?.next_step || "Open the run detail pages to continue reviewing."), /* @__PURE__ */ React.createElement("div", { className: "action-list" }, (compare.next_actions || []).map((action) => /* @__PURE__ */ React.createElement("button", { key: action.label, className: "secondary-button action-button", onClick: () => navigateWithinObservatory(action.href) }, /* @__PURE__ */ React.createElement("span", null, action.label), action.description ? /* @__PURE__ */ React.createElement("small", null, action.description) : null)))), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Metric comparison"), /* @__PURE__ */ React.createElement("p", null, "High-level metrics grouped by profile, coverage, efficiency, and quality."))), (compare.row_groups || []).map((group) => /* @__PURE__ */ React.createElement("section", { key: group.title, className: "compare-group" }, /* @__PURE__ */ React.createElement("h4", null, group.title), /* @__PURE__ */ React.createElement("table", { className: "data-table" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", null, /* @__PURE__ */ React.createElement("th", null, "Metric"), /* @__PURE__ */ React.createElement("th", null, "Baseline"), /* @__PURE__ */ React.createElement("th", null, "Candidate"), /* @__PURE__ */ React.createElement("th", null, "Interpretation"))), /* @__PURE__ */ React.createElement("tbody", null, (group.rows || []).map((row) => /* @__PURE__ */ React.createElement("tr", { key: row.metric, className: `tone-${row.tone || "neutral"}` }, /* @__PURE__ */ React.createElement("td", null, row.label || row.metric), /* @__PURE__ */ React.createElement("td", null, formatValue(row.left)), /* @__PURE__ */ React.createElement("td", null, formatValue(row.right)), /* @__PURE__ */ React.createElement("td", null, row.interpretation)))))))), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Question-level changes"), /* @__PURE__ */ React.createElement("p", null, "Question titles stay visible so coverage gaps and score shifts are easy to read."))), /* @__PURE__ */ React.createElement(CompareQuestionTable, { rows: compare.question_rows || [] }))), /* @__PURE__ */ React.createElement("aside", { className: "compare-sidebar" }, /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Report availability"), /* @__PURE__ */ React.createElement("p", null, "Open each run report directly when it exists."))), /* @__PURE__ */ React.createElement(ReportCard, { report: compare.run_pair?.candidate?.report }), /* @__PURE__ */ React.createElement(ReportCard, { report: compare.run_pair?.baseline?.report })))));
  }
  function WorkspaceModeBar({
    mode,
    navigate,
    studioHref,
    playgroundHref
  }) {
    const modeCopy = mode === "studio" ? {
      eyebrow: "Workspace mode",
      title: "Studio authoring",
      detail: "Edit the workflow graph, then switch to Playground to run and inspect it."
    } : {
      eyebrow: "Workspace mode",
      title: "Playground execution",
      detail: "Run a bounded question, inspect the trace, then switch back to Studio to edit."
    };
    return /* @__PURE__ */ React.createElement("div", { className: "workspace-mode-bar" }, /* @__PURE__ */ React.createElement("div", { className: "workspace-mode-copy" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, modeCopy.eyebrow), /* @__PURE__ */ React.createElement("strong", null, modeCopy.title), /* @__PURE__ */ React.createElement("span", null, modeCopy.detail)), /* @__PURE__ */ React.createElement("div", { className: "workspace-mode-toggle", role: "group", "aria-label": "Workspace mode" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        className: mode === "studio" ? "secondary-button active workspace-mode-button" : "secondary-button workspace-mode-button",
        type: "button",
        "aria-current": mode === "studio" ? "page" : void 0,
        onClick: () => navigate(studioHref)
      },
      "Studio"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        className: mode === "playground" ? "secondary-button active workspace-mode-button" : "secondary-button workspace-mode-button",
        type: "button",
        "aria-current": mode === "playground" ? "page" : void 0,
        onClick: () => navigate(playgroundHref)
      },
      "Playground"
    )));
  }
  function WorkspacePanelAdapter({
    frameClassName,
    leftPanel,
    centerPanel,
    rightPanel
  }) {
    return /* @__PURE__ */ React.createElement("div", { className: frameClassName }, leftPanel, centerPanel, rightPanel);
  }
  function WorkspaceModeShell({
    mode,
    navigate,
    studioHref,
    playgroundHref,
    children
  }) {
    return /* @__PURE__ */ React.createElement("section", { className: `workspace-live-shell workspace-mode-${mode}` }, /* @__PURE__ */ React.createElement(WorkspaceModeBar, { mode, navigate, studioHref, playgroundHref }), children);
  }
  function PlaygroundPage({
    route,
    shell,
    navigate,
    onMutate
  }) {
    const params = useMemo(() => new URLSearchParams(route.search), [route.search]);
    const requestedContext = params.get("context") === "template" || params.get("context") === "workflow" ? params.get("context") || "" : "";
    const requestedWorkflow = params.get("workflow") || "";
    const requestedTemplate = params.get("template") || params.get("template_id") || "";
    const resource = useJsonResource(`${bootstrap.api_root}/playground`, []);
    const [contextType, setContextType] = useState("workflow");
    const [workflowName, setWorkflowName] = useState("");
    const [templateId, setTemplateId] = useState("");
    const [questionPrompt, setQuestionPrompt] = useState("");
    const [questionTitle, setQuestionTitle] = useState("");
    const [resolutionCriteria, setResolutionCriteria] = useState("");
    const [selectedStepKey, setSelectedStepKey] = useState("");
    const [busy, setBusy] = useState(null);
    const [notice, setNotice] = useState(null);
    const session = resource.data?.session;
    const catalog = resource.data?.catalog || {};
    const workflows = catalog.workflows || [];
    const templates = catalog.templates || [];
    const contextPreview = resource.data?.context_preview;
    const lastResult = resource.data?.last_result;
    const steps = (lastResult?.inspection_steps || []).filter((step) => typeof step?.node_id === "string");
    const activeStep = steps.find((step) => playgroundStepKey(step) === selectedStepKey) || steps[0] || null;
    const resultTrace = lastResult?.execution_trace || {};
    const orderedTrace = (lastResult?.ordered_node_trace || resultTrace.items || []).filter((step) => typeof step?.node_id === "string");
    const graphTraceArtifact = lastResult?.graph_trace_artifact || {};
    const readyToRun = Boolean(questionPrompt.trim() && (contextType === "workflow" ? workflowName : templateId));
    const preRunTraceItems = [
      {
        order: 1,
        label: contextPreview?.reference_name || contextPreview?.title || (contextType === "template" ? "Selected template" : "Selected workflow"),
        status: readyToRun ? "ready" : "configure question",
        detail: readyToRun ? "Run the bounded question to generate a real execution trace for this context." : "Choose a workflow or template and enter a question before the playground shows a trace."
      }
    ];
    const summaryCards = lastResult?.summary_cards || [];
    const resultProbabilityCard = summaryCards.find((card) => String(card.label || "").toLowerCase().includes("probability"));
    const resultProbability = resultProbabilityCard?.value ?? lastResult?.probability_summary?.probability ?? lastResult?.run_summary?.probability;
    const secondarySummaryCards = summaryCards.filter((card) => card !== resultProbabilityCard);
    const latestRunSummary = lastResult?.run_summary?.summary || lastResult?.labeling?.notes?.[0] || "Use the playground for exploratory local analysis, not release-grade evidence.";
    const studioModeHref = contextType === "workflow" && workflowName ? `/studio?workflow=${encodeURIComponent(workflowName)}` : contextType === "template" && templateId ? `/studio?template=${encodeURIComponent(templateId)}` : "/studio";
    const playgroundModeHref = route.search ? `/playground?${route.search}` : "/playground";
    useEffect(() => {
      if (!session) return;
      const nextContextType = requestedContext || (requestedTemplate ? "template" : requestedWorkflow ? "workflow" : String(session.context_type || "workflow"));
      setContextType(nextContextType);
      setWorkflowName(String(requestedWorkflow || session.workflow_name || workflows[0]?.name || ""));
      setTemplateId(String(requestedTemplate || session.template_id || templates[0]?.template_id || ""));
      setQuestionPrompt(String(session.question_prompt || ""));
      setQuestionTitle(String(session.question_title || ""));
      setResolutionCriteria(String(session.resolution_criteria || ""));
    }, [session?.updated_at, session?.context_type, session?.workflow_name, session?.template_id, session?.question_prompt, session?.question_title, session?.resolution_criteria, workflows, templates, requestedContext, requestedWorkflow, requestedTemplate]);
    useEffect(() => {
      if (!steps.length) {
        setSelectedStepKey("");
        return;
      }
      if (!selectedStepKey || !steps.some((step) => playgroundStepKey(step) === selectedStepKey)) {
        setSelectedStepKey(playgroundStepKey(steps[0]));
      }
    }, [selectedStepKey, steps]);
    const payload = () => ({
      context_type: contextType,
      workflow_name: workflowName || void 0,
      template_id: templateId || void 0,
      question_prompt: questionPrompt,
      question_title: questionTitle || void 0,
      resolution_criteria: resolutionCriteria || void 0
    });
    async function persistPlaygroundState() {
      setBusy("Updating playground state");
      setNotice(null);
      try {
        await requestJson(`${bootstrap.api_root}/playground`, {
          method: "PATCH",
          body: JSON.stringify(payload())
        });
        resource.reload();
        onMutate();
        setNotice({
          tone: "success",
          title: "Playground state updated",
          body: "The current exploratory context is saved locally in the WebUI state store."
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setNotice({
          tone: "error",
          title: "Couldn't update playground state",
          body: `${message} Stay inside the bounded workflow/template + single-question playground contract.`
        });
      } finally {
        setBusy(null);
      }
    }
    async function runPlayground() {
      setBusy("Running playground session");
      setNotice(null);
      try {
        await requestJson(`${bootstrap.api_root}/playground/run`, {
          method: "POST",
          body: JSON.stringify(payload())
        });
        resource.reload();
        onMutate();
        setNotice({
          tone: "success",
          title: "Exploratory run finished",
          body: "Inspect the ordered step outputs below. The playground keeps node inspection read-only."
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setNotice({
          tone: "error",
          title: "Couldn't run playground session",
          body: `${message} The playground only runs one bounded custom question at a time.`
        });
      } finally {
        setBusy(null);
      }
    }
    function selectTraceNode(nodeId) {
      const matchingStep = steps.find((step) => String(step.node_id) === nodeId);
      if (matchingStep) {
        setSelectedStepKey(playgroundStepKey(matchingStep));
      }
    }
    function PlaygroundInputPanel() {
      return /* @__PURE__ */ React.createElement("aside", { className: "playground-input-panel" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header playground-panel-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Single question input"), /* @__PURE__ */ React.createElement("strong", null, contextPreview?.title || contextPreview?.reference_name || "Choose a forecasting context")), /* @__PURE__ */ React.createElement(StatusPill, { value: String(lastResult?.run?.status || session?.status || "ready") })), /* @__PURE__ */ React.createElement("div", { className: "playground-form-stack" }, /* @__PURE__ */ React.createElement("section", { className: "playground-section-card" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Query"), /* @__PURE__ */ React.createElement(
        "textarea",
        {
          className: "text-area-input playground-query-input",
          value: questionPrompt,
          onChange: (event) => setQuestionPrompt(event.target.value),
          placeholder: "Will the proposed merger between Company X and Y be approved by regulators before Q3?"
        }
      ))), /* @__PURE__ */ React.createElement("section", { className: "playground-section-card" }, /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Context"), /* @__PURE__ */ React.createElement("select", { value: contextType, onChange: (event) => setContextType(event.target.value) }, /* @__PURE__ */ React.createElement("option", { value: "workflow" }, "Workflow"), /* @__PURE__ */ React.createElement("option", { value: "template" }, "Template"))), contextType === "workflow" ? /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Workflow"), /* @__PURE__ */ React.createElement("select", { value: workflowName, onChange: (event) => setWorkflowName(event.target.value) }, workflows.map((item) => /* @__PURE__ */ React.createElement("option", { key: item.name, value: item.name }, item.title || item.name)))) : /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Template"), /* @__PURE__ */ React.createElement("select", { value: templateId, onChange: (event) => setTemplateId(event.target.value) }, templates.map((item) => /* @__PURE__ */ React.createElement("option", { key: item.template_id, value: item.template_id }, item.title))))), /* @__PURE__ */ React.createElement(
        DensityDisclosure,
        {
          className: "playground-options-disclosure",
          title: "Advanced run options",
          detail: "Keep optional metadata and tuning nearby without crowding the main prompt."
        },
        /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Optional title"), /* @__PURE__ */ React.createElement("input", { value: questionTitle, onChange: (event) => setQuestionTitle(event.target.value), placeholder: "Auto-derived when blank" })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Resolution criteria"), /* @__PURE__ */ React.createElement("input", { value: resolutionCriteria, onChange: (event) => setResolutionCriteria(event.target.value), placeholder: "Visible later in Observatory" }))),
        /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Confidence threshold"), /* @__PURE__ */ React.createElement("div", { className: "read-only-field", "aria-readonly": "true" }, /* @__PURE__ */ React.createElement("strong", null, "10%"), /* @__PURE__ */ React.createElement("span", null, "Fixed local baseline"))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Research depth"), /* @__PURE__ */ React.createElement("div", { className: "read-only-field", "aria-readonly": "true" }, /* @__PURE__ */ React.createElement("strong", null, "Standard"), /* @__PURE__ */ React.createElement("span", null, "Shared playground default"))))
      ))), /* @__PURE__ */ React.createElement("div", { className: "button-row playground-action-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: runPlayground, disabled: Boolean(busy) || !readyToRun }, busy === "Running playground session" ? busy : "Run forecast"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: persistPlaygroundState, disabled: Boolean(busy) }, "Save state")), contextPreview ? /* @__PURE__ */ React.createElement(
        DensityDisclosure,
        {
          className: "playground-section-card playground-inline-disclosure playground-context-disclosure",
          title: String(contextPreview.reference_name || "Context preview"),
          detail: `Bounded ${contextPreview.context_type || contextType} context. Open for entry, runtime, and route handoff only when you need supporting detail.`
        },
        /* @__PURE__ */ React.createElement("span", { className: "source-pill local" }, contextPreview.context_type || contextType),
        /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, contextPreview.description || "The playground keeps context bounded to a workflow or starter template."),
        /* @__PURE__ */ React.createElement("dl", { className: "context-list compact-context-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Entry"), /* @__PURE__ */ React.createElement("dd", null, contextPreview.entry || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Runtime"), /* @__PURE__ */ React.createElement("dd", null, contextPreview.runtime?.provider || "deterministic")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Question limit"), /* @__PURE__ */ React.createElement("dd", null, formatValue(contextPreview.questions_limit)))),
        /* @__PURE__ */ React.createElement("div", { className: "button-row" }, contextType === "workflow" && workflowName ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(`/studio?workflow=${encodeURIComponent(workflowName)}`) }, "Open in Studio") : null, /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate("/runs") }, "Open Observatory"))
      ) : null);
    }
    function PlaygroundCanvasPanel() {
      return /* @__PURE__ */ React.createElement("section", { className: "playground-canvas-panel" }, /* @__PURE__ */ React.createElement(
        PlaygroundGraphTracePreview,
        {
          canvas: lastResult?.canvas || contextPreview?.canvas || {},
          traceItems: orderedTrace,
          activeNodeId: String(activeStep?.node_id || ""),
          onSelectNode: selectTraceNode
        }
      ));
    }
    function PlaygroundTracePanel() {
      return /* @__PURE__ */ React.createElement("aside", { className: "live-trace-panel" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Live Execution Trace"), /* @__PURE__ */ React.createElement("h3", null, activeStep?.label || activeStep?.node_id || "Ready to run"))), lastResult ? /* @__PURE__ */ React.createElement("article", { className: "forecast-result-card" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, lastResult.run_id || "Latest exploratory run"), /* @__PURE__ */ React.createElement("strong", null, resultProbability != null ? formatProbability(resultProbability) : "Forecast ready"), /* @__PURE__ */ React.createElement("span", null, lastResult?.run_summary?.summary || lastResult?.labeling?.display_label || "Agent agreement"), /* @__PURE__ */ React.createElement("p", { className: "helper-text playground-run-note" }, latestRunSummary), /* @__PURE__ */ React.createElement("div", { className: "result-sparkline", "aria-hidden": "true" }, /* @__PURE__ */ React.createElement("span", null), /* @__PURE__ */ React.createElement("span", null), /* @__PURE__ */ React.createElement("span", null), /* @__PURE__ */ React.createElement("span", null)), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(`/runs/${lastResult.run_id}`) }, "Inspect run detail"), lastResult.report?.available ? /* @__PURE__ */ React.createElement("a", { className: "secondary-link", href: lastResult.report.href, target: "_blank", rel: "noreferrer" }, "Open report") : null)) : null, secondarySummaryCards.length ? /* @__PURE__ */ React.createElement(
        DensityDisclosure,
        {
          className: "trace-detail-card playground-inline-disclosure playground-metrics-disclosure",
          title: "Run metrics",
          detail: "Keep secondary summary cards nearby without interrupting the default result \u2192 trace \u2192 inspector scan path."
        },
        /* @__PURE__ */ React.createElement("div", { className: "stats-grid playground-trace-stats" }, secondarySummaryCards.map((card) => /* @__PURE__ */ React.createElement(MetricCard, { key: String(card.label), label: String(card.label), value: card.value })))
      ) : null, graphTraceArtifact.available === false && resultTrace.source === "sandbox" ? /* @__PURE__ */ React.createElement(
        Message,
        {
          tone: "warning",
          title: graphTraceArtifact.empty_state?.title || "No graph trace artifact",
          body: graphTraceArtifact.empty_state?.body || "Showing sandbox inspection steps without claiming a persisted graph_trace.jsonl artifact."
        }
      ) : null, /* @__PURE__ */ React.createElement("div", { className: "live-trace-stack" }, (orderedTrace.length ? orderedTrace : preRunTraceItems).map((item) => /* @__PURE__ */ React.createElement(
        "button",
        {
          key: `${item.order}-${item.node_id || item.label}`,
          type: "button",
          className: String(activeStep?.node_id || "") === String(item.node_id || "") ? "trace-stage active" : "trace-stage",
          onClick: () => item.node_id ? selectTraceNode(String(item.node_id)) : void 0,
          disabled: !item.node_id
        },
        /* @__PURE__ */ React.createElement("span", { className: "trace-ring" }),
        /* @__PURE__ */ React.createElement("strong", null, item.label || item.node_id),
        /* @__PURE__ */ React.createElement(StatusPill, { value: String(item.status || "pending") }),
        !item.node_id && item.detail ? /* @__PURE__ */ React.createElement("span", { className: "trace-stage-note" }, item.detail) : null
      ))), /* @__PURE__ */ React.createElement("article", { className: "trace-detail-card" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("strong", null, activeStep?.label || activeStep?.node_id || "Awaiting first trace step"), /* @__PURE__ */ React.createElement(StatusPill, { value: String(activeStep?.status || "pending") })), /* @__PURE__ */ React.createElement("dl", { className: "context-list compact-context-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Node"), /* @__PURE__ */ React.createElement("dd", null, activeStep?.node_id || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Route"), /* @__PURE__ */ React.createElement("dd", null, formatValue(activeStep?.route) || "default")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Latency"), /* @__PURE__ */ React.createElement("dd", null, formatValue(activeStep?.latency_seconds) || "\u2014"))), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, activeStep?.output_preview || lastResult?.run_summary?.summary || "Run the playground to inspect ordered sandbox outputs."), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate("/studio") }, "Open Studio"))));
    }
    function PlaygroundWorkspaceAdapter() {
      return /* @__PURE__ */ React.createElement(
        WorkspacePanelAdapter,
        {
          frameClassName: "playground-live-workspace",
          leftPanel: PlaygroundInputPanel(),
          centerPanel: PlaygroundCanvasPanel(),
          rightPanel: PlaygroundTracePanel()
        }
      );
    }
    return /* @__PURE__ */ React.createElement("main", { className: "page-grid playground-shell" }, resource.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Playground unavailable", body: resource.error }) : null, notice ? /* @__PURE__ */ React.createElement(Message, { tone: notice.tone, title: notice.title, body: notice.body }) : null, resource.loading && !resource.data ? /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading playground" }) : null, /* @__PURE__ */ React.createElement(
      WorkspaceModeShell,
      {
        mode: "playground",
        navigate,
        studioHref: studioModeHref,
        playgroundHref: playgroundModeHref
      },
      PlaygroundWorkspaceAdapter()
    ));
  }
  function WorkbenchPage({ route, shell, navigate, onMutate }) {
    const params = useMemo(() => new URLSearchParams(route.search), [route.search]);
    const draftId = params.get("draft");
    const requestedWorkflow = params.get("workflow");
    const requestedTemplate = params.get("template") || params.get("template_id");
    const requestedMode = params.get("mode");
    const isStudio = route.path === "/studio";
    const surfaceLabel = isStudio ? "Studio" : "Workbench";
    const surfaceBase = isStudio ? "/studio" : "/workbench";
    const studioModeHref = route.search ? `${surfaceBase}?${route.search}` : surfaceBase;
    const draftApiBase = isStudio ? `${bootstrap.api_root}/studio/drafts` : `${bootstrap.api_root}/drafts`;
    const catalogUrl = isStudio ? `${bootstrap.api_root}/studio/catalog` : `${bootstrap.api_root}/authoring/catalog`;
    const workflows = useJsonResource(`${bootstrap.api_root}/workflows`, [route.search]);
    const selectedWorkflow = preferredWorkbenchWorkflow(
      requestedWorkflow,
      shell?.overview?.latest_run?.workflow?.name,
      workflows.data
    );
    const authoringCatalog = useJsonResource(catalogUrl, [catalogUrl]);
    const draft = useJsonResource(draftId ? `${draftApiBase}/${draftId}` : null, [draftId, draftApiBase]);
    const workflow = useJsonResource(
      !draftId && selectedWorkflow ? `${bootstrap.api_root}/workflows/${encodeURIComponent(selectedWorkflow)}` : null,
      [selectedWorkflow, draftId]
    );
    const [busy, setBusy] = useState(null);
    const [actionNotice, setActionNotice] = useState(null);
    const [creationMode, setCreationMode] = useState("clone");
    const [createForm, setCreateForm] = useState({
      source_workflow_name: "",
      template_id: "",
      draft_workflow_name: "",
      title: "",
      description: ""
    });
    const [coreForm, setCoreForm] = useState({});
    const [selectedNodeName, setSelectedNodeName] = useState("");
    const [nodeForm, setNodeForm] = useState({});
    const [addNodeForm, setAddNodeForm] = useState({
      node_name: "",
      implementation: "",
      incoming_from: "",
      outgoing_to: "",
      description: "",
      optional: "false",
      runtime: ""
    });
    const [addEdgeForm, setAddEdgeForm] = useState({ from_node: "", to_node: "" });
    const [selectedEdgeId, setSelectedEdgeId] = useState("");
    const [inspectorMode, setInspectorMode] = useState("workflow");
    const [studioRailMode, setStudioRailMode] = useState("inspect");
    const [edgeDraftFrom, setEdgeDraftFrom] = useState("");
    const [localPositions, setLocalPositions] = useState({});
    const [studioBootstrapState, setStudioBootstrapState] = useState("idle");
    const [paletteQuery, setPaletteQuery] = useState("");
    const [paletteLibraryOpen, setPaletteLibraryOpen] = useState(false);
    useEffect(() => {
      if (requestedTemplate) {
        setCreationMode("template");
        setCreateForm((current) => ({ ...current, template_id: requestedTemplate }));
      } else if (requestedMode === "scratch" || requestedMode === "clone" || requestedMode === "template") {
        setCreationMode(requestedMode);
      }
    }, [requestedTemplate, requestedMode]);
    const activeDraft = draftFromPayload(draft.data);
    const activeWorkflow = activeDraft ? activeDraft.workflow : workflow.data?.workflow;
    const activeAuthoring = activeDraft ? activeDraft.authoring : workflow.data?.authoring;
    const activeCanvas = activeDraft ? activeDraft.canvas : workflow.data?.canvas;
    const activeGraph = activeAuthoring?.graph || {};
    const graphNodes = (activeGraph.nodes || []).filter((node) => typeof node?.name === "string");
    const graphTargets = (activeGraph.targets || []).filter((target) => typeof target?.name === "string");
    const selectedNode = graphNodes.find((node) => node.name === selectedNodeName) || null;
    const canvasEdges = activeCanvas?.edges || [];
    const graphEdges = activeGraph.edges || [];
    const selectedEdge = canvasEdges.find((edge) => studioEdgeKey(edge) === selectedEdgeId) || null;
    const overviewLatestRun = shell?.overview?.latest_run || null;
    const safeEditSupport = activeDraft?.guidance?.supported_edits || activeDraft?.safe_edit?.supported_edits || workflow.data?.safe_edit?.supported_edits || [];
    const safeEditLimitations = activeDraft?.guidance?.limitations || activeAuthoring?.limitations || defaultAuthoringLimitations();
    const sourceOfTruth = activeDraft?.guidance?.source_of_truth || defaultSourceOfTruth();
    const nextStep = activeDraft?.guidance?.next_step || buildDraftlessNextStep(activeWorkflow, overviewLatestRun);
    const stepState = draftId ? decorateStepState(activeDraft?.step_state || defaultStepState(), activeDraft, true) : decorateStepState(draftlessStepState(activeWorkflow), null, false);
    const validationStatus = buildValidationStatus(activeDraft);
    const validationFixes = buildValidationFixes(activeDraft);
    const runDisabled = !(activeDraft?.validation?.ok && !activeDraft?.validation?.stale);
    const templates = authoringCatalog.data?.templates || [];
    const nodeCatalog = authoringCatalog.data?.node_catalog || authoringCatalog.data?.node_palette?.items || [];
    const creationModes = authoringCatalog.data?.creation_modes || [];
    const creationDisabled = !createForm.draft_workflow_name || creationMode === "clone" && !(createForm.source_workflow_name || activeWorkflow?.name) || creationMode === "template" && !createForm.template_id;
    const showStudioDraftIde = isStudio && Boolean(draftId);
    const resumeTarget = shell?.overview?.resume_target || shell?.hub?.resume_target || {};
    const explicitStudioIntent = Boolean(requestedWorkflow || requestedTemplate || requestedMode);
    const studioResumeTarget = !isStudio || draftId || explicitStudioIntent || resumeTarget.kind !== "draft" || !resumeTarget.href ? null : {
      href: String(resumeTarget.href),
      label: String(resumeTarget.label || "Resume latest draft")
    };
    const studioIntent = useMemo(() => {
      if (!isStudio || draftId) return null;
      if (requestedMode === "scratch") return { creation_mode: "scratch" };
      if (requestedTemplate || requestedMode === "template") {
        return {
          creation_mode: "template",
          template_id: String(requestedTemplate || templates[0]?.template_id || "") || null
        };
      }
      if (requestedWorkflow || requestedMode === "clone") {
        if (!selectedWorkflow) return null;
        return {
          creation_mode: "clone",
          source_workflow_name: selectedWorkflow
        };
      }
      return null;
    }, [draftId, isStudio, requestedMode, requestedTemplate, requestedWorkflow, selectedWorkflow, templates]);
    const showStudioSetup = !showStudioDraftIde && (!isStudio || studioBootstrapState === "failed" || !studioIntent);
    const showWorkbenchSetupRail = showStudioSetup && !isStudio;
    const showWorkbenchFieldSetup = showStudioSetup && !isStudio;
    const showWorkbenchIdePanel = !isStudio || showStudioDraftIde || !showStudioSetup;
    const compareActions = activeDraft?.compare?.next_actions || [];
    const validationPillValue = activeDraft?.validation?.ok ? activeDraft?.validation?.stale ? "stale validation" : "validated" : "needs validation";
    const studioDraftTitle = activeDraft?.draft_workflow_name || activeWorkflow?.title || activeWorkflow?.name || "Studio draft";
    const playgroundModeHref = activeDraft?.draft_workflow_name ? `/playground?context=workflow&workflow=${encodeURIComponent(String(activeDraft.draft_workflow_name))}` : requestedTemplate ? `/playground?context=template&template=${encodeURIComponent(requestedTemplate)}` : selectedWorkflow ? `/playground?context=workflow&workflow=${encodeURIComponent(selectedWorkflow)}` : "/playground";
    const normalizedPaletteQuery = paletteQuery.trim().toLowerCase();
    const paletteGroups = useMemo(() => {
      const grouped = /* @__PURE__ */ new Map();
      nodeCatalog.forEach((item) => {
        const kind = String(item.kind || "other");
        const entries = grouped.get(kind) || [];
        entries.push(item);
        grouped.set(kind, entries);
      });
      return Array.from(grouped.entries()).sort(([left], [right]) => {
        const leftIndex = PALETTE_KIND_ORDER.indexOf(left);
        const rightIndex = PALETTE_KIND_ORDER.indexOf(right);
        if (leftIndex >= 0 && rightIndex >= 0) return leftIndex - rightIndex;
        if (leftIndex >= 0) return -1;
        if (rightIndex >= 0) return 1;
        return left.localeCompare(right);
      }).map(([kind, items]) => ({
        key: kind,
        label: paletteGroupLabel(kind),
        items: [...items].sort((left, right) => String(left.label || left.name || left.implementation || "").localeCompare(String(right.label || right.name || right.implementation || "")))
      }));
    }, [nodeCatalog]);
    const filteredPaletteGroups = useMemo(() => paletteGroups.map((group) => ({
      ...group,
      items: group.items.filter((item) => paletteMatchesQuery(item, normalizedPaletteQuery))
    })).filter((group) => group.items.length), [normalizedPaletteQuery, paletteGroups]);
    const filteredPaletteItems = useMemo(() => filteredPaletteGroups.flatMap((group) => group.items), [filteredPaletteGroups]);
    const paletteTopMatch = filteredPaletteItems[0] || null;
    useEffect(() => {
      setActionNotice(null);
    }, [draftId, selectedWorkflow]);
    useEffect(() => {
      if (draftId && busy === "Opening Studio graph IDE") {
        setBusy(null);
      }
    }, [busy, draftId]);
    useEffect(() => {
      if (!isStudio || draftId) {
        setStudioBootstrapState("idle");
      }
    }, [draftId, isStudio]);
    useEffect(() => {
      if (!isStudio || draftId || !studioIntent) return;
      if (studioBootstrapState === "bootstrapping" || studioBootstrapState === "failed") return;
      if (studioIntent.creation_mode === "template" && !studioIntent.template_id && authoringCatalog.loading) return;
      if (authoringCatalog.error) {
        setStudioBootstrapState("failed");
        return;
      }
      let cancelled = false;
      async function openStudioGraphIde() {
        let payload = { creation_mode: studioIntent.creation_mode };
        if (studioIntent.creation_mode === "template") {
          const templateId = String(studioIntent.template_id || "");
          if (!templateId) {
            setStudioBootstrapState("failed");
            setActionNotice({
              tone: "warning",
              title: "Studio needs a starter template",
              body: "No starter template was available to open directly in the Studio graph IDE."
            });
            return;
          }
          payload.template_id = templateId;
        } else if (studioIntent.creation_mode === "clone") {
          const sourceWorkflowName = studioIntent.source_workflow_name;
          if (!sourceWorkflowName) {
            setStudioBootstrapState("failed");
            setActionNotice({
              tone: "warning",
              title: "Studio needs a workflow",
              body: "No workflow was available to open directly in the Studio graph IDE."
            });
            return;
          }
          payload.source_workflow_name = sourceWorkflowName;
        }
        if (overviewLatestRun?.run_id) payload.baseline_run_id = overviewLatestRun.run_id;
        setStudioBootstrapState("bootstrapping");
        setBusy("Opening Studio graph IDE");
        setActionNotice(null);
        try {
          const created = await requestJson(draftApiBase, { method: "POST", body: JSON.stringify(payload) });
          if (cancelled) return;
          const createdDraft = draftFromPayload(created);
          onMutate();
          navigate(`/studio?draft=${createdDraft?.id || created.id}`);
        } catch (error) {
          if (cancelled) return;
          setStudioBootstrapState("failed");
          setActionNotice(buildActionErrorNotice("open Studio", error));
          setBusy(null);
        }
      }
      void openStudioGraphIde();
      return () => {
        cancelled = true;
      };
    }, [
      authoringCatalog.error,
      authoringCatalog.loading,
      draftApiBase,
      draftId,
      isStudio,
      navigate,
      onMutate,
      overviewLatestRun?.run_id,
      studioIntent
    ]);
    useEffect(() => {
      setCreateForm((current) => ({
        ...current,
        source_workflow_name: current.source_workflow_name || selectedWorkflow || "",
        template_id: current.template_id || String(templates[0]?.template_id || "")
      }));
      setAddNodeForm((current) => ({
        ...current,
        implementation: current.implementation || String(nodeCatalog[0]?.implementation || "")
      }));
    }, [selectedWorkflow, templates, nodeCatalog]);
    useEffect(() => {
      if (activeAuthoring?.core_form) {
        const nextCore = {};
        Object.entries(activeAuthoring.core_form).forEach(([key, value]) => {
          nextCore[key] = value == null ? "" : String(value);
        });
        setCoreForm(nextCore);
      }
    }, [activeAuthoring]);
    useEffect(() => {
      if (!graphNodes.length) {
        setSelectedNodeName("");
        setInspectorMode("workflow");
        return;
      }
      if (!selectedNodeName || !graphNodes.some((node) => node.name === selectedNodeName)) {
        setSelectedNodeName(String(graphNodes[0].name));
      }
    }, [graphNodes, selectedNodeName]);
    useEffect(() => {
      const names = new Set(graphNodes.map((node) => String(node.name)));
      setLocalPositions((current) => {
        const next = Object.fromEntries(Object.entries(current).filter(([name]) => names.has(name)));
        return Object.keys(next).length === Object.keys(current).length ? current : next;
      });
      if (edgeDraftFrom && !names.has(edgeDraftFrom)) {
        setEdgeDraftFrom("");
      }
    }, [graphNodes, edgeDraftFrom]);
    useEffect(() => {
      if (selectedEdgeId && !canvasEdges.some((edge) => studioEdgeKey(edge) === selectedEdgeId)) {
        setSelectedEdgeId("");
        if (inspectorMode === "edge") setInspectorMode("workflow");
      }
    }, [canvasEdges, selectedEdgeId, inspectorMode]);
    useEffect(() => {
      if (!selectedNode) {
        setNodeForm({});
        return;
      }
      const nextNodeForm = {
        description: String(selectedNode.description || ""),
        runtime: String(selectedNode.runtime || ""),
        optional: selectedNode.optional ? "true" : "false"
      };
      (selectedNode.aggregate_weights || []).forEach((item) => {
        nextNodeForm[`weight:${String(item.name)}`] = String(item.percent ?? "");
      });
      setNodeForm(nextNodeForm);
    }, [selectedNode]);
    async function createDraftFromMode() {
      setBusy("Creating authoring draft");
      setActionNotice(null);
      try {
        const payload = {
          creation_mode: creationMode,
          draft_workflow_name: createForm.draft_workflow_name,
          title: normalizeText(createForm.title) || void 0,
          description: normalizeText(createForm.description) || void 0
        };
        if (overviewLatestRun?.run_id) {
          payload.baseline_run_id = overviewLatestRun.run_id;
        }
        if (creationMode === "clone") {
          payload.source_workflow_name = createForm.source_workflow_name || activeWorkflow?.name || selectedWorkflow;
        } else if (creationMode === "template") {
          payload.template_id = createForm.template_id;
        }
        const created = await requestJson(draftApiBase, { method: "POST", body: JSON.stringify(payload) });
        const createdDraft = draftFromPayload(created);
        onMutate();
        navigate(`${surfaceBase}?draft=${createdDraft?.id || created.id}`);
      } catch (error) {
        setActionNotice(buildActionErrorNotice("create", error));
      } finally {
        setBusy(null);
      }
    }
    async function applyDraftAction(stage, action, successTitle, successBody) {
      if (!draftId) return null;
      setBusy(successTitle);
      setActionNotice(null);
      try {
        const updated = await requestJson(isStudio ? `${draftApiBase}/${draftId}/graph` : `${draftApiBase}/${draftId}`, {
          method: "PATCH",
          body: JSON.stringify({ action })
        });
        draft.reload();
        onMutate();
        setActionNotice({ tone: "success", title: successTitle, body: successBody });
        return draftFromPayload(updated);
      } catch (error) {
        setActionNotice(buildActionErrorNotice(stage, error));
        return null;
      } finally {
        setBusy(null);
      }
    }
    function selectWorkflowInspector() {
      setStudioRailMode("inspect");
      setInspectorMode("workflow");
      setSelectedEdgeId("");
      setEdgeDraftFrom("");
    }
    function selectNodeInspector(name) {
      setStudioRailMode("inspect");
      setSelectedNodeName(name);
      setSelectedEdgeId("");
      setInspectorMode("node");
    }
    function selectEdgeInspector(edge) {
      setStudioRailMode("inspect");
      setSelectedEdgeId(studioEdgeKey(edge));
      setEdgeDraftFrom("");
      setInspectorMode("edge");
    }
    async function applyCoreFields() {
      if (!draftId) return;
      await applyDraftAction(
        "workflow",
        {
          type: "update-core",
          metadata: {
            title: coreForm.title,
            description: coreForm.description,
            workflow_kind: coreForm.workflow_kind,
            tags: (coreForm.tags || "").split(",").map((item) => item.trim()).filter(Boolean)
          },
          questions: { limit: Number(coreForm.questions_limit || 0) },
          runtime: {
            provider: coreForm.runtime_provider,
            base_url: normalizeText(coreForm.runtime_base_url),
            model: normalizeText(coreForm.runtime_model),
            max_tokens: Number(coreForm.runtime_max_tokens || 0)
          },
          artifacts: {
            write_report: parseBooleanString(coreForm.artifacts_write_report),
            write_blueprint_copy: parseBooleanString(coreForm.artifacts_write_blueprint_copy),
            write_graph_trace: parseBooleanString(coreForm.artifacts_write_graph_trace)
          },
          scoring: {
            write_eval: parseBooleanString(coreForm.scoring_write_eval),
            write_train_backtest: parseBooleanString(coreForm.scoring_write_train_backtest)
          }
        },
        "Workflow fields updated",
        "Core workflow fields now reflect the latest authored state. Validate when you're ready to run."
      );
    }
    async function applyNodeUpdates() {
      if (!draftId || !selectedNode) return;
      const weights = {};
      Object.entries(nodeForm).forEach(([key, value]) => {
        if (key.startsWith("weight:")) {
          weights[key.replace(/^weight:/, "")] = value;
        }
      });
      await applyDraftAction(
        "node",
        {
          type: "update-node",
          node_name: selectedNode.name,
          description: nodeForm.description || "",
          runtime: normalizeText(nodeForm.runtime),
          optional: parseBooleanString(nodeForm.optional),
          weights: Object.keys(weights).length ? weights : void 0
        },
        "Node updated",
        `The visual editor saved changes for ${selectedNode.name}.`
      );
    }
    async function removeSelectedNode() {
      if (!draftId || !selectedNode) return;
      const removedName = String(selectedNode.name);
      const updated = await applyDraftAction(
        "node",
        { type: "remove-node", node_name: removedName },
        "Node removed",
        `${removedName} was removed from the draft graph.`
      );
      const nextNode = updated?.authoring?.graph?.nodes?.[0]?.name;
      setSelectedNodeName(nextNode ? String(nextNode) : "");
    }
    async function setEntry(entryName) {
      if (!draftId || !entryName) return;
      await applyDraftAction(
        "entry",
        { type: "set-entry", entry: entryName },
        "Entry updated",
        `${entryName} is now the workflow entry for this draft.`
      );
    }
    async function addNode(overrides = {}, dropPosition) {
      if (!draftId) return;
      const form = { ...addNodeForm, ...overrides };
      const action = {
        type: "add-node",
        node_name: form.node_name,
        implementation: form.implementation,
        description: normalizeText(form.description),
        runtime: normalizeText(form.runtime),
        optional: parseBooleanString(form.optional)
      };
      if (form.incoming_from) action.incoming_from = [form.incoming_from];
      if (form.outgoing_to) action.outgoing_to = [form.outgoing_to];
      const addedName = form.node_name;
      const updated = await applyDraftAction(
        "node",
        action,
        "Node added",
        `${addedName} is now part of the authored workflow graph${isStudio ? " and validation was refreshed." : "."}`
      );
      if (updated) {
        selectNodeInspector(addedName);
        if (dropPosition) {
          setLocalPositions((current) => ({ ...current, [addedName]: dropPosition }));
        }
        setAddNodeForm((current) => ({ ...current, node_name: "", description: "", runtime: "", incoming_from: "", outgoing_to: "" }));
      }
    }
    async function addPaletteNode(itemOrImplementation, dropPosition) {
      const item = typeof itemOrImplementation === "string" ? nodeCatalog.find((candidate) => candidate.implementation === itemOrImplementation) || { implementation: itemOrImplementation, name: itemOrImplementation } : itemOrImplementation;
      const connectionFrom = selectedNode?.name || activeGraph.entry || graphNodes[0]?.name || "";
      await addNode(
        {
          node_name: suggestNodeName(item, graphNodes),
          implementation: String(item.implementation || ""),
          incoming_from: String(connectionFrom || ""),
          outgoing_to: "",
          description: String(item.summary || item.description || ""),
          runtime: String(item.default_runtime || ""),
          optional: "false"
        },
        dropPosition
      );
    }
    async function addPaletteTopMatch() {
      if (!paletteTopMatch) return;
      await addPaletteNode(paletteTopMatch);
    }
    async function addEdge() {
      if (!draftId) return;
      await addEdgeFromValues(addEdgeForm.from_node, addEdgeForm.to_node);
    }
    async function removeEdge(fromNode, toNode) {
      if (!draftId) return;
      await applyDraftAction(
        "edge",
        { type: "remove-edge", from_node: fromNode, to_node: toNode },
        "Edge removed",
        `${fromNode} no longer connects to ${toNode}.`
      );
      setSelectedEdgeId("");
      if (inspectorMode === "edge") setInspectorMode("workflow");
    }
    async function createEdgeFromCanvas(fromNode, toNode) {
      setAddEdgeForm({ from_node: fromNode, to_node: toNode });
      await addEdgeFromValues(fromNode, toNode);
    }
    async function addEdgeFromValues(fromNode, toNode) {
      if (!draftId) return;
      const updated = await applyDraftAction(
        "edge",
        { type: "add-edge", from_node: fromNode, to_node: toNode },
        "Edge added",
        `${fromNode} now connects to ${toNode}${isStudio ? " and validation was refreshed." : "."}`
      );
      if (updated) {
        const addedEdge = (updated.authoring?.graph?.edges || []).find((edge) => edge.from === fromNode && edge.to === toNode);
        if (addedEdge) {
          setSelectedEdgeId(studioEdgeKey(addedEdge));
          setInspectorMode("edge");
        }
        setEdgeDraftFrom("");
      }
    }
    async function validateDraft() {
      if (!draftId) return;
      setBusy("Saving and validating draft");
      setActionNotice(null);
      try {
        const result = await requestJson(`${draftApiBase}/${draftId}/validate`, { method: "POST", body: JSON.stringify({}) });
        draft.reload();
        onMutate();
        const validation = result.validation;
        setActionNotice(
          validation?.ok ? {
            tone: validation.stale ? "warning" : "success",
            title: validation.stale ? "Validation needs a refresh" : "Validation passed",
            body: validation.stale ? "A newer edit changed the draft after validation. Validate once more before you run." : "The latest authored draft was saved and validated successfully. Next: run a candidate and compare it with the baseline."
          } : {
            tone: "warning",
            title: "Validation found issues",
            body: `${(validation?.errors || []).join(" ")} Fix the supported fields below; your draft context is still preserved.`
          }
        );
      } catch (error) {
        setActionNotice(buildActionErrorNotice("validate", error));
      } finally {
        setBusy(null);
      }
    }
    async function runDraft() {
      if (!draftId) return;
      setBusy("Running candidate");
      setActionNotice(null);
      try {
        const response = await requestJson(`${draftApiBase}/${draftId}/run`, { method: "POST", body: JSON.stringify({}) });
        onMutate();
        if (response.compare) {
          navigate(`/runs/${response.compare.candidate_run_id}/compare/${response.compare.baseline_run_id}`);
        } else {
          navigate(`/runs/${response.run_id}`);
        }
      } catch (error) {
        setActionNotice(buildActionErrorNotice("run", error));
      } finally {
        setBusy(null);
      }
    }
    async function createVersionSnapshotFromDraft() {
      if (!draftId) return;
      setBusy("Creating version snapshot");
      setActionNotice(null);
      try {
        const result = await requestJson(`${bootstrap.api_root}/versions`, {
          method: "POST",
          body: JSON.stringify({
            draft_id: draftId,
            label: `${activeDraft?.draft_workflow_name || activeWorkflow?.name || "workflow"} revision ${activeDraft?.revision ?? 0}`,
            set_default: true
          })
        });
        onMutate();
        setActionNotice({
          tone: "success",
          title: "Version snapshot created",
          body: `${result.label || result.id} is now the default saved snapshot for ${result.workflow_name}.`
        });
      } catch (error) {
        setActionNotice(buildActionErrorNotice("version snapshot", error));
      } finally {
        setBusy(null);
      }
    }
    async function persistNodePosition(name, position) {
      setLocalPositions((current) => ({ ...current, [name]: position }));
      if (!draftId || !isStudio) return;
      try {
        await requestJson(`${draftApiBase}/${draftId}/graph`, {
          method: "PATCH",
          body: JSON.stringify({ action: { type: "move-node", node_name: name, position } })
        });
        draft.reload();
      } catch (error) {
        setActionNotice(buildActionErrorNotice("layout", error));
      }
    }
    function StudioDraftPalettePanel() {
      return /* @__PURE__ */ React.createElement("section", { className: "playground-input-panel studio-palette-panel node-palette", "aria-label": "Studio node palette" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Quick add"), /* @__PURE__ */ React.createElement("p", null, "Search or insert one safe node first. Open the grouped library only when the quick path is not enough.")), /* @__PURE__ */ React.createElement("div", { className: "node-palette-toolbar" }, /* @__PURE__ */ React.createElement("label", { className: "node-palette-search" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Quick insert"), /* @__PURE__ */ React.createElement(
        "input",
        {
          type: "search",
          value: paletteQuery,
          onChange: (event) => setPaletteQuery(event.target.value),
          onKeyDown: (event) => {
            if (event.key === "Enter" && paletteTopMatch && !busy) {
              event.preventDefault();
              void addPaletteTopMatch();
            }
          },
          placeholder: "Search nodes, then press Enter to insert the top match",
          "aria-label": "Search studio node palette"
        }
      )), /* @__PURE__ */ React.createElement("div", { className: "node-palette-actions" }, /* @__PURE__ */ React.createElement("button", { className: "secondary-button", type: "button", onClick: () => void addPaletteTopMatch(), disabled: Boolean(busy) || !paletteTopMatch }, paletteTopMatch ? `Insert ${paletteTopMatch.label || paletteTopMatch.name}` : "No matching node"))), /* @__PURE__ */ React.createElement(
        "details",
        {
          className: "density-disclosure studio-library-disclosure",
          open: normalizedPaletteQuery ? true : paletteLibraryOpen || void 0,
          onToggle: (event) => {
            if (normalizedPaletteQuery) return;
            setPaletteLibraryOpen(event.currentTarget.open);
          }
        },
        /* @__PURE__ */ React.createElement("summary", null, /* @__PURE__ */ React.createElement("div", { className: "density-disclosure-copy" }, /* @__PURE__ */ React.createElement("strong", null, normalizedPaletteQuery ? `${filteredPaletteItems.length} matching nodes` : `Browse all ${nodeCatalog.length} safe nodes`), /* @__PURE__ */ React.createElement("p", null, normalizedPaletteQuery ? paletteTopMatch ? `Enter inserts ${paletteTopMatch.label || paletteTopMatch.name}.` : "Adjust the search to find another node." : "Keep the full library collapsed until you need the grouped catalog."))),
        /* @__PURE__ */ React.createElement("div", { className: "density-disclosure-body" }, /* @__PURE__ */ React.createElement("p", { className: "helper-text node-palette-status" }, normalizedPaletteQuery ? `${filteredPaletteItems.length} of ${nodeCatalog.length} nodes match the current search.` : `Grouped library \xB7 ${nodeCatalog.length} safe nodes available by category.`), /* @__PURE__ */ React.createElement("div", { className: "node-palette-scroll" }, filteredPaletteGroups.length ? filteredPaletteGroups.map((group, index) => /* @__PURE__ */ React.createElement(
          "details",
          {
            key: group.key,
            className: "palette-group-card",
            open: Boolean(normalizedPaletteQuery) || index === 0 || void 0
          },
          /* @__PURE__ */ React.createElement("summary", null, /* @__PURE__ */ React.createElement("span", null, group.label), /* @__PURE__ */ React.createElement("small", null, group.items.length, " nodes")),
          /* @__PURE__ */ React.createElement("div", { className: "node-palette-grid" }, group.items.map((item) => /* @__PURE__ */ React.createElement(
            "button",
            {
              key: item.implementation,
              type: "button",
              className: "palette-node-card",
              draggable: item.draggable !== false,
              onDragStart: (event) => {
                event.dataTransfer.setData("application/xrtm-node-implementation", String(item.implementation || ""));
                event.dataTransfer.effectAllowed = "copy";
              },
              onClick: () => void addPaletteNode(item),
              disabled: Boolean(busy)
            },
            /* @__PURE__ */ React.createElement("strong", null, item.label || item.name),
            /* @__PURE__ */ React.createElement("span", null, item.kind),
            /* @__PURE__ */ React.createElement("small", null, item.summary || item.description)
          )))
        )) : /* @__PURE__ */ React.createElement("div", { className: "palette-empty-state" }, /* @__PURE__ */ React.createElement("strong", null, "No safe nodes match that search."), /* @__PURE__ */ React.createElement("span", null, "Try a kind, label, or implementation name such as router, scorer, or baseline."))))
      ));
    }
    function StudioDraftCanvasPanel() {
      return /* @__PURE__ */ React.createElement("section", { className: "playground-canvas-panel studio-canvas-panel" }, /* @__PURE__ */ React.createElement(
        WorkflowCanvasSurface,
        {
          canvas: activeCanvas,
          entry: String(activeGraph.entry || ""),
          selectedNodeName: inspectorMode === "node" ? selectedNodeName : "",
          selectedEdgeId: inspectorMode === "edge" ? selectedEdgeId : "",
          localPositions,
          edgeDraftFrom,
          onMoveNode: (name, position) => setLocalPositions((current) => ({ ...current, [name]: position })),
          onMoveEnd: (name, position) => void persistNodePosition(name, position),
          onSelectNode: selectNodeInspector,
          onSelectEdge: selectEdgeInspector,
          onSelectWorkflow: selectWorkflowInspector,
          onAddNodeFromPalette: (implementation, position) => void addPaletteNode(implementation, position),
          onCreateEdge: (from, to) => void createEdgeFromCanvas(from, to)
        }
      ));
    }
    function StudioDraftSidePanel() {
      return /* @__PURE__ */ React.createElement("div", { className: "live-trace-panel studio-side-panel authoring-grid" }, /* @__PURE__ */ React.createElement("div", { className: "studio-live-meta" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Studio"), /* @__PURE__ */ React.createElement("strong", null, studioDraftTitle)), /* @__PURE__ */ React.createElement("div", { className: "meta-row" }, /* @__PURE__ */ React.createElement(SourceBadge, { source: activeWorkflow?.source || "builtin" }), /* @__PURE__ */ React.createElement(StatusPill, { value: validationPillValue }), activeDraft?.revision != null ? /* @__PURE__ */ React.createElement("span", null, "Revision ", activeDraft.revision) : null)), /* @__PURE__ */ React.createElement("div", { className: "studio-rail-tabs", role: "tablist", "aria-label": "Studio side panel" }, /* @__PURE__ */ React.createElement(
        "button",
        {
          id: "studio-rail-tab-inspect",
          role: "tab",
          "aria-selected": studioRailMode === "inspect",
          "aria-controls": "studio-side-panel-inspect",
          tabIndex: studioRailMode === "inspect" ? 0 : -1,
          className: studioRailMode === "inspect" ? "secondary-button active" : "secondary-button",
          type: "button",
          onClick: () => setStudioRailMode("inspect")
        },
        "Inspector"
      ), /* @__PURE__ */ React.createElement(
        "button",
        {
          id: "studio-rail-tab-run",
          role: "tab",
          "aria-selected": studioRailMode === "run",
          "aria-controls": "studio-side-panel-run",
          tabIndex: studioRailMode === "run" ? 0 : -1,
          className: studioRailMode === "run" ? "secondary-button active" : "secondary-button",
          type: "button",
          onClick: () => setStudioRailMode("run")
        },
        "Run"
      ), /* @__PURE__ */ React.createElement(
        "button",
        {
          id: "studio-rail-tab-tools",
          role: "tab",
          "aria-selected": studioRailMode === "tools",
          "aria-controls": "studio-side-panel-tools",
          tabIndex: studioRailMode === "tools" ? 0 : -1,
          className: studioRailMode === "tools" ? "secondary-button active" : "secondary-button",
          type: "button",
          onClick: () => setStudioRailMode("tools")
        },
        "Tools"
      )), studioRailMode === "inspect" ? /* @__PURE__ */ React.createElement(
        "section",
        {
          id: "studio-side-panel-inspect",
          role: "tabpanel",
          "aria-labelledby": "studio-rail-tab-inspect",
          className: "surface-card section-stack"
        },
        /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, "Context inspector"), /* @__PURE__ */ React.createElement("p", null, inspectorMode === "workflow" ? "Edit supported workflow settings without leaving the draft IDE." : inspectorMode === "edge" ? selectedEdge ? `Inspect ${selectedEdge.from} \u2192 ${selectedEdge.to}.` : "Select an edge from the canvas or list." : selectedNode ? `Edit ${selectedNode.name} inline.` : "Select a node from the canvas to edit it.")), inspectorMode === "workflow" ? /* @__PURE__ */ React.createElement(StatusPill, { value: "workflow" }) : inspectorMode === "edge" ? /* @__PURE__ */ React.createElement(StatusPill, { value: selectedEdge?.read_only ? "read-only edge" : "edge" }) : selectedNode ? /* @__PURE__ */ React.createElement(StatusPill, { value: selectedNode.kind || "node" }) : null),
        inspectorMode === "workflow" ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("dl", { className: "context-list compact-context-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Workflow"), /* @__PURE__ */ React.createElement("dd", null, activeDraft?.draft_workflow_name || activeWorkflow?.name || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Entry"), /* @__PURE__ */ React.createElement("dd", null, activeGraph.entry || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Revision"), /* @__PURE__ */ React.createElement("dd", null, activeDraft?.revision ?? "\u2014"))), /* @__PURE__ */ React.createElement("div", { className: "inspector-form-grid" }, /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Title"), /* @__PURE__ */ React.createElement("input", { value: coreForm.title || "", onChange: (event) => setCoreForm((current) => ({ ...current, title: event.target.value })) })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Workflow kind"), /* @__PURE__ */ React.createElement("input", { value: coreForm.workflow_kind || "", onChange: (event) => setCoreForm((current) => ({ ...current, workflow_kind: event.target.value })), list: "studio-workflow-kind-options" }))), /* @__PURE__ */ React.createElement("datalist", { id: "studio-workflow-kind-options" }, (authoringCatalog.data?.workflow_kind_options || []).map((item) => /* @__PURE__ */ React.createElement("option", { key: item, value: item }))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Description"), /* @__PURE__ */ React.createElement("textarea", { className: "text-area-input", value: coreForm.description || "", onChange: (event) => setCoreForm((current) => ({ ...current, description: event.target.value })) })), /* @__PURE__ */ React.createElement(
          DensityDisclosure,
          {
            className: "studio-disclosure studio-inline-disclosure",
            title: "Runtime and run bounds",
            detail: "Keep provider, question limits, and model tuning nearby without crowding the default workflow overview."
          },
          /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Runtime provider"), /* @__PURE__ */ React.createElement("select", { value: coreForm.runtime_provider || "deterministic", onChange: (event) => setCoreForm((current) => ({ ...current, runtime_provider: event.target.value })) }, (authoringCatalog.data?.runtime_provider_options || []).map((item) => /* @__PURE__ */ React.createElement("option", { key: item, value: item }, item)))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Question limit"), /* @__PURE__ */ React.createElement("input", { type: "number", min: 1, max: 25, value: coreForm.questions_limit || "", onChange: (event) => setCoreForm((current) => ({ ...current, questions_limit: event.target.value })) }))),
          /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Runtime model"), /* @__PURE__ */ React.createElement("input", { value: coreForm.runtime_model || "", onChange: (event) => setCoreForm((current) => ({ ...current, runtime_model: event.target.value })), placeholder: "phi-4-mini" })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Max tokens"), /* @__PURE__ */ React.createElement("input", { type: "number", min: 1, value: coreForm.runtime_max_tokens || "", onChange: (event) => setCoreForm((current) => ({ ...current, runtime_max_tokens: event.target.value })) })))
        ), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: applyCoreFields, disabled: Boolean(busy) }, "Apply workflow fields")))) : inspectorMode === "edge" ? selectedEdge ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("dl", { className: "context-list compact-context-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "From"), /* @__PURE__ */ React.createElement("dd", null, selectedEdge.from || selectedEdge.source || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "To"), /* @__PURE__ */ React.createElement("dd", null, selectedEdge.to || selectedEdge.target || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Kind"), /* @__PURE__ */ React.createElement("dd", null, selectedEdge.kind || "edge")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Editable"), /* @__PURE__ */ React.createElement("dd", null, selectedEdge.read_only ? "No" : "Yes"))), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => void removeEdge(String(selectedEdge.from), String(selectedEdge.to)), disabled: Boolean(busy) || Boolean(selectedEdge.read_only) }, "Remove selected edge")) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No edge selected", body: "Pick an edge from the canvas curve or edge list to inspect it." }) : selectedNode ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("dl", { className: "context-list compact-context-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Implementation"), /* @__PURE__ */ React.createElement("dd", null, selectedNode.implementation || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Runtime"), /* @__PURE__ */ React.createElement("dd", null, selectedNode.runtime || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Entry"), /* @__PURE__ */ React.createElement("dd", null, selectedNode.is_entry ? "Yes" : "No"))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Description"), /* @__PURE__ */ React.createElement("textarea", { className: "text-area-input", value: nodeForm.description || "", onChange: (event) => setNodeForm((current) => ({ ...current, description: event.target.value })) })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Runtime label"), /* @__PURE__ */ React.createElement("input", { value: nodeForm.runtime || "", onChange: (event) => setNodeForm((current) => ({ ...current, runtime: event.target.value })), placeholder: "Optional runtime tag" })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Optional"), /* @__PURE__ */ React.createElement("select", { value: nodeForm.optional || "false", onChange: (event) => setNodeForm((current) => ({ ...current, optional: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "false" }, "false"), /* @__PURE__ */ React.createElement("option", { value: "true" }, "true"))), (selectedNode.aggregate_weights || []).map((item) => {
          const key = `weight:${String(item.name)}`;
          return /* @__PURE__ */ React.createElement("label", { key }, /* @__PURE__ */ React.createElement("span", null, item.name, " weight"), /* @__PURE__ */ React.createElement("input", { type: "number", min: 0, max: 100, value: nodeForm[key] || "", onChange: (event) => setNodeForm((current) => ({ ...current, [key]: event.target.value })) }));
        }), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: applyNodeUpdates, disabled: Boolean(busy) }, "Apply node changes"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => void setEntry(String(selectedNode.name)), disabled: Boolean(busy) || selectedNode.is_entry }, "Set as entry"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => setEdgeDraftFrom(String(selectedNode.name)), disabled: Boolean(busy) }, "Start edge here"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: removeSelectedNode, disabled: Boolean(busy) }, "Remove node"))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No node selected", body: "Pick a node from the canvas to edit its supported fields." })
      ) : null, studioRailMode === "run" ? /* @__PURE__ */ React.createElement(
        "section",
        {
          id: "studio-side-panel-run",
          role: "tabpanel",
          "aria-labelledby": "studio-rail-tab-run",
          className: "surface-card section-stack studio-publish-card"
        },
        /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, "Validate + run"), /* @__PURE__ */ React.createElement("p", null, "Use one control stack for validation, version snapshots, candidate runs, and compare handoff.")), /* @__PURE__ */ React.createElement(StatusPill, { value: validationPillValue })),
        /* @__PURE__ */ React.createElement(Message, { tone: validationStatus.tone, title: validationStatus.title, body: validationStatus.body }),
        validationFixes.length ? /* @__PURE__ */ React.createElement("ul", { className: "teaching-list" }, validationFixes.map((note) => /* @__PURE__ */ React.createElement("li", { key: note }, note))) : null,
        /* @__PURE__ */ React.createElement("section", { className: "next-step-card" }, /* @__PURE__ */ React.createElement("strong", null, nextStep.title), /* @__PURE__ */ React.createElement("p", null, nextStep.detail)),
        /* @__PURE__ */ React.createElement("div", { className: "action-stack compact-action-stack" }, /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: createVersionSnapshotFromDraft, disabled: Boolean(busy) }, "Save version snapshot"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: validateDraft, disabled: Boolean(busy) }, "Save + validate"), /* @__PURE__ */ React.createElement("button", { className: "primary-button", disabled: Boolean(busy) || runDisabled, onClick: runDraft }, "Run candidate"), activeDraft?.last_run_id ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(`/runs/${activeDraft.last_run_id}`) }, "Inspect candidate") : null, /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate("/versions") }, "Open Versions")),
        compareActions.length ? /* @__PURE__ */ React.createElement("div", { className: "action-stack compact-action-stack" }, compareActions.slice(0, 2).map((action, index) => /* @__PURE__ */ React.createElement("button", { key: action.href || action.label || index, className: index === 0 ? "primary-button" : "secondary-button", onClick: () => navigate(String(action.href || "/runs")) }, action.label))) : null
      ) : null, studioRailMode === "tools" ? /* @__PURE__ */ React.createElement(
        "section",
        {
          id: "studio-side-panel-tools",
          role: "tabpanel",
          "aria-labelledby": "studio-rail-tab-tools",
          className: "section-stack"
        },
        /* @__PURE__ */ React.createElement(
          DensityDisclosure,
          {
            className: "surface-card section-stack studio-disclosure",
            title: "Add safe node",
            detail: "Open the explicit add-node form only when palette click or drag-drop is not enough."
          },
          /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Node name"), /* @__PURE__ */ React.createElement("input", { value: addNodeForm.node_name || "", onChange: (event) => setAddNodeForm((current) => ({ ...current, node_name: event.target.value })), placeholder: "question_context_2" })),
          /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Implementation"), /* @__PURE__ */ React.createElement("select", { value: addNodeForm.implementation || "", onChange: (event) => setAddNodeForm((current) => ({ ...current, implementation: event.target.value })) }, nodeCatalog.map((item) => /* @__PURE__ */ React.createElement("option", { key: item.implementation, value: item.implementation }, item.name, " \xB7 ", item.kind)))),
          /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Incoming from"), /* @__PURE__ */ React.createElement("select", { value: addNodeForm.incoming_from || "", onChange: (event) => setAddNodeForm((current) => ({ ...current, incoming_from: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "" }, "None"), graphTargets.map((target) => /* @__PURE__ */ React.createElement("option", { key: target.name, value: target.name }, target.name)))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Outgoing to"), /* @__PURE__ */ React.createElement("select", { value: addNodeForm.outgoing_to || "", onChange: (event) => setAddNodeForm((current) => ({ ...current, outgoing_to: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "" }, "None"), graphTargets.map((target) => /* @__PURE__ */ React.createElement("option", { key: target.name, value: target.name }, target.name))))),
          /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Description"), /* @__PURE__ */ React.createElement("textarea", { className: "text-area-input", value: addNodeForm.description || "", onChange: (event) => setAddNodeForm((current) => ({ ...current, description: event.target.value })) })),
          /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Runtime label"), /* @__PURE__ */ React.createElement("input", { value: addNodeForm.runtime || "", onChange: (event) => setAddNodeForm((current) => ({ ...current, runtime: event.target.value })), placeholder: "Optional runtime tag" })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Optional"), /* @__PURE__ */ React.createElement("select", { value: addNodeForm.optional || "false", onChange: (event) => setAddNodeForm((current) => ({ ...current, optional: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "false" }, "false"), /* @__PURE__ */ React.createElement("option", { value: "true" }, "true")))),
          /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => void addNode(), disabled: Boolean(busy) || !addNodeForm.node_name || !addNodeForm.implementation }, "Add node")
        ),
        /* @__PURE__ */ React.createElement(
          DensityDisclosure,
          {
            className: "surface-card section-stack studio-disclosure",
            title: "Edges and graph context",
            detail: "Keep edge wiring, parallel groups, and conditional routes behind one secondary disclosure."
          },
          /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "From"), /* @__PURE__ */ React.createElement("select", { value: addEdgeForm.from_node || "", onChange: (event) => setAddEdgeForm((current) => ({ ...current, from_node: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "" }, "Select"), graphTargets.map((target) => /* @__PURE__ */ React.createElement("option", { key: target.name, value: target.name }, target.name)))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "To"), /* @__PURE__ */ React.createElement("select", { value: addEdgeForm.to_node || "", onChange: (event) => setAddEdgeForm((current) => ({ ...current, to_node: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "" }, "Select"), graphTargets.map((target) => /* @__PURE__ */ React.createElement("option", { key: target.name, value: target.name }, target.name))))),
          /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => void addEdge(), disabled: Boolean(busy) || !addEdgeForm.from_node || !addEdgeForm.to_node }, "Add edge"),
          /* @__PURE__ */ React.createElement("div", { className: "edge-list" }, graphEdges.map((edge, index) => /* @__PURE__ */ React.createElement("div", { key: `${edge.from}-${edge.to}-${index}`, className: studioEdgeKey(edge) === selectedEdgeId ? "edge-row selected" : "edge-row" }, /* @__PURE__ */ React.createElement(
            "button",
            {
              className: "edge-row-button",
              type: "button",
              "aria-pressed": studioEdgeKey(edge) === selectedEdgeId,
              onClick: () => selectEdgeInspector(edge)
            },
            /* @__PURE__ */ React.createElement("span", { className: "table-primary" }, edge.from),
            /* @__PURE__ */ React.createElement("span", { className: "table-secondary" }, edge.to)
          ), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => void removeEdge(String(edge.from), String(edge.to)), disabled: Boolean(busy) }, "Remove")))),
          Object.keys(activeGraph.parallel_groups || {}).length || Object.keys(activeGraph.conditional_routes || {}).length ? /* @__PURE__ */ React.createElement("div", { className: "guidance-section minor-divider" }, Object.keys(activeGraph.parallel_groups || {}).length ? /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, "Parallel groups"), /* @__PURE__ */ React.createElement("ul", { className: "guidance-list compact-list" }, Object.entries(activeGraph.parallel_groups).map(([name, members]) => /* @__PURE__ */ React.createElement("li", { key: name }, /* @__PURE__ */ React.createElement("strong", null, name), /* @__PURE__ */ React.createElement("span", null, Array.isArray(members) ? members.join(", ") : ""))))) : null, Object.keys(activeGraph.conditional_routes || {}).length ? /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, "Conditional routes"), /* @__PURE__ */ React.createElement("ul", { className: "guidance-list compact-list" }, Object.entries(activeGraph.conditional_routes).map(([name, route2]) => /* @__PURE__ */ React.createElement("li", { key: name }, /* @__PURE__ */ React.createElement("strong", null, name), /* @__PURE__ */ React.createElement("span", null, JSON.stringify(route2)))))) : null) : null
        )
      ) : null);
    }
    function StudioDraftWorkspaceAdapter() {
      return /* @__PURE__ */ React.createElement(
        WorkspacePanelAdapter,
        {
          frameClassName: "playground-live-workspace studio-live-workspace studio-ide-panel",
          leftPanel: StudioDraftPalettePanel(),
          centerPanel: StudioDraftCanvasPanel(),
          rightPanel: StudioDraftSidePanel()
        }
      );
    }
    function LegacyWorkbenchIdePanel() {
      return /* @__PURE__ */ React.createElement("section", { className: "panel section-stack studio-ide-panel" }, /* @__PURE__ */ React.createElement("div", { className: "section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "3. Studio graph IDE"), /* @__PURE__ */ React.createElement("h3", null, "Drag nodes, drop safe palette items, select nodes/edges, then validate")), /* @__PURE__ */ React.createElement("p", { className: "section-copy" }, "Node positions persist with the draft layout while graph topology and configuration stay inside the shared authoring contract.")), !draftId ? isStudio && studioIntent && studioBootstrapState !== "failed" ? /* @__PURE__ */ React.createElement(LoadingCard, { label: "Opening Studio graph IDE" }) : /* @__PURE__ */ React.createElement(EmptyState, { title: "Create a draft to unlock graph authoring", body: "The canvas becomes editable as soon as you open a draft session." }) : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("section", { className: "node-palette", "aria-label": "Studio node palette" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Quick add"), /* @__PURE__ */ React.createElement("p", null, "Search or insert one safe node first. Open the grouped library only when the quick path is not enough.")), /* @__PURE__ */ React.createElement("div", { className: "node-palette-toolbar" }, /* @__PURE__ */ React.createElement("label", { className: "node-palette-search" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Quick insert"), /* @__PURE__ */ React.createElement(
        "input",
        {
          type: "search",
          value: paletteQuery,
          onChange: (event) => setPaletteQuery(event.target.value),
          onKeyDown: (event) => {
            if (event.key === "Enter" && paletteTopMatch && !busy) {
              event.preventDefault();
              void addPaletteTopMatch();
            }
          },
          placeholder: "Search nodes, then press Enter to insert the top match",
          "aria-label": "Search studio node palette"
        }
      )), /* @__PURE__ */ React.createElement("div", { className: "node-palette-actions" }, /* @__PURE__ */ React.createElement("button", { className: "secondary-button", type: "button", onClick: () => void addPaletteTopMatch(), disabled: Boolean(busy) || !paletteTopMatch }, paletteTopMatch ? `Insert ${paletteTopMatch.label || paletteTopMatch.name}` : "No matching node"))), /* @__PURE__ */ React.createElement(
        "details",
        {
          className: "density-disclosure studio-library-disclosure",
          open: normalizedPaletteQuery ? true : paletteLibraryOpen || void 0,
          onToggle: (event) => {
            if (normalizedPaletteQuery) return;
            setPaletteLibraryOpen(event.currentTarget.open);
          }
        },
        /* @__PURE__ */ React.createElement("summary", null, /* @__PURE__ */ React.createElement("div", { className: "density-disclosure-copy" }, /* @__PURE__ */ React.createElement("strong", null, normalizedPaletteQuery ? `${filteredPaletteItems.length} matching nodes` : `Browse all ${nodeCatalog.length} safe nodes`), /* @__PURE__ */ React.createElement("p", null, normalizedPaletteQuery ? paletteTopMatch ? `Enter inserts ${paletteTopMatch.label || paletteTopMatch.name}.` : "Adjust the search to find another node." : "Keep the full library collapsed until you need the grouped catalog."))),
        /* @__PURE__ */ React.createElement("div", { className: "density-disclosure-body" }, /* @__PURE__ */ React.createElement("p", { className: "helper-text node-palette-status" }, normalizedPaletteQuery ? `${filteredPaletteItems.length} of ${nodeCatalog.length} nodes match the current search.` : `Grouped library \xB7 ${nodeCatalog.length} safe nodes available by category.`), /* @__PURE__ */ React.createElement("div", { className: "node-palette-scroll" }, filteredPaletteGroups.length ? filteredPaletteGroups.map((group, index) => /* @__PURE__ */ React.createElement(
          "details",
          {
            key: group.key,
            className: "palette-group-card",
            open: Boolean(normalizedPaletteQuery) || index === 0 || void 0
          },
          /* @__PURE__ */ React.createElement("summary", null, /* @__PURE__ */ React.createElement("span", null, group.label), /* @__PURE__ */ React.createElement("small", null, group.items.length, " nodes")),
          /* @__PURE__ */ React.createElement("div", { className: "node-palette-grid" }, group.items.map((item) => /* @__PURE__ */ React.createElement(
            "button",
            {
              key: item.implementation,
              type: "button",
              className: "palette-node-card",
              draggable: item.draggable !== false,
              onDragStart: (event) => {
                event.dataTransfer.setData("application/xrtm-node-implementation", String(item.implementation || ""));
                event.dataTransfer.effectAllowed = "copy";
              },
              onClick: () => void addPaletteNode(item),
              disabled: Boolean(busy)
            },
            /* @__PURE__ */ React.createElement("strong", null, item.label || item.name),
            /* @__PURE__ */ React.createElement("span", null, item.kind),
            /* @__PURE__ */ React.createElement("small", null, item.summary || item.description)
          )))
        )) : /* @__PURE__ */ React.createElement("div", { className: "palette-empty-state" }, /* @__PURE__ */ React.createElement("strong", null, "No safe nodes match that search."), /* @__PURE__ */ React.createElement("span", null, "Try a kind, label, or implementation name such as router, scorer, or baseline."))))
      )), /* @__PURE__ */ React.createElement(
        WorkflowCanvasSurface,
        {
          canvas: activeCanvas,
          entry: String(activeGraph.entry || ""),
          selectedNodeName: inspectorMode === "node" ? selectedNodeName : "",
          selectedEdgeId: inspectorMode === "edge" ? selectedEdgeId : "",
          localPositions,
          edgeDraftFrom,
          onMoveNode: (name, position) => setLocalPositions((current) => ({ ...current, [name]: position })),
          onMoveEnd: (name, position) => void persistNodePosition(name, position),
          onSelectNode: selectNodeInspector,
          onSelectEdge: selectEdgeInspector,
          onSelectWorkflow: selectWorkflowInspector,
          onAddNodeFromPalette: (implementation, position) => void addPaletteNode(implementation, position),
          onCreateEdge: (from, to) => void createEdgeFromCanvas(from, to)
        }
      ), /* @__PURE__ */ React.createElement("div", { className: "three-column-grid authoring-grid" }, /* @__PURE__ */ React.createElement("section", { id: "studio-side-panel-inspect", className: "surface-card section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, "Context inspector"), /* @__PURE__ */ React.createElement("p", null, inspectorMode === "workflow" ? "Workflow config uses the same safe mutation action as the field form above." : inspectorMode === "edge" ? selectedEdge ? `Inspect ${selectedEdge.from} \u2192 ${selectedEdge.to}.` : "Select an edge from the canvas or list." : selectedNode ? `Edit ${selectedNode.name} inline.` : "Select a node from the canvas to edit it.")), inspectorMode === "workflow" ? /* @__PURE__ */ React.createElement(StatusPill, { value: "workflow" }) : inspectorMode === "edge" ? /* @__PURE__ */ React.createElement(StatusPill, { value: selectedEdge?.read_only ? "read-only edge" : "edge" }) : selectedNode ? /* @__PURE__ */ React.createElement(StatusPill, { value: selectedNode.kind || "node" }) : null), inspectorMode === "workflow" ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("dl", { className: "context-list compact-context-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Workflow"), /* @__PURE__ */ React.createElement("dd", null, activeDraft?.draft_workflow_name || activeWorkflow?.name || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Entry"), /* @__PURE__ */ React.createElement("dd", null, activeGraph.entry || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Revision"), /* @__PURE__ */ React.createElement("dd", null, activeDraft?.revision ?? "\u2014"))), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => document.getElementById("workflow-config-fields")?.scrollIntoView({ behavior: "smooth", block: "start" }) }, "Jump to workflow config")) : inspectorMode === "edge" ? selectedEdge ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("dl", { className: "context-list compact-context-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "From"), /* @__PURE__ */ React.createElement("dd", null, selectedEdge.from || selectedEdge.source || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "To"), /* @__PURE__ */ React.createElement("dd", null, selectedEdge.to || selectedEdge.target || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Kind"), /* @__PURE__ */ React.createElement("dd", null, selectedEdge.kind || "edge")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Editable"), /* @__PURE__ */ React.createElement("dd", null, selectedEdge.read_only ? "No" : "Yes"))), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => void removeEdge(String(selectedEdge.from), String(selectedEdge.to)), disabled: Boolean(busy) || Boolean(selectedEdge.read_only) }, "Remove selected edge")) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No edge selected", body: "Pick an edge from the canvas curve or edge list to inspect it." }) : selectedNode ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("dl", { className: "context-list compact-context-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Implementation"), /* @__PURE__ */ React.createElement("dd", null, selectedNode.implementation || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Runtime"), /* @__PURE__ */ React.createElement("dd", null, selectedNode.runtime || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Entry"), /* @__PURE__ */ React.createElement("dd", null, selectedNode.is_entry ? "Yes" : "No"))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Description"), /* @__PURE__ */ React.createElement("textarea", { className: "text-area-input", value: nodeForm.description || "", onChange: (event) => setNodeForm((current) => ({ ...current, description: event.target.value })) })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Runtime label"), /* @__PURE__ */ React.createElement("input", { value: nodeForm.runtime || "", onChange: (event) => setNodeForm((current) => ({ ...current, runtime: event.target.value })), placeholder: "Optional runtime tag" })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Optional"), /* @__PURE__ */ React.createElement("select", { value: nodeForm.optional || "false", onChange: (event) => setNodeForm((current) => ({ ...current, optional: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "false" }, "false"), /* @__PURE__ */ React.createElement("option", { value: "true" }, "true"))), (selectedNode.aggregate_weights || []).map((item) => {
        const key = `weight:${String(item.name)}`;
        return /* @__PURE__ */ React.createElement("label", { key }, /* @__PURE__ */ React.createElement("span", null, item.name, " weight"), /* @__PURE__ */ React.createElement("input", { type: "number", min: 0, max: 100, value: nodeForm[key] || "", onChange: (event) => setNodeForm((current) => ({ ...current, [key]: event.target.value })) }));
      }), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: applyNodeUpdates, disabled: Boolean(busy) }, "Apply node changes"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => void setEntry(String(selectedNode.name)), disabled: Boolean(busy) || selectedNode.is_entry }, "Set as entry"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => setEdgeDraftFrom(String(selectedNode.name)), disabled: Boolean(busy) }, "Start edge here"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: removeSelectedNode, disabled: Boolean(busy) }, "Remove node"))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No node selected", body: "Pick a node from the canvas to edit its supported fields." })), /* @__PURE__ */ React.createElement("section", { id: "studio-side-panel-tools", className: "section-stack" }, /* @__PURE__ */ React.createElement(
        DensityDisclosure,
        {
          className: "surface-card section-stack studio-disclosure",
          title: "Add safe node",
          detail: "Open the explicit add-node form only when palette click or drag-drop is not enough."
        },
        /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Node name"), /* @__PURE__ */ React.createElement("input", { value: addNodeForm.node_name || "", onChange: (event) => setAddNodeForm((current) => ({ ...current, node_name: event.target.value })), placeholder: "question_context_2" })),
        /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Implementation"), /* @__PURE__ */ React.createElement("select", { value: addNodeForm.implementation || "", onChange: (event) => setAddNodeForm((current) => ({ ...current, implementation: event.target.value })) }, nodeCatalog.map((item) => /* @__PURE__ */ React.createElement("option", { key: item.implementation, value: item.implementation }, item.name, " \xB7 ", item.kind)))),
        /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Incoming from"), /* @__PURE__ */ React.createElement("select", { value: addNodeForm.incoming_from || "", onChange: (event) => setAddNodeForm((current) => ({ ...current, incoming_from: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "" }, "None"), graphTargets.map((target) => /* @__PURE__ */ React.createElement("option", { key: target.name, value: target.name }, target.name)))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Outgoing to"), /* @__PURE__ */ React.createElement("select", { value: addNodeForm.outgoing_to || "", onChange: (event) => setAddNodeForm((current) => ({ ...current, outgoing_to: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "" }, "None"), graphTargets.map((target) => /* @__PURE__ */ React.createElement("option", { key: target.name, value: target.name }, target.name))))),
        /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Description"), /* @__PURE__ */ React.createElement("textarea", { className: "text-area-input", value: addNodeForm.description || "", onChange: (event) => setAddNodeForm((current) => ({ ...current, description: event.target.value })) })),
        /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Runtime label"), /* @__PURE__ */ React.createElement("input", { value: addNodeForm.runtime || "", onChange: (event) => setAddNodeForm((current) => ({ ...current, runtime: event.target.value })), placeholder: "Optional runtime tag" })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Optional"), /* @__PURE__ */ React.createElement("select", { value: addNodeForm.optional || "false", onChange: (event) => setAddNodeForm((current) => ({ ...current, optional: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "false" }, "false"), /* @__PURE__ */ React.createElement("option", { value: "true" }, "true")))),
        /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => void addNode(), disabled: Boolean(busy) || !addNodeForm.node_name || !addNodeForm.implementation }, "Add node")
      ), /* @__PURE__ */ React.createElement(
        DensityDisclosure,
        {
          className: "surface-card section-stack studio-disclosure",
          title: "Edges and graph context",
          detail: "Keep edge wiring, parallel groups, and conditional routes behind one secondary disclosure."
        },
        /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "From"), /* @__PURE__ */ React.createElement("select", { value: addEdgeForm.from_node || "", onChange: (event) => setAddEdgeForm((current) => ({ ...current, from_node: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "" }, "Select"), graphTargets.map((target) => /* @__PURE__ */ React.createElement("option", { key: target.name, value: target.name }, target.name)))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "To"), /* @__PURE__ */ React.createElement("select", { value: addEdgeForm.to_node || "", onChange: (event) => setAddEdgeForm((current) => ({ ...current, to_node: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "" }, "Select"), graphTargets.map((target) => /* @__PURE__ */ React.createElement("option", { key: target.name, value: target.name }, target.name))))),
        /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => void addEdge(), disabled: Boolean(busy) || !addEdgeForm.from_node || !addEdgeForm.to_node }, "Add edge"),
        /* @__PURE__ */ React.createElement("div", { className: "edge-list" }, graphEdges.map((edge, index) => /* @__PURE__ */ React.createElement("div", { key: `${edge.from}-${edge.to}-${index}`, className: studioEdgeKey(edge) === selectedEdgeId ? "edge-row selected" : "edge-row" }, /* @__PURE__ */ React.createElement(
          "button",
          {
            className: "edge-row-button",
            type: "button",
            "aria-pressed": studioEdgeKey(edge) === selectedEdgeId,
            onClick: () => selectEdgeInspector(edge)
          },
          /* @__PURE__ */ React.createElement("span", { className: "table-primary" }, edge.from),
          /* @__PURE__ */ React.createElement("span", { className: "table-secondary" }, edge.to)
        ), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => void removeEdge(String(edge.from), String(edge.to)), disabled: Boolean(busy) }, "Remove")))),
        Object.keys(activeGraph.parallel_groups || {}).length || Object.keys(activeGraph.conditional_routes || {}).length ? /* @__PURE__ */ React.createElement("div", { className: "guidance-section minor-divider" }, Object.keys(activeGraph.parallel_groups || {}).length ? /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, "Parallel groups"), /* @__PURE__ */ React.createElement("ul", { className: "guidance-list compact-list" }, Object.entries(activeGraph.parallel_groups).map(([name, members]) => /* @__PURE__ */ React.createElement("li", { key: name }, /* @__PURE__ */ React.createElement("strong", null, name), /* @__PURE__ */ React.createElement("span", null, Array.isArray(members) ? members.join(", ") : ""))))) : null, Object.keys(activeGraph.conditional_routes || {}).length ? /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, "Conditional routes"), /* @__PURE__ */ React.createElement("ul", { className: "guidance-list compact-list" }, Object.entries(activeGraph.conditional_routes).map(([name, route2]) => /* @__PURE__ */ React.createElement("li", { key: name }, /* @__PURE__ */ React.createElement("strong", null, name), /* @__PURE__ */ React.createElement("span", null, JSON.stringify(route2)))))) : null) : null
      )))));
    }
    return /* @__PURE__ */ React.createElement(
      "main",
      {
        className: isStudio ? `workbench-layout studio-workspace${showStudioDraftIde ? " studio-draft-mode" : ""}` : "workbench-layout",
        style: showStudioDraftIde ? { gridTemplateColumns: "minmax(0, 1fr)" } : void 0
      },
      showWorkbenchSetupRail ? /* @__PURE__ */ React.createElement("aside", { className: "panel step-panel" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Journey"), /* @__PURE__ */ React.createElement("h2", null, "Inspect \u2192 create \u2192 author"), /* @__PURE__ */ React.createElement("ol", { className: "step-list step-rail" }, stepState.map((step) => /* @__PURE__ */ React.createElement("li", { key: step.key, className: `step-item step-${step.state || "upcoming"}${step.locked ? " locked" : ""}` }, /* @__PURE__ */ React.createElement("div", { className: "step-head" }, /* @__PURE__ */ React.createElement("strong", null, step.label), /* @__PURE__ */ React.createElement("span", { className: `step-status ${step.state || "upcoming"}` }, stepBadgeLabel(step))), /* @__PURE__ */ React.createElement("span", null, step.description))))) : null,
      /* @__PURE__ */ React.createElement("section", { className: "workbench-main" }, workflow.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Workflow unavailable", body: workflow.error }) : null, draft.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Draft unavailable", body: draft.error }) : null, workflows.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Workflow catalog unavailable", body: workflows.error }) : null, authoringCatalog.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Authoring catalog unavailable", body: authoringCatalog.error }) : null, actionNotice ? /* @__PURE__ */ React.createElement(Message, { tone: actionNotice.tone, title: actionNotice.title, body: actionNotice.body }) : null, busy ? /* @__PURE__ */ React.createElement(LoadingCard, { label: busy }) : null, draftId && draft.loading && !draft.data ? /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading draft" }) : null, !draftId && (workflow.loading || authoringCatalog.loading) && !workflow.data ? /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading workflow authoring surface" }) : null, showStudioSetup ? /* @__PURE__ */ React.createElement("section", { className: "panel hero-panel workbench-hero" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, surfaceLabel), /* @__PURE__ */ React.createElement("h2", null, draftId ? "Drag-drop the bounded workflow graph IDE" : "Create a new authored workflow or clone one into a local draft"), /* @__PURE__ */ React.createElement("p", null, draftId ? isStudio ? "Move nodes locally, drag safe palette nodes onto the canvas, create/remove edges, edit supported config, validate, save, and run through the Studio API without arbitrary plugin or code editing." : "The legacy workbench route stays compatible with the same safe authoring backend while Studio is the primary graph IDE surface." : isStudio ? "Choose a workflow, starter template, or scratch path to open a local draft in the graph IDE. Resume stays available without duplicating the editor inside setup." : "Start from scratch, a template, or an existing workflow. Draft state stays local and resumable while the reusable workflow file remains coherent on disk."), /* @__PURE__ */ React.createElement("div", { className: "meta-row" }, /* @__PURE__ */ React.createElement(SourceBadge, { source: activeWorkflow?.source || "builtin" }), activeDraft?.creation_mode ? /* @__PURE__ */ React.createElement("span", null, "Mode: ", activeDraft.creation_mode) : null, activeDraft?.draft_workflow_name ? /* @__PURE__ */ React.createElement("span", null, "Draft: ", activeDraft.draft_workflow_name) : null, activeDraft?.baseline_run_id ? /* @__PURE__ */ React.createElement("span", null, "Baseline: ", activeDraft.baseline_run_id) : overviewLatestRun?.run_id ? /* @__PURE__ */ React.createElement("span", null, "Suggested baseline: ", overviewLatestRun.run_id) : null, activeDraft?.last_run_id ? /* @__PURE__ */ React.createElement("span", null, "Candidate: ", activeDraft.last_run_id) : null), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, studioResumeTarget ? /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => navigate(studioResumeTarget.href) }, studioResumeTarget.label) : null, overviewLatestRun?.run_id ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(`/runs/${overviewLatestRun.run_id}`) }, "Inspect latest run") : /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate("/runs") }, "Browse runs"), activeDraft?.last_run_id ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(`/runs/${activeDraft.last_run_id}`) }, "Inspect candidate run") : null)) : null, showStudioSetup ? /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, isStudio ? "Start here" : "1. Create draft"), /* @__PURE__ */ React.createElement("h3", null, isStudio ? "Create or resume a local Studio draft" : "Start from scratch, template, or clone")), /* @__PURE__ */ React.createElement("p", { className: "section-copy" }, isStudio ? "Studio setup is only the entry surface. Once a draft opens, workflow fields, graph editing, validation, and run actions stay inside the full editor." : "Creation routes all flow through the shared backend authoring service and still land in the local draft + workflow file model.")), /* @__PURE__ */ React.createElement("div", { className: "creation-mode-row" }, creationModes.map((mode) => /* @__PURE__ */ React.createElement(
        "button",
        {
          key: mode.key,
          className: creationMode === mode.key ? "workflow-tile active" : "workflow-tile",
          onClick: () => setCreationMode(String(mode.key || "clone")),
          type: "button"
        },
        /* @__PURE__ */ React.createElement("strong", null, mode.label),
        /* @__PURE__ */ React.createElement("span", { className: "workflow-note" }, mode.detail)
      ))), /* @__PURE__ */ React.createElement("div", { className: "split-grid" }, /* @__PURE__ */ React.createElement("section", { className: "surface-card section-stack" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Draft workflow name"), /* @__PURE__ */ React.createElement("input", { value: createForm.draft_workflow_name || "", onChange: (event) => setCreateForm((current) => ({ ...current, draft_workflow_name: event.target.value })), placeholder: "my-authored-workflow" })), creationMode === "clone" ? /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Source workflow"), /* @__PURE__ */ React.createElement("select", { value: createForm.source_workflow_name || selectedWorkflow || "", onChange: (event) => setCreateForm((current) => ({ ...current, source_workflow_name: event.target.value })) }, (workflows.data?.items || []).map((item) => /* @__PURE__ */ React.createElement("option", { key: item.name, value: item.name }, item.title || item.name)))) : null, creationMode === "template" ? /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Starter template"), /* @__PURE__ */ React.createElement("select", { value: createForm.template_id || "", onChange: (event) => setCreateForm((current) => ({ ...current, template_id: event.target.value })) }, templates.map((item) => /* @__PURE__ */ React.createElement("option", { key: item.template_id, value: item.template_id }, item.title)))) : null, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Title"), /* @__PURE__ */ React.createElement("input", { value: createForm.title || "", onChange: (event) => setCreateForm((current) => ({ ...current, title: event.target.value })), placeholder: "Optional display title" })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Description"), /* @__PURE__ */ React.createElement("textarea", { className: "text-area-input", value: createForm.description || "", onChange: (event) => setCreateForm((current) => ({ ...current, description: event.target.value })), placeholder: "Optional authoring summary" })), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: createDraftFromMode, disabled: Boolean(busy) || creationDisabled }, "Create draft"), studioResumeTarget ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(studioResumeTarget.href) }, studioResumeTarget.label) : null, !draftId && activeWorkflow?.name ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(`/workflows/${encodeURIComponent(activeWorkflow.name)}`) }, "Open workflow detail") : null)), /* @__PURE__ */ React.createElement("section", { className: "surface-card section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, activeWorkflow?.title || activeWorkflow?.name || selectedWorkflow), /* @__PURE__ */ React.createElement("p", null, activeWorkflow?.description || "Select a workflow or choose a starter mode.")), /* @__PURE__ */ React.createElement(SourceBadge, { source: activeWorkflow?.source || "builtin" })), studioResumeTarget ? /* @__PURE__ */ React.createElement("div", { className: "compact-action-stack" }, /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "A local draft is already available. Resume it directly or create a new draft from the selected workflow or template."), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(studioResumeTarget.href) }, studioResumeTarget.label)) : activeDraft ? /* @__PURE__ */ React.createElement("dl", { className: "context-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Draft mode"), /* @__PURE__ */ React.createElement("dd", null, activeDraft.creation_mode || "clone")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Source"), /* @__PURE__ */ React.createElement("dd", null, activeDraft.source_workflow_name || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Local workflow"), /* @__PURE__ */ React.createElement("dd", null, activeDraft.draft_workflow_name || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Status"), /* @__PURE__ */ React.createElement("dd", null, activeDraft.status || "\u2014"))) : activeWorkflow ? /* @__PURE__ */ React.createElement("dl", { className: "context-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Workflow kind"), /* @__PURE__ */ React.createElement("dd", null, activeWorkflow.workflow_kind || activeWorkflow.kind || "workflow")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Questions"), /* @__PURE__ */ React.createElement("dd", null, activeWorkflow.question_limit || workflow.data?.blueprint?.questions?.limit || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Runtime"), /* @__PURE__ */ React.createElement("dd", null, activeWorkflow.runtime_provider || workflow.data?.blueprint?.runtime?.provider || "deterministic")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Action"), /* @__PURE__ */ React.createElement("dd", null, creationMode === "clone" ? "Clone this workflow into a local authored draft." : creationMode === "template" ? "Create a new workflow from the selected starter template." : "Create a fresh safe starter workflow and begin authoring."))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "Select a workflow", body: isStudio ? "Studio will show the current workflow summary here before you create a draft." : "The workbench will show the current workflow summary here before you create a draft." }))), /* @__PURE__ */ React.createElement("div", { className: "workflow-list workflow-catalog" }, (workflows.data?.items || []).map((item) => /* @__PURE__ */ React.createElement(
        "button",
        {
          key: item.name,
          className: item.name === activeWorkflow?.name ? "workflow-tile active" : "workflow-tile",
          onClick: () => navigate(`${surfaceBase}?workflow=${encodeURIComponent(item.name)}`),
          type: "button"
        },
        /* @__PURE__ */ React.createElement("div", { className: "workflow-tile-head" }, /* @__PURE__ */ React.createElement("strong", null, item.title), /* @__PURE__ */ React.createElement(SourceBadge, { source: item.source })),
        /* @__PURE__ */ React.createElement("span", null, item.name),
        /* @__PURE__ */ React.createElement("span", { className: "workflow-note" }, item.source === "builtin" ? "Clone to author visually" : "Open a draft session for this local workflow")
      )))) : null, showWorkbenchFieldSetup ? /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "2. Workflow fields"), /* @__PURE__ */ React.createElement("h3", null, "Edit supported core fields through the shared authoring layer")), /* @__PURE__ */ React.createElement("p", { className: "section-copy" }, "Title, description, workflow kind, bounded runtime settings, scoring, and artifact toggles stay inside the safe product contract.")), !draftId ? /* @__PURE__ */ React.createElement(EmptyState, { title: "Create a draft to unlock field editing", body: "Once a draft exists, this form edits the authored workflow fields that the shared backend service supports." }) : /* @__PURE__ */ React.createElement("div", { className: "form-grid guided-form" }, /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Title"), /* @__PURE__ */ React.createElement("input", { value: coreForm.title || "", onChange: (event) => setCoreForm((current) => ({ ...current, title: event.target.value })) })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Workflow kind"), /* @__PURE__ */ React.createElement("input", { value: coreForm.workflow_kind || "", onChange: (event) => setCoreForm((current) => ({ ...current, workflow_kind: event.target.value })), list: "workflow-kind-options" }))), /* @__PURE__ */ React.createElement("datalist", { id: "workflow-kind-options" }, (authoringCatalog.data?.workflow_kind_options || []).map((item) => /* @__PURE__ */ React.createElement("option", { key: item, value: item }))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Description"), /* @__PURE__ */ React.createElement("textarea", { className: "text-area-input", value: coreForm.description || "", onChange: (event) => setCoreForm((current) => ({ ...current, description: event.target.value })) })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Tags"), /* @__PURE__ */ React.createElement("input", { value: coreForm.tags || "", onChange: (event) => setCoreForm((current) => ({ ...current, tags: event.target.value })), placeholder: "starter, local, benchmark" })), /* @__PURE__ */ React.createElement("div", { className: "three-column-grid compact-form-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Questions limit"), /* @__PURE__ */ React.createElement("input", { type: "number", min: 1, max: 25, value: coreForm.questions_limit || "", onChange: (event) => setCoreForm((current) => ({ ...current, questions_limit: event.target.value })) })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Runtime provider"), /* @__PURE__ */ React.createElement("select", { value: coreForm.runtime_provider || "deterministic", onChange: (event) => setCoreForm((current) => ({ ...current, runtime_provider: event.target.value })) }, (authoringCatalog.data?.runtime_provider_options || []).map((item) => /* @__PURE__ */ React.createElement("option", { key: item, value: item }, item)))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Max tokens"), /* @__PURE__ */ React.createElement("input", { type: "number", min: 1, value: coreForm.runtime_max_tokens || "", onChange: (event) => setCoreForm((current) => ({ ...current, runtime_max_tokens: event.target.value })) }))), /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Runtime base URL"), /* @__PURE__ */ React.createElement("input", { value: coreForm.runtime_base_url || "", onChange: (event) => setCoreForm((current) => ({ ...current, runtime_base_url: event.target.value })), placeholder: "http://127.0.0.1:11434/v1" })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Runtime model"), /* @__PURE__ */ React.createElement("input", { value: coreForm.runtime_model || "", onChange: (event) => setCoreForm((current) => ({ ...current, runtime_model: event.target.value })), placeholder: "phi-4-mini" }))), /* @__PURE__ */ React.createElement("div", { className: "three-column-grid compact-form-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Write HTML report"), /* @__PURE__ */ React.createElement("select", { value: coreForm.artifacts_write_report || "true", onChange: (event) => setCoreForm((current) => ({ ...current, artifacts_write_report: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "true" }, "true"), /* @__PURE__ */ React.createElement("option", { value: "false" }, "false"))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Write blueprint copy"), /* @__PURE__ */ React.createElement("select", { value: coreForm.artifacts_write_blueprint_copy || "true", onChange: (event) => setCoreForm((current) => ({ ...current, artifacts_write_blueprint_copy: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "true" }, "true"), /* @__PURE__ */ React.createElement("option", { value: "false" }, "false"))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Write graph trace"), /* @__PURE__ */ React.createElement("select", { value: coreForm.artifacts_write_graph_trace || "true", onChange: (event) => setCoreForm((current) => ({ ...current, artifacts_write_graph_trace: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "true" }, "true"), /* @__PURE__ */ React.createElement("option", { value: "false" }, "false")))), /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Write eval"), /* @__PURE__ */ React.createElement("select", { value: coreForm.scoring_write_eval || "true", onChange: (event) => setCoreForm((current) => ({ ...current, scoring_write_eval: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "true" }, "true"), /* @__PURE__ */ React.createElement("option", { value: "false" }, "false"))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Write train backtest"), /* @__PURE__ */ React.createElement("select", { value: coreForm.scoring_write_train_backtest || "true", onChange: (event) => setCoreForm((current) => ({ ...current, scoring_write_train_backtest: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "true" }, "true"), /* @__PURE__ */ React.createElement("option", { value: "false" }, "false")))), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: applyCoreFields, disabled: Boolean(busy) }, "Apply workflow fields")))) : null, showWorkbenchIdePanel ? showStudioDraftIde ? /* @__PURE__ */ React.createElement(
        WorkspaceModeShell,
        {
          mode: "studio",
          navigate,
          studioHref: studioModeHref,
          playgroundHref: playgroundModeHref
        },
        StudioDraftWorkspaceAdapter()
      ) : LegacyWorkbenchIdePanel() : null, showWorkbenchFieldSetup ? /* @__PURE__ */ React.createElement("section", { className: "panel" }, /* @__PURE__ */ React.createElement("div", { className: "section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "4. Save, validate + run"), /* @__PURE__ */ React.createElement("h3", null, "Save/validate inline, then run only when the authored draft is safe")), /* @__PURE__ */ React.createElement("p", { className: "section-copy" }, "Studio mutations preview validation immediately; this save/validate action persists the reusable workflow before run readiness is unlocked.")), !draftId ? /* @__PURE__ */ React.createElement(EmptyState, { title: "No draft to validate yet", body: "Create or open a draft session first. Then this panel will keep validation, fixes, and run readiness together." }) : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(Message, { tone: validationStatus.tone, title: validationStatus.title, body: validationStatus.body }), validationFixes.length ? /* @__PURE__ */ React.createElement("ul", { className: "teaching-list" }, validationFixes.map((note) => /* @__PURE__ */ React.createElement("li", { key: note }, note))) : null, /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: validateDraft, disabled: Boolean(busy) }, "Save + validate draft"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: createVersionSnapshotFromDraft, disabled: Boolean(busy) }, "Save version snapshot"), /* @__PURE__ */ React.createElement("button", { className: "primary-button", disabled: Boolean(busy) || runDisabled, onClick: runDraft }, "Run candidate")))) : null, showWorkbenchFieldSetup ? /* @__PURE__ */ React.createElement("section", { className: "panel" }, /* @__PURE__ */ React.createElement("div", { className: "section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "5. Compare + next step"), /* @__PURE__ */ React.createElement("h3", null, "Keep validate, run, and compare inside the same authoring loop")), /* @__PURE__ */ React.createElement("p", { className: "section-copy" }, "Once the candidate finishes, compare it immediately or jump into the run detail from the same authoring surface.")), activeDraft?.compare ? /* @__PURE__ */ React.createElement("div", { className: "compare-outcome" }, /* @__PURE__ */ React.createElement(Message, { tone: "success", title: `Compare verdict: ${activeDraft.compare.verdict?.label || "ready"}`, body: activeDraft.compare.verdict?.summary || "Open the comparison to inspect detailed metric deltas." }), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, (activeDraft.compare.next_actions || []).map((action, index) => /* @__PURE__ */ React.createElement("button", { key: action.href || action.label || index, className: index === 0 ? "primary-button" : "secondary-button", onClick: () => navigate(action.href) }, action.label)))) : activeDraft?.last_run_id ? /* @__PURE__ */ React.createElement(Message, { tone: "success", title: "Candidate run completed", body: "Inspect the candidate run now. Add a baseline if you want to compare it before deciding on the next edit." }) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No candidate run yet", body: "Once validation passes and you run a candidate, this panel will explain whether to compare, iterate, or stop." })) : null),
      showWorkbenchSetupRail ? /* @__PURE__ */ React.createElement("aside", { className: "panel guidance-panel" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Next step"), /* @__PURE__ */ React.createElement("section", { className: "next-step-card" }, /* @__PURE__ */ React.createElement("strong", null, nextStep.title), /* @__PURE__ */ React.createElement("p", null, nextStep.detail)), /* @__PURE__ */ React.createElement("section", { className: "guidance-section" }, /* @__PURE__ */ React.createElement("h3", null, "Authoring contract"), /* @__PURE__ */ React.createElement("ul", { className: "guidance-list" }, safeEditLimitations.map((item) => /* @__PURE__ */ React.createElement("li", { key: item }, item)))), /* @__PURE__ */ React.createElement("section", { className: "guidance-section" }, /* @__PURE__ */ React.createElement("h3", null, "Supported safe edits"), /* @__PURE__ */ React.createElement("ul", { className: "guidance-list compact-list" }, safeEditSupport.map((item) => /* @__PURE__ */ React.createElement("li", { key: item.key }, /* @__PURE__ */ React.createElement("strong", null, item.label), /* @__PURE__ */ React.createElement("span", null, item.detail))))), /* @__PURE__ */ React.createElement("section", { className: "guidance-section" }, /* @__PURE__ */ React.createElement("h3", null, "What stays authoritative"), /* @__PURE__ */ React.createElement("ul", { className: "guidance-list" }, sourceOfTruth.map((item) => /* @__PURE__ */ React.createElement("li", { key: item }, item))))) : null
    );
  }
  function GraphCanvasBase({
    nodes,
    edges,
    positions,
    emptyState,
    markerId,
    shellClassName = "workflow-canvas-shell",
    minWidth,
    minHeight,
    widthPadding,
    heightPadding,
    onStageClick,
    onShellDrop,
    edgeClassName,
    onEdgeClick,
    nodeClassName,
    onNodePointerDown,
    onNodePointerMove,
    onNodePointerUp,
    onNodeClick,
    renderNodeContents,
    centerContent = true,
    enableStagePan = false
  }) {
    const shellRef = React.useRef(null);
    const stageRef = React.useRef(null);
    const activeNodePointerRef = React.useRef(null);
    const stagePanRef = React.useRef(null);
    const stagePanMovedRef = React.useRef(false);
    const [stagePanning, setStagePanning] = useState(false);
    const [stageOffset, setStageOffset] = useState({ x: 0, y: 0 });
    const [viewportSize, setViewportSize] = useState({ width: minWidth, height: minHeight });
    const measureViewport = () => {
      const shell = shellRef.current;
      if (!shell) return;
      const style = window.getComputedStyle(shell);
      const horizontalPadding = Number.parseFloat(style.paddingLeft || "0") + Number.parseFloat(style.paddingRight || "0");
      const verticalPadding = Number.parseFloat(style.paddingTop || "0") + Number.parseFloat(style.paddingBottom || "0");
      const parentHeight = shell.parentElement ? shell.parentElement.clientHeight : 0;
      const next = {
        width: Math.max(1, Math.floor(shell.clientWidth - horizontalPadding)),
        height: Math.max(
          1,
          Math.floor(shell.clientHeight - verticalPadding),
          Math.floor(parentHeight - verticalPadding)
        )
      };
      setViewportSize((current) => current.width === next.width && current.height === next.height ? current : next);
    };
    useEffect(() => {
      measureViewport();
    });
    useEffect(() => {
      const shell = shellRef.current;
      if (!shell) return;
      measureViewport();
      if (typeof ResizeObserver === "function") {
        const observer = new ResizeObserver(() => {
          measureViewport();
        });
        observer.observe(shell);
        return () => observer.disconnect();
      }
      const onResize = () => {
        measureViewport();
      };
      window.addEventListener("resize", onResize);
      return () => window.removeEventListener("resize", onResize);
    }, [minHeight, minWidth]);
    const contentWidth = Math.max(minWidth, ...nodes.map((node) => (positions[String(node.name)] || { x: Number(node.x || 0), y: Number(node.y || 0) }).x + widthPadding));
    const contentHeight = Math.max(minHeight, ...nodes.map((node) => (positions[String(node.name)] || { x: Number(node.x || 0), y: Number(node.y || 0) }).y + heightPadding));
    const contentOffsetX = centerContent ? Math.max(0, Math.floor((viewportSize.width - contentWidth) / 2)) : 0;
    const contentOffsetY = centerContent ? Math.max(0, Math.floor((viewportSize.height - contentHeight) / 2)) : 0;
    const maxStageOffsetX = enableStagePan && !centerContent ? Math.max(0, viewportSize.width - contentWidth) : 0;
    const maxStageOffsetY = enableStagePan && !centerContent ? Math.max(0, viewportSize.height - contentHeight) : 0;
    const clampStageOffset = (x, y) => ({
      x: Math.max(0, Math.min(maxStageOffsetX, Math.round(x))),
      y: Math.max(0, Math.min(maxStageOffsetY, Math.round(y)))
    });
    useEffect(() => {
      const next = clampStageOffset(stageOffset.x, stageOffset.y);
      if (next.x === stageOffset.x && next.y === stageOffset.y) return;
      setStageOffset(next);
    }, [maxStageOffsetX, maxStageOffsetY, stageOffset.x, stageOffset.y]);
    if (!nodes.length) {
      return /* @__PURE__ */ React.createElement(EmptyState, { title: emptyState.title, body: emptyState.body });
    }
    const totalOffsetX = contentOffsetX + stageOffset.x;
    const totalOffsetY = contentOffsetY + stageOffset.y;
    const relativePoint = (event) => {
      const stage = stageRef.current;
      const rect = stage?.getBoundingClientRect();
      if (!rect) return { x: 0, y: 0 };
      return {
        x: event.clientX - rect.left + (stage?.scrollLeft || 0),
        y: event.clientY - rect.top + (stage?.scrollTop || 0)
      };
    };
    const graphPoint = (event) => {
      const point = relativePoint(event);
      return {
        x: point.x - totalOffsetX,
        y: point.y - totalOffsetY
      };
    };
    const findNode = (nodeName) => nodes.find((node) => String(node.name) === nodeName) || null;
    const positionForNode = (node) => positions[String(node.name)] || { x: Number(node.x || 0), y: Number(node.y || 0) };
    const clampPosition = (x, y) => ({
      x: Math.max(0, Math.min(contentWidth - 180, Math.round(x))),
      y: Math.max(0, Math.min(contentHeight - 90, Math.round(y)))
    });
    const handleActiveNodePointerMove = (event) => {
      const activeNodePointer = activeNodePointerRef.current;
      if (!activeNodePointer || activeNodePointer.pointerId !== event.pointerId) return false;
      const node = findNode(activeNodePointer.nodeName);
      if (!node) {
        finishNodePointer(event.pointerId);
        return true;
      }
      onNodePointerMove?.({ pointerId: event.pointerId }, node, positionForNode(node), graphPoint(event), clampPosition);
      return true;
    };
    const handleActiveNodePointerEnd = (pointerId) => {
      const activeNodePointer = activeNodePointerRef.current;
      if (!activeNodePointer || activeNodePointer.pointerId !== pointerId) return false;
      const node = findNode(activeNodePointer.nodeName);
      finishNodePointer(pointerId);
      if (node) {
        onNodePointerUp?.({ pointerId }, node, positionForNode(node));
      }
      return true;
    };
    const finishNodePointer = (pointerId) => {
      const active = activeNodePointerRef.current;
      if (!active || active.pointerId !== pointerId) return null;
      activeNodePointerRef.current = null;
      if (active.captureTarget.hasPointerCapture(pointerId)) {
        active.captureTarget.releasePointerCapture(pointerId);
      }
      return active;
    };
    const finishStagePan = (stage, pointerId) => {
      if (stagePanRef.current?.pointerId !== pointerId) return;
      stagePanRef.current = null;
      setStagePanning(false);
      if (stage.hasPointerCapture(pointerId)) {
        stage.releasePointerCapture(pointerId);
      }
    };
    const handleCanvasBackgroundClick = () => {
      if (stagePanMovedRef.current) {
        stagePanMovedRef.current = false;
        return;
      }
      onStageClick?.();
    };
    return /* @__PURE__ */ React.createElement(
      "div",
      {
        ref: shellRef,
        className: shellClassName,
        onDragOver: (event) => {
          if (onShellDrop && Array.from(event.dataTransfer.types).includes("application/xrtm-node-implementation")) {
            event.preventDefault();
            event.dataTransfer.dropEffect = "copy";
          }
        },
        onDrop: (event) => {
          if (!onShellDrop) return;
          const implementation = event.dataTransfer.getData("application/xrtm-node-implementation");
          if (!implementation) return;
          event.preventDefault();
          const point = graphPoint(event);
          onShellDrop(implementation, clampPosition(point.x - 82, point.y - 34));
        }
      },
      /* @__PURE__ */ React.createElement(
        "div",
        {
          ref: stageRef,
          className: `workflow-canvas-stage${enableStagePan ? " canvas-pannable" : ""}${stagePanning ? " panning" : ""}`,
          onPointerDown: (event) => {
            if (!enableStagePan) return;
            const target = event.target;
            if (!(target instanceof Element)) return;
            const isCanvasBackground = target === event.currentTarget || target.tagName.toLowerCase() === "svg";
            if (!isCanvasBackground) return;
            stagePanRef.current = {
              pointerId: event.pointerId,
              startX: event.clientX,
              startY: event.clientY,
              scrollLeft: event.currentTarget.scrollLeft,
              scrollTop: event.currentTarget.scrollTop,
              offsetX: stageOffset.x,
              offsetY: stageOffset.y
            };
            stagePanMovedRef.current = false;
            setStagePanning(true);
            event.currentTarget.setPointerCapture(event.pointerId);
          },
          onPointerMove: (event) => {
            if (handleActiveNodePointerMove(event)) return;
            const pan = stagePanRef.current;
            if (!pan || pan.pointerId !== event.pointerId) return;
            const deltaX = event.clientX - pan.startX;
            const deltaY = event.clientY - pan.startY;
            if (!stagePanMovedRef.current && (Math.abs(deltaX) > 3 || Math.abs(deltaY) > 3)) {
              stagePanMovedRef.current = true;
            }
            const maxScrollLeft = Math.max(0, event.currentTarget.scrollWidth - event.currentTarget.clientWidth);
            const maxScrollTop = Math.max(0, event.currentTarget.scrollHeight - event.currentTarget.clientHeight);
            const nextScrollLeft = Math.max(0, Math.min(maxScrollLeft, pan.scrollLeft - deltaX));
            const nextScrollTop = Math.max(0, Math.min(maxScrollTop, pan.scrollTop - deltaY));
            const nextStageOffset = clampStageOffset(
              pan.offsetX + (deltaX - (pan.scrollLeft - nextScrollLeft)),
              pan.offsetY + (deltaY - (pan.scrollTop - nextScrollTop))
            );
            event.currentTarget.scrollLeft = nextScrollLeft;
            event.currentTarget.scrollTop = nextScrollTop;
            setStageOffset((current) => current.x === nextStageOffset.x && current.y === nextStageOffset.y ? current : nextStageOffset);
          },
          onPointerUp: (event) => {
            if (handleActiveNodePointerEnd(event.pointerId)) return;
            finishStagePan(event.currentTarget, event.pointerId);
          },
          onPointerCancel: (event) => {
            if (handleActiveNodePointerEnd(event.pointerId)) return;
            finishStagePan(event.currentTarget, event.pointerId);
          },
          onClick: (event) => {
            if (event.currentTarget === event.target) handleCanvasBackgroundClick();
          }
        },
        /* @__PURE__ */ React.createElement(
          "div",
          {
            className: "workflow-canvas-content",
            style: {
              width: `${contentWidth}px`,
              height: `${contentHeight}px`,
              left: `${totalOffsetX}px`,
              top: `${totalOffsetY}px`
            }
          },
          /* @__PURE__ */ React.createElement("svg", { className: "workflow-canvas-svg", viewBox: `0 0 ${contentWidth} ${contentHeight}`, preserveAspectRatio: "xMinYMin meet", onClick: handleCanvasBackgroundClick }, /* @__PURE__ */ React.createElement("defs", null, /* @__PURE__ */ React.createElement("marker", { id: markerId, markerWidth: "8", markerHeight: "8", refX: "7", refY: "4", orient: "auto" }, /* @__PURE__ */ React.createElement("path", { d: "M0,0 L8,4 L0,8 z", fill: "#91a5ca" }))), edges.map((edge, index) => {
            const from = positions[String(edge.from || "")];
            const to = positions[String(edge.to || "")];
            if (!from || !to) return null;
            const x1 = from.x + 164;
            const y1 = from.y + 34;
            const x2 = to.x;
            const y2 = to.y + 34;
            const midX = (x1 + x2) / 2;
            const midY = (y1 + y2) / 2;
            return /* @__PURE__ */ React.createElement("g", { key: `${edge.from}-${edge.to}-${index}`, className: "workflow-canvas-edge-hit", onClick: (event) => {
              event.stopPropagation();
              onEdgeClick?.(edge);
            } }, /* @__PURE__ */ React.createElement("path", { className: edgeClassName(edge, index), d: `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`, markerEnd: `url(#${markerId})` }), edge.label ? /* @__PURE__ */ React.createElement("text", { className: "workflow-canvas-label", x: midX, y: midY - 6 }, String(edge.label)) : null);
          })),
          nodes.map((node) => {
            const name = String(node.name);
            const position = positions[name] || { x: Number(node.x || 0), y: Number(node.y || 0) };
            return /* @__PURE__ */ React.createElement(
              "button",
              {
                key: name,
                type: "button",
                className: nodeClassName(node),
                style: { left: `${position.x}px`, top: `${position.y}px` },
                onPointerDown: (event) => {
                  if (!onNodePointerDown && !onNodePointerMove && !onNodePointerUp) return;
                  const captureTarget = event.currentTarget;
                  activeNodePointerRef.current = { pointerId: event.pointerId, nodeName: name, captureTarget };
                  captureTarget.setPointerCapture(event.pointerId);
                  onNodePointerDown?.({ pointerId: event.pointerId }, node, position, graphPoint(event));
                },
                onPointerMove: (event) => {
                  event.stopPropagation();
                  handleActiveNodePointerMove(event);
                },
                onPointerUp: (event) => {
                  event.stopPropagation();
                  handleActiveNodePointerEnd(event.pointerId);
                },
                onPointerCancel: (event) => {
                  event.stopPropagation();
                  handleActiveNodePointerEnd(event.pointerId);
                },
                onClick: (event) => {
                  event.stopPropagation();
                  onNodeClick?.(event, node);
                }
              },
              renderNodeContents(node)
            );
          })
        )
      )
    );
  }
  function WorkflowCanvasSurface({
    canvas,
    entry,
    selectedNodeName,
    selectedEdgeId,
    localPositions,
    edgeDraftFrom,
    onMoveNode,
    onMoveEnd,
    onSelectNode,
    onSelectEdge,
    onSelectWorkflow,
    onAddNodeFromPalette,
    onCreateEdge
  }) {
    const dragRef = React.useRef(null);
    const suppressClickRef = React.useRef(false);
    const nodes = (canvas?.nodes || []).filter((node) => typeof node?.name === "string");
    const edges = canvas?.edges || [];
    const positions = Object.fromEntries(
      nodes.map((node) => [String(node.name), localPositions[String(node.name)] || { x: Number(node.x || 0), y: Number(node.y || 0) }])
    );
    return /* @__PURE__ */ React.createElement(
      GraphCanvasBase,
      {
        nodes,
        edges,
        positions,
        emptyState: { title: "No graph nodes yet", body: "Add a node or load another workflow to populate the visual graph surface." },
        markerId: "workflow-arrow",
        minWidth: 680,
        minHeight: 360,
        widthPadding: 240,
        heightPadding: 150,
        centerContent: false,
        enableStagePan: true,
        onStageClick: onSelectWorkflow,
        onShellDrop: onAddNodeFromPalette,
        edgeClassName: (edge) => `workflow-canvas-edge ${studioEdgeKey(edge) === selectedEdgeId ? "selected" : ""} ${edge.read_only ? "readonly" : ""}`,
        onEdgeClick: onSelectEdge,
        nodeClassName: (node) => {
          const name = String(node.name);
          return `workflow-canvas-node ${selectedNodeName === name ? "selected" : ""} ${entry === name ? "entry" : ""} ${edgeDraftFrom === name ? "edge-source" : ""}`;
        },
        onNodePointerDown: (event, node, position, point) => {
          dragRef.current = { nodeName: String(node.name), offsetX: point.x - position.x, offsetY: point.y - position.y, pointerId: event.pointerId };
          suppressClickRef.current = false;
        },
        onNodePointerMove: (event, node, _position, point, clampPosition) => {
          const drag = dragRef.current;
          if (!drag || drag.pointerId !== event.pointerId || drag.nodeName !== String(node.name)) return;
          suppressClickRef.current = true;
          onMoveNode(String(node.name), clampPosition(point.x - drag.offsetX, point.y - drag.offsetY));
        },
        onNodePointerUp: (event, node, position) => {
          if (dragRef.current?.pointerId === event.pointerId) {
            onMoveEnd(String(node.name), position);
            dragRef.current = null;
          }
        },
        onNodeClick: (_event, node) => {
          const name = String(node.name);
          if (suppressClickRef.current) {
            suppressClickRef.current = false;
            return;
          }
          if (edgeDraftFrom && edgeDraftFrom !== name) {
            onCreateEdge(edgeDraftFrom, name);
          } else {
            onSelectNode(name);
          }
        },
        renderNodeContents: (node) => /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("strong", null, String(node.name)), /* @__PURE__ */ React.createElement("span", null, node.kind), /* @__PURE__ */ React.createElement(StatusPill, { value: String(node.status || (entry === String(node.name) ? "entry" : "ready")) }))
      }
    );
  }
  function PlaygroundGraphTracePreview({
    canvas,
    traceItems,
    activeNodeId,
    onSelectNode
  }) {
    const nodes = (canvas?.nodes || []).filter((node) => typeof node?.name === "string");
    const edges = canvas?.edges || [];
    const traceByNode = Object.fromEntries(traceItems.map((item) => [String(item.node_id), item]));
    const positions = Object.fromEntries(nodes.map((node) => [String(node.name), { x: Number(node.x || 0), y: Number(node.y || 0) }]));
    return /* @__PURE__ */ React.createElement(
      GraphCanvasBase,
      {
        nodes,
        edges,
        positions,
        emptyState: { title: "No graph preview", body: "This context did not expose canvas-ready graph nodes." },
        markerId: "playground-arrow",
        shellClassName: "workflow-canvas-shell playground-trace-canvas",
        minWidth: 680,
        minHeight: 360,
        widthPadding: 240,
        heightPadding: 150,
        centerContent: false,
        enableStagePan: true,
        edgeClassName: (edge) => {
          const sourceTrace = traceByNode[String(edge.from || "")];
          const targetTrace = traceByNode[String(edge.to || "")];
          const traced = sourceTrace && targetTrace && Number(sourceTrace.order || 0) <= Number(targetTrace.order || 0);
          return `workflow-canvas-edge ${traced ? "executed" : ""}`;
        },
        nodeClassName: (node) => {
          const trace = traceByNode[String(node.name)];
          const executed = Boolean(trace || node.executed);
          const active = activeNodeId === String(node.name);
          return `workflow-canvas-node playground-trace-node ${executed ? "executed" : "not-executed"} ${active ? "active" : ""} ${node.is_entry ? "entry" : ""}`;
        },
        onNodeClick: (_event, node) => onSelectNode(String(node.name)),
        renderNodeContents: (node) => {
          const trace = traceByNode[String(node.name)];
          const executed = Boolean(trace || node.executed);
          return /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("strong", null, String(node.name)), /* @__PURE__ */ React.createElement("span", null, node.kind || node.node_type || "node"), /* @__PURE__ */ React.createElement("span", { className: "trace-chip" }, executed ? `#${formatValue(trace?.order || node.trace_order)}` : "Not run"), /* @__PURE__ */ React.createElement(StatusPill, { value: String(trace?.status || node.status || (node.is_entry ? "entry" : "ready")) }));
        }
      }
    );
  }
  function normalizeText(value) {
    const text = String(value || "").trim();
    return text ? text : null;
  }
  function parseBooleanString(value) {
    return String(value || "false").toLowerCase() === "true";
  }
  function previewBatchRows(rowsText) {
    return String(rowsText || "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean).map((line, index) => {
      try {
        const payload = JSON.parse(line);
        const question = String(payload.question || payload.text || payload.prompt || "");
        const title = String(payload.title || "");
        return { row_index: index, question: question || "[missing question]", title };
      } catch {
        return { row_index: index, question: line, title: "" };
      }
    });
  }
  function draftlessStepState(activeWorkflow) {
    const source = activeWorkflow?.source || "builtin";
    const cloneDescription = source === "local" ? "Open a draft session for the local workflow." : "Create a draft from scratch, template, or clone before editing.";
    return [
      { key: "inspect", label: "Inspect", locked: false, description: "Review the workflow and choose a baseline run." },
      { key: "clone", label: "Create", locked: false, description: cloneDescription },
      { key: "edit", label: "Author", locked: true, description: "Locked until a draft session exists." },
      { key: "validate", label: "Validate", locked: true, description: "Locked until the authored draft can be checked inline." },
      { key: "run", label: "Run", locked: true, description: "Locked until validation passes." },
      { key: "compare", label: "Compare", locked: true, description: "Locked until a candidate run exists." },
      { key: "next-step", label: "Next step", locked: false, description: "The draft editor will explain what to do after each step." }
    ];
  }
  function decorateStepState(steps, activeDraft, hasDraft) {
    const rank = { inspect: 0, clone: 1, edit: 2, validate: 3, run: 4, compare: 5, "next-step": 6 };
    const currentKey = currentJourneyKey(activeDraft, hasDraft);
    return steps.map((step) => {
      let state = step.locked ? "locked" : "upcoming";
      if (!step.locked && rank[step.key] < rank[currentKey]) {
        state = "complete";
      }
      if (!step.locked && step.key === currentKey) {
        state = "current";
      }
      return { ...step, state };
    });
  }
  function currentJourneyKey(activeDraft, hasDraft) {
    if (!hasDraft) return "clone";
    if (activeDraft?.compare) return "compare";
    if (activeDraft?.last_run_id) return "next-step";
    const validation = activeDraft?.validation;
    if (validation?.ok && !validation?.stale) return "run";
    if (validation && !validation.ok) return "edit";
    if (activeDraft?.status === "draft-dirty") return "validate";
    return "edit";
  }
  function stepBadgeLabel(step) {
    if (step.state === "complete") return "Done";
    if (step.state === "current") return "Now";
    if (step.state === "locked") return "Locked";
    return "Next";
  }
  function buildActionErrorNotice(stage, error) {
    const message = error instanceof Error ? error.message : String(error);
    const hints = {
      clone: "Built-in workflows remain read-only until the draft creation step succeeds.",
      create: "Use one of the supported scratch, template, or clone modes to create a safe authored draft.",
      workflow: "Only the supported authored workflow fields can be changed from this surface.",
      node: "Stay inside the built-in safe node catalog and keep the graph connected when you change nodes.",
      edge: "Basic edge edits must keep the graph reachable and acyclic.",
      entry: "Choose an existing node or group as the workflow entry.",
      validate: "Fix the supported fields below, then validate again without losing the current draft context.",
      run: "The draft stays loaded. Re-validate the latest authored graph before you try another run."
    };
    return {
      tone: "error",
      title: `Couldn't ${stage}`,
      body: `${message} ${hints[stage] || "Review the current step and try again."}`
    };
  }
  function buildValidationStatus(activeDraft) {
    if (activeDraft?.preview_error) {
      return {
        tone: "warning",
        title: "Preview blocked",
        body: `${activeDraft.preview_error} Fix the supported fields below; your draft session remains intact.`
      };
    }
    const validation = activeDraft?.validation;
    if (!validation) {
      return {
        tone: "warning",
        title: "Validate before run",
        body: "Validate inline before you run this draft. The run step stays locked until the latest validation passes."
      };
    }
    if (validation.ok && validation.stale) {
      return {
        tone: "warning",
        title: "Validation is stale",
        body: "Newer edits changed the draft after the last passing validation. Validate once more before you run."
      };
    }
    if (validation.ok) {
      return {
        tone: "success",
        title: "Validation passed",
        body: "The latest authored workflow is runnable. Next: run a candidate and compare it with the baseline."
      };
    }
    return {
      tone: "warning",
      title: "Validation found issues",
      body: `${(validation.errors || []).join(" ")} Fix the supported fields below, then validate again.`
    };
  }
  function buildValidationFixes(activeDraft) {
    const rawErrors = [activeDraft?.preview_error, ...activeDraft?.validation?.errors || []].filter(Boolean);
    const notes = /* @__PURE__ */ new Set();
    rawErrors.forEach((error) => {
      const lower = error.toLowerCase();
      if (lower.includes("questions.limit") || lower.includes("questions_limit")) {
        notes.add("Use a whole-number question limit inside the safe range shown in the form.");
      }
      if (lower.includes("artifacts_write_report")) {
        notes.add("Set Write HTML report to true or false only.");
      }
      if (lower.includes("weight:")) {
        notes.add("Enter every supported weight as a number from 0 to 100; the draft editor will normalize them after validation.");
      }
      if (lower.includes("unsupported edit field")) {
        notes.add("Stay inside the listed authoring controls. The draft editor does not expose arbitrary JSON or unsupported implementation edits.");
      }
      if (lower.includes("clone this workflow")) {
        notes.add("Clone the workflow into a local draft first. Built-ins remain read-only reference blueprints.");
      }
    });
    return Array.from(notes);
  }
  function buildDraftlessNextStep(activeWorkflow, latestRun) {
    if (activeWorkflow?.source === "local") {
      return {
        key: "clone",
        title: "Open a draft session for the local workflow",
        detail: "Local workflows are reusable on disk, but the draft editor still uses a draft session so validation, run readiness, and resume state stay explicit."
      };
    }
    if (latestRun?.run_id) {
      return {
        key: "inspect",
        title: "Inspect the latest run, then create a draft",
        detail: "Review the baseline context first, then create a local authored draft before making visual changes."
      };
    }
    return {
      key: "clone",
      title: "Create a draft to begin",
      detail: "Choose a workflow from the catalog or starter modes, then create a local draft. Visual authoring unlocks after that step succeeds."
    };
  }
  function defaultSourceOfTruth() {
    return [
      "Built-in workflows stay read-only until you clone them into a local workflow.",
      "Reusable local workflows remain JSON files on disk.",
      "Draft blueprint state, validation snapshots, and resume state live in SQLite until validate or run writes the local workflow file."
    ];
  }
  function defaultAuthoringLimitations() {
    return [
      "Only shared safe-product workflow fields and graph mutations are exposed.",
      "Node implementations stay inside the built-in product workflow node catalog.",
      "Parallel-group and conditional-route editing stay read-only in this pass.",
      "API keys are not persisted as authored workflow fields from the WebUI."
    ];
  }
  function playgroundStepKey(step) {
    return String(step.order || step.node_id || "step");
  }
  function SourceBadge({ source }) {
    const normalized = String(source || "unknown").toLowerCase();
    const label = normalized === "builtin" ? "Built-in \xB7 read-only" : normalized === "local" ? "Local workflow" : source;
    return /* @__PURE__ */ React.createElement("span", { className: `source-pill ${normalized}` }, label);
  }
  function RunLaunchResultCard({ result, navigate }) {
    return /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Latest launched run"), /* @__PURE__ */ React.createElement("p", null, "Jump straight into detail, report, or compare while the context is fresh."))), /* @__PURE__ */ React.createElement("div", { className: "inline-action-card" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, result.run_id), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, result.command || "Run created", " \xB7 ", result.provider || "deterministic", " \xB7 ", result.status || "running")), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => navigate(result.href) }, "Inspect run"), result.report_href ? /* @__PURE__ */ React.createElement("a", { className: "secondary-link", href: result.report_href, target: "_blank", rel: "noreferrer" }, "Open report") : null, result.compare?.href ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(result.compare.href) }, "Compare") : null)));
  }
  function MetricCard({ label, value }) {
    return /* @__PURE__ */ React.createElement("article", { className: "panel metric-card" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, label), /* @__PURE__ */ React.createElement("strong", null, String(value ?? "\u2014")));
  }
  function StatusPill({ value }) {
    return /* @__PURE__ */ React.createElement("span", { className: `status-pill ${String(value || "unknown").replace(/[^a-z0-9-]/gi, "-").toLowerCase()}` }, value || "unknown");
  }
  function Message({ tone, title, body }) {
    return /* @__PURE__ */ React.createElement("section", { className: `panel message ${tone}` }, /* @__PURE__ */ React.createElement("strong", null, title), /* @__PURE__ */ React.createElement("p", null, body));
  }
  function LoadingCard({ label }) {
    return /* @__PURE__ */ React.createElement("section", { className: "panel loading-card" }, /* @__PURE__ */ React.createElement("span", { className: "spinner" }), /* @__PURE__ */ React.createElement("span", null, label));
  }
  function EmptyState({ title, body }) {
    return /* @__PURE__ */ React.createElement("section", { className: "empty-state" }, /* @__PURE__ */ React.createElement("strong", null, title), /* @__PURE__ */ React.createElement("p", null, body));
  }
  function KeyValueGroup({ group }) {
    return /* @__PURE__ */ React.createElement("article", { className: "info-card" }, /* @__PURE__ */ React.createElement("h4", null, group.title), /* @__PURE__ */ React.createElement("dl", { className: "key-value-list" }, (group.items || []).map((item) => /* @__PURE__ */ React.createElement("div", { key: item.label }, /* @__PURE__ */ React.createElement("dt", null, item.label), /* @__PURE__ */ React.createElement("dd", null, formatValue(item.value))))));
  }
  function RunForecastTable({ rows, emptyState }) {
    if (!rows.length) {
      return /* @__PURE__ */ React.createElement(EmptyState, { title: emptyState?.title || "No forecasts", body: emptyState?.body || "No forecast rows are available." });
    }
    return /* @__PURE__ */ React.createElement("div", { className: "table-wrap" }, /* @__PURE__ */ React.createElement("table", { className: "data-table forecast-table" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", null, /* @__PURE__ */ React.createElement("th", null, "Question"), /* @__PURE__ */ React.createElement("th", null, "Forecast"), /* @__PURE__ */ React.createElement("th", null, "Outcome"), /* @__PURE__ */ React.createElement("th", null, "Brier"), /* @__PURE__ */ React.createElement("th", null, "Resolution"))), /* @__PURE__ */ React.createElement("tbody", null, rows.map((row) => /* @__PURE__ */ React.createElement("tr", { key: row.question_id || row.question_title }, /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement("div", { className: "table-primary" }, row.question_title || row.question_id || "Untitled question"), /* @__PURE__ */ React.createElement("div", { className: "table-secondary" }, row.question_id), row.question_text ? /* @__PURE__ */ React.createElement("div", { className: "table-secondary clamp-2" }, row.question_text) : null), /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement("div", { className: "table-primary" }, formatProbability(row.probability)), /* @__PURE__ */ React.createElement("div", { className: "table-secondary" }, "Confidence: ", formatValue(row.confidence)), row.tokens_used != null ? /* @__PURE__ */ React.createElement("div", { className: "table-secondary" }, "Tokens: ", formatValue(row.tokens_used)) : null), /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement("div", { className: "table-primary" }, formatOutcome(row.outcome)), /* @__PURE__ */ React.createElement("div", { className: "table-secondary" }, "Resolved: ", formatBoolean(row.resolved))), /* @__PURE__ */ React.createElement("td", null, formatValue(row.brier_score)), /* @__PURE__ */ React.createElement("td", null, formatTimestamp(row.resolution_date)))))));
  }
  function ArtifactList({ items }) {
    if (!items.length) {
      return /* @__PURE__ */ React.createElement(EmptyState, { title: "No artifact index", body: "This run did not expose a file inventory." });
    }
    return /* @__PURE__ */ React.createElement("ul", { className: "artifact-list" }, items.map((item) => /* @__PURE__ */ React.createElement("li", { key: item.name, className: item.available ? "" : "missing" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, item.label || item.name), /* @__PURE__ */ React.createElement("span", null, item.path)), /* @__PURE__ */ React.createElement("span", { className: `availability-pill ${item.available ? "available" : "missing"}` }, item.available ? "Available" : "Missing"))));
  }
  function ReportCard({ report, onGenerate, generating = false }) {
    if (!report) {
      return /* @__PURE__ */ React.createElement(EmptyState, { title: "No report metadata", body: "This surface did not expose report availability information." });
    }
    return /* @__PURE__ */ React.createElement("section", { className: `report-card ${report.available ? "available" : "missing"}` }, /* @__PURE__ */ React.createElement("div", { className: "report-card-copy" }, /* @__PURE__ */ React.createElement("strong", null, report.label || "HTML report"), /* @__PURE__ */ React.createElement("p", null, report.description || "No report description available."), report.path ? /* @__PURE__ */ React.createElement("span", { className: "workflow-note" }, report.path) : null), /* @__PURE__ */ React.createElement("div", { className: "button-row report-card-actions" }, report.available ? /* @__PURE__ */ React.createElement("a", { className: "secondary-link", href: report.href, target: "_blank", rel: "noreferrer" }, report.open_label || "Open report") : /* @__PURE__ */ React.createElement("span", { className: "availability-pill missing" }, "Unavailable"), onGenerate ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: onGenerate, disabled: generating }, generating ? "Generating report" : report.generate_label || (report.available ? "Regenerate report" : "Generate report")) : null));
  }
  function ExportCard({ item }) {
    return /* @__PURE__ */ React.createElement("article", { className: "info-card export-card" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("strong", null, String(item.label || "Export")), /* @__PURE__ */ React.createElement(StatusPill, { value: String(item.format || "file") })), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, String(item.description || "Download exported run evidence.")), item.filename ? /* @__PURE__ */ React.createElement("span", { className: "workflow-note" }, String(item.filename)) : null, /* @__PURE__ */ React.createElement("a", { className: "secondary-link", href: String(item.href || "#"), download: item.filename ? String(item.filename) : void 0 }, "Download"));
  }
  function CompareRunCard({ label, run }) {
    if (!run) {
      return /* @__PURE__ */ React.createElement("article", { className: "compare-run-card" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, label), /* @__PURE__ */ React.createElement("strong", null, "Run unavailable"));
    }
    return /* @__PURE__ */ React.createElement("article", { className: "compare-run-card" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, label), /* @__PURE__ */ React.createElement("strong", null, run.label || run.run_id), /* @__PURE__ */ React.createElement("div", { className: "meta-row" }, /* @__PURE__ */ React.createElement(StatusPill, { value: run.status }), /* @__PURE__ */ React.createElement("span", null, run.provider || "Unknown provider")), /* @__PURE__ */ React.createElement("span", null, formatTimestamp(run.updated_at)), /* @__PURE__ */ React.createElement("span", null, run.report?.available ? "Report ready" : "No report"));
  }
  function CompareQuestionTable({ rows }) {
    if (!rows.length) {
      return /* @__PURE__ */ React.createElement(EmptyState, { title: "No shared question rows", body: "Run another comparable candidate to unlock question-level review." });
    }
    return /* @__PURE__ */ React.createElement("div", { className: "table-wrap" }, /* @__PURE__ */ React.createElement("table", { className: "data-table forecast-table" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", null, /* @__PURE__ */ React.createElement("th", null, "Question"), /* @__PURE__ */ React.createElement("th", null, "Coverage"), /* @__PURE__ */ React.createElement("th", null, "Baseline"), /* @__PURE__ */ React.createElement("th", null, "Candidate"), /* @__PURE__ */ React.createElement("th", null, "Brier shift"))), /* @__PURE__ */ React.createElement("tbody", null, rows.map((row) => /* @__PURE__ */ React.createElement("tr", { key: row.question_id, className: `tone-${row.tone || "neutral"}` }, /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement("div", { className: "table-primary" }, row.question_title || row.question_id), row.question_text ? /* @__PURE__ */ React.createElement("div", { className: "table-secondary clamp-2" }, row.question_text) : null), /* @__PURE__ */ React.createElement("td", null, formatCoverage(row.status)), /* @__PURE__ */ React.createElement("td", null, formatProbability(row.baseline_probability)), /* @__PURE__ */ React.createElement("td", null, formatProbability(row.candidate_probability)), /* @__PURE__ */ React.createElement("td", null, formatSignedValue(row.brier_delta)))))));
  }
  function ArtifactPreview({ label, value }) {
    return /* @__PURE__ */ React.createElement("details", { className: "artifact-preview" }, /* @__PURE__ */ React.createElement("summary", null, label), isEmptyValue(value) ? /* @__PURE__ */ React.createElement("p", { className: "table-secondary" }, "No structured payload available.") : /* @__PURE__ */ React.createElement("pre", null, JSON.stringify(value, null, 2)));
  }
  function formatValue(value) {
    if (value === null || value === void 0 || value === "") return "\u2014";
    if (typeof value === "boolean") return value ? "Yes" : "No";
    if (typeof value === "number") {
      if (Number.isInteger(value)) return value.toLocaleString();
      const digits = Math.abs(value) >= 1 ? 3 : 4;
      return value.toFixed(digits).replace(/0+$/, "").replace(/\.$/, "");
    }
    if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}T/.test(value)) return formatTimestamp(value);
    return String(value);
  }
  function formatProbability(value) {
    if (typeof value !== "number") return "\u2014";
    return `${(value * 100).toFixed(1)}%`;
  }
  function formatSignedValue(value) {
    if (typeof value !== "number") return "\u2014";
    const formatted = formatValue(value);
    return value > 0 ? `+${formatted}` : formatted;
  }
  function formatBoolean(value) {
    if (value === null || value === void 0) return "\u2014";
    return value ? "Yes" : "No";
  }
  function formatOutcome(value) {
    if (value === true) return "Yes";
    if (value === false) return "No";
    return "Unresolved";
  }
  function formatTimestamp(value) {
    if (!value) return "\u2014";
    const date = new Date(String(value));
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString();
  }
  function formatCoverage(value) {
    if (!value) return "Unknown";
    return String(value).replace(/-/g, " ");
  }
  function isEmptyValue(value) {
    if (value === null || value === void 0 || value === "") return true;
    if (Array.isArray(value)) return value.length === 0;
    if (typeof value === "object") return Object.keys(value).length === 0;
    return false;
  }
  function defaultStepState() {
    return [
      { key: "inspect", label: "Inspect", locked: false, description: "Review the workflow and baseline context." },
      { key: "clone", label: "Create", locked: false, description: "Create or reopen a local draft session." },
      { key: "edit", label: "Author", locked: true, description: "Locked until a draft exists." },
      { key: "validate", label: "Validate", locked: true, description: "Validate inline before the run step unlocks." },
      { key: "run", label: "Run", locked: true, description: "Locked until validation passes." },
      { key: "compare", label: "Compare", locked: true, description: "Locked until a candidate run exists." },
      { key: "next-step", label: "Next step", locked: false, description: "The shell keeps your place in SQLite and explains what to do next." }
    ];
  }
  var root = document.getElementById("root");
  if (root) {
    ReactDOMClient.createRoot(root).render(/* @__PURE__ */ React.createElement(App, null));
  }
})();
