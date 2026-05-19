interface Window {
  __XRTM_WEBUI_BOOTSTRAP__?: {
    api_root: string;
    initial_path: string;
    initial_query: string;
    initial_error: string | null;
  };
}

type JsonObject = Record<string, any>;

type Route = { path: string; search: string };
type ThemeMode = "system" | "light" | "dark";
type ResolvedTheme = "light" | "dark";
type StudioRouteIntent =
  | { creation_mode: "scratch" }
  | { creation_mode: "template"; template_id: string | null }
  | { creation_mode: "clone"; source_workflow_name: string };

const ReactDOMClient = ReactDOM as typeof import("react-dom/client") & typeof import("react-dom");
const { useEffect, useMemo, useState } = React;
const THEME_STORAGE_KEY = "xrtm.webui.themeMode";
const SYSTEM_THEME_QUERY = "(prefers-color-scheme: dark)";
const THEME_MODE_SEQUENCE: ThemeMode[] = ["system", "light", "dark"];
const bootstrap = window.__XRTM_WEBUI_BOOTSTRAP__ ?? {
  api_root: "/api",
  initial_path: window.location.pathname,
  initial_query: window.location.search.replace(/^\?/, ""),
  initial_error: null,
};

function isThemeMode(value: string | null): value is ThemeMode {
  return value === "system" || value === "light" || value === "dark";
}

function readStoredThemeMode(): ThemeMode {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isThemeMode(stored) ? stored : "system";
  } catch (error) {
    console.warn("Unable to read stored theme mode.", error);
    return "system";
  }
}

function systemPrefersDark(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia(SYSTEM_THEME_QUERY).matches;
}

function resolveTheme(mode: ThemeMode, prefersDark: boolean): ResolvedTheme {
  if (mode === "system") return prefersDark ? "dark" : "light";
  return mode;
}

function applyDocumentTheme(mode: ThemeMode, theme: ResolvedTheme): void {
  document.documentElement.dataset.themeMode = mode;
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
}

function nextThemeMode(mode: ThemeMode): ThemeMode {
  const index = THEME_MODE_SEQUENCE.indexOf(mode);
  return THEME_MODE_SEQUENCE[(index + 1) % THEME_MODE_SEQUENCE.length];
}

function currentRoute(): Route {
  return { path: window.location.pathname, search: window.location.search.replace(/^\?/, "") };
}

function routePath(route: Route): string {
  return route.search ? `${route.path}?${route.search}` : route.path;
}

function observatoryRouteFamily(path: string): "/observatory" | "/runs" {
  return path === "/observatory" || path.startsWith("/observatory/") ? "/observatory" : "/runs";
}

function observatoryUiHref(currentPath: string, target: string): string {
  if (!target) return observatoryRouteFamily(currentPath);
  return /^\/(?:runs|observatory)(?=\/|\?|$)/.test(target)
    ? target.replace(/^\/(?:runs|observatory)/, observatoryRouteFamily(currentPath))
    : target;
}

function parsePositiveIntegerInput(value: string): number | null {
  const normalized = value.trim();
  if (!normalized) return null;
  const parsed = Number.parseInt(normalized, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function runWithoutRowSelection(event: React.MouseEvent<HTMLElement>, action: () => void): void {
  event.stopPropagation();
  action();
}

function isNavItemActive(routePath: string, href: string): boolean {
  if (href === "/" || href === "/hub") return routePath === "/" || routePath === "/hub" || routePath === "/start" || /^\/workflows\/[^/]+$/.test(routePath);
  if (href === "/start") return routePath === "/start" || /^\/workflows\/[^/]+$/.test(routePath);
  if (href === "/runs" || href === "/observatory") return routePath === "/runs" || routePath === "/observatory" || /^\/(?:runs|observatory)\/[^/]+(?:\/compare\/[^/]+)?$/.test(routePath);
  if (href === "/studio") return routePath === "/studio" || routePath === "/workbench";
  if (href === "/batch") return routePath === "/batch";
  if (href === "/versions") return routePath === "/versions";
  if (href === "/api") return routePath === "/api";
  return routePath === href;
}

function railIcon(label: string, href: string): string {
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

function surfaceTitle(routePath: string, appChrome: JsonObject): { title: string; eyebrow: string; summary: string } {
  if (routePath === "/" || routePath === "/hub") {
    return {
      title: "Hub",
      eyebrow: "Local entry",
      summary: "Choose quickstart, Playground, Studio, or recent local work.",
    };
  }
  if (routePath === "/start") {
    return {
      title: "Start",
      eyebrow: "Quickstart",
      summary: "Run first success, bounded demos, or a named workflow without leaving the WebUI.",
    };
  }
  if (/^\/workflows\/[^/]+$/.test(routePath)) {
    return {
      title: "Workflow detail",
      eyebrow: "Inspect + launch",
      summary: "Validate, inspect, and run a reusable workflow from the shared shell.",
    };
  }
  if (routePath === "/studio" || routePath === "/workbench") {
    return {
      title: "Studio",
      eyebrow: "Graph IDE",
      summary: "Build, validate, and version forecasting workflows visually.",
    };
  }
  if (routePath === "/playground") {
    return {
      title: "Playground",
      eyebrow: "Single question",
      summary: "Run one question through a workflow and inspect the trace.",
    };
  }
  if (routePath === "/runs" || routePath === "/observatory" || /^\/(?:runs|observatory)\//.test(routePath)) {
    return {
      title: "Observatory",
      eyebrow: "Analytics",
      summary: "Inspect runs, calibration, uncertainty, and workflow performance.",
    };
  }
  if (routePath === "/batch") {
    return {
      title: "Batch Runner",
      eyebrow: "Dataset execution",
      summary: "Map saved workflow versions to tables of forecasting questions.",
    };
  }
  if (routePath === "/versions") {
    return {
      title: "Versions",
      eyebrow: "Version lineage",
      summary: "Compare workflow revisions, diffs, defaults, and rollbacks.",
    };
  }
  if (routePath === "/api") {
    return {
      title: "Control",
      eyebrow: "Settings + API",
      summary: "Run saved versions, webhooks, and local integration settings.",
    };
  }
  if (routePath === "/operations") {
    return {
      title: "Operations",
      eyebrow: "Profiles + retention",
      summary: "Manage repeatable profiles, monitors, and artifact cleanup locally.",
    };
  }
  if (routePath === "/advanced") {
    return {
      title: "Advanced",
      eyebrow: "Extended lanes",
      summary: "Review advanced capabilities with explicit readiness and safety labels.",
    };
  }
  return {
    title: String(appChrome.name || "XRTM WebUI"),
    eyebrow: "Local cockpit",
    summary: String(appChrome.summary || "File-backed runs, local workflows, and resumable SQLite state."),
  };
}

function EnvironmentCardView({ card }: { card: JsonObject }): React.ReactElement {
  return (
    <article className="environment-card">
      <div className="environment-card-head">
        <strong>{card.label}</strong>
        {card.status ? <StatusPill value={String(card.status)} /> : null}
      </div>
      <span className="environment-card-value" title={String(card.value || "—")}>{card.value || "—"}</span>
      {card.detail ? <span className="environment-card-detail" title={String(card.detail)}>{card.detail}</span> : null}
    </article>
  );
}

function environmentCardKey(card: JsonObject): string {
  return String(card.key || card.label || "environment-card");
}

function environmentCardValue(card: JsonObject | null | undefined): string {
  const value = card?.value;
  return value === undefined || value === null || value === "" ? "—" : String(value);
}

function EnvironmentDisclosureView(
  { cards, trustCues, status }: { cards: JsonObject[]; trustCues: string[]; status: JsonObject },
): React.ReactElement | null {
  if (!cards.length && !trustCues.length) return null;

  const byKey = new Map(cards.map((card) => [environmentCardKey(card), card] as const));
  const localLlmCard = byKey.get("local-llm");
  const workflowsCard = byKey.get("workflows");
  const runsCard = byKey.get("runs");
  const appDbCard = byKey.get("app-db");
  const versionCard = byKey.get("version");
  const seenCardKeys = new Set<string>();
  const prioritizedCards = [
    localLlmCard,
    workflowsCard,
    runsCard,
    appDbCard,
    versionCard,
    ...cards.filter((card) => !["local-llm", "workflows", "runs", "app-db", "version"].includes(environmentCardKey(card))),
  ].filter((card): card is JsonObject => {
    if (!card) return false;
    const key = environmentCardKey(card);
    if (seenCardKeys.has(key)) return false;
    seenCardKeys.add(key);
    return true;
  });
  const drawerSummary = trustCues.join(" • ") || "Local environment detail";
  const statusLabel = String(status.label || "Open system detail");
  const statusDetail = String(status.detail || drawerSummary);
  const statusTitle = `${statusLabel}. ${statusDetail}`;

  return (
    <details className="environment-shell system-disclosure" id="shell-environment">
      <summary
        className={`shell-status-button ${String(status.tone || "neutral")}`}
        title={statusTitle}
        aria-label={statusTitle}
      >
        <span className="shell-status-dot" aria-hidden="true" />
      </summary>
      <section className="system-drawer" aria-label="System detail">
        <header className="system-drawer-head">
          <div className="system-drawer-title-row">
            <div className="system-drawer-copy">
              <span className="eyebrow">System</span>
              <strong>{statusLabel}</strong>
            </div>
            {versionCard ? <span className="version-pill">{environmentCardValue(versionCard)}</span> : null}
          </div>
          <p>{statusDetail}</p>
          {trustCues.length ? (
            <div className="system-trust-row" aria-label="Local shell trust cues">
              {trustCues.map((cue) => (
                <span key={cue} className="system-trust-pill">{cue}</span>
              ))}
            </div>
          ) : null}
        </header>
        <section className="environment-strip system-drawer-grid" aria-label="Environment status">
          {prioritizedCards.map((card) => (
            <EnvironmentCardView key={environmentCardKey(card)} card={card} />
          ))}
        </section>
      </section>
    </details>
  );
}

function DensityDisclosure({
  title,
  detail,
  className = "",
  defaultOpen = false,
  children,
}: {
  title: string;
  detail?: string;
  className?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}): React.ReactElement {
  return (
    <details className={["density-disclosure", className].filter(Boolean).join(" ")} open={defaultOpen || undefined}>
      <summary>
        <div className="density-disclosure-copy">
          <strong>{title}</strong>
          {detail ? <p>{detail}</p> : null}
        </div>
      </summary>
      <div className="density-disclosure-body">{children}</div>
    </details>
  );
}

function RouteIdentityPanel({
  eyebrow,
  title,
  summary,
  items,
  className = "",
}: {
  eyebrow: string;
  title: string;
  summary: string;
  items: Array<{ label: string; title: string; detail: string }>;
  className?: string;
}): React.ReactElement {
  return (
    <section className={["panel", "route-identity-panel", className].filter(Boolean).join(" ")}>
      <div className="route-identity-header">
        <div>
          <span className="eyebrow">{eyebrow}</span>
          <h3>{title}</h3>
        </div>
        <p>{summary}</p>
      </div>
      <div className="route-identity-grid">
        {items.map((item) => (
          <article key={item.label} className="route-identity-card">
            <span>{item.label}</span>
            <strong>{item.title}</strong>
            <p>{item.detail}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

async function requestJson(url: string, init?: RequestInit): Promise<JsonObject> {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  const body = await response.text();
  const payload = body ? JSON.parse(body) : {};
  if (!response.ok) {
    throw new Error(payload.error || `${response.status} ${response.statusText}`);
  }
  return payload;
}

function draftFromPayload(payload: JsonObject | null): JsonObject | null {
  if (!payload) return null;
  return payload.draft && typeof payload.draft === "object" ? payload.draft : payload;
}

function studioEdgeKey(edge: JsonObject): string {
  const from = edge.from || edge.source;
  const to = edge.to || edge.target;
  if (from || to) return `${from || "?"}->${to || "?"}:${edge.label || ""}`;
  return String(edge.id || "edge");
}

function suggestNodeName(item: JsonObject, existingNodes: JsonObject[]): string {
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

const PALETTE_KIND_LABELS: Record<string, string> = {
  tool: "Tools",
  model: "Models",
  scorer: "Scorers",
  aggregator: "Aggregators",
  router: "Routers",
  "human-gate": "Human gates",
};

const PALETTE_KIND_ORDER = ["tool", "model", "router", "aggregator", "scorer", "human-gate"];

function paletteGroupLabel(kind: string): string {
  if (PALETTE_KIND_LABELS[kind]) return PALETTE_KIND_LABELS[kind];
  return kind
    .split(/[^a-z0-9]+/i)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ") || "Other";
}

function paletteMatchesQuery(item: JsonObject, query: string): boolean {
  if (!query) return true;
  const fields = [
    item.label,
    item.name,
    item.kind,
    item.implementation,
    item.summary,
    item.description,
  ];
  return fields.some((value) => String(value || "").toLowerCase().includes(query));
}

function useJsonResource(url: string | null, deps: React.DependencyList): { data: JsonObject | null; loading: boolean; error: string | null; reload: () => void } {
  const [data, setData] = useState<JsonObject | null>(null);
  const [loading, setLoading] = useState<boolean>(Boolean(url));
  const [error, setError] = useState<string | null>(null);
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
    requestJson(url)
      .then((payload) => {
        if (!cancelled) {
          setData(payload);
          setLoading(false);
        }
      })
      .catch((err) => {
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

function ThemeModeSwitch(
  { mode, resolvedTheme, onChange }: { mode: ThemeMode; resolvedTheme: ResolvedTheme; onChange: (mode: ThemeMode) => void },
): React.ReactElement {
  const current = mode === "system"
    ? { icon: "◐", label: `Theme: system (${resolvedTheme})` }
    : mode === "light"
      ? { icon: "☼", label: "Theme: light" }
      : { icon: "☾", label: "Theme: dark" };
  const next = nextThemeMode(mode);
  const nextLabel = next === "system" ? "system" : next;

  return (
    <button
      type="button"
      className="theme-icon-button"
      data-theme-mode={mode}
      title={`${current.label}. Click to switch to ${nextLabel}.`}
      aria-label={`${current.label}. Click to switch to ${nextLabel}.`}
      onClick={() => onChange(next)}
    >
      <span className="theme-icon" aria-hidden="true">{current.icon}</span>
    </button>
  );
}

function App(): React.ReactElement {
  const [route, setRoute] = useState<Route>({ path: bootstrap.initial_path, search: bootstrap.initial_query });
  const [shellRefresh, setShellRefresh] = useState(0);
  const [themeMode, setThemeMode] = useState<ThemeMode>(() => readStoredThemeMode());
  const [prefersDark, setPrefersDark] = useState<boolean>(() => systemPrefersDark());
  const shell = useJsonResource(`${bootstrap.api_root}/app-shell`, [route.path, route.search, shellRefresh]);
  const resolvedTheme = resolveTheme(themeMode, prefersDark);

  useEffect(() => {
    const onPopState = () => setRoute(currentRoute());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return undefined;
    const query = window.matchMedia(SYSTEM_THEME_QUERY);
    const onChange = (event: MediaQueryListEvent) => setPrefersDark(event.matches);
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

  const navigate = React.useCallback((path: string) => {
    window.history.pushState({}, "", path);
    setRoute(currentRoute());
  }, []);
  const refreshShell = React.useCallback(() => setShellRefresh((value) => value + 1), []);

  const appChrome = (shell.data?.app || {}) as JsonObject;
  const nav = appChrome.nav ?? [
    { label: "Hub", href: "/hub" },
    { label: "Studio", href: "/studio" },
    { label: "Playground", href: "/playground" },
    { label: "Observatory", href: "/observatory" },
    { label: "Batch", href: "/batch" },
    { label: "Versions", href: "/versions" },
    { label: "API", href: "/api" },
    { label: "Operations", href: "/operations" },
    { label: "Advanced", href: "/advanced" },
  ];
  const trustCues = (appChrome.trust_cues || ["Shared local shell", "File-backed history", "SQLite draft state"]) as string[];
  const environmentCards = (shell.data?.environment?.cards || [
    { key: "version", label: "Version", value: shell.data?.app?.version ? `xrtm ${String(shell.data.app.version)}` : "unknown" },
    { key: "runs", label: "Runs", value: shell.data?.environment?.runs_dir || "—" },
    { key: "workflows", label: "Workflows", value: shell.data?.environment?.workflows_dir || "—" },
    {
      key: "local-llm",
      label: "Local LLM",
      value: shell.data?.environment?.local_llm?.healthy ? "Healthy" : "Unavailable",
      status: shell.data?.environment?.local_llm?.healthy ? "healthy" : "unavailable",
      detail: shell.data?.environment?.local_llm?.base_url || shell.data?.environment?.local_llm?.error || "Unavailable",
    },
    { key: "app-db", label: "App DB", value: shell.data?.environment?.app_db || "—" },
  ]) as JsonObject[];
  const localLlmCard = environmentCards.find((card) => environmentCardKey(card) === "local-llm");
  const shellStatus = ((appChrome.system_status as JsonObject | undefined) || (
    localLlmCard?.status === "healthy"
      ? {
          tone: "healthy",
          label: "System healthy",
          detail: String(localLlmCard.detail || "Local model connectivity is ready."),
        }
      : localLlmCard?.status === "unavailable"
        ? {
            tone: "warning",
            label: "System needs attention",
            detail: String(localLlmCard.detail || "Open System for local environment detail."),
          }
        : {
            tone: "neutral",
            label: "Open System",
            detail: "View compact local environment detail.",
          }
  )) as JsonObject;
  let page: React.ReactElement;
  if (route.path === "/" || route.path === "/hub") {
    page = <HubPage shell={shell.data} navigate={navigate} />;
  } else if (route.path === "/start") {
    page = <StartPage shell={shell.data} navigate={navigate} onMutate={refreshShell} />;
  } else if (route.path === "/runs" || route.path === "/observatory") {
    page = <RunsPage route={route} navigate={navigate} />;
  } else if (route.path === "/playground") {
    page = <PlaygroundPage route={route} shell={shell.data} navigate={navigate} onMutate={refreshShell} />;
  } else if (route.path === "/batch") {
    page = <BatchPage navigate={navigate} />;
  } else if (route.path === "/versions") {
    page = <VersionsPage navigate={navigate} />;
  } else if (route.path === "/api") {
    page = <ApiControlPage navigate={navigate} />;
  } else if (route.path === "/operations") {
    page = <OperationsPage navigate={navigate} onMutate={refreshShell} />;
  } else if (route.path === "/advanced") {
    page = <AdvancedPage />;
  } else if (route.path === "/studio" || route.path === "/workbench") {
    page = <WorkbenchPage route={route} shell={shell.data} navigate={navigate} onMutate={refreshShell} />;
  } else if (/^\/(?:runs|observatory)\/[^/]+\/compare\/[^/]+$/.test(route.path)) {
    const match = route.path.match(/^\/(?:runs|observatory)\/([^/]+)\/compare\/([^/]+)$/)!;
    page = <ComparePage routePath={route.path} candidateRunId={match[1]} baselineRunId={match[2]} navigate={navigate} />;
  } else if (/^\/workflows\/[^/]+$/.test(route.path)) {
    page = <WorkflowDetailPage workflowName={decodeURIComponent(route.path.split("/")[2])} navigate={navigate} onMutate={refreshShell} />;
  } else if (/^\/(?:runs|observatory)\/[^/]+$/.test(route.path)) {
    page = <RunDetailPage routePath={route.path} runId={route.path.split("/")[2]} navigate={navigate} onMutate={refreshShell} />;
  } else {
    page = <WorkbenchPage route={route} shell={shell.data} navigate={navigate} onMutate={refreshShell} />;
  }
  const surface = surfaceTitle(route.path, appChrome);

  return (
    <div className="app-shell product-shell">
      <aside className="icon-rail" aria-label="Primary product navigation">
        <a
          className="rail-brand"
          href="/hub"
          onClick={(event) => {
            event.preventDefault();
            navigate("/hub");
          }}
          aria-label="XRTM Hub"
        >
          X
        </a>
        <nav className="rail-nav" aria-label="Primary">
          {nav.map((item: JsonObject) => {
            const href = String(item.href || "/");
            const active = isNavItemActive(route.path, href);
            const label = String(item.label || href);
            return (
              <a
                key={href}
                className={active ? "rail-link active" : "rail-link"}
                href={href}
                title={label}
                aria-label={label}
                aria-current={active ? "page" : undefined}
                onClick={(event) => {
                  event.preventDefault();
                  navigate(href);
                }}
              >
                <span>{railIcon(label, href)}</span>
              </a>
            );
          })}
        </nav>
        <button className="rail-exit" title="Local shell" aria-label="Local shell">LS</button>
      </aside>
      <section className="product-main">
        <header className="product-topbar">
          <div className="product-title-block">
            <div className="product-route-line">
              <h1>{surface.title}</h1>
              <span className="product-route-context">{surface.eyebrow}</span>
            </div>
            <p className="shell-copy">{surface.summary}</p>
          </div>
          <div className="product-action-cluster">
            {shell.data?.app?.version ? <span className="version-pill">v{String(shell.data.app.version)}</span> : null}
            {shell.data ? <EnvironmentDisclosureView cards={environmentCards} trustCues={trustCues} status={shellStatus} /> : null}
            <ThemeModeSwitch mode={themeMode} resolvedTheme={resolvedTheme} onChange={setThemeMode} />
            <button
              type="button"
              className="shell-icon-button"
              title="Open API control"
              aria-label="Open API control"
              onClick={() => navigate("/api")}
            >
              <span aria-hidden="true">⚙</span>
            </button>
          </div>
        </header>
        {bootstrap.initial_error ? <Message tone="error" title="Initial error" body={bootstrap.initial_error} /> : null}
        {shell.error ? <Message tone="error" title="App shell error" body={shell.error} /> : null}
        {shell.loading && !shell.data ? <LoadingCard label="Loading app shell" /> : null}
        <div className="page-stack">{page}</div>
      </section>
    </div>
  );
}

function HubPage({ shell, navigate }: { shell: JsonObject | null; navigate: (path: string) => void }): React.ReactElement {
  const hub = (shell?.hub || shell?.overview) as JsonObject | undefined;
  if (!hub) {
    return <LoadingCard label="Loading Hub" />;
  }
  const hero = (hub.hero || shell?.overview?.hero || {}) as JsonObject;
  const doors = (hub.doors || []) as JsonObject[];
  const templates = (hub.templates || []) as JsonObject[];
  const workflows = (hub.workflows || []) as JsonObject[];
  const readiness = (hub.readiness || []) as JsonObject[];
  const counts = (hub.counts || shell?.overview?.counts || {}) as JsonObject;
  const latestRun = (hub.latest_run || shell?.overview?.latest_run) as JsonObject | null;
  const resumeTarget = (hub.resume_target || shell?.overview?.resume_target || {}) as JsonObject;
  const playgroundAction = (doors[0]?.primary_cta || {}) as JsonObject;
  const quickstartAction = (doors[0]?.secondary_cta || {}) as JsonObject;
  const studioAction = (doors[1]?.primary_cta || {}) as JsonObject;
  const hasResumeTarget = Boolean(resumeTarget.href) && String(resumeTarget.kind || "") !== "studio";
  const heroMetrics = [
    {
      label: "Templates",
      value: counts.templates ?? templates.length,
      detail: "Starter paths",
    },
    {
      label: "Workflows",
      value: counts.workflows ?? workflows.length,
      detail: "Indexed locally",
    },
    {
      label: "Runs",
      value: counts.runs ?? 0,
      detail: latestRun ? "Latest ready" : "Fresh shell",
    },
  ];
  const heroReadiness = readiness.slice(0, 2);
  const leadTemplates = templates.slice(0, 3);
  const overflowTemplates = templates.slice(3);
  const continuityTitle = hasResumeTarget
    ? String(resumeTarget.label || "Resume local work")
    : latestRun
      ? "Latest local run is ready"
      : "Fresh local shell";
  const continuitySummary = hasResumeTarget
    ? "Pick up the latest draft, Playground session, or run without leaving the Hub."
    : latestRun
      ? "Inspect the latest run when you want traces, artifacts, or provenance."
      : "Quickstart, Playground, and Studio are ready when you want a first local run or draft.";
  const workflowDisclosureTitle = `Indexed workflows · ${workflows.length}`;

  return (
    <main className="page-grid hub-page">
      <section className="panel hero-panel hub-hero">
        <div className="hub-hero-copy">
          <div className="hub-hero-heading">
            <span className="eyebrow">{hero.eyebrow || "Entry route"}</span>
            <h2>{hero.title || "Choose a first move"}</h2>
            <p>{hero.summary || "Run the first-success quickstart, open Playground for one bounded question, or enter Studio for a draft."}</p>
          </div>
          <div className="button-row hub-hero-actions">
            <button className="primary-button" onClick={() => navigate(String(playgroundAction.href || "/playground"))}>
              {String(playgroundAction.label || "Open Playground")}
            </button>
            <button className="secondary-button" onClick={() => navigate(String(studioAction.href || "/studio"))}>
              {String(studioAction.label || "Open Studio")}
            </button>
            <button className="secondary-button" onClick={() => navigate(String(quickstartAction.href || "/start"))}>
              {String(quickstartAction.label || "Run first-success quickstart")}
            </button>
          </div>
          <div className="hub-hero-metrics" aria-label="Hub overview">
            {heroMetrics.map((item) => (
              <article key={item.label} className="hub-hero-metric">
                <span>{item.label}</span>
                <strong>{formatValue(item.value)}</strong>
                <small>{item.detail}</small>
              </article>
            ))}
          </div>
        </div>
        <aside className="hub-hero-aside">
          <div className="hub-hero-aside-header">
            <span className="eyebrow">Continuity</span>
            <h3>{continuityTitle}</h3>
            <p>{continuitySummary}</p>
          </div>
          {hasResumeTarget ? (
            <button className="secondary-button hub-resume-button" onClick={() => navigate(String(resumeTarget.href))}>
              {String(resumeTarget.label || "Resume")}
            </button>
          ) : null}
          {heroReadiness.length ? (
            <div className="hub-hero-readiness" aria-label="Hub readiness">
              {heroReadiness.map((item) => (
                <div key={String(item.key || item.label)} className="hub-readiness-chip">
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                </div>
              ))}
            </div>
          ) : null}
        </aside>
      </section>

      <section className="hub-content-grid">
        <div className="hub-main-column">
          <section className="hub-section hub-door-section" aria-label="Hub entry doors">
            <div className="section-header hub-section-header">
              <div className="hub-section-intro">
                <span className="eyebrow">Entry doors</span>
                <h3>Pick a calm starting lane</h3>
                <p>Keep the template-first path upfront, while the workflow-authoring lane stays available when you need it.</p>
              </div>
            </div>
            <div className="hub-door-grid">
              {doors.map((door, index) => (
                <article key={String(door.key || door.label)} className="panel section-stack hub-door-card">
                  <div className="hub-door-topline">
                    <span className="hub-door-path">{index === 0 ? "Template-first path" : "Authoring path"}</span>
                    <StatusPill value={String(door.status || "local")} />
                  </div>
                  <div className="hub-door-heading">
                    <span className="eyebrow">{door.label}</span>
                    <h3>{door.title}</h3>
                  </div>
                  <p className="helper-text">{door.summary}</p>
                  <div className="button-row">
                    {door.primary_cta ? (
                      <button className="primary-button" onClick={() => navigate(String(door.primary_cta.href))}>
                        {String(door.primary_cta.label)}
                      </button>
                    ) : null}
                    {door.secondary_cta ? (
                      <button className="secondary-button" onClick={() => navigate(String(door.secondary_cta.href))}>
                        {String(door.secondary_cta.label)}
                      </button>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="panel section-stack hub-section" id="workflow-config-fields">
            <div className="section-header hub-section-header">
              <div className="hub-section-intro">
                <span className="eyebrow">Templates</span>
                <h3>Starter templates</h3>
                <p>Keep the newcomer-default set upfront, then open the broader starter catalog only when you need another path.</p>
              </div>
              <span className="section-count">{templates.length} starter {templates.length === 1 ? "path" : "paths"}</span>
            </div>
            <div className="hub-template-grid">
              {leadTemplates.map((template) => (
                <article key={String(template.template_id)} className="workflow-tile hub-template-card">
                  <div className="workflow-tile-head">
                    <strong>{template.title}</strong>
                    <StatusPill value={String(template.workflow_kind || "workflow")} />
                  </div>
                  <p className="workflow-note hub-card-copy">{template.description}</p>
                  {((template.tags || []) as string[]).length ? (
                    <div className="hub-tag-row">
                      {((template.tags || []) as string[]).slice(0, 3).map((tag) => <span key={tag} className="hub-tag">{tag}</span>)}
                    </div>
                  ) : null}
                  <div className="button-row hub-card-actions">
                    <button className="primary-button" onClick={() => navigate(String(template.playground_href || `/playground?context=template&template=${template.template_id}`))}>
                      Open Playground
                    </button>
                    <button className="secondary-button" onClick={() => navigate(String(template.studio_href || `/studio?mode=template&template=${template.template_id}`))}>
                      Open Studio
                    </button>
                  </div>
                </article>
              ))}
            </div>
            {overflowTemplates.length ? (
              <DensityDisclosure
                className="hub-template-disclosure"
                title={`More starter paths · ${overflowTemplates.length}`}
                detail="Keep the broader starter catalog nearby without turning the Hub into a wall of equal-priority cards."
              >
                <div className="hub-template-grid">
                  {overflowTemplates.map((template) => (
                    <article key={String(template.template_id)} className="workflow-tile hub-template-card">
                      <div className="workflow-tile-head">
                        <strong>{template.title}</strong>
                        <StatusPill value={String(template.workflow_kind || "workflow")} />
                      </div>
                      <p className="workflow-note hub-card-copy">{template.description}</p>
                      {((template.tags || []) as string[]).length ? (
                        <div className="hub-tag-row">
                          {((template.tags || []) as string[]).slice(0, 3).map((tag) => <span key={tag} className="hub-tag">{tag}</span>)}
                        </div>
                      ) : null}
                      <div className="button-row hub-card-actions">
                        <button className="primary-button" onClick={() => navigate(String(template.playground_href || `/playground?context=template&template=${template.template_id}`))}>
                          Open Playground
                        </button>
                        <button className="secondary-button" onClick={() => navigate(String(template.studio_href || `/studio?mode=template&template=${template.template_id}`))}>
                          Open Studio
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              </DensityDisclosure>
            ) : null}
            {!templates.length ? <EmptyState title="No starter templates found" body="The Hub could not load starter templates from the authoring catalog." /> : null}
          </section>

          <DensityDisclosure
            className="panel hub-workflow-disclosure"
            title={workflowDisclosureTitle}
            detail="Open the broader workflow catalog only when you want a specific saved workflow or draft path."
          >
            {workflows.length ? (
              <div className="hub-workflow-scroll">
                <div className="action-list hub-workflow-list">
                  {workflows.map((workflow) => (
                    <article key={String(workflow.name)} className="workflow-tile hub-workflow-card">
                      <div className="hub-workflow-copy">
                        <div className="workflow-tile-head">
                          <strong>{workflow.title || workflow.name}</strong>
                          <SourceBadge source={String(workflow.source || "builtin")} />
                        </div>
                        <p className="hub-workflow-name">{workflow.name}</p>
                        <p className="workflow-note hub-card-copy">{workflow.description || "Reusable workflow from the registry."}</p>
                        <div className="hub-workflow-meta">
                          <span>Runtime {workflow.runtime_provider || "mock"}</span>
                          <span>{formatValue(workflow.question_limit)} questions</span>
                        </div>
                      </div>
                      <div className="button-row hub-workflow-actions">
                        <button className="primary-button" onClick={() => navigate(String(workflow.playground_href || `/playground?context=workflow&workflow=${workflow.name}`))}>
                          Open Playground
                        </button>
                        <button className="secondary-button" onClick={() => navigate(String(workflow.studio_href || `/studio?workflow=${workflow.name}`))}>
                          Open Studio
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              </div>
            ) : (
              <EmptyState title="No workflows indexed" body="Refresh the local workflow registry or create a draft in Studio." />
            )}
          </DensityDisclosure>
        </div>

        <aside className="hub-side-column">
          <section className="panel section-stack hub-context-panel">
            <div className="section-header hub-section-header">
              <div className="hub-section-intro">
                <span className="eyebrow">Route context</span>
                <h3>Recent activity and local posture</h3>
                <p>Keep continuity visible in one calm side rail instead of stacking multiple equal-weight panels.</p>
              </div>
            </div>
            <div className="hub-context-block">
              <div className="hub-context-header">
                <span className="eyebrow">Recent activity</span>
                <h4>Latest local run</h4>
              </div>
              {latestRun ? (
                <article className="hub-run-card">
                  <div className="hub-run-header">
                    <div>
                      <strong>{latestRun.workflow?.title || latestRun.run_id}</strong>
                      <p className="workflow-note">{latestRun.workflow?.name || latestRun.provider || "Local run"}</p>
                    </div>
                    <StatusPill value={String(latestRun.status || "ready")} />
                  </div>
                  <dl className="context-list hub-run-meta">
                    <div><dt>Updated</dt><dd>{latestRun.updated_at || "—"}</dd></div>
                    <div><dt>Run ID</dt><dd>{latestRun.run_id || "—"}</dd></div>
                  </dl>
                  <button className="primary-button" onClick={() => navigate(`/observatory/${latestRun.run_id}`)}>Inspect latest run</button>
                </article>
              ) : (
                <EmptyState title="No runs yet" body="Open Playground or the first-success quickstart to create a local run history entry." />
              )}
            </div>
            <div className="hub-context-block">
              {readiness.length ? (
                <DensityDisclosure
                  className="hub-readiness-disclosure"
                  title={`Local readiness · ${readiness.length}`}
                  detail="System posture stays visible here without competing with the main entry flow."
                >
                  <div className="hub-readiness-list">
                    {readiness.map((item) => (
                      <article key={String(item.key || item.label)} className="info-card hub-readiness-card">
                        <div className="surface-header">
                          <strong>{item.label}</strong>
                          <StatusPill value={String(item.status || "ready")} />
                        </div>
                        <p className="helper-text">{item.value}</p>
                        {item.detail ? <span className="workflow-note">{item.detail}</span> : null}
                      </article>
                    ))}
                  </div>
                </DensityDisclosure>
              ) : (
                <EmptyState title="No readiness data" body="Hub readiness details were not available from the local shell." />
              )}
            </div>
          </section>
        </aside>
      </section>
    </main>
  );
}

function BatchPage({ navigate }: { navigate: (path: string) => void }): React.ReactElement {
  const batch = useJsonResource(`${bootstrap.api_root}/batch`, []);
  const versions = useJsonResource(`${bootstrap.api_root}/versions`, []);
  const [workflowName, setWorkflowName] = useState("");
  const [versionId, setVersionId] = useState("");
  const [label, setLabel] = useState("");
  const [rowsText, setRowsText] = useState("Will the batch remain local?\n{\"question\":\"Does JSONL work?\"}");
  const [notice, setNotice] = useState<{ tone: string; title: string; body: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [activeBatchId, setActiveBatchId] = useState("");
  const versionItems = (versions.data?.items || []) as JsonObject[];
  const batchItems = (batch.data?.items || []) as JsonObject[];
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
      const payload: JsonObject = { rows: rowsText, label: label || undefined };
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

  async function runBatchAction(item: JsonObject, action: "run" | "cancel" | "retry") {
    setBusy(true);
    setNotice(null);
    try {
      if (action === "cancel") {
        const updated = await requestJson(String(item.routes?.cancel || `${bootstrap.api_root}/batch/${item.id}`), {
          method: "PATCH",
          body: JSON.stringify({ action: "cancel" }),
        });
        setNotice({ tone: "success", title: "Batch cancellation requested", body: `${updated.label || updated.id} will stop after the current row.` });
      } else {
        const href = action === "run" ? String(item.routes?.run) : String(item.routes?.retry);
        const updated = await requestJson(href, { method: "POST", body: JSON.stringify({}) });
        setNotice({
          tone: "success",
          title: action === "run" ? "Batch started" : "Batch retry started",
          body: `${updated.label || updated.id} is now ${updated.status}.`,
        });
      }
      batch.reload();
    } catch (error) {
      setNotice(buildActionErrorNotice(`batch ${action}`, error));
    } finally {
      setBusy(false);
    }
  }

  function exportBatch(item: JsonObject, format: "json" | "csv") {
    const route = format === "csv" ? item.routes?.export_csv : item.routes?.export_json;
    if (!route) return;
    window.location.assign(String(route));
  }

  const batchHeroMetrics = [
    { label: "Staged", value: batch.data?.counts?.staged ?? 0, detail: "ready definitions" },
    { label: "Running", value: batch.data?.counts?.running ?? 0, detail: "live executions" },
    { label: "Completed", value: batch.data?.counts?.completed ?? 0, detail: "finished locally" },
    { label: "Workflow versions", value: versionItems.length, detail: "available snapshots" },
  ];
  const batchFocusItems = [
    {
      label: "Stage",
      title: "Capture rows against one snapshot",
      detail: "Start with a version or workflow fallback, then keep import detail bounded to the composer.",
    },
    {
      label: "Queue",
      title: "Scan live batches without row noise",
      detail: "The registry stays open for quick status checks while row-level detail waits below.",
    },
    {
      label: "Inspect",
      title: "Open row detail only when needed",
      detail: "Per-row progress and run links stay available, but they no longer dominate the default view.",
    },
  ];
  const activeBatchVersion = activeBatch?.version_id || activeBatch?.version?.id || "Workflow fallback";

  return (
    <main className="page-grid batch-shell operations-route">
      {batch.error ? <Message tone="error" title="Batch API unavailable" body={batch.error} /> : null}
      {versions.error ? <Message tone="error" title="Versions API unavailable" body={versions.error} /> : null}
      {notice ? <Message tone={notice.tone} title={notice.title} body={notice.body} /> : null}
      {batch.loading && !batch.data ? <LoadingCard label="Loading batch runner" /> : null}
      <section className="panel hero-panel operations-hero">
        <div className="operations-hero-grid">
          <div className="operations-hero-copy">
            <span className="eyebrow">Batch Runner</span>
            <h2>{batch.data?.surface?.title || "Run saved workflow snapshots across local question batches"}</h2>
            <p>
              {batch.data?.surface?.summary || "Map saved workflow versions to many forecasting questions, track row-level progress, and feed resolved evidence back into Observatory."}
            </p>
            <div className="button-row operations-hero-actions">
              <button className="primary-button" onClick={() => navigate("/versions")}>Create/select version</button>
              <button className="secondary-button" onClick={() => navigate("/observatory")}>Review analytics</button>
            </div>
          </div>
          <div className="operations-hero-side">
            <article className="operations-trust-card">
              <span className="eyebrow">Runtime contract</span>
              <strong>Local batch state stays aligned with shared workflow snapshots.</strong>
              <p>{batch.data?.execution_policy?.runtime_contract || "Batch executions reuse shared workflow snapshots and stay within the local product contract."}</p>
              <div className="operations-pill-row">
                <span className="shell-trust-pill">Local-first orchestration</span>
                <span className="shell-trust-pill">Version-aware staging</span>
                {activeBatch ? <StatusPill value={String(activeBatch.status || "staged")} /> : null}
              </div>
            </article>
            <div className="operations-stat-grid">
              {batchHeroMetrics.map((metric) => (
                <article key={metric.label} className="operations-stat-card">
                  <span>{metric.label}</span>
                  <strong>{metric.value}</strong>
                  <small>{metric.detail}</small>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>
      <RouteIdentityPanel
        className="batch-identity-panel"
        eyebrow="Batch flow"
        title="Stage, queue, then inspect deliberately"
        summary="Batch now reads as a dataset lane first: composition stays foregrounded, active queues stay scannable, and row detail opens only on demand."
        items={batchFocusItems}
      />
      <section className="split-grid operations-lead-grid">
        <article className="panel section-stack operations-form-panel">
          <div className="operations-section-heading">
            <div>
              <span className="eyebrow">Input mapping</span>
              <h3>Stage a local batch</h3>
              <p className="helper-text">Paste one question per line or JSONL rows. The batch snapshot stays local, aligned with CLI/WebUI workflow contracts, and can be executed, cancelled, retried, or exported.</p>
            </div>
            <div className="operations-pill-row">
              <span className="shell-trust-pill">Rows preview</span>
              <span className="shell-trust-pill">Export ready</span>
            </div>
          </div>
          <div className="operations-field-grid">
            <label>
              <span>Workflow version</span>
              <select value={versionId} onChange={(event) => setVersionId(event.target.value)}>
                <option value="">Use workflow name instead</option>
                {versionItems.map((item) => <option key={item.id} value={item.id}>{item.label || item.id}</option>)}
              </select>
            </label>
            <label>
              <span>Workflow name fallback</span>
              <input value={workflowName} onChange={(event) => setWorkflowName(event.target.value)} placeholder="demo-provider-free" />
            </label>
            <label className="operations-field-span">
              <span>Batch label</span>
              <input value={label} onChange={(event) => setLabel(event.target.value)} placeholder="Optional local label" />
            </label>
          </div>
          <label>
            <span>Rows</span>
            <textarea className="text-area-input batch-rows-input" value={rowsText} onChange={(event) => setRowsText(event.target.value)} />
          </label>
          <DensityDisclosure
            className="operations-subpanel section-stack"
            title={`Parsed row preview · ${parsedRowsPreview.length} rows`}
            detail="Questions are mapped immediately into the local row table, but the preview stays collapsed until you need to inspect it."
          >
            {parsedRowsPreview.length ? (
              <div className="mock-data-grid">
                <span>Row</span>
                <span>Question</span>
                <span>Title</span>
                {parsedRowsPreview.slice(0, 6).flatMap((row) => [
                  <span key={`row-${row.row_index}`}>{row.row_index}</span>,
                  <span key={`question-${row.row_index}`}>{row.question}</span>,
                  <span key={`title-${row.row_index}`}>{row.title || "—"}</span>,
                ])}
              </div>
            ) : (
              <EmptyState title="No batch rows parsed yet" body="Enter one question per line or JSONL rows with question/text/prompt fields." />
            )}
          </DensityDisclosure>
          <div className="operations-footer">
            <div className="operations-inline-note">
              <strong>Snapshot provenance stays attached.</strong>
              <p className="helper-text">Stage first, then run, retry, or export without changing the shared batch/API surface.</p>
            </div>
            <button className="primary-button" onClick={createBatchDefinition} disabled={busy || (!versionId && !workflowName) || !rowsText.trim()}>
              {busy ? "Creating batch" : "Stage batch"}
            </button>
          </div>
        </article>
        <article className="panel section-stack operations-summary-panel">
          <div className="operations-section-heading">
            <div>
              <span className="eyebrow">Execution</span>
              <h3>Batch posture</h3>
              <p className="helper-text">{batch.data?.execution_policy?.runtime_contract || "Batch executions reuse shared workflow snapshots and do not introduce WebUI-only execution."}</p>
            </div>
            {activeBatch ? <StatusPill value={String(activeBatch.status || "staged")} /> : <span className="shell-trust-pill">No active batch</span>}
          </div>
          <div className="operations-stat-grid">
            <article className="operations-stat-card">
              <span>With errors</span>
              <strong>{batch.data?.counts?.with_errors ?? 0}</strong>
              <small>rows needing review</small>
            </article>
            <article className="operations-stat-card">
              <span>Preview rows</span>
              <strong>{parsedRowsPreview.length}</strong>
              <small>captured instantly</small>
            </article>
            <article className="operations-stat-card">
              <span>Selected version</span>
              <strong>{versionId || "fallback"}</strong>
              <small>used for new stage</small>
            </article>
          </div>
          <article className="operations-subpanel">
            <div className="surface-header">
              <div>
                <strong>{activeBatch ? activeBatch.label || activeBatch.id : "No batch selected"}</strong>
                <p className="helper-text">{activeBatch ? "Keep detail close without flooding the route with row-level noise." : "Select a staged definition below to inspect version provenance and row posture."}</p>
              </div>
              {activeBatch ? <StatusPill value={String(activeBatch.status || "staged")} /> : null}
            </div>
            <div className="operations-keyline-list">
              <div><span>Version</span><strong>{activeBatchVersion}</strong></div>
              <div><span>Rows</span><strong>{activeBatch ? formatValue(activeBatch.row_count) : "—"}</strong></div>
              <div><span>Progress</span><strong>{activeBatch ? `${formatValue(activeBatch.progress?.percent)}%` : "—"}</strong></div>
            </div>
          </article>
        </article>
      </section>
      <section className="panel section-stack operations-table-card">
        <div className="operations-table-header">
          <div>
            <span className="eyebrow">Local batches</span>
            <h3>Staged definitions</h3>
            <p className="helper-text">Select a definition to inspect row-level progress, provenance, and export actions.</p>
          </div>
          <div className="operations-pill-row">
            <span className="shell-trust-pill">{batchItems.length} definitions</span>
            {activeBatch ? <span className="shell-trust-pill">Selected: {activeBatch.label || activeBatch.id}</span> : null}
          </div>
        </div>
        {batchItems.length ? (
          <div className="table-wrap operations-table-wrap">
            <table className="data-table">
                <thead><tr><th>Batch</th><th>Workflow</th><th>Status</th><th>Rows</th><th>Progress</th><th>Actions</th></tr></thead>
                <tbody>
                  {batchItems.map((item) => (
                    <tr key={item.id} className={String(item.id) === String(activeBatch?.id || "") ? "is-active" : undefined}>
                      <td>
                        <button
                          className="table-link-button operations-row-button"
                          type="button"
                          aria-pressed={String(item.id) === String(activeBatch?.id || "")}
                          onClick={() => setActiveBatchId(String(item.id))}
                        >
                          <span className="table-primary">{item.label || item.id}</span>
                          <span className="table-secondary">{item.id}</span>
                        </button>
                      </td>
                      <td>{item.workflow_name}</td>
                      <td><StatusPill value={item.status} /></td>
                      <td>{formatValue(item.row_count)}</td>
                    <td>{formatValue(item.progress?.percent)}%</td>
                    <td>
                      <div className="button-row operations-table-actions">
                        {item.status === "staged" ? <button className="primary-button" onClick={(event) => runWithoutRowSelection(event, () => void runBatchAction(item, "run"))} disabled={busy}>Run</button> : null}
                        {item.status === "queued" || item.status === "running" || item.status === "cancel-requested" ? <button className="secondary-button" onClick={(event) => runWithoutRowSelection(event, () => void runBatchAction(item, "cancel"))} disabled={busy}>Cancel</button> : null}
                        {item.status === "cancelled" || item.status === "failed" || item.status === "completed-with-errors" ? <button className="secondary-button" onClick={(event) => runWithoutRowSelection(event, () => void runBatchAction(item, "retry"))} disabled={busy}>Retry</button> : null}
                        <button className="secondary-button" onClick={(event) => runWithoutRowSelection(event, () => exportBatch(item, "csv"))}>CSV</button>
                        <button className="secondary-button" onClick={(event) => runWithoutRowSelection(event, () => exportBatch(item, "json"))}>JSON</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No batch definitions yet" body="Create a staged batch from a saved workflow version or workflow name." />
        )}
      </section>
      {activeBatch ? (
        <DensityDisclosure
          className="panel section-stack operations-detail-card"
          title={`${activeBatch.label || activeBatch.id} row detail`}
          detail="Open row-level progress only when you need the staged table and run links."
        >
          <div className="operations-detail-strip">
            <div><span>Completed</span><strong>{activeBatch.summary?.completed_rows ?? 0}</strong></div>
            <div><span>Failed</span><strong>{activeBatch.summary?.failed_rows ?? 0}</strong></div>
            <div><span>Cancelled</span><strong>{activeBatch.summary?.cancelled_rows ?? 0}</strong></div>
          </div>
          {Array.isArray(activeBatch.rows) && activeBatch.rows.length ? (
            <div className="table-wrap operations-table-wrap">
              <table className="data-table">
                <thead><tr><th>Row</th><th>Status</th><th>Question</th><th>Run</th><th>Result</th></tr></thead>
                <tbody>
                  {activeBatch.rows.map((row) => (
                    <tr key={`${activeBatch.id}-${row.row_index}`}>
                      <td>{row.row_index}</td>
                      <td><StatusPill value={row.status} /></td>
                      <td>{row.input?.question || row.input?.text || row.input?.prompt || "—"}</td>
                      <td>{row.run_href ? <button className="table-link-button" onClick={() => navigate(String(row.run_href))}>{row.run_id || "Open run"}</button> : "—"}</td>
                      <td>{row.result?.probability_summary?.cards?.[1]?.value != null ? `${formatValue(row.result.probability_summary.cards[1].value)} avg` : row.error || "Pending"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title="No staged rows" body="Add rows to this batch or select another batch definition." />
          )}
        </DensityDisclosure>
      ) : null}
    </main>
  );
}

function VersionsPage({ navigate }: { navigate: (path: string) => void }): React.ReactElement {
  const versions = useJsonResource(`${bootstrap.api_root}/versions`, []);
  const workflows = useJsonResource(`${bootstrap.api_root}/workflows`, []);
  const [workflowName, setWorkflowName] = useState("");
  const [label, setLabel] = useState("");
  const [parentId, setParentId] = useState("");
  const [selectedVersionId, setSelectedVersionId] = useState("");
  const [compareVersionId, setCompareVersionId] = useState("");
  const [diff, setDiff] = useState<JsonObject | null>(null);
  const [notice, setNotice] = useState<{ tone: string; title: string; body: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const versionItems = (versions.data?.items || []) as JsonObject[];
  const workflowItems = (workflows.data?.items || []) as JsonObject[];
  const selectedVersion = useMemo(() => {
    if (selectedVersionId) return versionItems.find((item) => String(item.id) === selectedVersionId) || versionItems[0] || null;
    return versionItems[0] || null;
  }, [selectedVersionId, versionItems]);
  const selectVersion = (id: string) => {
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
        body: JSON.stringify({ workflow_name: workflowName, label: label || undefined, parent_id: parentId || undefined }),
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

  async function runVersionSnapshot(item: JsonObject) {
    setBusy(true);
    setNotice(null);
    try {
      const result = await requestJson(String(item.routes?.run?.href || `${bootstrap.api_root}/versions/${item.id}/run`), {
        method: "POST",
        body: JSON.stringify({ user: "webui-versions" }),
      });
      versions.reload();
      setNotice({ tone: "success", title: "Version run completed", body: `${result.run_id} executed from ${item.label || item.id}.` });
    } catch (error) {
      setNotice(buildActionErrorNotice("version run", error));
    } finally {
      setBusy(false);
    }
  }

  async function rollbackVersion(item: JsonObject) {
    setBusy(true);
    setNotice(null);
    try {
      const result = await requestJson(String(item.routes?.rollback?.href || `${bootstrap.api_root}/versions/${item.id}/rollback`), {
        method: "POST",
        body: JSON.stringify({ mode: "version", label: `${item.workflow_name} rollback`, set_default: true }),
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

  async function setDefaultVersion(item: JsonObject) {
    setBusy(true);
    setNotice(null);
    try {
      const result = await requestJson(String(item.routes?.set_default?.href || `${bootstrap.api_root}/versions/${item.id}`), {
        method: "PATCH",
        body: JSON.stringify({ set_default: true }),
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
      detail: "safety posture",
    },
    {
      label: "Selected",
      value: selectedVersion?.label || selectedVersion?.id || "—",
      detail: "active comparison target",
    },
  ];
  const versionFocusItems = [
    {
      label: "Freeze",
      title: "Create a reusable lineage anchor",
      detail: "New snapshots stay close to the create form instead of expanding into a permanent provenance wall.",
    },
    {
      label: "Select",
      title: "Browse history from one calm registry",
      detail: "Default, rollback, and run actions remain visible while the table keeps the route grounded in lineage.",
    },
    {
      label: "Compare",
      title: "Open deeper diffs only when asked",
      detail: "Route metadata, recent runs, and graph/config deltas move behind deliberate disclosure.",
    },
  ];

  return (
    <main className="page-grid versions-shell operations-route">
      {versions.error ? <Message tone="error" title="Versions API unavailable" body={versions.error} /> : null}
      {workflows.error ? <Message tone="error" title="Workflow catalog unavailable" body={workflows.error} /> : null}
      {notice ? <Message tone={notice.tone} title={notice.title} body={notice.body} /> : null}
      {versions.loading && !versions.data ? <LoadingCard label="Loading versions" /> : null}
      <section className="panel hero-panel operations-hero">
        <div className="operations-hero-grid">
          <div className="operations-hero-copy">
            <span className="eyebrow">Versions</span>
            <h2>{versions.data?.surface?.title || "Prompt and graph provenance across Studio, Playground, Batch, and API runs"}</h2>
            <p>
              {versions.data?.surface?.summary || "Versioning becomes the connective tissue for graph snapshots, prompt/config diffs, run provenance, rollback, and workflow score comparisons."}
            </p>
            <div className="button-row operations-hero-actions">
              <button className="primary-button" onClick={() => navigate("/studio")}>Open Studio</button>
              <button className="secondary-button" onClick={() => navigate("/batch")}>Use in Batch</button>
            </div>
          </div>
          <div className="operations-hero-side">
            <article className="operations-trust-card">
              <span className="eyebrow">Provenance</span>
              <strong>Immutable local snapshots keep Batch, Studio, and API on one lineage spine.</strong>
              <p>{selectedVersion?.run_provenance?.execution_linkage?.notes?.[0] || "Snapshots preserve the shared workflow blueprint contract and keep run provenance visible without dominating the page."}</p>
              <div className="operations-pill-row">
                <span className="shell-trust-pill">Immutable history</span>
                <span className="shell-trust-pill">Rollback ready</span>
                {selectedVersion?.is_default ? <StatusPill value="default" /> : null}
              </div>
            </article>
            <div className="operations-stat-grid">
              {versionHeroMetrics.map((metric) => (
                <article key={metric.label} className="operations-stat-card">
                  <span>{metric.label}</span>
                  <strong>{metric.value}</strong>
                  <small>{metric.detail}</small>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>
      <RouteIdentityPanel
        className="versions-identity-panel"
        eyebrow="Lineage rhythm"
        title="Freeze, select, and compare with less framing noise"
        summary="Versions now foregrounds snapshot lineage and reusable defaults, while deeper provenance tools stay one click away."
        items={versionFocusItems}
      />
      <section className="split-grid operations-lead-grid">
        <article className="panel section-stack operations-form-panel">
          <div className="operations-section-heading">
            <div>
              <span className="eyebrow">Create snapshot</span>
              <h3>Freeze a shared workflow blueprint</h3>
              <p className="helper-text">Capture a crisp revision without adding a dense provenance wall to the route.</p>
            </div>
            <div className="operations-pill-row">
              <span className="shell-trust-pill">Shared contract</span>
              <span className="shell-trust-pill">Diffable state</span>
            </div>
          </div>
          <div className="operations-field-grid">
            <label>
              <span>Workflow</span>
              <select value={workflowName} onChange={(event) => setWorkflowName(event.target.value)}>
                {!workflowItems.length ? <option value="">No workflows registered yet</option> : null}
                {workflowItems.map((item) => <option key={item.name} value={item.name}>{item.title || item.name}</option>)}
              </select>
            </label>
            <label>
              <span>Label</span>
              <input value={label} onChange={(event) => setLabel(event.target.value)} placeholder="Macro consensus v3" />
            </label>
            <label className="operations-field-span">
              <span>Parent version</span>
              <select value={parentId} onChange={(event) => setParentId(event.target.value)}>
                <option value="">None</option>
                {versionItems.map((item) => <option key={item.id} value={item.id}>{item.label || item.id}</option>)}
              </select>
            </label>
          </div>
          <div className="operations-footer">
            <div className="operations-inline-note">
              <strong>Every snapshot is reusable elsewhere.</strong>
              <p className="helper-text">The same saved version can move straight into Batch or Control with no route-specific branching.</p>
            </div>
            <button className="primary-button" onClick={createVersionSnapshot} disabled={busy || !workflowName}>{busy ? "Creating version" : "Create version"}</button>
          </div>
        </article>
        <article className="panel section-stack operations-summary-panel">
          <div className="operations-section-heading">
            <div>
              <span className="eyebrow">Contract</span>
              <h3>CLI/WebUI aligned snapshots</h3>
              <p className="helper-text">{versions.data?.guidance?.runtime_contract || "Snapshots preserve the shared workflow blueprint contract and do not add WebUI-only code paths."}</p>
            </div>
            {selectedVersion?.is_default ? <StatusPill value="default" /> : <span className="shell-trust-pill">Local provenance</span>}
          </div>
          <div className="operations-stat-grid">
            <article className="operations-stat-card">
              <span>Recent runs</span>
              <strong>{selectedVersion?.run_provenance?.recent_run_ids?.length ?? 0}</strong>
              <small>linked to selected snapshot</small>
            </article>
            <article className="operations-stat-card">
              <span>Parent lineage</span>
              <strong>{selectedVersion?.parent_id || "root"}</strong>
              <small>rollback anchor</small>
            </article>
            <article className="operations-stat-card">
              <span>Runtime</span>
              <strong>{selectedVersion?.config?.runtime?.provider || selectedVersion?.metadata?.runtime_provider || "—"}</strong>
              <small>execution provider</small>
            </article>
          </div>
          <article className="operations-subpanel">
            <div className="surface-header">
              <div>
                <strong>{selectedVersion?.label || selectedVersion?.id || "No version selected"}</strong>
                <p className="helper-text">{selectedVersion ? "Keep default, rollback, and run lineage close at hand while the route stays visually quiet." : "Choose a version below to inspect its lineage and route contract."}</p>
              </div>
              {selectedVersion?.is_default ? <StatusPill value="default" /> : null}
            </div>
            <div className="operations-keyline-list">
              <div><span>Workflow</span><strong>{selectedVersion?.workflow_name || "—"}</strong></div>
              <div><span>Last run</span><strong>{selectedVersion?.run_provenance?.last_run_id || "—"}</strong></div>
              <div><span>Created</span><strong>{selectedVersion ? formatTimestamp(selectedVersion.created_at) : "—"}</strong></div>
            </div>
          </article>
        </article>
      </section>
      <section className="panel section-stack operations-table-card">
        <div className="operations-table-header">
          <div>
            <span className="eyebrow">Version history</span>
            <h3>Local snapshots</h3>
            <p className="helper-text">Browse lineage, run, default, and rollback actions without collapsing the route into a dense admin ledger.</p>
          </div>
          <div className="operations-pill-row">
            <span className="shell-trust-pill">{versionItems.length} snapshots</span>
            {selectedVersion ? <span className="shell-trust-pill">Selected: {selectedVersion.label || selectedVersion.id}</span> : null}
          </div>
        </div>
        {versionItems.length ? (
          <div className="table-wrap operations-table-wrap">
            <table className="data-table">
                <thead><tr><th>Version</th><th>Workflow</th><th>Source</th><th>Parent</th><th>Created</th><th>Actions</th></tr></thead>
                <tbody>
                  {versionItems.map((item) => (
                    <tr key={item.id} className={String(item.id) === String(selectedVersion?.id || "") ? "is-active" : undefined}>
                      <td>
                        <button
                          className="table-link-button operations-row-button"
                          type="button"
                          aria-pressed={String(item.id) === String(selectedVersion?.id || "")}
                          onClick={() => selectVersion(String(item.id))}
                        >
                          <span className="table-primary">{item.label || item.id}</span>
                          <span className="table-secondary">{item.id}</span>
                        </button>
                      </td>
                      <td><button className="table-link-button" onClick={(event) => runWithoutRowSelection(event, () => navigate(`/studio?workflow=${encodeURIComponent(String(item.workflow_name))}`))}>{item.workflow_name}</button></td>
                    <td>{item.source}</td>
                    <td>{item.parent_id || "—"}</td>
                    <td>{formatTimestamp(item.created_at)}</td>
                    <td>
                      <div className="button-row operations-table-actions">
                        <button className="secondary-button" onClick={(event) => runWithoutRowSelection(event, () => void runVersionSnapshot(item))} disabled={busy}>Run</button>
                        <button className="secondary-button" onClick={(event) => runWithoutRowSelection(event, () => void setDefaultVersion(item))} disabled={busy || item.is_default}>Default</button>
                        <button className="secondary-button" onClick={(event) => runWithoutRowSelection(event, () => void rollbackVersion(item))} disabled={busy}>Rollback</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No version snapshots yet" body="Create one from a registered workflow, then use it in Batch or Control." />
        )}
      </section>
      {selectedVersion ? (
        <DensityDisclosure
          className="panel section-stack operations-detail-card versions-detail-panel"
          title={`${selectedVersion.label || selectedVersion.id} lineage detail`}
          detail="Open recent runs, compare tools, and route metadata only when you need deeper provenance context."
        >
          <div className="operations-table-header">
            <div>
              <span className="eyebrow">Selected version</span>
              <h3>{selectedVersion.label || selectedVersion.id}</h3>
              <p className="helper-text">{selectedVersion.run_provenance?.execution_linkage?.notes?.[0] || "Version snapshots keep run provenance attached to the shared local workflow contract."}</p>
            </div>
            <div className="operations-pill-row">
              {selectedVersion.is_default ? <StatusPill value="default" /> : null}
              <span className="shell-trust-pill">{selectedVersion.source || "local snapshot"}</span>
            </div>
          </div>
          <div className="operations-detail-strip">
            <div><span>Workflow</span><strong>{selectedVersion.workflow_name}</strong></div>
            <div><span>Parent</span><strong>{selectedVersion.parent_id || "—"}</strong></div>
            <div><span>Last run</span><strong>{selectedVersion.run_provenance?.last_run_id || "—"}</strong></div>
            <div><span>Provider</span><strong>{selectedVersion.config?.runtime?.provider || selectedVersion.metadata?.runtime_provider || "—"}</strong></div>
          </div>
          {Array.isArray(selectedVersion.run_provenance?.recent_run_ids) && selectedVersion.run_provenance.recent_run_ids.length ? (
            <div className="button-row operations-related-actions">
              {selectedVersion.run_provenance.recent_run_ids.map((runId: string) => (
                <button key={runId} className="secondary-button" onClick={() => navigate(`/runs/${encodeURIComponent(runId)}`)}>{runId}</button>
              ))}
            </div>
          ) : null}
          <div className="operations-card-grid">
            <DensityDisclosure
              className="operations-subpanel section-stack"
              title="Compare snapshots"
              detail="Open graph and config path diffs only when you need lineage detail."
            >
              <label>
                <span>Compare against</span>
                <select value={compareVersionId} onChange={(event) => setCompareVersionId(event.target.value)}>
                  <option value="">Select another version</option>
                  {versionItems.filter((item) => String(item.id) !== String(selectedVersion.id)).map((item) => (
                    <option key={item.id} value={item.id}>{item.label || item.id}</option>
                  ))}
                </select>
              </label>
              <button className="primary-button" onClick={loadDiff} disabled={busy || !compareVersionId}>Load diff</button>
              {diff ? (
                <>
                  <div className="operations-detail-strip compact-detail-strip">
                    <div><span>Changed paths</span><strong>{diff.summary?.changed ?? 0}</strong></div>
                    <div><span>Same workflow</span><strong>{diff.summary?.same_workflow ? "yes" : "no"}</strong></div>
                  </div>
                  <pre className="code-card">{JSON.stringify(diff.changed_paths || [], null, 2)}</pre>
                </>
              ) : <p className="helper-text">Load a diff to inspect graph/config/canvas path changes between two local snapshots.</p>}
            </DensityDisclosure>
            <DensityDisclosure
              className="operations-subpanel section-stack"
              title="Snapshot summary"
              detail="Keep route metadata and graph counts available without leaving JSON panels open all the time."
            >
              <div className="operations-detail-strip compact-detail-strip">
                <div><span>Nodes</span><strong>{Object.keys(selectedVersion.graph?.nodes || {}).length}</strong></div>
                <div><span>Edges</span><strong>{(selectedVersion.graph?.edges || []).length}</strong></div>
                <div><span>Provider</span><strong>{selectedVersion.config?.runtime?.provider || selectedVersion.metadata?.runtime_provider || "—"}</strong></div>
              </div>
              <pre className="code-card">{JSON.stringify(selectedVersion.routes || {}, null, 2)}</pre>
            </DensityDisclosure>
          </div>
        </DensityDisclosure>
      ) : null}
    </main>
  );
}

function ApiControlPage({ navigate }: { navigate: (path: string) => void }): React.ReactElement {
  const api = useJsonResource(`${bootstrap.api_root}/api-control`, []);
  const webhooks = useJsonResource(`${bootstrap.api_root}/webhooks`, []);
  const [url, setUrl] = useState("https://example.com/xrtm");
  const [events, setEvents] = useState("run.completed,batch.completed");
  const [secret, setSecret] = useState("");
  const [versionId, setVersionId] = useState("");
  const [notice, setNotice] = useState<{ tone: string; title: string; body: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const endpoints = (webhooks.data?.items || []) as JsonObject[];
  const deliveries = (webhooks.data?.deliveries || []) as JsonObject[];
  const versionItems = (api.data?.snapshots?.versions?.items || []) as JsonObject[];

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
          secret: secret || undefined,
        }),
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

  async function deleteWebhook(id: string) {
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

  async function testWebhook(id: string) {
    setBusy(`Testing ${id}`);
    setNotice(null);
    try {
      const result = await requestJson(`${bootstrap.api_root}/webhooks/${id}/test`, {
        method: "POST",
        body: JSON.stringify({ event_type: "run.completed" }),
      });
      webhooks.reload();
      api.reload();
      setNotice({
        tone: result.delivery?.status === "delivered" ? "success" : "warning",
        title: "Webhook test sent",
        body: `${id} returned ${result.delivery?.status || "unknown"}.`,
      });
    } catch (error) {
      setNotice(buildActionErrorNotice("webhook test", error));
    } finally {
      setBusy(null);
    }
  }

  async function retryDelivery(id: string) {
    setBusy(`Retrying ${id}`);
    setNotice(null);
    try {
      const delivery = await requestJson(`${bootstrap.api_root}/webhooks/deliveries/${id}/retry`, { method: "POST", body: JSON.stringify({}) });
      webhooks.reload();
      api.reload();
      setNotice({
        tone: delivery.status === "delivered" ? "success" : "warning",
        title: "Delivery retried",
        body: `${id} is now ${delivery.status}.`,
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
        body: JSON.stringify({ user: "webui-api" }),
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
    { label: "Token mode", value: String(api.data?.token_behavior?.mode || "local-no-auth"), detail: "current auth posture" },
  ];
  const apiFocusItems = [
    {
      label: "Run",
      title: "Lead with saved version execution",
      detail: "The default control surface keeps version-backed runs first so newcomers land on the shared contract.",
    },
    {
      label: "Integrate",
      title: "Keep webhook setup adjacent, not dominant",
      detail: "Endpoint registration stays visible beside execution without turning the route into a dense admin console.",
    },
    {
      label: "Audit",
      title: "Review delivery history on demand",
      detail: "Recent attempts and retries remain available, but signed log detail is tucked behind disclosure.",
    },
  ];

  return (
    <main className="page-grid api-shell operations-route">
      {api.error ? <Message tone="error" title="Control unavailable" body={api.error} /> : null}
      {webhooks.error ? <Message tone="error" title="Webhook registry unavailable" body={webhooks.error} /> : null}
      {notice ? <Message tone={notice.tone} title={notice.title} body={notice.body} /> : null}
      {api.loading && !api.data ? <LoadingCard label="Loading Control" /> : null}
      <section className="panel hero-panel operations-hero">
        <div className="operations-hero-grid">
          <div className="operations-hero-copy">
            <span className="eyebrow">Control</span>
            <h2>{api.data?.surface?.title || "Local control and integration plane"}</h2>
            <p>
              {api.data?.surface?.summary || "Run saved versions, inspect batch and webhook state, and manage local integration settings without leaving the product shell."}
            </p>
            <div className="button-row operations-hero-actions">
              <button className="primary-button" onClick={() => navigate("/versions")}>Select version</button>
              <button className="secondary-button" onClick={() => navigate("/batch")}>Create batch</button>
            </div>
          </div>
          <div className="operations-hero-side">
            <article className="operations-trust-card">
              <span className="eyebrow">Trust cues</span>
              <strong>Token posture, version routing, and webhook signing stay visible without taking over the route.</strong>
              <p>{api.data?.token_behavior?.notes?.[0] || "The control plane is local-only and does not require auth tokens today."}</p>
              <div className="operations-pill-row">
                <span className="shell-trust-pill">Signed deliveries</span>
                <span className="shell-trust-pill">Local integration plane</span>
                <span className="shell-trust-pill">Token: {String(api.data?.token_behavior?.mode || "local-no-auth")}</span>
              </div>
            </article>
            <div className="operations-stat-grid">
              {apiHeroMetrics.map((metric) => (
                <article key={metric.label} className="operations-stat-card">
                  <span>{metric.label}</span>
                  <strong>{metric.value}</strong>
                  <small>{metric.detail}</small>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>
      <RouteIdentityPanel
        className="api-identity-panel"
        eyebrow="Control loop"
        title="Run, integrate, then audit as needed"
        summary="Control now emphasizes the primary local API workflow first, with endpoint setup and signed delivery history stepping back until needed."
        items={apiFocusItems}
      />
      <section className="split-grid operations-lead-grid">
        <article className="panel section-stack operations-form-panel">
          <div className="operations-section-heading">
            <div>
              <span className="eyebrow">Execution API</span>
              <h3>Run a saved version snapshot</h3>
              <p className="helper-text">{api.data?.execution_policy?.summary || "The API records local state and delegates execution to shared product workflow services."}</p>
            </div>
            <div className="operations-pill-row">
              <span className="shell-trust-pill">Version-aware routes</span>
              <span className="shell-trust-pill">Token: {String(api.data?.token_behavior?.mode || "local-no-auth")}</span>
            </div>
          </div>
          <label>
              <span>Version</span>
              <select value={versionId} onChange={(event) => setVersionId(event.target.value)}>
                {!versionItems.length ? <option value="">No saved versions yet</option> : null}
                {versionItems.map((item) => <option key={item.id} value={item.id}>{item.label || item.id}</option>)}
              </select>
            </label>
          <div className="operations-footer">
            <div className="operations-inline-note">
              <strong>Published routes stay shared.</strong>
              <p className="helper-text">Use the same saved version from this route, Batch, or Versions without changing the API contract.</p>
            </div>
            <button className="primary-button" onClick={runVersionSnapshot} disabled={Boolean(busy) || !versionId}>
              {busy?.startsWith("Running ") ? busy : "Run version"}
            </button>
          </div>
          <div className="operations-card-grid">
            <DensityDisclosure
              className="operations-subpanel section-stack"
              title="Route examples"
              detail="Keep example payloads nearby without leaving long JSON blocks open on the main surface."
            >
              <pre className="code-card">{JSON.stringify(api.data?.route_examples || [], null, 2)}</pre>
            </DensityDisclosure>
            <DensityDisclosure
              className="operations-subpanel section-stack"
              title="Shared endpoints"
              detail="Published route contracts stay available here, but collapsed until you need them."
            >
              <pre className="code-card">{JSON.stringify(api.data?.routes || { versions: "/api/versions", batch: "/api/batch", webhooks: "/api/webhooks" }, null, 2)}</pre>
            </DensityDisclosure>
          </div>
        </article>
        <article className="panel section-stack operations-form-panel">
          <div className="operations-section-heading">
            <div>
              <span className="eyebrow">Webhooks</span>
              <h3>Register a signed lifecycle endpoint</h3>
              <p className="helper-text">Endpoints support signed test deliveries and manual retry from the same muted control surface.</p>
            </div>
            <div className="operations-pill-row">
              <span className="shell-trust-pill">Signed test delivery</span>
              <span className="shell-trust-pill">Manual retry</span>
            </div>
          </div>
          <div className="operations-field-grid">
            <label className="operations-field-span"><span>URL</span><input value={url} onChange={(event) => setUrl(event.target.value)} /></label>
            <label><span>Events</span><input value={events} onChange={(event) => setEvents(event.target.value)} /></label>
            <label><span>Secret</span><input type="password" autoComplete="new-password" value={secret} onChange={(event) => setSecret(event.target.value)} placeholder="Optional signing secret" /></label>
          </div>
          <div className="operations-footer">
            <div className="operations-inline-note">
              <strong>Signing metadata stays visible.</strong>
              <p className="helper-text">Keep delivery trust cues close without forcing operators into a dense registry wall.</p>
            </div>
            <button className="primary-button" onClick={createWebhook} disabled={Boolean(busy) || !url.trim()}>{busy === "Creating webhook" ? busy : "Register webhook"}</button>
          </div>
          <article className="operations-subpanel">
            <div className="operations-keyline-list">
              <div><span>Endpoints</span><strong>{endpoints.length}</strong></div>
              <div><span>Deliveries</span><strong>{deliveries.length}</strong></div>
              <div><span>Secret</span><strong>{secret.trim() ? "provided" : "optional"}</strong></div>
            </div>
          </article>
        </article>
      </section>
      <section className="panel section-stack operations-table-card">
        <div className="operations-table-header">
          <div>
            <span className="eyebrow">Webhook registry</span>
            <h3>Endpoints and deliveries</h3>
            <p className="helper-text">Keep endpoint health, signing, and actions visible with more breathing room around each registry row.</p>
          </div>
          <div className="operations-pill-row">
            <span className="shell-trust-pill">{endpoints.length} endpoints</span>
            <span className="shell-trust-pill">{deliveries.length} deliveries</span>
          </div>
        </div>
        {endpoints.length ? (
          <div className="table-wrap operations-table-wrap">
            <table className="data-table">
              <thead><tr><th>Endpoint</th><th>Events</th><th>Signing</th><th>Status</th><th /></tr></thead>
              <tbody>
                {endpoints.map((endpoint) => (
                  <tr key={endpoint.id}>
                    <td><div className="table-primary">{endpoint.url}</div><div className="table-secondary">{endpoint.id}</div></td>
                    <td>{(endpoint.events || []).join(", ")}</td>
                    <td>{endpoint.signing?.secret_set ? endpoint.signing.secret_hint : "not set"}</td>
                    <td><StatusPill value={endpoint.enabled ? "enabled" : "disabled"} /></td>
                    <td>
                      <div className="button-row operations-table-actions">
                        <button className="secondary-button" onClick={() => void testWebhook(String(endpoint.id))} disabled={Boolean(busy)}>Test</button>
                        <button className="secondary-button" onClick={() => void deleteWebhook(String(endpoint.id))} disabled={Boolean(busy)}>Delete</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No webhooks registered" body="Register a local endpoint to prepare for signed lifecycle deliveries." />
        )}
      </section>
      <DensityDisclosure
        className="panel section-stack operations-table-card operations-log-panel"
        title={`Delivery log · ${deliveries.length}`}
        detail="Open signed delivery history only when you need to inspect responses or retry failed attempts."
      >
        {deliveries.length ? (
          <div className="table-wrap operations-table-wrap">
            <table className="data-table">
              <thead><tr><th>Delivery</th><th>Event</th><th>Status</th><th>Attempts</th><th>Response</th><th /></tr></thead>
              <tbody>
                {deliveries.map((delivery) => (
                  <tr key={delivery.id}>
                    <td><div className="table-primary">{delivery.id}</div><div className="table-secondary">{delivery.endpoint_id}</div></td>
                    <td>{delivery.event_type}</td>
                    <td><StatusPill value={delivery.status} /></td>
                    <td>{delivery.attempts}</td>
                    <td>{delivery.response_status || delivery.error || "—"}</td>
                    <td>{delivery.status === "failed" ? <button className="secondary-button" onClick={() => void retryDelivery(String(delivery.id))} disabled={Boolean(busy)}>Retry</button> : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No deliveries yet" body="Run a saved version, batch, or webhook test to populate the delivery log." />
        )}
      </DensityDisclosure>
    </main>
  );
}

function StartPage({
  shell,
  navigate,
  onMutate,
}: {
  shell: JsonObject | null;
  navigate: (path: string) => void;
  onMutate: () => void;
}): React.ReactElement {
  const health = useJsonResource(`${bootstrap.api_root}/health`, []);
  const providers = useJsonResource(`${bootstrap.api_root}/providers/status`, []);
  const workflows = useJsonResource(`${bootstrap.api_root}/workflows`, []);
  const runs = useJsonResource(`${bootstrap.api_root}/runs`, []);
  const [mode, setMode] = useState("start");
  const [provider, setProvider] = useState("mock");
  const [limit, setLimit] = useState("2");
  const [user, setUser] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [maxTokens, setMaxTokens] = useState("768");
  const [baselineRunId, setBaselineRunId] = useState("");
  const [selectedWorkflow, setSelectedWorkflow] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: string; title: string; body: string } | null>(null);
  const [result, setResult] = useState<JsonObject | null>(null);
  const workflowDetail = useJsonResource(
    selectedWorkflow ? `${bootstrap.api_root}/workflows/${encodeURIComponent(selectedWorkflow)}` : null,
    [selectedWorkflow],
  );
  const workflowExplain = useJsonResource(
    selectedWorkflow ? `${bootstrap.api_root}/workflows/${encodeURIComponent(selectedWorkflow)}/explain` : null,
    [selectedWorkflow],
  );

  useEffect(() => {
    const items = (workflows.data?.items || []) as JsonObject[];
    if (!selectedWorkflow && items.length) {
      setSelectedWorkflow(String(items[0].name || ""));
    }
  }, [selectedWorkflow, workflows.data]);

  async function launchRun() {
    setBusy("Running");
    setNotice(null);
    try {
      const payload: JsonObject = { limit: Number(limit), user: user || undefined };
      if (baselineRunId) {
        payload.baseline_run_id = baselineRunId;
      }
      let response: JsonObject;
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
        body:
          response.compare?.href
            ? "The candidate is ready with a baseline comparison link."
            : "Inspect the new run now, then export or compare it from the run detail page.",
      });
    } catch (error) {
      setNotice(buildActionErrorNotice("run", error));
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="page-grid">
      <section className="panel hero-panel">
        <span className="eyebrow">Start</span>
        <h2>Run first success without leaving the WebUI</h2>
        <p>Use the provider-free quickstart, launch a bounded demo, or run a named workflow with the same product services used by the CLI.</p>
        <div className="button-row">
          <button className="primary-button" onClick={launchRun} disabled={Boolean(busy) || (mode === "workflow" && !selectedWorkflow)}>
            {busy || (mode === "start" ? "Run quickstart" : mode === "demo" ? "Run demo" : "Run workflow")}
          </button>
          {selectedWorkflow ? (
            <button className="secondary-button" onClick={() => navigate(`/workflows/${encodeURIComponent(selectedWorkflow)}`)}>
              Open workflow detail
            </button>
          ) : null}
          {shell?.overview?.latest_run?.run_id ? (
            <button className="secondary-button" onClick={() => navigate(`/runs/${shell.overview.latest_run.run_id}`)}>
              Inspect latest run
            </button>
          ) : null}
        </div>
      </section>

      {notice ? <Message tone={notice.tone} title={notice.title} body={notice.body} /> : null}
      {result ? <RunLaunchResultCard result={result} navigate={navigate} /> : null}

      <div className="split-grid">
        <section className="panel section-stack">
          <div className="section-header">
            <div>
              <h3>Run controls</h3>
              <p>Start small with the released baseline, then move to demo or named workflow execution.</p>
            </div>
          </div>
          <form
            className="form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              void launchRun();
            }}
          >
            <label>
              <span>Mode</span>
              <select value={mode} onChange={(event) => setMode(event.target.value)}>
                <option value="start">First-success quickstart</option>
                <option value="demo">Bounded demo run</option>
                <option value="workflow">Named workflow run</option>
              </select>
            </label>
            {mode === "workflow" ? (
              <label>
                <span>Workflow</span>
                <select value={selectedWorkflow} onChange={(event) => setSelectedWorkflow(event.target.value)}>
                  {(workflows.data?.items || []).map((item: JsonObject) => (
                    <option key={item.name} value={item.name}>
                      {item.title || item.name}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            {mode !== "start" ? (
              <label>
                <span>Provider</span>
                <select value={provider} onChange={(event) => setProvider(event.target.value)}>
                  <option value="mock">Provider-free baseline</option>
                  <option value="local-llm">Local OpenAI-compatible endpoint</option>
                </select>
              </label>
            ) : null}
            <div className="two-field-grid">
              <label>
                <span>Question limit</span>
                <input value={limit} onChange={(event) => setLimit(event.target.value)} />
              </label>
              <label>
                <span>Baseline run</span>
                <select value={baselineRunId} onChange={(event) => setBaselineRunId(event.target.value)}>
                  <option value="">None</option>
                  {(runs.data?.items || []).map((run: JsonObject) => (
                    <option key={run.run_id} value={run.run_id}>
                      {run.run_id}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {mode !== "start" && provider === "local-llm" ? (
              <div className="two-field-grid">
                <label>
                  <span>Base URL</span>
                  <input value={baseUrl} placeholder="http://localhost:8000/v1" onChange={(event) => setBaseUrl(event.target.value)} />
                </label>
                <label>
                  <span>Model</span>
                  <input value={model} placeholder="your-model-id" onChange={(event) => setModel(event.target.value)} />
                </label>
              </div>
            ) : null}
            {mode !== "start" ? (
              <label>
                <span>Max tokens</span>
                <input value={maxTokens} onChange={(event) => setMaxTokens(event.target.value)} />
              </label>
            ) : null}
            <label>
              <span>User attribution</span>
              <input value={user} placeholder="Optional analyst or operator name" onChange={(event) => setUser(event.target.value)} />
            </label>
          </form>
        </section>

        <section className="panel section-stack">
          <div className="section-header">
            <div>
              <h3>Environment health</h3>
              <p>Readiness, provider status, and the currently selected workflow stay visible before you launch anything.</p>
            </div>
          </div>
          <div className="stats-grid">
            <MetricCard label="Ready checks passing" value={(health.data?.checks || []).filter((item: JsonObject) => item.ok).length} />
            <MetricCard label="Checks total" value={(health.data?.checks || []).length} />
            <MetricCard label="Local LLM healthy" value={String(Boolean(providers.data?.local_llm?.healthy))} />
          </div>
          {health.error ? <Message tone="error" title="Health unavailable" body={health.error} /> : null}
          {(health.data?.checks || []).length ? (
            <div className="card-grid">
              {(health.data?.checks || []).map((item: JsonObject) => (
                <article key={item.name} className="info-card">
                  <div className="surface-header">
                    <strong>{item.name}</strong>
                    <StatusPill value={item.ok ? "ready" : "failed"} />
                  </div>
                  <p className="helper-text">{item.detail}</p>
                </article>
              ))}
            </div>
          ) : null}
          <div className="provider-status-grid">
            <article className="info-card">
              <h4>Provider-free baseline</h4>
              <p className="helper-text">Works out of the box for first success and deterministic smoke validation.</p>
            </article>
            <article className="info-card">
              <h4>Local OpenAI-compatible</h4>
              <p className="helper-text">
                {providers.data?.local_llm?.healthy
                  ? `Healthy at ${providers.data?.local_llm?.base_url || "configured endpoint"}.`
                  : providers.data?.local_llm?.status || "Currently unavailable."}
              </p>
            </article>
          </div>
        </section>
      </div>

      <section className="panel section-stack">
        <div className="section-header">
          <div>
            <h3>Workflow guide</h3>
            <p>Inspect the selected workflow before running it so the graph and expected artifacts stay explicit.</p>
          </div>
        </div>
        {workflowDetail.loading && !workflowDetail.data ? <LoadingCard label="Loading workflow detail" /> : null}
        {workflowDetail.error ? <Message tone="error" title="Workflow detail unavailable" body={workflowDetail.error} /> : null}
        {workflowDetail.data ? (
          <div className="split-grid">
            <section className="section-stack">
              <article className="info-card">
                <div className="surface-header">
                  <div>
                    <strong>{workflowDetail.data.workflow?.title || workflowDetail.data.workflow?.name}</strong>
                    <p className="helper-text">{workflowDetail.data.workflow?.description || "No description available."}</p>
                  </div>
                  <span className={`source-pill ${workflowDetail.data.workflow?.source || "builtin"}`}>
                    {workflowDetail.data.workflow?.source || "builtin"}
                  </span>
                </div>
                <dl className="context-list">
                  <div>
                    <dt>Runtime provider</dt>
                    <dd>{workflowDetail.data.workflow?.runtime_provider || "mock"}</dd>
                  </div>
                  <div>
                    <dt>Question limit</dt>
                    <dd>{workflowDetail.data.workflow?.question_limit || "—"}</dd>
                  </div>
                  <div>
                    <dt>Kind</dt>
                    <dd>{workflowDetail.data.workflow?.workflow_kind || "workflow"}</dd>
                  </div>
                </dl>
              </article>
              <article className="info-card">
                <h4>Explain</h4>
                <p className="helper-text">{workflowExplain.data?.explanation?.summary || "Choose a workflow to load its explanation."}</p>
                {(workflowExplain.data?.explanation?.runtime_requirements || []).length ? (
                  <ul className="guidance-list">
                    {(workflowExplain.data?.explanation?.runtime_requirements || []).map((item: string) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                ) : null}
              </article>
            </section>
            <section className="section-stack">
              <div className="canvas-grid">
                {(workflowDetail.data.canvas?.nodes || []).map((node: JsonObject) => (
                  <article key={node.name} className="canvas-node">
                    <strong>{node.name}</strong>
                    <span>{node.kind}</span>
                    <span>{node.description || node.implementation || "No description"}</span>
                    <StatusPill value={node.status || "ready"} />
                  </article>
                ))}
              </div>
            </section>
          </div>
        ) : null}
      </section>
    </main>
  );
}

function WorkflowDetailPage({
  workflowName,
  navigate,
  onMutate,
}: {
  workflowName: string;
  navigate: (path: string) => void;
  onMutate: () => void;
}): React.ReactElement {
  const detail = useJsonResource(`${bootstrap.api_root}/workflows/${encodeURIComponent(workflowName)}`, [workflowName]);
  const explain = useJsonResource(`${bootstrap.api_root}/workflows/${encodeURIComponent(workflowName)}/explain`, [workflowName]);
  const runs = useJsonResource(`${bootstrap.api_root}/runs`, [workflowName]);
  const [provider, setProvider] = useState("");
  const [limit, setLimit] = useState("");
  const [baselineRunId, setBaselineRunId] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: string; title: string; body: string } | null>(null);

  useEffect(() => {
    if (detail.data?.workflow && !provider) {
      setProvider(detail.data.workflow.runtime_provider || "");
      setLimit(String(detail.data.workflow.question_limit || ""));
    }
  }, [detail.data, provider]);

  async function validateWorkflow() {
    setBusy("Validating workflow");
    setNotice(null);
    try {
      const response = await requestJson(`${bootstrap.api_root}/workflows/${encodeURIComponent(workflowName)}/validate`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      setNotice({ tone: "success", title: "Workflow valid", body: `${response.workflow_name} is ready to run.` });
    } catch (error) {
      setNotice(buildActionErrorNotice("validate", error));
    } finally {
      setBusy(null);
    }
  }

  async function runWorkflow() {
    setBusy("Running workflow");
    setNotice(null);
    try {
      const payload: JsonObject = {
        workflow_name: workflowName,
        write_report: true,
      };
      if (provider) payload.provider = provider;
      if (limit) payload.limit = Number(limit);
      if (baselineRunId) payload.baseline_run_id = baselineRunId;
      const response = await requestJson(`${bootstrap.api_root}/runs`, { method: "POST", body: JSON.stringify(payload) });
      onMutate();
      setNotice({
        tone: "success",
        title: "Workflow launched",
        body: response.compare?.href ? "The candidate run is ready with a comparison link." : "Inspect the run detail to review report and exports.",
      });
      navigate(response.compare?.href || response.href);
    } catch (error) {
      setNotice(buildActionErrorNotice("run", error));
    } finally {
      setBusy(null);
    }
  }

  if (detail.error) {
    return <Message tone="error" title="Workflow unavailable" body={detail.error} />;
  }
  if (detail.loading || !detail.data) {
    return <LoadingCard label="Loading workflow detail" />;
  }

  return (
    <main className="page-grid">
      <section className="panel hero-panel">
        <span className="eyebrow">Workflow</span>
        <h2>{detail.data.workflow?.title || detail.data.workflow?.name}</h2>
        <p>{detail.data.workflow?.description || explain.data?.explanation?.summary || "Inspect, validate, and run this workflow from the WebUI."}</p>
        <div className="button-row">
          <button className="primary-button" onClick={runWorkflow} disabled={Boolean(busy)}>
            {busy === "Running workflow" ? busy : "Run workflow"}
          </button>
          <button className="secondary-button" onClick={validateWorkflow} disabled={Boolean(busy)}>
            {busy === "Validating workflow" ? busy : "Validate"}
          </button>
          <button className="secondary-button" onClick={() => navigate("/start")}>Back to start</button>
        </div>
      </section>
      {notice ? <Message tone={notice.tone} title={notice.title} body={notice.body} /> : null}
      <div className="split-grid">
        <section className="panel section-stack">
          <div className="section-header">
            <div>
              <h3>Execution settings</h3>
              <p>Override the released provider or question limit when you want a bounded comparison run.</p>
            </div>
          </div>
          <div className="two-field-grid">
            <label>
              <span>Provider</span>
              <select value={provider} onChange={(event) => setProvider(event.target.value)}>
                <option value="mock">Provider-free baseline</option>
                <option value="local-llm">Local OpenAI-compatible endpoint</option>
              </select>
            </label>
            <label>
              <span>Question limit</span>
              <input value={limit} onChange={(event) => setLimit(event.target.value)} />
            </label>
          </div>
          <label>
            <span>Baseline run for compare</span>
            <select value={baselineRunId} onChange={(event) => setBaselineRunId(event.target.value)}>
              <option value="">None</option>
              {(runs.data?.items || []).map((run: JsonObject) => (
                <option key={run.run_id} value={run.run_id}>
                  {run.run_id}
                </option>
              ))}
            </select>
          </label>
          <article className="info-card">
            <h4>Explain</h4>
            <p className="helper-text">{explain.data?.explanation?.summary || "Workflow explanation unavailable."}</p>
            <ul className="guidance-list">
              {(explain.data?.explanation?.expected_artifacts || []).map((item: string) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
        </section>
        <section className="panel section-stack">
          <div className="section-header">
            <div>
              <h3>Canvas</h3>
              <p>Graph nodes stay visible so you can inspect the release-safe workflow shape before running it.</p>
            </div>
          </div>
          <div className="canvas-grid">
            {(detail.data.canvas?.nodes || []).map((node: JsonObject) => (
              <article key={node.name} className="canvas-node">
                <strong>{node.name}</strong>
                <span>{node.kind}</span>
                <span>{node.description || node.implementation || "No description"}</span>
                <StatusPill value={node.status || "ready"} />
              </article>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}

function OperationsPage({ navigate, onMutate }: { navigate: (path: string) => void; onMutate: () => void }): React.ReactElement {
  const profiles = useJsonResource(`${bootstrap.api_root}/profiles`, []);
  const monitors = useJsonResource(`${bootstrap.api_root}/monitors`, []);
  const runs = useJsonResource(`${bootstrap.api_root}/runs`, []);
  const [profileName, setProfileName] = useState("local-default");
  const [profileProvider, setProfileProvider] = useState("mock");
  const [profileLimit, setProfileLimit] = useState("5");
  const [selectedProfile, setSelectedProfile] = useState("");
  const [selectedMonitor, setSelectedMonitor] = useState("");
  const [selectedArtifactRun, setSelectedArtifactRun] = useState("");
  const [cleanupKeep, setCleanupKeep] = useState("5");
  const [cleanupPreview, setCleanupPreview] = useState<JsonObject | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: string; title: string; body: string } | null>(null);
  const profileDetail = useJsonResource(
    selectedProfile ? `${bootstrap.api_root}/profiles/${encodeURIComponent(selectedProfile)}` : null,
    [selectedProfile],
  );
  const monitorDetail = useJsonResource(selectedMonitor ? `${bootstrap.api_root}/monitors/${selectedMonitor}` : null, [selectedMonitor]);
  const artifactDetail = useJsonResource(
    selectedArtifactRun ? `${bootstrap.api_root}/artifacts/${selectedArtifactRun}` : null,
    [selectedArtifactRun],
  );
  const profileItems = (profiles.data?.items || []) as JsonObject[];
  const monitorItems = (monitors.data?.items || []) as JsonObject[];
  const runItems = (runs.data?.items || []) as JsonObject[];
  const selectedProfileItem = useMemo(() => {
    if (selectedProfile) return profileItems.find((item) => String(item.name) === selectedProfile) || profileItems[0] || null;
    return profileItems[0] || null;
  }, [selectedProfile, profileItems]);
  const selectedMonitorItem = useMemo(() => {
    if (selectedMonitor) return monitorItems.find((item) => String(item.run_id) === selectedMonitor) || monitorItems[0] || null;
    return monitorItems[0] || null;
  }, [selectedMonitor, monitorItems]);
  const selectedProfileSummary = (profileDetail.data?.profile || selectedProfileItem || null) as JsonObject | null;
  const selectedMonitorSummary = (monitorDetail.data?.monitor || selectedMonitorItem || null) as JsonObject | null;
  const activeMonitorCount = monitorItems.filter((item) => {
    const status = String(item.status || "").toLowerCase();
    return status && !["halted", "completed", "stopped"].includes(status);
  }).length;
  const operationsHeroMetrics = [
    { label: "Profiles", value: profileItems.length, detail: "repeatable presets" },
    { label: "Active monitors", value: activeMonitorCount, detail: "running or resumable" },
    { label: "Run directories", value: runItems.length, detail: "artifact inventory" },
    { label: "Cleanup preview", value: cleanupPreview?.count ?? 0, detail: "pending removals" },
  ];
  const operationsFocusItems = [
    {
      label: "Preset",
      title: "Save one calm local profile first",
      detail: "Profile composition stays up front, while the registry and run actions sit behind bounded disclosure.",
    },
    {
      label: "Monitor",
      title: "Operate lifecycle controls from a contained registry",
      detail: "Run, pause, resume, and halt remain visible without forcing full monitor detail to stay open.",
    },
    {
      label: "Retain",
      title: "Preview cleanup before delete",
      detail: "Artifacts and retention now read as a deliberate maintenance lane rather than always-on operator chrome.",
    },
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

  async function createProfile(template: "starter" | "custom") {
    setBusy("Saving profile");
    setNotice(null);
    try {
      await requestJson(`${bootstrap.api_root}/profiles`, {
        method: "POST",
        body: JSON.stringify({
          name: profileName,
          template: template === "starter" ? "starter" : undefined,
          provider: template === "starter" ? undefined : profileProvider,
          limit: template === "starter" ? undefined : parsedProfileLimit ?? undefined,
          write_report: true,
        }),
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

  async function runProfile(name: string) {
    setBusy(`Running ${name}`);
    setNotice(null);
    try {
      const result = await requestJson(`${bootstrap.api_root}/profiles/${encodeURIComponent(name)}/run`, {
        method: "POST",
        body: JSON.stringify({}),
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
        body: JSON.stringify({ limit: parsedProfileLimit, provider: profileProvider }),
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

  async function mutateMonitor(runId: string, action: string) {
    setBusy(action);
    setNotice(null);
    try {
      await requestJson(`${bootstrap.api_root}/monitors/${runId}/${action}`, {
        method: "POST",
        body: JSON.stringify({}),
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
        body: JSON.stringify({ keep: parsedCleanupKeep }),
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
        body: JSON.stringify({ keep: parsedCleanupKeep, confirm: "delete" }),
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

  return (
    <main className="page-grid operations-shell operations-route">
      {profiles.error ? <Message tone="error" title="Profiles unavailable" body={profiles.error} /> : null}
      {monitors.error ? <Message tone="error" title="Monitors unavailable" body={monitors.error} /> : null}
      {runs.error ? <Message tone="error" title="Runs unavailable" body={runs.error} /> : null}
      {profiles.loading && monitors.loading && runs.loading && !profileItems.length && !monitorItems.length && !runItems.length ? (
        <LoadingCard label="Loading operations" />
      ) : null}
      <section className="panel hero-panel operations-hero">
        <div className="operations-hero-grid">
          <div className="operations-hero-copy">
            <span className="eyebrow">Operations</span>
            <h2>Operate profiles, monitors, and retention without a sprawling admin wall</h2>
            <p>
              Keep repeatable profiles, monitor lifecycles, and artifact cleanup visible in calm local surfaces instead of long stacked operator panels.
            </p>
            <div className="button-row operations-hero-actions">
              <button className="primary-button" onClick={() => navigate("/runs")}>Inspect recent runs</button>
              <button className="secondary-button" onClick={() => navigate("/api")}>Open Control</button>
            </div>
          </div>
          <div className="operations-hero-side">
            <article className="operations-trust-card">
              <span className="eyebrow">Operator loop</span>
              <strong>Profiles, monitor cadence, and retention stay available, but detail only expands when the task needs it.</strong>
              <p>Use the same local product services as the CLI while keeping saved presets, live monitor state, and cleanup consequences readable.</p>
              <div className="operations-pill-row">
                <span className="shell-trust-pill">Profile reuse</span>
                <span className="shell-trust-pill">Lifecycle controls</span>
                <span className="shell-trust-pill">Explicit cleanup</span>
              </div>
            </article>
            <div className="operations-stat-grid">
              {operationsHeroMetrics.map((metric) => (
                <article key={metric.label} className="operations-stat-card">
                  <span>{metric.label}</span>
                  <strong>{metric.value}</strong>
                  <small>{metric.detail}</small>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>
      {notice ? <Message tone={notice.tone} title={notice.title} body={notice.body} /> : null}
      <RouteIdentityPanel
        className="operations-identity-panel"
        eyebrow="Operator rhythm"
        title="Preset, monitor, and retain with calmer defaults"
        summary="Operations now separates everyday preset work from heavier lifecycle and cleanup detail, while preserving the same local control surface."
        items={operationsFocusItems}
      />
      <section className="split-grid operations-lead-grid">
        <article className="panel section-stack operations-form-panel">
          <div className="operations-section-heading">
            <div>
              <span className="eyebrow">Profiles</span>
              <h3>Save repeatable local presets</h3>
              <p className="helper-text">Create a starter or custom profile, then keep the saved list contained in a selectable registry instead of a growing action stack.</p>
            </div>
            <div className="operations-pill-row">
              <span className="shell-trust-pill">Starter-safe</span>
              <span className="shell-trust-pill">Runnable locally</span>
            </div>
          </div>
          <div className="operations-field-grid">
            <label>
              <span>Name</span>
              <input value={profileName} onChange={(event) => setProfileName(event.target.value)} />
            </label>
            <label>
              <span>Provider</span>
              <select value={profileProvider} onChange={(event) => setProfileProvider(event.target.value)}>
                <option value="mock">Provider-free baseline</option>
                <option value="local-llm">Local OpenAI-compatible endpoint</option>
              </select>
            </label>
            <label className="operations-field-span">
              <span>Question limit</span>
              <input type="number" min={1} step={1} inputMode="numeric" value={profileLimit} onChange={(event) => setProfileLimit(event.target.value)} />
            </label>
          </div>
          <div className="operations-footer">
            <div className="operations-inline-note">
              <strong>Profiles stay reusable across local operator flows.</strong>
              <p className="helper-text">Save first, then run from here or keep the preset available for later monitor and Control work.</p>
            </div>
            <div className="button-row">
              <button className="primary-button" onClick={() => void createProfile("custom")} disabled={Boolean(busy) || parsedProfileLimit == null}>
                {busy === "Saving profile" ? busy : "Save profile"}
              </button>
              <button className="secondary-button" onClick={() => void createProfile("starter")} disabled={Boolean(busy)}>
                Save starter profile
              </button>
            </div>
          </div>
          <DensityDisclosure
            className="operations-subpanel section-stack"
            title={`Saved profiles · ${profileItems.length}`}
            detail="Select a saved preset when you need detail or a run, while the route keeps a bounded table instead of an uncontained stack."
          >
            {profileItems.length ? (
              <div className="table-wrap operations-table-wrap">
                <table className="data-table">
                  <thead><tr><th>Profile</th><th>Provider</th><th>Limit</th><th>Runs dir</th><th>Actions</th></tr></thead>
                  <tbody>
                    {profileItems.map((profile) => (
                      <tr key={profile.name} className={String(profile.name) === String(selectedProfileSummary?.name || "") ? "is-active" : undefined}>
                        <td>
                          <button
                            className="table-link-button operations-row-button"
                            type="button"
                            aria-pressed={String(profile.name) === String(selectedProfileSummary?.name || "")}
                            onClick={() => setSelectedProfile(String(profile.name))}
                          >
                            <span className="table-primary">{profile.name}</span>
                            <span className="table-secondary">{profile.provider || "provider-free"}</span>
                          </button>
                        </td>
                        <td>{profile.provider || "mock"}</td>
                        <td>{formatValue(profile.limit)}</td>
                        <td>{profile.runs_dir || "runs"}</td>
                        <td>
                          <div className="button-row operations-table-actions">
                            <button className="secondary-button" onClick={(event) => runWithoutRowSelection(event, () => setSelectedProfile(String(profile.name)))}>Show</button>
                            <button className="secondary-button" onClick={(event) => runWithoutRowSelection(event, () => void runProfile(String(profile.name)))} disabled={Boolean(busy)}>Run</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState title="No profiles yet" body="Save a starter or custom profile to keep a repeatable local preset on hand." />
            )}
          </DensityDisclosure>
        </article>
        <article className="panel section-stack operations-summary-panel">
          <div className="operations-section-heading">
            <div>
              <span className="eyebrow">Posture</span>
              <h3>Selected operator context</h3>
              <p className="helper-text">Keep the current profile, monitor, and cleanup consequences close without making them permanent full-height panels.</p>
            </div>
            {selectedMonitorSummary ? <StatusPill value={String(selectedMonitorSummary.status || "ready")} /> : <span className="shell-trust-pill">No monitor selected</span>}
          </div>
          <div className="operations-stat-grid">
            <article className="operations-stat-card">
              <span>Profiles</span>
              <strong>{profileItems.length}</strong>
              <small>saved presets</small>
            </article>
            <article className="operations-stat-card">
              <span>Monitors</span>
              <strong>{monitorItems.length}</strong>
              <small>tracked lifecycles</small>
            </article>
            <article className="operations-stat-card">
              <span>Selected run</span>
              <strong>{selectedArtifactRun || "—"}</strong>
              <small>artifact inventory target</small>
            </article>
          </div>
          <article className="operations-subpanel">
            <div className="surface-header">
              <div>
                <strong>{selectedProfileSummary?.name || "No profile selected"}</strong>
                <p className="helper-text">{selectedProfileSummary ? "Keep the active preset readable while the full list stays tucked into the bounded registry." : "Select a saved preset to inspect its run posture."}</p>
              </div>
              {selectedProfileSummary ? <StatusPill value="ready" /> : null}
            </div>
            <div className="operations-keyline-list">
              <div><span>Provider</span><strong>{selectedProfileSummary?.provider || "—"}</strong></div>
              <div><span>Limit</span><strong>{selectedProfileSummary?.limit != null ? formatValue(selectedProfileSummary.limit) : "—"}</strong></div>
              <div><span>Runs dir</span><strong>{selectedProfileSummary?.runs_dir || "—"}</strong></div>
            </div>
          </article>
          <DensityDisclosure
            className="operations-subpanel section-stack"
            title={selectedMonitorSummary?.run_id ? `Monitor detail · ${selectedMonitorSummary.run_id}` : "Monitor detail"}
            detail="Lifecycle controls stay available below, while selected state opens only when you need the run cadence and watch count."
          >
            {selectedMonitorSummary ? (
              <div className="operations-keyline-list">
                <div><span>Status</span><strong>{selectedMonitorSummary.status || "—"}</strong></div>
                <div><span>Cycles</span><strong>{formatValue(selectedMonitorSummary.cycles)}</strong></div>
                <div><span>Watches</span><strong>{(selectedMonitorSummary.watches || []).length}</strong></div>
              </div>
            ) : (
              <EmptyState title="No monitor selected" body="Start or select a monitor to review its lifecycle detail." />
            )}
          </DensityDisclosure>
          <DensityDisclosure
            className="operations-subpanel section-stack"
            title="Cleanup posture"
            detail="Preview the deletion boundary before acting so retention stays explicit instead of hidden inside a dense footer."
          >
            <div className="operations-keyline-list">
              <div><span>Keep newest</span><strong>{cleanupKeep}</strong></div>
              <div><span>Preview count</span><strong>{cleanupPreview?.count ?? 0}</strong></div>
              <div><span>Available runs</span><strong>{runItems.length}</strong></div>
            </div>
          </DensityDisclosure>
        </article>
      </section>
      <section className="split-grid operations-control-grid">
        <article className="panel section-stack operations-table-card">
          <div className="operations-table-header">
            <div>
              <span className="eyebrow">Monitors</span>
              <h3>Lifecycle controls</h3>
              <p className="helper-text">Start a monitor, then keep cycle and pause controls in a contained registry instead of an endlessly growing operator list.</p>
            </div>
            <div className="operations-pill-row">
              <span className="shell-trust-pill">{monitorItems.length} monitors</span>
              <button className="primary-button" onClick={() => void createMonitor()} disabled={Boolean(busy) || parsedProfileLimit == null}>
                {busy === "Starting monitor" ? busy : "Start monitor"}
              </button>
            </div>
          </div>
          {monitorItems.length ? (
            <div className="table-wrap operations-table-wrap">
              <table className="data-table">
                  <thead><tr><th>Monitor</th><th>Status</th><th>Provider</th><th>Cycles</th><th>Watches</th><th>Actions</th></tr></thead>
                  <tbody>
                    {monitorItems.map((monitor) => (
                      <tr key={monitor.run_id} className={String(monitor.run_id) === String(selectedMonitorSummary?.run_id || "") ? "is-active" : undefined}>
                        <td>
                          <button
                            className="table-link-button operations-row-button"
                            type="button"
                            aria-pressed={String(monitor.run_id) === String(selectedMonitorSummary?.run_id || "")}
                            onClick={() => setSelectedMonitor(String(monitor.run_id))}
                          >
                            <span className="table-primary">{monitor.run_id}</span>
                            <span className="table-secondary">{monitor.provider || "provider-free"}</span>
                          </button>
                        </td>
                        <td><StatusPill value={String(monitor.status || "ready")} /></td>
                      <td>{monitor.provider || "mock"}</td>
                      <td>{formatValue(monitor.cycles)}</td>
                      <td>{(monitor.watches || []).length}</td>
                      <td>
                        <div className="button-row operations-table-actions">
                          <button className="secondary-button" onClick={(event) => runWithoutRowSelection(event, () => setSelectedMonitor(String(monitor.run_id)))}>Show</button>
                          <button className="secondary-button" onClick={(event) => runWithoutRowSelection(event, () => void mutateMonitor(String(monitor.run_id), "run-once"))} disabled={Boolean(busy)}>Run once</button>
                          <button className="secondary-button" onClick={(event) => runWithoutRowSelection(event, () => void mutateMonitor(String(monitor.run_id), "pause"))} disabled={Boolean(busy)}>Pause</button>
                          <button className="secondary-button" onClick={(event) => runWithoutRowSelection(event, () => void mutateMonitor(String(monitor.run_id), "resume"))} disabled={Boolean(busy)}>Resume</button>
                          <button className="secondary-button" onClick={(event) => runWithoutRowSelection(event, () => void mutateMonitor(String(monitor.run_id), "halt"))} disabled={Boolean(busy)}>Halt</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title="No monitors yet" body="Start a monitor to keep a resumable local lifecycle on hand." />
          )}
        </article>
        <DensityDisclosure
          className="panel section-stack operations-detail-card operations-retention-panel"
          title={`Artifacts + retention · ${cleanupPreview?.count ?? 0} previewed`}
          detail="Inspect artifact inventory and explicit cleanup controls only when you are intentionally doing maintenance work."
        >
          <div className="operations-table-header">
            <div>
              <span className="eyebrow">Artifacts + retention</span>
              <h3>Contained cleanup workflow</h3>
              <p className="helper-text">Inspect one run, preview retention, then confirm deletion from clearly separated subpanels.</p>
            </div>
            <div className="operations-pill-row">
              <span className="shell-trust-pill">{runItems.length} runs</span>
              <span className="shell-trust-pill">Explicit delete</span>
            </div>
          </div>
          <div className="three-column-grid operations-retention-grid">
            <section className="operations-subpanel section-stack operations-retention-column">
              <div className="surface-header">
                <div>
                  <strong>Artifact inventory</strong>
                  <p className="helper-text">Choose one run to inspect packaged artifacts without letting the inventory take over the whole route.</p>
                </div>
              </div>
              {runItems.length ? (
                <label>
                  <span>Run</span>
                  <select value={selectedArtifactRun} onChange={(event) => setSelectedArtifactRun(event.target.value)}>
                    {runItems.map((run) => (
                      <option key={run.run_id} value={run.run_id}>
                        {run.run_id}
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <EmptyState title="No runs available yet" body="Run a profile or saved version first to populate the local artifact inventory." />
              )}
              {runItems.length && artifactDetail.data ? (
                <div className="operations-retention-scroll">
                  <ul className="artifact-list">
                    {(artifactDetail.data.artifacts || []).map((item: JsonObject) => (
                      <li key={item.name}>
                        <div>
                          <strong>{item.name}</strong>
                          <span>{item.path}</span>
                        </div>
                        <span className={`availability-pill ${item.exists ? "available" : "missing"}`}>{item.exists ? "Present" : "Missing"}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : runItems.length ? (
                <EmptyState title="No artifact detail yet" body="Select a run with local artifacts to review its inventory." />
              ) : null}
            </section>
            <section className="operations-subpanel section-stack operations-retention-column">
              <div className="surface-header">
                <div>
                  <strong>Retention boundary</strong>
                  <p className="helper-text">Preview the deletion set before you confirm cleanup so removal never feels bundled into another control surface.</p>
                </div>
              </div>
              <label>
                <span>Keep newest run directories</span>
                <input type="number" min={1} step={1} inputMode="numeric" value={cleanupKeep} onChange={(event) => setCleanupKeep(event.target.value)} />
              </label>
              <div className="operations-keyline-list">
                <div><span>Current target</span><strong>{selectedArtifactRun || "—"}</strong></div>
                <div><span>Preview removals</span><strong>{cleanupPreview?.count ?? 0}</strong></div>
              </div>
              <div className="button-row">
                <button className="secondary-button" onClick={() => void previewCleanup()} disabled={Boolean(busy) || parsedCleanupKeep == null}>
                  {busy === "Previewing cleanup" ? busy : "Preview cleanup"}
                </button>
                <button className="primary-button" onClick={() => void runCleanup()} disabled={Boolean(busy) || parsedCleanupKeep == null || !cleanupPreview?.count}>
                  {busy === "Cleaning artifacts" ? busy : "Delete previewed runs"}
                </button>
              </div>
            </section>
            <section className="operations-subpanel section-stack operations-retention-column">
              {cleanupPreview ? (
                <article className="operations-retention-preview">
                  <div className="surface-header">
                    <div>
                      <strong>Cleanup preview</strong>
                      <p className="helper-text">{cleanupPreview.count || 0} run directories would be removed while keeping the newest {cleanupPreview.keep}.</p>
                    </div>
                  </div>
                  <div className="operations-retention-scroll">
                    <ul className="guidance-list compact-list">
                      {(cleanupPreview.items || []).map((item: JsonObject) => (
                        <li key={item.run_id}>{item.run_id}</li>
                      ))}
                    </ul>
                  </div>
                </article>
              ) : (
                <EmptyState title="No cleanup preview yet" body="Preview retention first so deletion stays explicit." />
              )}
            </section>
          </div>
        </DensityDisclosure>
      </section>
    </main>
  );
}

function AdvancedPage(): React.ReactElement {
  const cards = [
    {
      title: "Validation and corpora",
      status: "advanced",
      body: "Validation suites, corpora preparation, and release-gate validation remain advanced lanes with explicit safety and runtime rules.",
      emphasis: "Explicit validation before execution",
      detail: "Keep these lanes visible for advanced operators, but collapse the operational burden until a user intentionally enters the workflow.",
    },
    {
      title: "Benchmark and stress",
      status: "advanced",
      body: "Benchmark compare, cache, and stress flows need heavier validation and should not be mistaken for first-success paths.",
      emphasis: "Heavier runtime and review cost",
      detail: "This lane belongs behind clear readiness language so performance and stress work do not read like default day-one controls.",
    },
    {
      title: "Performance and competition",
      status: "experimental",
      body: "Performance budgets and competition dry-runs are visible here so advanced users can see the lane without overselling it to newcomers.",
      emphasis: "Visible, but not newcomer default",
      detail: "Expose the capability honestly with status labels, then use calm disclosure for the surrounding context instead of keeping the whole lane expanded.",
    },
  ];
  const advancedStats = [
    { label: "Visible lanes", value: cards.length, detail: "kept in view" },
    { label: "Default posture", value: "guided", detail: "not first-success" },
    { label: "Safety labels", value: "explicit", detail: "readiness stays honest" },
    { label: "Release frame", value: "0.8.4", detail: "bug-fix + polish" },
  ];
  const advancedFocusItems = [
    {
      label: "Visible",
      title: "Keep advanced lanes in plain sight",
      detail: "Capabilities remain discoverable so experienced operators do not need to hunt through secondary chrome.",
    },
    {
      label: "Honest",
      title: "Lead with readiness and safety labels",
      detail: "Advanced and experimental posture stays explicit before any deeper lane detail opens up.",
    },
    {
      label: "Calm",
      title: "Use disclosure instead of permanent warning walls",
      detail: "Context waits behind deliberate expansion, keeping the route distinct without overstating danger.",
    },
  ];

  return (
    <main className="page-grid advanced-shell operations-route">
      <section className="panel hero-panel operations-hero">
        <div className="operations-hero-grid">
          <div className="operations-hero-copy">
            <span className="eyebrow">Advanced</span>
            <h2>Visible advanced lanes with calm disclosure and honest status labels</h2>
            <p className="section-copy">The product should not hide advanced capabilities, but it also should not present them as newcomer defaults.</p>
          </div>
          <div className="operations-hero-side">
            <article className="operations-trust-card">
              <span className="eyebrow">Default stance</span>
              <strong>Advanced capability remains visible, while surrounding detail waits behind deliberate disclosure.</strong>
              <p>Keep readiness, safety, and release framing close so users can see what exists without mistaking these lanes for the main entry path.</p>
              <div className="operations-pill-row">
                <span className="shell-trust-pill">Explicit readiness</span>
                <span className="shell-trust-pill">Visible, not default</span>
                <span className="shell-trust-pill">Calm disclosure</span>
              </div>
            </article>
            <div className="operations-stat-grid">
              {advancedStats.map((metric) => (
                <article key={metric.label} className="operations-stat-card">
                  <span>{metric.label}</span>
                  <strong>{metric.value}</strong>
                  <small>{metric.detail}</small>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>
      <RouteIdentityPanel
        className="advanced-identity-panel"
        eyebrow="Advanced posture"
        title="Visible lanes, honest labels, calmer defaults"
        summary="Advanced remains explicit and reachable, but the route now leans on posture and disclosure instead of always-expanded context."
        items={advancedFocusItems}
      />
      <section className="split-grid operations-lead-grid">
        <article className="panel section-stack operations-form-panel">
          <div className="operations-section-heading">
            <div>
              <span className="eyebrow">Lane catalog</span>
              <h3>Advanced capabilities stay visible</h3>
              <p className="helper-text">Each lane remains discoverable, but the heavier context opens only when an operator intentionally drills in.</p>
            </div>
            <div className="operations-pill-row">
              <span className="shell-trust-pill">No hidden lanes</span>
              <span className="shell-trust-pill">Scoped disclosure</span>
            </div>
          </div>
          <div className="operations-lane-list">
            {cards.map((card) => (
              <DensityDisclosure
                key={card.title}
                className="operations-subpanel section-stack"
                title={`${card.title} · ${card.status === "experimental" ? "Experimental" : "Advanced"}`}
                detail={card.body}
              >
                <div className="operations-keyline-list">
                  <div><span>Status</span><strong>{card.status}</strong></div>
                  <div><span>Why disclosed</span><strong>{card.emphasis}</strong></div>
                </div>
                <p className="helper-text">{card.detail}</p>
              </DensityDisclosure>
            ))}
          </div>
        </article>
        <article className="panel section-stack operations-summary-panel">
          <div className="operations-section-heading">
            <div>
              <span className="eyebrow">Route posture</span>
              <h3>Advanced without permanent clutter</h3>
              <p className="helper-text">Keep the page structurally separate from day-one routes by foregrounding posture, labels, and release framing before control density.</p>
            </div>
            <span className="shell-trust-pill">Not newcomer default</span>
          </div>
          <div className="operations-keyline-list">
            <div><span>Primary audience</span><strong>operators who already know the lane</strong></div>
            <div><span>Interaction model</span><strong>inspect first, expand deliberately</strong></div>
            <div><span>Product promise</span><strong>polish and clarification, not new feature families</strong></div>
          </div>
          <div className="operations-card-grid advanced-card-grid">
            <article className="advanced-note-card">
              <span className="eyebrow">Visibility</span>
              <strong>Capabilities remain findable</strong>
              <p className="helper-text">The route shows advanced work plainly instead of hiding it behind secondary navigation.</p>
            </article>
            <article className="advanced-note-card">
              <span className="eyebrow">Separation</span>
              <strong>Status labels do the sorting</strong>
              <p className="helper-text">Advanced and experimental posture stays legible through cards, spacing, and labels rather than dense warning chrome.</p>
            </article>
            <article className="advanced-note-card">
              <span className="eyebrow">Release trust</span>
              <strong>0.8.4 remains polish work</strong>
              <p className="helper-text">This route clarifies existing lanes while keeping the broader product framing calm and truthful.</p>
            </article>
          </div>
        </article>
      </section>
    </main>
  );
}

function RunsPage({ route, navigate }: { route: Route; navigate: (path: string) => void }): React.ReactElement {
  const params = useMemo(() => new URLSearchParams(route.search), [route.search]);
  const resource = useJsonResource(`${bootstrap.api_root}/runs${route.search ? `?${route.search}` : ""}`, [route.search]);
  const [query, setQuery] = useState(params.get("q") || "");
  const [status, setStatus] = useState(params.get("status") || "");
  const [provider, setProvider] = useState(params.get("provider") || "");
  const analytics = (resource.data?.analytics || {}) as JsonObject;
  const summaryCards = (resource.data?.summary_cards || []) as JsonObject[];
  const calibrationBins = (analytics.calibration_curve || []) as JsonObject[];
  const uncertaintyBins = (analytics.uncertainty_distribution || []) as JsonObject[];
  const workflowScoreRows = (analytics.workflow_scores || []) as JsonObject[];
  const versionScoreRows = (analytics.version_scores || []) as JsonObject[];
  const scoreHistoryRows = (analytics.score_history || []) as JsonObject[];
  const runItems = (resource.data?.items || []) as JsonObject[];
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
    leadRun?.observatory?.inspect_href || (leadRun?.run_id ? `/runs/${leadRun.run_id}` : ""),
  );
  const leadRunReportHref = leadRun?.run_id ? `/runs/${leadRun.run_id}/report` : "";
  const hasActiveFilters = Boolean(query || status || provider);
  const leadRunFacts = [
    leadRun?.updated_at ? `Updated ${leadRun.updated_at}` : null,
    leadRun?.observatory?.version_label ? `Version ${leadRun.observatory.version_label}` : null,
    leadRun?.observatory?.score_label != null ? `Lead score ${formatValue(leadRun.observatory.score_label)}` : null,
  ].filter(Boolean) as string[];
  const controlStats = [
    { label: "Runs", value: formatValue(analytics.summary?.run_count ?? runItems.length) },
    { label: "Resolved", value: formatValue(analytics.summary?.resolved_score_rows ?? analytics.resolved_rows ?? 0) },
    { label: "Reports", value: formatValue(reportReadyCount) },
  ];
  const trustFacts = [
    { label: "Resolved", value: formatValue(analytics.summary?.resolved_score_rows ?? analytics.resolved_rows ?? 0) },
    { label: "Forecasts", value: formatValue(analytics.forecast_rows || 0) },
    { label: "ECE", value: analytics.summary?.ece != null ? formatValue(analytics.summary.ece) : "—" },
    { label: "Log score", value: analytics.summary?.log_score != null ? formatValue(analytics.summary.log_score) : "—" },
  ];
  const leadTrustFacts = trustFacts.slice(0, 2);
  const scoreTrustFacts = trustFacts.slice(2);
  const filterSummary = hasActiveFilters
    ? [
      query ? `Search: ${query}` : null,
      status ? `Status: ${status}` : null,
      provider ? `Provider: ${provider}` : null,
    ].filter(Boolean).join(" • ")
    : "Search, status, and provider stay available when you need a narrower slice.";

  useEffect(() => {
    setQuery(params.get("q") || "");
    setStatus(params.get("status") || "");
    setProvider(params.get("provider") || "");
  }, [params]);

  return (
    <main className="page-grid observatory-page">
      <section className="observatory-lead-grid">
        <section className="panel observatory-control-panel">
          <div className="section-header observatory-control-header">
            <div>
              <span className="eyebrow">Observatory</span>
              <h2>{resource.data?.surface?.title || "Observatory run inspector"}</h2>
              <p>Filter recent runs, check calibration, and jump into trusted analysis without leaving the overview.</p>
            </div>
            <dl className="observatory-control-stats">
              {controlStats.map((stat) => (
                <div key={stat.label}>
                  <dt>{stat.label}</dt>
                  <dd>{stat.value}</dd>
                </div>
              ))}
            </dl>
          </div>
          <DensityDisclosure
            className="observatory-filter-disclosure"
            title={hasActiveFilters ? "Filters applied" : "Filter runs"}
            detail={filterSummary}
            defaultOpen={hasActiveFilters}
          >
            <form
              className="observatory-filter-row"
              onSubmit={(event) => {
                event.preventDefault();
                const next = new URLSearchParams();
                if (query) next.set("q", query);
                if (status) next.set("status", status);
                if (provider) next.set("provider", provider);
                navigate(next.toString() ? observatoryUiHref(route.path, `/runs?${next.toString()}`) : observatoryBasePath);
              }}
            >
              <label className="observatory-filter-field">
                <span>Search</span>
                <input placeholder="Run or workflow" value={query} onChange={(event) => setQuery(event.target.value)} />
              </label>
              <label className="observatory-filter-field">
                <span>Status</span>
                <select value={status} onChange={(event) => setStatus(event.target.value)}>
                  <option value="">Any status</option>
                  {statusOptions.map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
              </label>
              <label className="observatory-filter-field">
                <span>Provider</span>
                <select value={provider} onChange={(event) => setProvider(event.target.value)}>
                  <option value="">Any provider</option>
                  {providerOptions.map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
              </label>
              <button className="secondary-button" type="submit">Apply</button>
            </form>
          </DensityDisclosure>
          <section className="observatory-run-focus">
            <div className="surface-header">
              <div>
                <span className="eyebrow">Run analysis</span>
                <h3>{leadRun?.observatory?.label || "Open the latest run"}</h3>
                <p>{leadRun?.observatory?.summary || "Recent run shortcuts appear here once Observatory has indexed local history."}</p>
              </div>
              {leadRun?.status ? <StatusPill value={String(leadRun.status)} /> : null}
            </div>
            {leadRunFacts.length ? (
              <div className="meta-row observatory-run-focus-meta">
                {leadRunFacts.map((fact) => <span key={fact}>{fact}</span>)}
              </div>
            ) : null}
            <div className="button-row observatory-run-focus-actions">
              <button
                className="primary-button"
                type="button"
                disabled={!leadRunInspectHref}
                onClick={() => leadRunInspectHref && navigate(leadRunInspectHref)}
              >
                Inspect latest run
              </button>
              {leadRun?.observatory?.report_available ? (
                <a className="secondary-link" href={leadRunReportHref} target="_blank" rel="noreferrer">Open report</a>
              ) : null}
            </div>
            {recentRuns.length ? (
              <DensityDisclosure
                className="observatory-quick-runs-disclosure"
                title={`Recent shortcuts · ${recentRuns.length}`}
                detail="Adjacent runs stay nearby, but collapsed until you want to branch from the lead run."
              >
                <div className="observatory-quick-runs">
                  <div className="observatory-quick-run-list">
                    {recentRuns.map((run: JsonObject) => (
                      <button
                        key={String(run.run_id)}
                        className="observatory-quick-run"
                        type="button"
                        onClick={() => navigate(observatoryUiHref(route.path, run.observatory?.inspect_href || `/runs/${run.run_id}`))}
                      >
                        <span className="observatory-quick-run-label">Run shortcut</span>
                        <span className="table-primary clamp-2" title={String(run.observatory?.label || run.run_id)}>{run.observatory?.label || run.run_id}</span>
                        <span className="table-secondary" title={String(run.run_id)}>Run ID · {run.run_id}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </DensityDisclosure>
            ) : null}
          </section>
        </section>
        <article className="panel chart-panel observatory-primary-panel">
          <div className="section-header">
            <div>
              <span className="eyebrow">Calibration Curve</span>
              <h3>Calibration at a glance</h3>
              <p>See whether forecast confidence tracks observed outcomes before opening a run.</p>
            </div>
            <div className="observatory-primary-meta">
              <span>{formatValue(analytics.forecast_rows || 0)} forecasts</span>
              <span>{analytics.resolved_rows ? `${formatValue(analytics.resolved_rows)} resolved` : "Awaiting outcomes"}</span>
            </div>
          </div>
          <div className="observatory-primary-shell">
            <CalibrationCurveChart bins={calibrationBins} />
            <aside className="observatory-primary-summary">
              <div className="brier-summary-card observatory-brier-card">
                <span>Brier</span>
                <strong>{analytics.summary?.brier != null ? formatValue(analytics.summary.brier) : "No score yet"}</strong>
                <em>{analytics.resolved_rows ? "Resolved evidence available" : "Needs resolved rows"}</em>
              </div>
              <dl className="observatory-trust-facts observatory-trust-facts-primary">
                {leadTrustFacts.map((fact) => (
                  <div key={fact.label}>
                    <dt>{fact.label}</dt>
                    <dd>{fact.value}</dd>
                  </div>
                ))}
              </dl>
              {scoreTrustFacts.length ? (
                <DensityDisclosure
                  className="observatory-score-detail-disclosure"
                  title="Scoring detail"
                  detail="ECE and log score stay nearby without expanding the lead trust stack."
                >
                  <dl className="observatory-trust-facts observatory-trust-facts-secondary">
                    {scoreTrustFacts.map((fact) => (
                      <div key={fact.label}>
                        <dt>{fact.label}</dt>
                        <dd>{fact.value}</dd>
                      </div>
                    ))}
                  </dl>
                </DensityDisclosure>
              ) : null}
              <p className="helper-text">Keep trust metrics compact here, then open a run for row-level evidence, reports, and comparisons.</p>
            </aside>
          </div>
        </article>
      </section>
      {resource.error ? <Message tone="error" title="Runs unavailable" body={resource.error} /> : null}
      {resource.loading ? <LoadingCard label="Loading runs" /> : null}
      <section className="panel section-stack observatory-run-table">
        <div className="section-header">
          <div>
            <span className="eyebrow">Runs</span>
            <h3>Recent runs</h3>
            <p>Open a run to inspect artifacts, compare reports, or continue analysis immediately.</p>
          </div>
          <span className="section-count">{formatValue(runItems.length)} shown</span>
        </div>
        {runItems.length ? (
          <div className="table-wrap observatory-run-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Workflow</th>
                  <th>Version</th>
                  <th>Status</th>
                  <th>Provider</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {runItems.map((run: JsonObject) => (
                  <tr key={run.run_id}>
                    <td><a href={observatoryUiHref(route.path, `/runs/${run.run_id}`)} onClick={(event) => { event.preventDefault(); navigate(observatoryUiHref(route.path, `/runs/${run.run_id}`)); }}>{run.run_id}</a></td>
                    <td>
                      <div className="table-primary">{run.observatory?.label || run.workflow?.title || run.workflow?.name || "Unknown workflow"}</div>
                      <div className="table-secondary">{run.observatory?.summary || run.workflow?.name || "—"}</div>
                    </td>
                    <td>{run.observatory?.version_label || "—"}</td>
                    <td><StatusPill value={run.status} /></td>
                    <td>{run.provider}</td>
                    <td>{run.updated_at || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        {!resource.loading && !runItems.length ? (
          <EmptyState
            title={resource.data?.empty_state?.title || "No runs match the current filter"}
            body={resource.data?.empty_state?.body || "Clear filters or start a provider-free workflow to create a run for inspection."}
          />
        ) : null}
      </section>
      <DensityDisclosure
        className="panel section-stack observatory-disclosure"
        title="Secondary analytics"
        detail="Open the broader run mix, probability spread, and score rollups after the main trust and run-access view."
      >
        {summaryCards.length ? (
          <section className="section-stack observatory-summary-section">
            <div className="stats-grid observatory-summary-grid">
              {summaryCards.map((card: JsonObject) => <MetricCard key={card.label} label={card.label} value={card.value} />)}
            </div>
          </section>
        ) : null}
        <section className="observatory-dashboard">
          <article className="panel chart-panel uncertainty-panel observatory-secondary-panel">
            <div className="section-header">
              <div>
                <span className="eyebrow">Probability spread</span>
                <h3>Where historic forecasts cluster</h3>
                <p>Use the band view after calibration to spot where certainty stacks up.</p>
              </div>
              <span className="section-count">{formatValue(analytics.forecast_rows || 0)} rows</span>
            </div>
            <UncertaintyHistogram bins={uncertaintyBins} />
          </article>
          <article className="panel chart-panel observatory-secondary-panel observatory-history-panel">
            <div className="section-header">
              <div>
                <span className="eyebrow">Trend</span>
                <h3>Brier score over recent runs</h3>
                <p>Keep the score trend nearby without crowding the main trust surface.</p>
              </div>
              <span className="section-count">{scoreHistoryRows.length} scored runs</span>
            </div>
            <ScoreHistoryChart rows={scoreHistoryRows} />
          </article>
        </section>
        <section className="split-grid observatory-score-grid">
          <article className="panel section-stack">
            <div className="section-header">
              <div>
                <span className="eyebrow">Workflow scores</span>
                <h3>Workflow rollup</h3>
                <p>Compare scored runs by workflow after scanning the lead trust view.</p>
              </div>
            </div>
            <WorkflowScoreTable rows={workflowScoreRows} navigate={navigate} />
          </article>
          <article className="panel section-stack">
            <div className="section-header">
              <div>
                <span className="eyebrow">Version scores</span>
                <h3>Saved snapshot rollup</h3>
                <p>Inspect version performance without pulling more tables into the lead area.</p>
              </div>
            </div>
              <VersionScoreTable rows={versionScoreRows} navigate={navigate} routePath={route.path} />
          </article>
        </section>
      </DensityDisclosure>
    </main>
  );
}

function CalibrationCurveChart({ bins }: { bins: JsonObject[] }): React.ReactElement {
  const plotted = bins.filter((bin) => typeof bin.mean_probability === "number" && typeof bin.observed_frequency === "number");
  const points = plotted.map((bin) => `${Math.max(0, Math.min(1, Number(bin.mean_probability))) * 100},${100 - Math.max(0, Math.min(1, Number(bin.observed_frequency))) * 100}`).join(" ");
  const summary = plotted.length
    ? `${plotted.length} calibration bins. ${plotted.map((bin) => `${bin.label || "bin"} mean ${formatProbability(bin.mean_probability)}, observed ${formatProbability(bin.observed_frequency)}`).join(". ")}.`
    : "Resolved forecast rows are required before the calibration curve can be drawn.";
  return (
    <div className="calibration-chart" role="img" aria-label="Calibration curve" aria-describedby="calibration-chart-summary">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        <line className="chart-grid-line" x1="0" y1="100" x2="100" y2="0" />
        {points ? <polyline className="calibration-line primary" points={points} /> : null}
        {plotted.map((bin) => (
          <circle
            key={String(bin.label)}
            className="calibration-dot"
            cx={Math.max(0, Math.min(1, Number(bin.mean_probability))) * 100}
            cy={100 - Math.max(0, Math.min(1, Number(bin.observed_frequency))) * 100}
            r="1.8"
          />
        ))}
      </svg>
      <div className="chart-axis x-axis" aria-hidden="true">Forecasted Probability</div>
      <div className="chart-axis y-axis" aria-hidden="true">Observed Frequency</div>
      <p id="calibration-chart-summary" className="sr-only">{summary}</p>
      {!plotted.length ? <EmptyState title="Calibration pending" body="Resolved forecast rows are required before the curve can be drawn." /> : null}
    </div>
  );
}

function UncertaintyHistogram({ bins }: { bins: JsonObject[] }): React.ReactElement {
  const maxCount = Math.max(1, ...bins.map((bin) => Number(bin.count || 0)));
  const summary = bins.length
    ? `${bins.length} uncertainty bands. ${bins.map((bin) => `${bin.label || "band"} forecast count ${formatValue(bin.count || 0)}, observed true ${formatValue(bin.observed_true || 0)}`).join(". ")}.`
    : "No forecast rows are available for the uncertainty histogram yet.";
  return (
    <div className="histogram-chart" role="img" aria-label="Uncertainty distribution" aria-describedby="uncertainty-chart-summary">
      {bins.map((bin) => {
        const height = Math.max(4, (Number(bin.count || 0) / maxCount) * 100);
        return (
          <div key={String(bin.label)} className="histogram-bin">
            <span className="histogram-bar forecast" style={{ height: `${height}%` }} />
            <span className="histogram-bar observed" style={{ height: `${Math.max(3, (Number(bin.observed_true || 0) / maxCount) * 100)}%` }} />
            <small>{String(bin.label || "").replace("-100%", "%")}</small>
          </div>
        );
      })}
      <p id="uncertainty-chart-summary" className="sr-only">{summary}</p>
    </div>
  );
}

function WorkflowScoreTable({ rows, navigate }: { rows: JsonObject[]; navigate: (path: string) => void }): React.ReactElement {
  if (!rows.length) {
    return <EmptyState title="No workflow scores yet" body="Run workflows with scoring artifacts to populate score history." />;
  }
  return (
    <div className="table-wrap score-table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Workflow</th>
            <th>Runs</th>
            <th>Brier</th>
            <th>ECE</th>
            <th>Scoring rule</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={String(row.workflow)}>
              <td>
                <button className="table-link-button" onClick={() => navigate(`/studio?workflow=${encodeURIComponent(String(row.workflow))}`)}>
                  {row.label || row.workflow}
                </button>
              </td>
              <td>{formatValue(row.runs)}</td>
              <td>{formatValue(row.brier)}</td>
              <td>{formatValue(row.ece)}</td>
              <td>{row.status || "insufficient evidence"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function VersionScoreTable({
  rows,
  navigate,
  routePath,
}: {
  rows: JsonObject[];
  navigate: (path: string) => void;
  routePath: string;
}): React.ReactElement {
  if (!rows.length) {
    return <EmptyState title="No version scores yet" body="Run saved version snapshots or version-backed batches to populate version history." />;
  }
  return (
    <div className="table-wrap score-table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Version</th>
            <th>Workflow</th>
            <th>Runs</th>
            <th>Brier</th>
            <th>ECE</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={String(row.version_id)}>
              <td>
                <button className="table-link-button" onClick={() => navigate(observatoryUiHref(routePath, `/runs?q=${encodeURIComponent(String(row.version_id))}`))}>
                  {row.label || row.version_id}
                </button>
              </td>
              <td>{row.workflow_name || "—"}</td>
              <td>{formatValue(row.runs)}</td>
              <td>{formatValue(row.brier)}</td>
              <td>{formatValue(row.ece)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ScoreHistoryChart({ rows }: { rows: JsonObject[] }): React.ReactElement {
  const plotted = rows.filter((row) => typeof row.brier === "number");
  if (!plotted.length) {
    return <EmptyState title="No score trend yet" body="Resolved runs with scoring artifacts are required before score history can be plotted." />;
  }
  const points = plotted.map((row, index) => {
    const x = plotted.length === 1 ? 50 : (index / (plotted.length - 1)) * 100;
    const y = 100 - Math.max(0, Math.min(1, Number(row.brier))) * 100;
    return `${x},${y}`;
  }).join(" ");
  const summary = `${plotted.length} scored runs. ${plotted.map((row) => `${row.label || row.workflow || row.run_id}: Brier ${formatValue(row.brier)}`).join(". ")}.`;
  return (
    <div className="score-history-chart" role="img" aria-label="Brier score history" aria-describedby="score-history-summary">
      <div className="surface-header">
        <strong>Brier score history</strong>
        <span className="helper-text">{plotted.length} scored runs</span>
      </div>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        <line className="chart-grid-line" x1="0" y1="50" x2="100" y2="50" />
        <polyline className="calibration-line primary" points={points} />
        {plotted.map((row, index) => {
          const x = plotted.length === 1 ? 50 : (index / (plotted.length - 1)) * 100;
          const y = 100 - Math.max(0, Math.min(1, Number(row.brier))) * 100;
          return <circle key={String(row.run_id)} className="calibration-dot" cx={x} cy={y} r="1.8" />;
        })}
      </svg>
      <div className="score-history-labels">
        {plotted.map((row) => (
          <div key={String(row.run_id)}>
            <strong>{formatValue(row.brier)}</strong>
            <span>{row.label || row.workflow || row.run_id}</span>
          </div>
        ))}
      </div>
      <p id="score-history-summary" className="sr-only">{summary}</p>
    </div>
  );
}

function RunDetailPage({
  routePath,
  runId,
  navigate,
  onMutate,
}: {
  routePath: string;
  runId: string;
  navigate: (path: string) => void;
  onMutate: () => void;
}): React.ReactElement {
  const resource = useJsonResource(`${bootstrap.api_root}/runs/${runId}`, [runId]);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: string; title: string; body: string } | null>(null);
  const navigateWithinObservatory = (target: string) => navigate(observatoryUiHref(routePath, target));

  async function generateReport() {
    setBusy("Generating report");
    setNotice(null);
    try {
      const result = await requestJson(`${bootstrap.api_root}/runs/${runId}/report`, {
        method: "POST",
        body: JSON.stringify({}),
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
    return <Message tone="error" title="Run detail unavailable" body={resource.error} />;
  }
  if (resource.loading || !resource.data) {
    return <LoadingCard label="Loading run detail" />;
  }
  const run = resource.data;
  const report = run.artifacts?.report || {};
  return (
    <main className="page-grid detail-shell">
      {notice ? <Message tone={notice.tone} title={notice.title} body={notice.body} /> : null}
      <section className="panel hero-panel detail-hero">
        <span className="eyebrow">Observatory / Run inspector</span>
        <h2>{run.hero?.title || run.workflow?.title || run.run_id}</h2>
        <p>{run.hero?.summary || run.observatory?.summary || "Inspect the latest run summary, question rows, trace, and artifacts."}</p>
        <div className="meta-row">
          <StatusPill value={run.run?.status} />
          <span>{run.run?.provider || "Unknown provider"}</span>
          <span>{run.run?.updated_at || run.run?.completed_at || "—"}</span>
        </div>
        <div className="button-row">
          <button className="primary-button" onClick={() => navigateWithinObservatory(run.observatory?.runs_href || "/runs")}>Back to Observatory</button>
          {run.recommended_compare ? (
            <button className="secondary-button" onClick={() => navigateWithinObservatory(run.recommended_compare.href)}>
              Compare with {run.recommended_compare.run_id}
            </button>
          ) : null}
          {report.available ? (
            <a className="secondary-link" href={report.href} target="_blank" rel="noreferrer">Open HTML report</a>
          ) : null}
          <button className="secondary-button" onClick={generateReport} disabled={busy === "Generating report"}>
            {busy === "Generating report" ? busy : report.available ? "Regenerate report" : "Generate report"}
          </button>
          {(run.artifacts?.exports || [
            { label: "Export JSON", href: `${bootstrap.api_root}/runs/${runId}/export?format=json` },
            { label: "Export CSV", href: `${bootstrap.api_root}/runs/${runId}/export?format=csv` },
          ]).map((item: JsonObject) => (
            <a key={item.label} className="secondary-link" href={item.href}>{item.label}</a>
          ))}
        </div>
      </section>
      <section className="stats-grid">
        {(run.summary_cards || []).map((card: JsonObject) => <MetricCard key={card.label} label={card.label} value={card.value} />)}
      </section>
      <div className="detail-grid">
        <div className="detail-main">
          <section className="panel section-stack">
            <div className="section-header">
              <div>
                <h3>Readable summary</h3>
                <p>Grouped metadata keeps the run context visible without opening raw JSON.</p>
              </div>
            </div>
            <div className="info-grid">
              {(run.metadata_groups || []).map((group: JsonObject) => <KeyValueGroup key={group.title} group={group} />)}
            </div>
          </section>
          <section className="panel section-stack">
            <div className="section-header">
              <div>
                <h3>Probability & result summary</h3>
                <p>Forecast probabilities, resolution coverage, and existing run result fields in one Observatory review block.</p>
              </div>
            </div>
            {(run.probability_summary?.cards || []).length ? (
              <div className="stats-grid">
                {(run.probability_summary?.cards || []).map((card: JsonObject) => <MetricCard key={card.label} label={card.label} value={card.label.toLowerCase().includes("probability") ? formatProbability(card.value) : card.value} />)}
              </div>
            ) : null}
            {(run.probability_summary?.groups || []).some((group: JsonObject) => (group.items || []).length) ? (
              <div className="info-grid">
                {(run.probability_summary?.groups || []).filter((group: JsonObject) => (group.items || []).length).map((group: JsonObject) => <KeyValueGroup key={group.title} group={group} />)}
              </div>
            ) : (
              <EmptyState title={run.probability_summary?.empty_state?.title || "No probability rows"} body={run.probability_summary?.empty_state?.body || "This run does not include probability rows."} />
            )}
          </section>
          <section className="panel section-stack">
            <div className="section-header">
              <div>
                <h3>Score summary</h3>
                <p>Existing eval/train outputs stay explicit when they are present.</p>
              </div>
            </div>
            {(run.score_summary?.groups || []).length ? (
              <div className="info-grid">
                {(run.score_summary?.groups || []).map((group: JsonObject) => <KeyValueGroup key={group.title} group={group} />)}
              </div>
            ) : (
              <EmptyState title={run.score_summary?.empty_state?.title || "No score outputs"} body={run.score_summary?.empty_state?.body || "This run does not include evaluation or training score fields."} />
            )}
          </section>
          <section className="panel section-stack">
            <div className="section-header">
              <div>
                <h3>Results snapshot</h3>
                <p>Core quality, training, and usage metrics in one place.</p>
              </div>
            </div>
            {(run.result_groups || []).length ? (
              <div className="info-grid">
                {(run.result_groups || []).map((group: JsonObject) => <KeyValueGroup key={group.title} group={group} />)}
              </div>
            ) : (
              <EmptyState title="No result summary yet" body="This run does not include evaluation or training summary fields." />
            )}
          </section>
          <section className="panel section-stack">
            <div className="section-header">
              <div>
                <h3>Forecast table</h3>
                <p>Question titles, forecast values, and scoring context for quick review.</p>
              </div>
              <span className="section-count">{run.forecast_table?.count || 0} rows</span>
            </div>
            <RunForecastTable rows={run.forecast_table?.rows || []} emptyState={run.forecast_table?.empty_state} />
          </section>
        </div>
        <aside className="detail-sidebar">
          <section className="panel section-stack">
            <div className="section-header">
              <div>
                <h3>Guided actions</h3>
                <p>Jump to the next useful surface from this run.</p>
              </div>
            </div>
            <div className="action-stack">
              {(run.guided_actions || []).map((action: JsonObject) => (
                <button key={action.label} className="secondary-button action-button" onClick={() => navigateWithinObservatory(action.href)}>
                  {action.label}
                </button>
                ))}
              </div>
            </section>
          <section className="panel section-stack">
            <div className="section-header">
              <div>
                <h3>Version provenance</h3>
                <p>Keep the exact saved snapshot visible when the run came from Versions or a version-backed batch.</p>
              </div>
            </div>
            {run.version?.version_id ? (
              <article className="info-card">
                <div className="surface-header">
                  <strong>{run.version.label || run.version.version_id}</strong>
                  <StatusPill value={run.version.source || "version"} />
                </div>
                <dl className="context-list">
                  <div>
                    <dt>Version ID</dt>
                    <dd>{run.version.version_id}</dd>
                  </div>
                  <div>
                    <dt>Workflow</dt>
                    <dd>{run.version.workflow_name || run.workflow?.name || "—"}</dd>
                  </div>
                </dl>
                <div className="button-row">
                  <button className="secondary-button" onClick={() => navigate("/versions")}>Open Versions</button>
                  <button className="secondary-button" onClick={() => navigateWithinObservatory(`/runs?q=${encodeURIComponent(String(run.version.version_id))}`)}>Related runs</button>
                </div>
              </article>
            ) : (
              <EmptyState title="No saved version linked" body="This run came from a workflow or surface that did not persist version provenance." />
            )}
          </section>
          <section className="panel section-stack">
            <div className="section-header">
              <div>
                <h3>Report & artifacts</h3>
                <p>Use the report when available; fall back to raw files when it is not.</p>
              </div>
            </div>
            <ReportCard report={report} />
            <ArtifactList items={run.artifacts?.items || []} />
            {(run.artifacts?.exports || []).length ? (
              <div className="button-row">
                {(run.artifacts?.exports || []).map((item: JsonObject) => (
                  <a key={item.label} className="secondary-link" href={item.href}>{item.label}</a>
                ))}
              </div>
            ) : null}
            {Object.keys(run.artifacts?.raw || {}).length ? (
              <details className="artifact-preview">
                <summary>Raw structured payloads</summary>
                {Object.entries(run.artifacts?.raw || {}).map(([key, value]) => <ArtifactPreview key={key} label={key} value={value} />)}
              </details>
            ) : null}
          </section>
          <section className="panel section-stack">
            <div className="section-header">
              <div>
                <h3>Compare next</h3>
                <p>Pick a baseline to understand whether the candidate moved the right metrics.</p>
              </div>
            </div>
            {(run.baseline_candidates || []).length ? (
              <div className="action-list">
                {(run.baseline_candidates || []).map((item: JsonObject) => (
                  <button key={item.run_id} className="secondary-button action-button" onClick={() => navigateWithinObservatory(item.href)}>
                    {item.label || item.run_id}
                  </button>
                ))}
              </div>
            ) : (
              <EmptyState title="No comparison candidates" body="Run another workflow revision to unlock side-by-side comparison." />
            )}
          </section>
          <section className="panel section-stack">
            <div className="section-header">
              <div>
                <h3>Execution trace</h3>
                <p>Ordered graph trace or sandbox inspection steps where the run persisted them.</p>
              </div>
            </div>
            {(run.execution_trace?.items || []).length ? (
              <ul className="timeline-list">
                {(run.execution_trace?.items || []).map((item: JsonObject, index: number) => (
                  <li key={`${item.node_id}-${index}`}>
                    <strong>{item.order}. {item.label || item.node_id}</strong>
                    <span>{item.node_id} · {item.node_type || "node"} · {item.status || "observed"}</span>
                    {item.preview ? <span className="table-secondary">{item.preview}</span> : null}
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title={run.execution_trace?.empty_state?.title || "No execution trace"} body={run.execution_trace?.empty_state?.body || "This run did not persist graph trace rows."} />
            )}
          </section>
          <section className="panel section-stack">
            <div className="section-header">
              <div>
                <h3>Uncertainty</h3>
                <p>Shown only when the artifacts include enough uncertainty or reliability data.</p>
              </div>
            </div>
            {run.uncertainty_summary?.available ? (
              <div className="info-grid">
                {(run.uncertainty_summary?.groups || []).map((group: JsonObject) => <KeyValueGroup key={group.title} group={group} />)}
              </div>
            ) : (
              <EmptyState title={run.uncertainty_summary?.empty_state?.title || "Uncertainty unavailable"} body={run.uncertainty_summary?.empty_state?.body || "No uncertainty fields were present in the current read model."} />
            )}
          </section>
        </aside>
      </div>
    </main>
  );
}

function ComparePage({
  routePath,
  candidateRunId,
  baselineRunId,
  navigate,
}: {
  routePath: string;
  candidateRunId: string;
  baselineRunId: string;
  navigate: (path: string) => void;
}): React.ReactElement {
  const resource = useJsonResource(`${bootstrap.api_root}/runs/${candidateRunId}/compare/${baselineRunId}`, [candidateRunId, baselineRunId]);
  const navigateWithinObservatory = (target: string) => navigate(observatoryUiHref(routePath, target));
  if (resource.error) {
    return <Message tone="error" title="Comparison unavailable" body={resource.error} />;
  }
  if (resource.loading || !resource.data) {
    return <LoadingCard label="Loading comparison" />;
  }
  const compare = resource.data;
  return (
    <main className="page-grid compare-shell">
      <section className={`panel hero-panel compare-hero ${compare.verdict?.tone || "neutral"}`}>
        <span className="eyebrow">Compare</span>
        <h2>{compare.verdict?.headline || compare.verdict?.label || "Comparison ready"}</h2>
        <p>{compare.verdict?.summary || "Review grouped metrics and question-level changes before choosing the next step."}</p>
        <div className="compare-run-grid">
          <CompareRunCard label="Candidate" run={compare.run_pair?.candidate} />
          <CompareRunCard label="Baseline" run={compare.run_pair?.baseline} />
        </div>
        <div className="button-row">
          <button className="secondary-button" onClick={() => navigateWithinObservatory(`/runs/${candidateRunId}`)}>Inspect candidate run</button>
          <button className="secondary-button" onClick={() => navigateWithinObservatory(`/runs/${baselineRunId}`)}>Inspect baseline run</button>
          <button className="secondary-button" onClick={() => navigate("/workbench")}>Back to workbench</button>
        </div>
      </section>
      <section className="stats-grid">
        {(compare.summary_cards || []).map((card: JsonObject) => <MetricCard key={card.label} label={card.label} value={card.value} />)}
      </section>
      <div className="compare-grid">
        <div className="compare-main">
          <section className={`panel verdict-panel ${compare.verdict?.tone || "neutral"}`}>
            <span className="eyebrow">Verdict</span>
            <h3>{compare.verdict?.label || "No verdict yet"}</h3>
            <p>{compare.verdict?.next_step || "Open the run detail pages to continue reviewing."}</p>
            <div className="action-list">
              {(compare.next_actions || []).map((action: JsonObject) => (
                <button key={action.label} className="secondary-button action-button" onClick={() => navigateWithinObservatory(action.href)}>
                  <span>{action.label}</span>
                  {action.description ? <small>{action.description}</small> : null}
                </button>
              ))}
            </div>
          </section>
          <section className="panel section-stack">
            <div className="section-header">
              <div>
                <h3>Metric comparison</h3>
                <p>High-level metrics grouped by profile, coverage, efficiency, and quality.</p>
              </div>
            </div>
            {(compare.row_groups || []).map((group: JsonObject) => (
              <section key={group.title} className="compare-group">
                <h4>{group.title}</h4>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Metric</th>
                      <th>Baseline</th>
                      <th>Candidate</th>
                      <th>Interpretation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(group.rows || []).map((row: JsonObject) => (
                      <tr key={row.metric} className={`tone-${row.tone || "neutral"}`}>
                        <td>{row.label || row.metric}</td>
                        <td>{formatValue(row.left)}</td>
                        <td>{formatValue(row.right)}</td>
                        <td>{row.interpretation}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            ))}
          </section>
          <section className="panel section-stack">
            <div className="section-header">
              <div>
                <h3>Question-level changes</h3>
                <p>Question titles stay visible so coverage gaps and score shifts are easy to read.</p>
              </div>
            </div>
            <CompareQuestionTable rows={compare.question_rows || []} />
          </section>
        </div>
        <aside className="compare-sidebar">
          <section className="panel section-stack">
            <div className="section-header">
              <div>
                <h3>Report availability</h3>
                <p>Open each run report directly when it exists.</p>
              </div>
            </div>
            <ReportCard report={compare.run_pair?.candidate?.report} />
            <ReportCard report={compare.run_pair?.baseline?.report} />
          </section>
        </aside>
      </div>
    </main>
  );
}

function PlaygroundPage({
  route,
  shell,
  navigate,
  onMutate,
}: {
  route: Route;
  shell: JsonObject | null;
  navigate: (path: string) => void;
  onMutate: () => void;
}): React.ReactElement {
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
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: string; title: string; body: string } | null>(null);

  const session = resource.data?.session;
  const catalog = (resource.data?.catalog || {}) as JsonObject;
  const workflows = (catalog.workflows || []) as JsonObject[];
  const templates = (catalog.templates || []) as JsonObject[];
  const contextPreview = resource.data?.context_preview as JsonObject | null;
  const lastResult = resource.data?.last_result as JsonObject | null;
  const steps = ((lastResult?.inspection_steps || []) as JsonObject[]).filter((step) => typeof step?.node_id === "string");
  const activeStep = steps.find((step) => playgroundStepKey(step) === selectedStepKey) || steps[0] || null;
  const resultTrace = (lastResult?.execution_trace || {}) as JsonObject;
  const orderedTrace = ((lastResult?.ordered_node_trace || resultTrace.items || []) as JsonObject[]).filter((step) => typeof step?.node_id === "string");
  const graphTraceArtifact = (lastResult?.graph_trace_artifact || {}) as JsonObject;
  const readyToRun = Boolean(questionPrompt.trim() && (contextType === "workflow" ? workflowName : templateId));
  const preRunTraceItems = [
    {
      order: 1,
      label: contextPreview?.reference_name || contextPreview?.title || (contextType === "template" ? "Selected template" : "Selected workflow"),
      status: readyToRun ? "ready" : "configure question",
      detail: readyToRun
        ? "Run the bounded question to generate a real execution trace for this context."
        : "Choose a workflow or template and enter a question before the playground shows a trace.",
    },
  ] as JsonObject[];
  const summaryCards = ((lastResult?.summary_cards || []) as JsonObject[]);
  const resultProbabilityCard = summaryCards.find((card) => String(card.label || "").toLowerCase().includes("probability"));
  const resultProbability = resultProbabilityCard?.value ?? lastResult?.probability_summary?.probability ?? lastResult?.run_summary?.probability;
  const secondarySummaryCards = summaryCards.filter((card) => card !== resultProbabilityCard);
  const latestRunSummary = lastResult?.run_summary?.summary || lastResult?.labeling?.notes?.[0] || "Use the playground for exploratory local analysis, not release-grade evidence.";

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

  const payload = (): JsonObject => ({
    context_type: contextType,
    workflow_name: workflowName || undefined,
    template_id: templateId || undefined,
    question_prompt: questionPrompt,
    question_title: questionTitle || undefined,
    resolution_criteria: resolutionCriteria || undefined,
  });

  async function persistPlaygroundState() {
    setBusy("Updating playground state");
    setNotice(null);
    try {
      await requestJson(`${bootstrap.api_root}/playground`, {
        method: "PATCH",
        body: JSON.stringify(payload()),
      });
      resource.reload();
      onMutate();
      setNotice({
        tone: "success",
        title: "Playground state updated",
        body: "The current exploratory context is saved locally in the WebUI state store.",
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setNotice({
        tone: "error",
        title: "Couldn't update playground state",
        body: `${message} Stay inside the bounded workflow/template + single-question playground contract.`,
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
        body: JSON.stringify(payload()),
      });
      resource.reload();
      onMutate();
      setNotice({
        tone: "success",
        title: "Exploratory run finished",
        body: "Inspect the ordered step outputs below. The playground keeps node inspection read-only.",
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setNotice({
        tone: "error",
        title: "Couldn't run playground session",
        body: `${message} The playground only runs one bounded custom question at a time.`,
      });
    } finally {
      setBusy(null);
    }
  }

  function selectTraceNode(nodeId: string) {
    const matchingStep = steps.find((step) => String(step.node_id) === nodeId);
    if (matchingStep) {
      setSelectedStepKey(playgroundStepKey(matchingStep));
    }
  }

  return (
    <main className="page-grid playground-shell">
      {resource.error ? <Message tone="error" title="Playground unavailable" body={resource.error} /> : null}
      {notice ? <Message tone={notice.tone} title={notice.title} body={notice.body} /> : null}
      {resource.loading && !resource.data ? <LoadingCard label="Loading playground" /> : null}

      <section className="playground-live-workspace">
        <aside className="playground-input-panel">
          <div className="surface-header playground-panel-header">
            <div>
              <span className="eyebrow">Single question input</span>
              <strong>{contextPreview?.title || contextPreview?.reference_name || "Choose a forecasting context"}</strong>
            </div>
            <StatusPill value={String(lastResult?.run?.status || session?.status || "ready")} />
          </div>
          <div className="playground-form-stack">
            <section className="playground-section-card">
              <label>
                <span>Query</span>
                <textarea
                  className="text-area-input playground-query-input"
                  value={questionPrompt}
                  onChange={(event) => setQuestionPrompt(event.target.value)}
                  placeholder="Will the proposed merger between Company X and Y be approved by regulators before Q3?"
                />
              </label>
            </section>
            <section className="playground-section-card">
              <div className="two-field-grid">
                <label>
                  <span>Context</span>
                  <select value={contextType} onChange={(event) => setContextType(event.target.value)}>
                    <option value="workflow">Workflow</option>
                    <option value="template">Template</option>
                  </select>
                </label>
                {contextType === "workflow" ? (
                  <label>
                    <span>Workflow</span>
                    <select value={workflowName} onChange={(event) => setWorkflowName(event.target.value)}>
                      {workflows.map((item: JsonObject) => (
                        <option key={item.name} value={item.name}>{item.title || item.name}</option>
                      ))}
                    </select>
                  </label>
                ) : (
                  <label>
                    <span>Template</span>
                    <select value={templateId} onChange={(event) => setTemplateId(event.target.value)}>
                      {templates.map((item: JsonObject) => (
                        <option key={item.template_id} value={item.template_id}>{item.title}</option>
                      ))}
                    </select>
                  </label>
                )}
              </div>
              <DensityDisclosure
                className="playground-options-disclosure"
                title="Advanced run options"
                detail="Keep optional metadata and tuning nearby without crowding the main prompt."
              >
                <div className="two-field-grid">
                  <label>
                    <span>Optional title</span>
                    <input value={questionTitle} onChange={(event) => setQuestionTitle(event.target.value)} placeholder="Auto-derived when blank" />
                  </label>
                  <label>
                    <span>Resolution criteria</span>
                    <input value={resolutionCriteria} onChange={(event) => setResolutionCriteria(event.target.value)} placeholder="Visible later in Observatory" />
                  </label>
                </div>
                <div className="two-field-grid">
                  <label>
                    <span>Confidence threshold</span>
                    <div className="read-only-field" aria-readonly="true">
                      <strong>10%</strong>
                      <span>Fixed local baseline</span>
                    </div>
                  </label>
                  <label>
                    <span>Research depth</span>
                    <div className="read-only-field" aria-readonly="true">
                      <strong>Standard</strong>
                      <span>Shared playground default</span>
                    </div>
                  </label>
                </div>
              </DensityDisclosure>
            </section>
          </div>
          <div className="button-row playground-action-row">
            <button className="primary-button" onClick={runPlayground} disabled={Boolean(busy) || !readyToRun}>
              {busy === "Running playground session" ? busy : "Run forecast"}
            </button>
            <button className="secondary-button" onClick={persistPlaygroundState} disabled={Boolean(busy)}>Save state</button>
          </div>
          {contextPreview ? (
            <DensityDisclosure
              className="playground-section-card playground-inline-disclosure playground-context-disclosure"
              title={String(contextPreview.reference_name || "Context preview")}
              detail={`Bounded ${contextPreview.context_type || contextType} context. Open for entry, runtime, and route handoff only when you need supporting detail.`}
            >
              <span className="source-pill local">{contextPreview.context_type || contextType}</span>
              <p className="helper-text">{contextPreview.description || "The playground keeps context bounded to a workflow or starter template."}</p>
              <dl className="context-list compact-context-list">
                <div><dt>Entry</dt><dd>{contextPreview.entry || "—"}</dd></div>
                <div><dt>Runtime</dt><dd>{contextPreview.runtime?.provider || "mock"}</dd></div>
                <div><dt>Question limit</dt><dd>{formatValue(contextPreview.questions_limit)}</dd></div>
              </dl>
              <div className="button-row">
                {contextType === "workflow" && workflowName ? (
                  <button className="secondary-button" onClick={() => navigate(`/studio?workflow=${encodeURIComponent(workflowName)}`)}>
                    Open in Studio
                  </button>
                ) : null}
                <button className="secondary-button" onClick={() => navigate("/runs")}>Open Observatory</button>
              </div>
            </DensityDisclosure>
          ) : null}
        </aside>
        <section className="playground-canvas-panel">
          <PlaygroundGraphTracePreview
            canvas={((lastResult?.canvas || contextPreview?.canvas || {}) as JsonObject)}
            traceItems={orderedTrace}
            activeNodeId={String(activeStep?.node_id || "")}
            onSelectNode={selectTraceNode}
          />
        </section>
        <aside className="live-trace-panel">
          <div className="surface-header">
            <div>
              <span className="eyebrow">Live Execution Trace</span>
              <h3>{activeStep?.label || activeStep?.node_id || "Ready to run"}</h3>
            </div>
          </div>
          {lastResult ? (
            <article className="forecast-result-card">
              <span className="eyebrow">{lastResult.run_id || "Latest exploratory run"}</span>
              <strong>{resultProbability != null ? formatProbability(resultProbability) : "Forecast ready"}</strong>
              <span>{lastResult?.run_summary?.summary || lastResult?.labeling?.display_label || "Agent agreement"}</span>
              <p className="helper-text playground-run-note">{latestRunSummary}</p>
              <div className="result-sparkline" aria-hidden="true"><span /><span /><span /><span /></div>
              <div className="button-row">
                <button className="secondary-button" onClick={() => navigate(`/runs/${lastResult.run_id}`)}>Inspect run detail</button>
                {lastResult.report?.available ? <a className="secondary-link" href={lastResult.report.href} target="_blank" rel="noreferrer">Open report</a> : null}
              </div>
            </article>
          ) : null}
          {secondarySummaryCards.length ? (
            <DensityDisclosure
              className="trace-detail-card playground-inline-disclosure playground-metrics-disclosure"
              title="Run metrics"
              detail="Keep secondary summary cards nearby without interrupting the default result → trace → inspector scan path."
            >
              <div className="stats-grid playground-trace-stats">
                {secondarySummaryCards.map((card: JsonObject) => (
                  <MetricCard key={String(card.label)} label={String(card.label)} value={card.value} />
                ))}
              </div>
            </DensityDisclosure>
          ) : null}
          {graphTraceArtifact.available === false && resultTrace.source === "sandbox" ? (
            <Message
              tone="warning"
              title={graphTraceArtifact.empty_state?.title || "No graph trace artifact"}
              body={graphTraceArtifact.empty_state?.body || "Showing sandbox inspection steps without claiming a persisted graph_trace.jsonl artifact."}
            />
          ) : null}
          <div className="live-trace-stack">
              {(orderedTrace.length ? orderedTrace : preRunTraceItems).map((item: JsonObject) => (
              <button
                  key={`${item.order}-${item.node_id || item.label}`}
                  type="button"
                  className={String(activeStep?.node_id || "") === String(item.node_id || "") ? "trace-stage active" : "trace-stage"}
                  onClick={() => item.node_id ? selectTraceNode(String(item.node_id)) : undefined}
                  disabled={!item.node_id}
                >
                  <span className="trace-ring" />
                  <strong>{item.label || item.node_id}</strong>
                  <StatusPill value={String(item.status || "pending")} />
                  {!item.node_id && item.detail ? <span className="trace-stage-note">{item.detail}</span> : null}
                </button>
            ))}
          </div>
          <article className="trace-detail-card">
            <div className="surface-header">
              <strong>{activeStep?.label || activeStep?.node_id || "Awaiting first trace step"}</strong>
              <StatusPill value={String(activeStep?.status || "pending")} />
            </div>
            <dl className="context-list compact-context-list">
              <div><dt>Node</dt><dd>{activeStep?.node_id || "—"}</dd></div>
              <div><dt>Route</dt><dd>{formatValue(activeStep?.route) || "default"}</dd></div>
              <div><dt>Latency</dt><dd>{formatValue(activeStep?.latency_seconds) || "—"}</dd></div>
            </dl>
            <p className="helper-text">{activeStep?.output_preview || lastResult?.run_summary?.summary || "Run the playground to inspect ordered sandbox outputs."}</p>
            <div className="button-row">
              <button className="secondary-button" onClick={() => navigate("/studio")}>Open Studio</button>
            </div>
          </article>
        </aside>
      </section>
    </main>
  );
}

function WorkbenchPage({ route, shell, navigate, onMutate }: { route: Route; shell: JsonObject | null; navigate: (path: string) => void; onMutate: () => void }): React.ReactElement {
  const params = useMemo(() => new URLSearchParams(route.search), [route.search]);
  const draftId = params.get("draft");
  const requestedWorkflow = params.get("workflow");
  const requestedTemplate = params.get("template") || params.get("template_id");
  const requestedMode = params.get("mode");
  const selectedWorkflow = requestedWorkflow || shell?.overview?.latest_run?.workflow?.name || "demo-provider-free";
  const isStudio = route.path === "/studio";
  const surfaceLabel = isStudio ? "Studio" : "Workbench";
  const surfaceBase = isStudio ? "/studio" : "/workbench";
  const draftApiBase = isStudio ? `${bootstrap.api_root}/studio/drafts` : `${bootstrap.api_root}/drafts`;
  const catalogUrl = isStudio ? `${bootstrap.api_root}/studio/catalog` : `${bootstrap.api_root}/authoring/catalog`;
  const workflows = useJsonResource(`${bootstrap.api_root}/workflows`, [route.search]);
  const authoringCatalog = useJsonResource(catalogUrl, [catalogUrl]);
  const draft = useJsonResource(draftId ? `${draftApiBase}/${draftId}` : null, [draftId, draftApiBase]);
  const workflow = useJsonResource(!draftId ? `${bootstrap.api_root}/workflows/${selectedWorkflow}` : null, [selectedWorkflow, draftId]);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<{ tone: string; title: string; body: string } | null>(null);
  const [creationMode, setCreationMode] = useState("clone");
  const [createForm, setCreateForm] = useState<Record<string, string>>({
    source_workflow_name: "",
    template_id: "",
    draft_workflow_name: "",
    title: "",
    description: "",
  });
  const [coreForm, setCoreForm] = useState<Record<string, string>>({});
  const [selectedNodeName, setSelectedNodeName] = useState("");
  const [nodeForm, setNodeForm] = useState<Record<string, string>>({});
  const [addNodeForm, setAddNodeForm] = useState<Record<string, string>>({
    node_name: "",
    implementation: "",
    incoming_from: "",
    outgoing_to: "",
    description: "",
    optional: "false",
    runtime: "",
  });
  const [addEdgeForm, setAddEdgeForm] = useState<Record<string, string>>({ from_node: "", to_node: "" });
  const [selectedEdgeId, setSelectedEdgeId] = useState("");
  const [inspectorMode, setInspectorMode] = useState<"workflow" | "node" | "edge">("workflow");
  const [studioRailMode, setStudioRailMode] = useState<"inspect" | "run" | "tools">("inspect");
  const [edgeDraftFrom, setEdgeDraftFrom] = useState("");
  const [localPositions, setLocalPositions] = useState<Record<string, { x: number; y: number }>>({});
  const [studioBootstrapState, setStudioBootstrapState] = useState<"idle" | "bootstrapping" | "failed">("idle");
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
  const activeGraph = (activeAuthoring?.graph || {}) as JsonObject;
  const graphNodes = ((activeGraph.nodes || []) as JsonObject[]).filter((node) => typeof node?.name === "string");
  const graphTargets = ((activeGraph.targets || []) as JsonObject[]).filter((target) => typeof target?.name === "string");
  const selectedNode = graphNodes.find((node) => node.name === selectedNodeName) || null;
  const canvasEdges = ((activeCanvas?.edges || []) as JsonObject[]);
  const graphEdges = ((activeGraph.edges || []) as JsonObject[]);
  const selectedEdge = canvasEdges.find((edge) => studioEdgeKey(edge) === selectedEdgeId) || null;
  const overviewLatestRun = shell?.overview?.latest_run || null;
  const safeEditSupport = (activeDraft?.guidance?.supported_edits || activeDraft?.safe_edit?.supported_edits || workflow.data?.safe_edit?.supported_edits || []) as JsonObject[];
  const safeEditLimitations = (activeDraft?.guidance?.limitations || activeAuthoring?.limitations || defaultAuthoringLimitations()) as string[];
  const sourceOfTruth = (activeDraft?.guidance?.source_of_truth || defaultSourceOfTruth()) as string[];
  const nextStep = (activeDraft?.guidance?.next_step || buildDraftlessNextStep(activeWorkflow, overviewLatestRun)) as JsonObject;
  const stepState = draftId
    ? decorateStepState((activeDraft?.step_state || defaultStepState()) as JsonObject[], activeDraft, true)
    : decorateStepState(draftlessStepState(activeWorkflow), null, false);
  const validationStatus = buildValidationStatus(activeDraft);
  const validationFixes = buildValidationFixes(activeDraft);
  const runDisabled = !(activeDraft?.validation?.ok && !activeDraft?.validation?.stale);
  const templates = (authoringCatalog.data?.templates || []) as JsonObject[];
  const nodeCatalog = ((authoringCatalog.data?.node_catalog || authoringCatalog.data?.node_palette?.items || []) as JsonObject[]);
  const creationModes = (authoringCatalog.data?.creation_modes || []) as JsonObject[];
  const creationDisabled = !createForm.draft_workflow_name || (creationMode === "clone" && !(createForm.source_workflow_name || activeWorkflow?.name)) || (creationMode === "template" && !createForm.template_id);
  const showStudioDraftIde = isStudio && Boolean(draftId);
  const resumeTarget = (shell?.overview?.resume_target || shell?.hub?.resume_target || {}) as JsonObject;
  const explicitStudioIntent = Boolean(requestedWorkflow || requestedTemplate || requestedMode);
  const studioResumeTarget = !isStudio || draftId || explicitStudioIntent || resumeTarget.kind !== "draft" || !resumeTarget.href
    ? null
    : {
      href: String(resumeTarget.href),
      label: String(resumeTarget.label || "Resume latest draft"),
    };
  const studioIntent = useMemo<StudioRouteIntent | null>(() => {
    if (!isStudio || draftId) return null;
    if (requestedMode === "scratch") return { creation_mode: "scratch" };
    if (requestedTemplate || requestedMode === "template") {
      return {
        creation_mode: "template",
        template_id: String(requestedTemplate || templates[0]?.template_id || "") || null,
      };
    }
    if (requestedWorkflow || requestedMode === "clone") {
      return {
        creation_mode: "clone",
        source_workflow_name: requestedWorkflow || selectedWorkflow,
      };
    }
    return null;
  }, [draftId, isStudio, requestedMode, requestedTemplate, requestedWorkflow, selectedWorkflow, templates]);
  const showStudioSetup = !showStudioDraftIde && (!isStudio || studioBootstrapState === "failed" || !studioIntent);
  const showWorkbenchSetupRail = showStudioSetup && !isStudio;
  const showWorkbenchFieldSetup = showStudioSetup && !isStudio;
  const showWorkbenchIdePanel = !isStudio || showStudioDraftIde || !showStudioSetup;
  const compareActions = ((activeDraft?.compare?.next_actions || []) as JsonObject[]);
  const validationPillValue = activeDraft?.validation?.ok ? (activeDraft?.validation?.stale ? "stale validation" : "validated") : "needs validation";
  const studioDraftTitle = activeDraft?.draft_workflow_name || activeWorkflow?.title || activeWorkflow?.name || "Studio draft";
  const normalizedPaletteQuery = paletteQuery.trim().toLowerCase();
  const paletteGroups = useMemo(() => {
    const grouped = new Map<string, JsonObject[]>();
    nodeCatalog.forEach((item) => {
      const kind = String(item.kind || "other");
      const entries = grouped.get(kind) || [];
      entries.push(item);
      grouped.set(kind, entries);
    });
    return Array.from(grouped.entries())
      .sort(([left], [right]) => {
        const leftIndex = PALETTE_KIND_ORDER.indexOf(left);
        const rightIndex = PALETTE_KIND_ORDER.indexOf(right);
        if (leftIndex >= 0 && rightIndex >= 0) return leftIndex - rightIndex;
        if (leftIndex >= 0) return -1;
        if (rightIndex >= 0) return 1;
        return left.localeCompare(right);
      })
      .map(([kind, items]) => ({
        key: kind,
        label: paletteGroupLabel(kind),
        items: [...items].sort((left, right) => String(left.label || left.name || left.implementation || "").localeCompare(String(right.label || right.name || right.implementation || ""))),
      }));
  }, [nodeCatalog]);
  const filteredPaletteGroups = useMemo(() => paletteGroups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => paletteMatchesQuery(item, normalizedPaletteQuery)),
    }))
    .filter((group) => group.items.length), [normalizedPaletteQuery, paletteGroups]);
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
      let payload: JsonObject = { creation_mode: studioIntent.creation_mode };
      if (studioIntent.creation_mode === "template") {
        const templateId = String(studioIntent.template_id || "");
        if (!templateId) {
          setStudioBootstrapState("failed");
          setActionNotice({
            tone: "warning",
            title: "Studio needs a starter template",
            body: "No starter template was available to open directly in the Studio graph IDE.",
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
            body: "No workflow was available to open directly in the Studio graph IDE.",
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
    studioIntent,
  ]);

  useEffect(() => {
    setCreateForm((current) => ({
      ...current,
      source_workflow_name: current.source_workflow_name || selectedWorkflow,
      template_id: current.template_id || String(templates[0]?.template_id || ""),
    }));
    setAddNodeForm((current) => ({
      ...current,
      implementation: current.implementation || String(nodeCatalog[0]?.implementation || ""),
    }));
  }, [selectedWorkflow, templates, nodeCatalog]);

  useEffect(() => {
    if (activeAuthoring?.core_form) {
      const nextCore: Record<string, string> = {};
      Object.entries(activeAuthoring.core_form as JsonObject).forEach(([key, value]) => {
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
    const nextNodeForm: Record<string, string> = {
      description: String(selectedNode.description || ""),
      runtime: String(selectedNode.runtime || ""),
      optional: selectedNode.optional ? "true" : "false",
    };
    ((selectedNode.aggregate_weights || []) as JsonObject[]).forEach((item) => {
      nextNodeForm[`weight:${String(item.name)}`] = String(item.percent ?? "");
    });
    setNodeForm(nextNodeForm);
  }, [selectedNode]);

  async function createDraftFromMode() {
    setBusy("Creating authoring draft");
    setActionNotice(null);
    try {
      const payload: JsonObject = {
        creation_mode: creationMode,
        draft_workflow_name: createForm.draft_workflow_name,
        title: normalizeText(createForm.title) || undefined,
        description: normalizeText(createForm.description) || undefined,
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

  async function applyDraftAction(stage: string, action: JsonObject, successTitle: string, successBody: string): Promise<JsonObject | null> {
    if (!draftId) return null;
    setBusy(successTitle);
    setActionNotice(null);
    try {
      const updated = await requestJson(isStudio ? `${draftApiBase}/${draftId}/graph` : `${draftApiBase}/${draftId}`, {
        method: "PATCH",
        body: JSON.stringify({ action }),
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

  function selectNodeInspector(name: string) {
    setStudioRailMode("inspect");
    setSelectedNodeName(name);
    setSelectedEdgeId("");
    setInspectorMode("node");
  }

  function selectEdgeInspector(edge: JsonObject) {
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
          tags: (coreForm.tags || "").split(",").map((item) => item.trim()).filter(Boolean),
        },
        questions: { limit: Number(coreForm.questions_limit || 0) },
        runtime: {
          provider: coreForm.runtime_provider,
          base_url: normalizeText(coreForm.runtime_base_url),
          model: normalizeText(coreForm.runtime_model),
          max_tokens: Number(coreForm.runtime_max_tokens || 0),
        },
        artifacts: {
          write_report: parseBooleanString(coreForm.artifacts_write_report),
          write_blueprint_copy: parseBooleanString(coreForm.artifacts_write_blueprint_copy),
          write_graph_trace: parseBooleanString(coreForm.artifacts_write_graph_trace),
        },
        scoring: {
          write_eval: parseBooleanString(coreForm.scoring_write_eval),
          write_train_backtest: parseBooleanString(coreForm.scoring_write_train_backtest),
        },
      },
      "Workflow fields updated",
      "Core workflow fields now reflect the latest authored state. Validate when you're ready to run."
    );
  }

  async function applyNodeUpdates() {
    if (!draftId || !selectedNode) return;
    const weights: Record<string, string> = {};
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
        weights: Object.keys(weights).length ? weights : undefined,
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

  async function setEntry(entryName: string) {
    if (!draftId || !entryName) return;
    await applyDraftAction(
      "entry",
      { type: "set-entry", entry: entryName },
      "Entry updated",
      `${entryName} is now the workflow entry for this draft.`
    );
  }

  async function addNode(overrides: Record<string, string> = {}, dropPosition?: { x: number; y: number }) {
    if (!draftId) return;
    const form = { ...addNodeForm, ...overrides };
    const action: JsonObject = {
      type: "add-node",
      node_name: form.node_name,
      implementation: form.implementation,
      description: normalizeText(form.description),
      runtime: normalizeText(form.runtime),
      optional: parseBooleanString(form.optional),
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

  async function addPaletteNode(itemOrImplementation: JsonObject | string, dropPosition?: { x: number; y: number }) {
    const item = typeof itemOrImplementation === "string"
      ? nodeCatalog.find((candidate) => candidate.implementation === itemOrImplementation) || { implementation: itemOrImplementation, name: itemOrImplementation }
      : itemOrImplementation;
    const connectionFrom = selectedNode?.name || activeGraph.entry || graphNodes[0]?.name || "";
    await addNode(
      {
        node_name: suggestNodeName(item, graphNodes),
        implementation: String(item.implementation || ""),
        incoming_from: String(connectionFrom || ""),
        outgoing_to: "",
        description: String(item.summary || item.description || ""),
        runtime: String(item.default_runtime || ""),
        optional: "false",
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

  async function removeEdge(fromNode: string, toNode: string) {
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

  async function createEdgeFromCanvas(fromNode: string, toNode: string) {
    setAddEdgeForm({ from_node: fromNode, to_node: toNode });
    await addEdgeFromValues(fromNode, toNode);
  }

  async function addEdgeFromValues(fromNode: string, toNode: string) {
    if (!draftId) return;
    const updated = await applyDraftAction(
      "edge",
      { type: "add-edge", from_node: fromNode, to_node: toNode },
      "Edge added",
      `${fromNode} now connects to ${toNode}${isStudio ? " and validation was refreshed." : "."}`
    );
    if (updated) {
      const addedEdge = ((updated.authoring?.graph?.edges || []) as JsonObject[]).find((edge) => edge.from === fromNode && edge.to === toNode);
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
        validation?.ok
          ? {
              tone: validation.stale ? "warning" : "success",
              title: validation.stale ? "Validation needs a refresh" : "Validation passed",
              body: validation.stale
                ? "A newer edit changed the draft after validation. Validate once more before you run."
                : "The latest authored draft was saved and validated successfully. Next: run a candidate and compare it with the baseline.",
            }
          : {
              tone: "warning",
              title: "Validation found issues",
              body: `${(validation?.errors || []).join(" ")} Fix the supported fields below; your draft context is still preserved.`,
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
          set_default: true,
        }),
      });
      onMutate();
      setActionNotice({
        tone: "success",
        title: "Version snapshot created",
        body: `${result.label || result.id} is now the default saved snapshot for ${result.workflow_name}.`,
      });
    } catch (error) {
      setActionNotice(buildActionErrorNotice("version snapshot", error));
    } finally {
      setBusy(null);
    }
  }

  async function persistNodePosition(name: string, position: { x: number; y: number }) {
    setLocalPositions((current) => ({ ...current, [name]: position }));
    if (!draftId || !isStudio) return;
    try {
      await requestJson(`${draftApiBase}/${draftId}/graph`, {
        method: "PATCH",
        body: JSON.stringify({ action: { type: "move-node", node_name: name, position } }),
      });
      draft.reload();
    } catch (error) {
      setActionNotice(buildActionErrorNotice("layout", error));
    }
  }

  return (
    <main
      className={isStudio ? `workbench-layout studio-workspace${showStudioDraftIde ? " studio-draft-mode" : ""}` : "workbench-layout"}
      style={showStudioDraftIde ? { gridTemplateColumns: "minmax(0, 1fr)" } : undefined}
    >
      {showWorkbenchSetupRail ? (
        <aside className="panel step-panel">
          <span className="eyebrow">Journey</span>
          <h2>Inspect → create → author</h2>
          <ol className="step-list step-rail">
            {stepState.map((step: JsonObject) => (
              <li key={step.key} className={`step-item step-${step.state || "upcoming"}${step.locked ? " locked" : ""}`}>
                <div className="step-head">
                  <strong>{step.label}</strong>
                  <span className={`step-status ${step.state || "upcoming"}`}>{stepBadgeLabel(step)}</span>
                </div>
                <span>{step.description}</span>
              </li>
            ))}
          </ol>
        </aside>
      ) : null}
      <section className="workbench-main">
        {workflow.error ? <Message tone="error" title="Workflow unavailable" body={workflow.error} /> : null}
        {draft.error ? <Message tone="error" title="Draft unavailable" body={draft.error} /> : null}
        {workflows.error ? <Message tone="error" title="Workflow catalog unavailable" body={workflows.error} /> : null}
        {authoringCatalog.error ? <Message tone="error" title="Authoring catalog unavailable" body={authoringCatalog.error} /> : null}
        {actionNotice ? <Message tone={actionNotice.tone} title={actionNotice.title} body={actionNotice.body} /> : null}
        {busy ? <LoadingCard label={busy} /> : null}
        {draftId && draft.loading && !draft.data ? <LoadingCard label="Loading draft" /> : null}
        {!draftId && (workflow.loading || authoringCatalog.loading) && !workflow.data ? <LoadingCard label="Loading workflow authoring surface" /> : null}

      {showStudioSetup ? (
        <section className="panel hero-panel workbench-hero">
          <span className="eyebrow">{surfaceLabel}</span>
          <h2>{draftId ? "Drag-drop the bounded workflow graph IDE" : "Create a new authored workflow or clone one into a local draft"}</h2>
          <p>
            {draftId
              ? isStudio
                ? "Move nodes locally, drag safe palette nodes onto the canvas, create/remove edges, edit supported config, validate, save, and run through the Studio API without arbitrary plugin or code editing."
                : "The legacy workbench route stays compatible with the same safe authoring backend while Studio is the primary graph IDE surface."
              : isStudio
                ? "Choose a workflow, starter template, or scratch path to open a local draft in the graph IDE. Resume stays available without duplicating the editor inside setup."
                : "Start from scratch, a template, or an existing workflow. Draft state stays local and resumable while the reusable workflow file remains coherent on disk."}
          </p>
          <div className="meta-row">
            <SourceBadge source={activeWorkflow?.source || "builtin"} />
            {activeDraft?.creation_mode ? <span>Mode: {activeDraft.creation_mode}</span> : null}
            {activeDraft?.draft_workflow_name ? <span>Draft: {activeDraft.draft_workflow_name}</span> : null}
            {activeDraft?.baseline_run_id ? <span>Baseline: {activeDraft.baseline_run_id}</span> : overviewLatestRun?.run_id ? <span>Suggested baseline: {overviewLatestRun.run_id}</span> : null}
            {activeDraft?.last_run_id ? <span>Candidate: {activeDraft.last_run_id}</span> : null}
          </div>
          <div className="button-row">
            {studioResumeTarget ? (
              <button className="primary-button" onClick={() => navigate(studioResumeTarget.href)}>
                {studioResumeTarget.label}
              </button>
            ) : null}
            {overviewLatestRun?.run_id ? (
              <button className="secondary-button" onClick={() => navigate(`/runs/${overviewLatestRun.run_id}`)}>Inspect latest run</button>
            ) : (
              <button className="secondary-button" onClick={() => navigate("/runs")}>Browse runs</button>
            )}
            {activeDraft?.last_run_id ? <button className="secondary-button" onClick={() => navigate(`/runs/${activeDraft.last_run_id}`)}>Inspect candidate run</button> : null}
          </div>
        </section>
        ) : null}

        {showStudioSetup ? (
        <section className="panel section-stack">
          <div className="section-heading">
            <div>
              <span className="eyebrow">{isStudio ? "Start here" : "1. Create draft"}</span>
              <h3>{isStudio ? "Create or resume a local Studio draft" : "Start from scratch, template, or clone"}</h3>
            </div>
            <p className="section-copy">
              {isStudio
                ? "Studio setup is only the entry surface. Once a draft opens, workflow fields, graph editing, validation, and run actions stay inside the full editor."
                : "Creation routes all flow through the shared backend authoring service and still land in the local draft + workflow file model."}
            </p>
          </div>
          <div className="creation-mode-row">
            {creationModes.map((mode: JsonObject) => (
              <button
                key={mode.key}
                className={creationMode === mode.key ? "workflow-tile active" : "workflow-tile"}
                onClick={() => setCreationMode(String(mode.key || "clone"))}
                type="button"
              >
                <strong>{mode.label}</strong>
                <span className="workflow-note">{mode.detail}</span>
              </button>
            ))}
          </div>
          <div className="split-grid">
            <section className="surface-card section-stack">
              <label>
                <span>Draft workflow name</span>
                <input value={createForm.draft_workflow_name || ""} onChange={(event) => setCreateForm((current) => ({ ...current, draft_workflow_name: event.target.value }))} placeholder="my-authored-workflow" />
              </label>
              {creationMode === "clone" ? (
                <label>
                  <span>Source workflow</span>
                  <select value={createForm.source_workflow_name || selectedWorkflow} onChange={(event) => setCreateForm((current) => ({ ...current, source_workflow_name: event.target.value }))}>
                    {(workflows.data?.items || []).map((item: JsonObject) => (
                      <option key={item.name} value={item.name}>{item.title || item.name}</option>
                    ))}
                  </select>
                </label>
              ) : null}
              {creationMode === "template" ? (
                <label>
                  <span>Starter template</span>
                  <select value={createForm.template_id || ""} onChange={(event) => setCreateForm((current) => ({ ...current, template_id: event.target.value }))}>
                    {templates.map((item: JsonObject) => (
                      <option key={item.template_id} value={item.template_id}>{item.title}</option>
                    ))}
                  </select>
                </label>
              ) : null}
              <label>
                <span>Title</span>
                <input value={createForm.title || ""} onChange={(event) => setCreateForm((current) => ({ ...current, title: event.target.value }))} placeholder="Optional display title" />
              </label>
              <label>
                <span>Description</span>
                <textarea className="text-area-input" value={createForm.description || ""} onChange={(event) => setCreateForm((current) => ({ ...current, description: event.target.value }))} placeholder="Optional authoring summary" />
              </label>
              <div className="button-row">
                <button className="primary-button" onClick={createDraftFromMode} disabled={Boolean(busy) || creationDisabled}>Create draft</button>
                {studioResumeTarget ? (
                  <button className="secondary-button" onClick={() => navigate(studioResumeTarget.href)}>
                    {studioResumeTarget.label}
                  </button>
                ) : null}
                {!draftId && activeWorkflow?.name ? (
                  <button className="secondary-button" onClick={() => navigate(`/workflows/${encodeURIComponent(activeWorkflow.name)}`)}>Open workflow detail</button>
                ) : null}
              </div>
            </section>
            <section className="surface-card section-stack">
              <div className="surface-header">
                <div>
                  <strong>{activeWorkflow?.title || activeWorkflow?.name || selectedWorkflow}</strong>
                  <p>{activeWorkflow?.description || "Select a workflow or choose a starter mode."}</p>
                </div>
                <SourceBadge source={activeWorkflow?.source || "builtin"} />
              </div>
              {studioResumeTarget ? (
                <div className="compact-action-stack">
                  <p className="helper-text">A local draft is already available. Resume it directly or create a new draft from the selected workflow or template.</p>
                  <button className="secondary-button" onClick={() => navigate(studioResumeTarget.href)}>
                    {studioResumeTarget.label}
                  </button>
                </div>
              ) : activeDraft ? (
                <dl className="context-list">
                  <div><dt>Draft mode</dt><dd>{activeDraft.creation_mode || "clone"}</dd></div>
                  <div><dt>Source</dt><dd>{activeDraft.source_workflow_name || "—"}</dd></div>
                  <div><dt>Local workflow</dt><dd>{activeDraft.draft_workflow_name || "—"}</dd></div>
                  <div><dt>Status</dt><dd>{activeDraft.status || "—"}</dd></div>
                </dl>
              ) : activeWorkflow ? (
                <dl className="context-list">
                  <div><dt>Workflow kind</dt><dd>{activeWorkflow.workflow_kind || activeWorkflow.kind || "workflow"}</dd></div>
                  <div><dt>Questions</dt><dd>{activeWorkflow.question_limit || workflow.data?.blueprint?.questions?.limit || "—"}</dd></div>
                  <div><dt>Runtime</dt><dd>{activeWorkflow.runtime_provider || workflow.data?.blueprint?.runtime?.provider || "mock"}</dd></div>
                  <div><dt>Action</dt><dd>{creationMode === "clone" ? "Clone this workflow into a local authored draft." : creationMode === "template" ? "Create a new workflow from the selected starter template." : "Create a fresh safe starter workflow and begin authoring."}</dd></div>
                </dl>
              ) : (
                <EmptyState title="Select a workflow" body={isStudio ? "Studio will show the current workflow summary here before you create a draft." : "The workbench will show the current workflow summary here before you create a draft."} />
              )}
            </section>
          </div>
          <div className="workflow-list workflow-catalog">
            {(workflows.data?.items || []).map((item: JsonObject) => (
              <button
                key={item.name}
                className={item.name === activeWorkflow?.name ? "workflow-tile active" : "workflow-tile"}
                onClick={() => navigate(`${surfaceBase}?workflow=${encodeURIComponent(item.name)}`)}
                type="button"
              >
                <div className="workflow-tile-head">
                  <strong>{item.title}</strong>
                  <SourceBadge source={item.source} />
                </div>
                <span>{item.name}</span>
                <span className="workflow-note">{item.source === "builtin" ? "Clone to author visually" : "Open a draft session for this local workflow"}</span>
              </button>
            ))}
          </div>
        </section>
        ) : null}

        {showWorkbenchFieldSetup ? (
        <section className="panel section-stack">
          <div className="section-heading">
            <div>
              <span className="eyebrow">2. Workflow fields</span>
              <h3>Edit supported core fields through the shared authoring layer</h3>
            </div>
            <p className="section-copy">Title, description, workflow kind, bounded runtime settings, scoring, and artifact toggles stay inside the safe product contract.</p>
          </div>
          {!draftId ? (
            <EmptyState title="Create a draft to unlock field editing" body="Once a draft exists, this form edits the authored workflow fields that the shared backend service supports." />
          ) : (
            <div className="form-grid guided-form">
              <div className="two-field-grid">
                <label>
                  <span>Title</span>
                  <input value={coreForm.title || ""} onChange={(event) => setCoreForm((current) => ({ ...current, title: event.target.value }))} />
                </label>
                <label>
                  <span>Workflow kind</span>
                  <input value={coreForm.workflow_kind || ""} onChange={(event) => setCoreForm((current) => ({ ...current, workflow_kind: event.target.value }))} list="workflow-kind-options" />
                </label>
              </div>
              <datalist id="workflow-kind-options">
                {((authoringCatalog.data?.workflow_kind_options || []) as string[]).map((item) => <option key={item} value={item} />)}
              </datalist>
              <label>
                <span>Description</span>
                <textarea className="text-area-input" value={coreForm.description || ""} onChange={(event) => setCoreForm((current) => ({ ...current, description: event.target.value }))} />
              </label>
              <label>
                <span>Tags</span>
                <input value={coreForm.tags || ""} onChange={(event) => setCoreForm((current) => ({ ...current, tags: event.target.value }))} placeholder="starter, local, benchmark" />
              </label>
              <div className="three-column-grid compact-form-grid">
                <label>
                  <span>Questions limit</span>
                  <input type="number" min={1} max={25} value={coreForm.questions_limit || ""} onChange={(event) => setCoreForm((current) => ({ ...current, questions_limit: event.target.value }))} />
                </label>
                <label>
                  <span>Runtime provider</span>
                  <select value={coreForm.runtime_provider || "mock"} onChange={(event) => setCoreForm((current) => ({ ...current, runtime_provider: event.target.value }))}>
                    {((authoringCatalog.data?.runtime_provider_options || []) as string[]).map((item) => <option key={item} value={item}>{item}</option>)}
                  </select>
                </label>
                <label>
                  <span>Max tokens</span>
                  <input type="number" min={1} value={coreForm.runtime_max_tokens || ""} onChange={(event) => setCoreForm((current) => ({ ...current, runtime_max_tokens: event.target.value }))} />
                </label>
              </div>
              <div className="two-field-grid">
                <label>
                  <span>Runtime base URL</span>
                  <input value={coreForm.runtime_base_url || ""} onChange={(event) => setCoreForm((current) => ({ ...current, runtime_base_url: event.target.value }))} placeholder="http://127.0.0.1:11434/v1" />
                </label>
                <label>
                  <span>Runtime model</span>
                  <input value={coreForm.runtime_model || ""} onChange={(event) => setCoreForm((current) => ({ ...current, runtime_model: event.target.value }))} placeholder="phi-4-mini" />
                </label>
              </div>
              <div className="three-column-grid compact-form-grid">
                <label>
                  <span>Write HTML report</span>
                  <select value={coreForm.artifacts_write_report || "true"} onChange={(event) => setCoreForm((current) => ({ ...current, artifacts_write_report: event.target.value }))}>
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </select>
                </label>
                <label>
                  <span>Write blueprint copy</span>
                  <select value={coreForm.artifacts_write_blueprint_copy || "true"} onChange={(event) => setCoreForm((current) => ({ ...current, artifacts_write_blueprint_copy: event.target.value }))}>
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </select>
                </label>
                <label>
                  <span>Write graph trace</span>
                  <select value={coreForm.artifacts_write_graph_trace || "true"} onChange={(event) => setCoreForm((current) => ({ ...current, artifacts_write_graph_trace: event.target.value }))}>
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </select>
                </label>
              </div>
              <div className="two-field-grid">
                <label>
                  <span>Write eval</span>
                  <select value={coreForm.scoring_write_eval || "true"} onChange={(event) => setCoreForm((current) => ({ ...current, scoring_write_eval: event.target.value }))}>
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </select>
                </label>
                <label>
                  <span>Write train backtest</span>
                  <select value={coreForm.scoring_write_train_backtest || "true"} onChange={(event) => setCoreForm((current) => ({ ...current, scoring_write_train_backtest: event.target.value }))}>
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </select>
                </label>
              </div>
              <div className="button-row">
                <button className="primary-button" onClick={applyCoreFields} disabled={Boolean(busy)}>Apply workflow fields</button>
              </div>
            </div>
          )}
        </section>
        ) : null}

        {showWorkbenchIdePanel ? (
        <section className="panel section-stack studio-ide-panel">
          <div className="section-heading">
            <div>
              <span className="eyebrow">{showStudioDraftIde ? "Studio" : "3. Studio graph IDE"}</span>
              <h3>{showStudioDraftIde ? studioDraftTitle : "Drag nodes, drop safe palette items, select nodes/edges, then validate"}</h3>
            </div>
            <p className="section-copy">
              {showStudioDraftIde
                ? "Keep palette, canvas, inspector, validation, and versioning inside one draft IDE."
                : "Node positions persist with the draft layout while graph topology and configuration stay inside the shared authoring contract."}
            </p>
            {showStudioDraftIde ? (
              <div className="meta-row">
                <SourceBadge source={activeWorkflow?.source || "builtin"} />
                <StatusPill value={validationPillValue} />
                {activeDraft?.revision != null ? <span>Revision {activeDraft.revision}</span> : null}
                {activeGraph.entry ? <span>Entry: {String(activeGraph.entry)}</span> : null}
                {activeDraft?.baseline_run_id ? <span>Baseline: {activeDraft.baseline_run_id}</span> : null}
                {activeDraft?.last_run_id ? <span>Candidate: {activeDraft.last_run_id}</span> : null}
              </div>
            ) : null}
          </div>
          {!draftId ? (
            isStudio && studioIntent && studioBootstrapState !== "failed"
              ? <LoadingCard label="Opening Studio graph IDE" />
              : <EmptyState title="Create a draft to unlock graph authoring" body="The canvas becomes editable as soon as you open a draft session." />
          ) : (
            <>
              <div className="studio-toolbar">
                <button className={inspectorMode === "workflow" ? "secondary-button active" : "secondary-button"} onClick={selectWorkflowInspector}>Workflow inspector</button>
                <button className={inspectorMode === "node" ? "secondary-button active" : "secondary-button"} onClick={() => selectedNodeName && selectNodeInspector(selectedNodeName)} disabled={!selectedNodeName}>Node inspector</button>
                <button className={inspectorMode === "edge" ? "secondary-button active" : "secondary-button"} onClick={() => selectedEdge && selectEdgeInspector(selectedEdge)} disabled={!selectedEdge}>Edge inspector</button>
                {edgeDraftFrom ? (
                  <button className="secondary-button active" onClick={() => setEdgeDraftFrom("")}>Creating edge from {edgeDraftFrom} · cancel</button>
                ) : selectedNode ? (
                  <button className="secondary-button" onClick={() => setEdgeDraftFrom(String(selectedNode.name))}>Start edge from selected node</button>
                ) : null}
              </div>

              <section className="node-palette" aria-label="Studio node palette">
                <div>
                  <span className="eyebrow">Quick add</span>
                  <p>Search or insert one safe node first. Open the grouped library only when the quick path is not enough.</p>
                </div>
                <div className="node-palette-toolbar">
                  <label className="node-palette-search">
                    <span className="eyebrow">Quick insert</span>
                    <input
                      type="search"
                      value={paletteQuery}
                      onChange={(event) => setPaletteQuery(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" && paletteTopMatch && !busy) {
                          event.preventDefault();
                          void addPaletteTopMatch();
                        }
                      }}
                      placeholder="Search nodes, then press Enter to insert the top match"
                      aria-label="Search studio node palette"
                    />
                  </label>
                  <div className="node-palette-actions">
                    <button className="secondary-button" type="button" onClick={() => void addPaletteTopMatch()} disabled={Boolean(busy) || !paletteTopMatch}>
                      {paletteTopMatch ? `Insert ${paletteTopMatch.label || paletteTopMatch.name}` : "No matching node"}
                    </button>
                  </div>
                </div>
                <details
                  className="density-disclosure studio-library-disclosure"
                  open={normalizedPaletteQuery ? true : paletteLibraryOpen || undefined}
                  onToggle={(event) => {
                    if (normalizedPaletteQuery) return;
                    setPaletteLibraryOpen((event.currentTarget as HTMLDetailsElement).open);
                  }}
                >
                  <summary>
                    <div className="density-disclosure-copy">
                      <strong>{normalizedPaletteQuery ? `${filteredPaletteItems.length} matching nodes` : `Browse all ${nodeCatalog.length} safe nodes`}</strong>
                      <p>
                        {normalizedPaletteQuery
                          ? paletteTopMatch
                            ? `Enter inserts ${paletteTopMatch.label || paletteTopMatch.name}.`
                            : "Adjust the search to find another node."
                          : "Keep the full library collapsed until you need the grouped catalog."}
                      </p>
                    </div>
                  </summary>
                  <div className="density-disclosure-body">
                    <p className="helper-text node-palette-status">
                      {normalizedPaletteQuery
                        ? `${filteredPaletteItems.length} of ${nodeCatalog.length} nodes match the current search.`
                        : `Grouped library · ${nodeCatalog.length} safe nodes available by category.`}
                    </p>
                    <div className="node-palette-scroll">
                      {filteredPaletteGroups.length ? (
                        filteredPaletteGroups.map((group, index) => (
                          <details
                            key={group.key}
                            className="palette-group-card"
                            open={Boolean(normalizedPaletteQuery) || index === 0 || undefined}
                          >
                            <summary>
                              <span>{group.label}</span>
                              <small>{group.items.length} nodes</small>
                            </summary>
                            <div className="node-palette-grid">
                              {group.items.map((item: JsonObject) => (
                                <button
                                  key={item.implementation}
                                  type="button"
                                  className="palette-node-card"
                                  draggable={item.draggable !== false}
                                  onDragStart={(event: React.DragEvent<HTMLButtonElement>) => {
                                    event.dataTransfer.setData("application/xrtm-node-implementation", String(item.implementation || ""));
                                    event.dataTransfer.effectAllowed = "copy";
                                  }}
                                  onClick={() => void addPaletteNode(item)}
                                  disabled={Boolean(busy)}
                                >
                                  <strong>{item.label || item.name}</strong>
                                  <span>{item.kind}</span>
                                  <small>{item.summary || item.description}</small>
                                </button>
                              ))}
                            </div>
                          </details>
                        ))
                      ) : (
                        <div className="palette-empty-state">
                          <strong>No safe nodes match that search.</strong>
                          <span>Try a kind, label, or implementation name such as router, scorer, or baseline.</span>
                        </div>
                      )}
                    </div>
                  </div>
                </details>
              </section>

              <WorkflowCanvasSurface
                canvas={activeCanvas}
                entry={String(activeGraph.entry || "")}
                selectedNodeName={inspectorMode === "node" ? selectedNodeName : ""}
                selectedEdgeId={inspectorMode === "edge" ? selectedEdgeId : ""}
                localPositions={localPositions}
                edgeDraftFrom={edgeDraftFrom}
                onMoveNode={(name, position) => setLocalPositions((current) => ({ ...current, [name]: position }))}
                onMoveEnd={(name, position) => void persistNodePosition(name, position)}
                onSelectNode={selectNodeInspector}
                onSelectEdge={selectEdgeInspector}
                onSelectWorkflow={selectWorkflowInspector}
                onAddNodeFromPalette={(implementation, position) => void addPaletteNode(implementation, position)}
                onCreateEdge={(from, to) => void createEdgeFromCanvas(from, to)}
              />

              <div className={showStudioDraftIde ? "split-grid authoring-grid" : "three-column-grid authoring-grid"}>
                {showStudioDraftIde ? (
                  <div className="studio-rail-tabs" role="tablist" aria-label="Studio side panel">
                    <button
                      id="studio-rail-tab-inspect"
                      role="tab"
                      aria-selected={studioRailMode === "inspect"}
                      aria-controls="studio-side-panel-inspect"
                      tabIndex={studioRailMode === "inspect" ? 0 : -1}
                      className={studioRailMode === "inspect" ? "secondary-button active" : "secondary-button"}
                      type="button"
                      onClick={() => setStudioRailMode("inspect")}
                    >
                      Inspector
                    </button>
                    <button
                      id="studio-rail-tab-run"
                      role="tab"
                      aria-selected={studioRailMode === "run"}
                      aria-controls="studio-side-panel-run"
                      tabIndex={studioRailMode === "run" ? 0 : -1}
                      className={studioRailMode === "run" ? "secondary-button active" : "secondary-button"}
                      type="button"
                      onClick={() => setStudioRailMode("run")}
                    >
                      Run
                    </button>
                    <button
                      id="studio-rail-tab-tools"
                      role="tab"
                      aria-selected={studioRailMode === "tools"}
                      aria-controls="studio-side-panel-tools"
                      tabIndex={studioRailMode === "tools" ? 0 : -1}
                      className={studioRailMode === "tools" ? "secondary-button active" : "secondary-button"}
                      type="button"
                      onClick={() => setStudioRailMode("tools")}
                    >
                      Tools
                    </button>
                  </div>
                ) : null}
                {(!showStudioDraftIde || studioRailMode === "inspect") ? (
                <section
                  id="studio-side-panel-inspect"
                  role={showStudioDraftIde ? "tabpanel" : undefined}
                  aria-labelledby={showStudioDraftIde ? "studio-rail-tab-inspect" : undefined}
                  className="surface-card section-stack"
                >
                  <div className="surface-header">
                    <div>
                      <strong>Context inspector</strong>
                      <p>
                        {inspectorMode === "workflow"
                          ? showStudioDraftIde
                            ? "Edit supported workflow settings without leaving the draft IDE."
                            : "Workflow config uses the same safe mutation action as the field form above."
                          : inspectorMode === "edge"
                            ? selectedEdge ? `Inspect ${selectedEdge.from} → ${selectedEdge.to}.` : "Select an edge from the canvas or list."
                            : selectedNode ? `Edit ${selectedNode.name} inline.` : "Select a node from the canvas to edit it."}
                      </p>
                    </div>
                    {inspectorMode === "workflow" ? <StatusPill value="workflow" /> : inspectorMode === "edge" ? <StatusPill value={selectedEdge?.read_only ? "read-only edge" : "edge"} /> : selectedNode ? <StatusPill value={selectedNode.kind || "node"} /> : null}
                  </div>
                  {inspectorMode === "workflow" ? (
                    <>
                      <dl className="context-list compact-context-list">
                        <div><dt>Workflow</dt><dd>{activeDraft?.draft_workflow_name || activeWorkflow?.name || "—"}</dd></div>
                        <div><dt>Entry</dt><dd>{activeGraph.entry || "—"}</dd></div>
                        <div><dt>Revision</dt><dd>{activeDraft?.revision ?? "—"}</dd></div>
                      </dl>
                      {showStudioDraftIde ? (
                        <div className="inspector-form-grid">
                          <div className="two-field-grid">
                            <label>
                              <span>Title</span>
                              <input value={coreForm.title || ""} onChange={(event) => setCoreForm((current) => ({ ...current, title: event.target.value }))} />
                            </label>
                            <label>
                              <span>Workflow kind</span>
                              <input value={coreForm.workflow_kind || ""} onChange={(event) => setCoreForm((current) => ({ ...current, workflow_kind: event.target.value }))} list="studio-workflow-kind-options" />
                            </label>
                          </div>
                          <datalist id="studio-workflow-kind-options">
                            {((authoringCatalog.data?.workflow_kind_options || []) as string[]).map((item) => <option key={item} value={item} />)}
                          </datalist>
                          <label>
                            <span>Description</span>
                            <textarea className="text-area-input" value={coreForm.description || ""} onChange={(event) => setCoreForm((current) => ({ ...current, description: event.target.value }))} />
                          </label>
                          <DensityDisclosure
                            className="studio-disclosure studio-inline-disclosure"
                            title="Runtime and run bounds"
                            detail="Keep provider, question limits, and model tuning nearby without crowding the default workflow overview."
                          >
                            <div className="two-field-grid">
                              <label>
                                <span>Runtime provider</span>
                                <select value={coreForm.runtime_provider || "mock"} onChange={(event) => setCoreForm((current) => ({ ...current, runtime_provider: event.target.value }))}>
                                  {((authoringCatalog.data?.runtime_provider_options || []) as string[]).map((item) => <option key={item} value={item}>{item}</option>)}
                                </select>
                              </label>
                              <label>
                                <span>Question limit</span>
                                <input type="number" min={1} max={25} value={coreForm.questions_limit || ""} onChange={(event) => setCoreForm((current) => ({ ...current, questions_limit: event.target.value }))} />
                              </label>
                            </div>
                            <div className="two-field-grid">
                              <label>
                                <span>Runtime model</span>
                                <input value={coreForm.runtime_model || ""} onChange={(event) => setCoreForm((current) => ({ ...current, runtime_model: event.target.value }))} placeholder="phi-4-mini" />
                              </label>
                              <label>
                                <span>Max tokens</span>
                                <input type="number" min={1} value={coreForm.runtime_max_tokens || ""} onChange={(event) => setCoreForm((current) => ({ ...current, runtime_max_tokens: event.target.value }))} />
                              </label>
                            </div>
                          </DensityDisclosure>
                          <div className="button-row">
                            <button className="primary-button" onClick={applyCoreFields} disabled={Boolean(busy)}>Apply workflow fields</button>
                          </div>
                        </div>
                      ) : (
                        <button className="secondary-button" onClick={() => document.getElementById("workflow-config-fields")?.scrollIntoView({ behavior: "smooth", block: "start" })}>Jump to workflow config</button>
                      )}
                    </>
                  ) : inspectorMode === "edge" ? (
                    selectedEdge ? (
                      <>
                        <dl className="context-list compact-context-list">
                          <div><dt>From</dt><dd>{selectedEdge.from || selectedEdge.source || "—"}</dd></div>
                          <div><dt>To</dt><dd>{selectedEdge.to || selectedEdge.target || "—"}</dd></div>
                          <div><dt>Kind</dt><dd>{selectedEdge.kind || "edge"}</dd></div>
                          <div><dt>Editable</dt><dd>{selectedEdge.read_only ? "No" : "Yes"}</dd></div>
                        </dl>
                        <button className="secondary-button" onClick={() => void removeEdge(String(selectedEdge.from), String(selectedEdge.to))} disabled={Boolean(busy) || Boolean(selectedEdge.read_only)}>Remove selected edge</button>
                      </>
                    ) : (
                      <EmptyState title="No edge selected" body="Pick an edge from the canvas curve or edge list to inspect it." />
                    )
                  ) : selectedNode ? (
                    <>
                      <dl className="context-list compact-context-list">
                        <div><dt>Implementation</dt><dd>{selectedNode.implementation || "—"}</dd></div>
                        <div><dt>Runtime</dt><dd>{selectedNode.runtime || "—"}</dd></div>
                        <div><dt>Entry</dt><dd>{selectedNode.is_entry ? "Yes" : "No"}</dd></div>
                      </dl>
                      <label>
                        <span>Description</span>
                        <textarea className="text-area-input" value={nodeForm.description || ""} onChange={(event) => setNodeForm((current) => ({ ...current, description: event.target.value }))} />
                      </label>
                      <label>
                        <span>Runtime label</span>
                        <input value={nodeForm.runtime || ""} onChange={(event) => setNodeForm((current) => ({ ...current, runtime: event.target.value }))} placeholder="Optional runtime tag" />
                      </label>
                      <label>
                        <span>Optional</span>
                        <select value={nodeForm.optional || "false"} onChange={(event) => setNodeForm((current) => ({ ...current, optional: event.target.value }))}>
                          <option value="false">false</option>
                          <option value="true">true</option>
                        </select>
                      </label>
                      {((selectedNode.aggregate_weights || []) as JsonObject[]).map((item) => {
                        const key = `weight:${String(item.name)}`;
                        return (
                          <label key={key}>
                            <span>{item.name} weight</span>
                            <input type="number" min={0} max={100} value={nodeForm[key] || ""} onChange={(event) => setNodeForm((current) => ({ ...current, [key]: event.target.value }))} />
                          </label>
                        );
                      })}
                      <div className="button-row">
                        <button className="primary-button" onClick={applyNodeUpdates} disabled={Boolean(busy)}>Apply node changes</button>
                        <button className="secondary-button" onClick={() => void setEntry(String(selectedNode.name))} disabled={Boolean(busy) || selectedNode.is_entry}>Set as entry</button>
                        <button className="secondary-button" onClick={() => setEdgeDraftFrom(String(selectedNode.name))} disabled={Boolean(busy)}>Start edge here</button>
                        <button className="secondary-button" onClick={removeSelectedNode} disabled={Boolean(busy)}>Remove node</button>
                      </div>
                    </>
                  ) : (
                      <EmptyState title="No node selected" body="Pick a node from the canvas to edit its supported fields." />
                    )}
                </section>
                ) : null}

                {showStudioDraftIde && studioRailMode === "run" ? (
                  <section
                    id="studio-side-panel-run"
                    role="tabpanel"
                    aria-labelledby="studio-rail-tab-run"
                    className="surface-card section-stack studio-publish-card"
                  >
                    <div className="surface-header">
                      <div>
                        <strong>Validate + run</strong>
                        <p>Use one control stack for validation, version snapshots, candidate runs, and compare handoff.</p>
                      </div>
                      <StatusPill value={validationPillValue} />
                    </div>
                    <Message tone={validationStatus.tone} title={validationStatus.title} body={validationStatus.body} />
                    {validationFixes.length ? (
                      <ul className="teaching-list">
                        {validationFixes.map((note) => <li key={note}>{note}</li>)}
                      </ul>
                    ) : null}
                    <section className="next-step-card">
                      <strong>{nextStep.title}</strong>
                      <p>{nextStep.detail}</p>
                    </section>
                    <div className="action-stack compact-action-stack">
                      <button className="secondary-button" onClick={createVersionSnapshotFromDraft} disabled={Boolean(busy)}>Save version snapshot</button>
                      <button className="secondary-button" onClick={validateDraft} disabled={Boolean(busy)}>Save + validate</button>
                      <button className="primary-button" disabled={Boolean(busy) || runDisabled} onClick={runDraft}>Run candidate</button>
                      {activeDraft?.last_run_id ? <button className="secondary-button" onClick={() => navigate(`/runs/${activeDraft.last_run_id}`)}>Inspect candidate</button> : null}
                      <button className="secondary-button" onClick={() => navigate("/versions")}>Open Versions</button>
                    </div>
                    {compareActions.length ? (
                      <div className="action-stack compact-action-stack">
                        {compareActions.slice(0, 2).map((action: JsonObject, index: number) => (
                          <button key={action.href || action.label || index} className={index === 0 ? "primary-button" : "secondary-button"} onClick={() => navigate(String(action.href || "/runs"))}>
                            {action.label}
                          </button>
                        ))}
                      </div>
                      ) : null}
                  </section>
                ) : null}

                {(!showStudioDraftIde || studioRailMode === "tools") ? (
                <section
                  id="studio-side-panel-tools"
                  role={showStudioDraftIde ? "tabpanel" : undefined}
                  aria-labelledby={showStudioDraftIde ? "studio-rail-tab-tools" : undefined}
                  className="section-stack"
                >
                <DensityDisclosure
                  className="surface-card section-stack studio-disclosure"
                  title="Add safe node"
                  detail="Open the explicit add-node form only when palette click or drag-drop is not enough."
                >
                  <label>
                    <span>Node name</span>
                    <input value={addNodeForm.node_name || ""} onChange={(event) => setAddNodeForm((current) => ({ ...current, node_name: event.target.value }))} placeholder="question_context_2" />
                  </label>
                  <label>
                    <span>Implementation</span>
                    <select value={addNodeForm.implementation || ""} onChange={(event) => setAddNodeForm((current) => ({ ...current, implementation: event.target.value }))}>
                      {nodeCatalog.map((item: JsonObject) => (
                        <option key={item.implementation} value={item.implementation}>{item.name} · {item.kind}</option>
                      ))}
                    </select>
                  </label>
                  <div className="two-field-grid">
                    <label>
                      <span>Incoming from</span>
                      <select value={addNodeForm.incoming_from || ""} onChange={(event) => setAddNodeForm((current) => ({ ...current, incoming_from: event.target.value }))}>
                        <option value="">None</option>
                        {graphTargets.map((target: JsonObject) => <option key={target.name} value={target.name}>{target.name}</option>)}
                      </select>
                    </label>
                    <label>
                      <span>Outgoing to</span>
                      <select value={addNodeForm.outgoing_to || ""} onChange={(event) => setAddNodeForm((current) => ({ ...current, outgoing_to: event.target.value }))}>
                        <option value="">None</option>
                        {graphTargets.map((target: JsonObject) => <option key={target.name} value={target.name}>{target.name}</option>)}
                      </select>
                    </label>
                  </div>
                  <label>
                    <span>Description</span>
                    <textarea className="text-area-input" value={addNodeForm.description || ""} onChange={(event) => setAddNodeForm((current) => ({ ...current, description: event.target.value }))} />
                  </label>
                  <div className="two-field-grid">
                    <label>
                      <span>Runtime label</span>
                      <input value={addNodeForm.runtime || ""} onChange={(event) => setAddNodeForm((current) => ({ ...current, runtime: event.target.value }))} placeholder="Optional runtime tag" />
                    </label>
                    <label>
                      <span>Optional</span>
                      <select value={addNodeForm.optional || "false"} onChange={(event) => setAddNodeForm((current) => ({ ...current, optional: event.target.value }))}>
                        <option value="false">false</option>
                        <option value="true">true</option>
                      </select>
                    </label>
                  </div>
                  <button className="primary-button" onClick={() => void addNode()} disabled={Boolean(busy) || !addNodeForm.node_name || !addNodeForm.implementation}>Add node</button>
                </DensityDisclosure>

                <DensityDisclosure
                  className="surface-card section-stack studio-disclosure"
                  title="Edges and graph context"
                  detail="Keep edge wiring, parallel groups, and conditional routes behind one secondary disclosure."
                >
                  <div className="two-field-grid">
                    <label>
                      <span>From</span>
                      <select value={addEdgeForm.from_node || ""} onChange={(event) => setAddEdgeForm((current) => ({ ...current, from_node: event.target.value }))}>
                        <option value="">Select</option>
                        {graphTargets.map((target: JsonObject) => <option key={target.name} value={target.name}>{target.name}</option>)}
                      </select>
                    </label>
                    <label>
                      <span>To</span>
                      <select value={addEdgeForm.to_node || ""} onChange={(event) => setAddEdgeForm((current) => ({ ...current, to_node: event.target.value }))}>
                        <option value="">Select</option>
                        {graphTargets.map((target: JsonObject) => <option key={target.name} value={target.name}>{target.name}</option>)}
                      </select>
                    </label>
                  </div>
                  <button className="primary-button" onClick={() => void addEdge()} disabled={Boolean(busy) || !addEdgeForm.from_node || !addEdgeForm.to_node}>Add edge</button>
                  <div className="edge-list">
                    {graphEdges.map((edge: JsonObject, index: number) => (
                      <div key={`${edge.from}-${edge.to}-${index}`} className={studioEdgeKey(edge) === selectedEdgeId ? "edge-row selected" : "edge-row"}>
                        <button
                          className="edge-row-button"
                          type="button"
                          aria-pressed={studioEdgeKey(edge) === selectedEdgeId}
                          onClick={() => selectEdgeInspector(edge)}
                        >
                          <span className="table-primary">{edge.from}</span>
                          <span className="table-secondary">{edge.to}</span>
                        </button>
                        <button className="secondary-button" onClick={() => void removeEdge(String(edge.from), String(edge.to))} disabled={Boolean(busy)}>Remove</button>
                      </div>
                    ))}
                  </div>
                  {(Object.keys(activeGraph.parallel_groups || {}).length || Object.keys(activeGraph.conditional_routes || {}).length) ? (
                    <div className="guidance-section minor-divider">
                      {Object.keys(activeGraph.parallel_groups || {}).length ? (
                        <div>
                          <strong>Parallel groups</strong>
                          <ul className="guidance-list compact-list">
                            {Object.entries(activeGraph.parallel_groups as JsonObject).map(([name, members]) => (
                              <li key={name}><strong>{name}</strong><span>{Array.isArray(members) ? members.join(", ") : ""}</span></li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                      {Object.keys(activeGraph.conditional_routes || {}).length ? (
                        <div>
                          <strong>Conditional routes</strong>
                          <ul className="guidance-list compact-list">
                            {Object.entries(activeGraph.conditional_routes as JsonObject).map(([name, route]) => (
                              <li key={name}><strong>{name}</strong><span>{JSON.stringify(route)}</span></li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </DensityDisclosure>
                </section>
                ) : null}
              </div>
            </>
          )}
        </section>
        ) : null}

        {showWorkbenchFieldSetup ? (
        <section className="panel">
          <div className="section-heading">
            <div>
              <span className="eyebrow">4. Save, validate + run</span>
              <h3>Save/validate inline, then run only when the authored draft is safe</h3>
            </div>
            <p className="section-copy">Studio mutations preview validation immediately; this save/validate action persists the reusable workflow before run readiness is unlocked.</p>
          </div>
          {!draftId ? (
            <EmptyState title="No draft to validate yet" body="Create or open a draft session first. Then this panel will keep validation, fixes, and run readiness together." />
          ) : (
            <>
              <Message tone={validationStatus.tone} title={validationStatus.title} body={validationStatus.body} />
              {validationFixes.length ? (
                <ul className="teaching-list">
                  {validationFixes.map((note) => <li key={note}>{note}</li>)}
                </ul>
              ) : null}
              <div className="button-row">
                <button className="primary-button" onClick={validateDraft} disabled={Boolean(busy)}>Save + validate draft</button>
                <button className="secondary-button" onClick={createVersionSnapshotFromDraft} disabled={Boolean(busy)}>Save version snapshot</button>
                <button className="primary-button" disabled={Boolean(busy) || runDisabled} onClick={runDraft}>Run candidate</button>
              </div>
            </>
          )}
        </section>
        ) : null}

        {showWorkbenchFieldSetup ? (
        <section className="panel">
          <div className="section-heading">
            <div>
              <span className="eyebrow">5. Compare + next step</span>
              <h3>Keep validate, run, and compare inside the same authoring loop</h3>
            </div>
            <p className="section-copy">Once the candidate finishes, compare it immediately or jump into the run detail from the same authoring surface.</p>
          </div>
          {activeDraft?.compare ? (
            <div className="compare-outcome">
              <Message tone="success" title={`Compare verdict: ${activeDraft.compare.verdict?.label || "ready"}`} body={activeDraft.compare.verdict?.summary || "Open the comparison to inspect detailed metric deltas."} />
              <div className="button-row">
                {(activeDraft.compare.next_actions || []).map((action: JsonObject, index: number) => (
                  <button key={action.href || action.label || index} className={index === 0 ? "primary-button" : "secondary-button"} onClick={() => navigate(action.href)}>
                    {action.label}
                  </button>
                ))}
              </div>
            </div>
          ) : activeDraft?.last_run_id ? (
            <Message tone="success" title="Candidate run completed" body="Inspect the candidate run now. Add a baseline if you want to compare it before deciding on the next edit." />
          ) : (
            <EmptyState title="No candidate run yet" body="Once validation passes and you run a candidate, this panel will explain whether to compare, iterate, or stop." />
          )}
        </section>
        ) : null}
      </section>
        {showWorkbenchSetupRail ? (
       <aside className="panel guidance-panel">
        <span className="eyebrow">Next step</span>
        <section className="next-step-card">
          <strong>{nextStep.title}</strong>
          <p>{nextStep.detail}</p>
        </section>
        <section className="guidance-section">
          <h3>Authoring contract</h3>
          <ul className="guidance-list">
            {safeEditLimitations.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </section>
        <section className="guidance-section">
          <h3>Supported safe edits</h3>
          <ul className="guidance-list compact-list">
            {safeEditSupport.map((item: JsonObject) => (
              <li key={item.key}>
                <strong>{item.label}</strong>
                <span>{item.detail}</span>
              </li>
            ))}
          </ul>
        </section>
        <section className="guidance-section">
          <h3>What stays authoritative</h3>
          <ul className="guidance-list">
            {sourceOfTruth.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </section>
      </aside>
      ) : null}
    </main>
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
}: {
  nodes: JsonObject[];
  edges: JsonObject[];
  positions: Record<string, { x: number; y: number }>;
  emptyState: { title: string; body: string };
  markerId: string;
  shellClassName?: string;
  minWidth: number;
  minHeight: number;
  widthPadding: number;
  heightPadding: number;
  onStageClick?: () => void;
  onShellDrop?: (implementation: string, position: { x: number; y: number }) => void;
  edgeClassName: (edge: JsonObject, index: number) => string;
  onEdgeClick?: (edge: JsonObject) => void;
  nodeClassName: (node: JsonObject) => string;
  onNodePointerDown?: (
    event: React.PointerEvent<HTMLButtonElement>,
    node: JsonObject,
    position: { x: number; y: number },
    point: { x: number; y: number }
  ) => void;
  onNodePointerMove?: (
    event: React.PointerEvent<HTMLButtonElement>,
    node: JsonObject,
    position: { x: number; y: number },
    point: { x: number; y: number },
    clampPosition: (x: number, y: number) => { x: number; y: number }
  ) => void;
  onNodePointerUp?: (
    event: React.PointerEvent<HTMLButtonElement>,
    node: JsonObject,
    position: { x: number; y: number }
  ) => void;
  onNodeClick?: (event: React.MouseEvent<HTMLButtonElement>, node: JsonObject) => void;
  renderNodeContents: (node: JsonObject) => React.ReactNode;
}): React.ReactElement {
  const shellRef = React.useRef<HTMLDivElement | null>(null);
  const stageRef = React.useRef<HTMLDivElement | null>(null);
  const [viewportSize, setViewportSize] = useState({ width: minWidth, height: minHeight });
  const measureViewport = () => {
    const shell = shellRef.current;
    if (!shell) return;
    const style = window.getComputedStyle(shell);
    const horizontalPadding = Number.parseFloat(style.paddingLeft || "0") + Number.parseFloat(style.paddingRight || "0");
    const verticalPadding = Number.parseFloat(style.paddingTop || "0") + Number.parseFloat(style.paddingBottom || "0");
    const next = {
      width: Math.max(minWidth, Math.floor(shell.clientWidth - horizontalPadding)),
      height: Math.max(minHeight, Math.floor(shell.clientHeight - verticalPadding)),
    };
    setViewportSize((current) => (current.width === next.width && current.height === next.height ? current : next));
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
  if (!nodes.length) {
    return <EmptyState title={emptyState.title} body={emptyState.body} />;
  }
  const contentWidth = Math.max(minWidth, ...nodes.map((node) => (positions[String(node.name)] || { x: Number(node.x || 0), y: Number(node.y || 0) }).x + widthPadding));
  const contentHeight = Math.max(minHeight, ...nodes.map((node) => (positions[String(node.name)] || { x: Number(node.x || 0), y: Number(node.y || 0) }).y + heightPadding));
  const width = Math.max(viewportSize.width, contentWidth);
  const height = Math.max(viewportSize.height, contentHeight);
  const contentOffsetX = Math.max(0, Math.floor((width - contentWidth) / 2));
  const contentOffsetY = Math.max(0, Math.floor((height - contentHeight) / 2));
  const relativePoint = (event: { clientX: number; clientY: number }) => {
    const rect = stageRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  };
  const graphPoint = (event: { clientX: number; clientY: number }) => {
    const point = relativePoint(event);
    return {
      x: point.x - contentOffsetX,
      y: point.y - contentOffsetY,
    };
  };
  const clampPosition = (x: number, y: number) => ({
    x: Math.max(0, Math.min(contentWidth - 180, Math.round(x))),
    y: Math.max(0, Math.min(contentHeight - 90, Math.round(y))),
  });
  return (
    <div
      ref={shellRef}
      className={shellClassName}
      onDragOver={(event) => {
        if (onShellDrop && Array.from(event.dataTransfer.types).includes("application/xrtm-node-implementation")) {
          event.preventDefault();
          event.dataTransfer.dropEffect = "copy";
        }
      }}
      onDrop={(event) => {
        if (!onShellDrop) return;
        const implementation = event.dataTransfer.getData("application/xrtm-node-implementation");
        if (!implementation) return;
        event.preventDefault();
        const point = graphPoint(event);
        onShellDrop(implementation, clampPosition(point.x - 82, point.y - 34));
      }}
    >
      <div
        ref={stageRef}
        className="workflow-canvas-stage"
        style={{ height: `${height}px`, width: `${width}px` }}
        onClick={(event) => {
          if (event.currentTarget === event.target) onStageClick?.();
        }}
      >
        <div
          className="workflow-canvas-content"
          style={{
            width: `${contentWidth}px`,
            height: `${contentHeight}px`,
            left: `${contentOffsetX}px`,
            top: `${contentOffsetY}px`,
          }}
        >
          <svg className="workflow-canvas-svg" viewBox={`0 0 ${contentWidth} ${contentHeight}`} preserveAspectRatio="xMinYMin meet" onClick={onStageClick}>
            <defs>
              <marker id={markerId} markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
                <path d="M0,0 L8,4 L0,8 z" fill="#91a5ca" />
              </marker>
            </defs>
            {edges.map((edge, index) => {
              const from = positions[String(edge.from || "")];
              const to = positions[String(edge.to || "")];
              if (!from || !to) return null;
              const x1 = from.x + 164;
              const y1 = from.y + 34;
              const x2 = to.x;
              const y2 = to.y + 34;
              const midX = (x1 + x2) / 2;
              const midY = (y1 + y2) / 2;
              return (
                <g key={`${edge.from}-${edge.to}-${index}`} className="workflow-canvas-edge-hit" onClick={(event) => { event.stopPropagation(); onEdgeClick?.(edge); }}>
                  <path className={edgeClassName(edge, index)} d={`M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`} markerEnd={`url(#${markerId})`} />
                  {edge.label ? <text className="workflow-canvas-label" x={midX} y={midY - 6}>{String(edge.label)}</text> : null}
                </g>
              );
            })}
          </svg>
          {nodes.map((node) => {
            const name = String(node.name);
            const position = positions[name] || { x: Number(node.x || 0), y: Number(node.y || 0) };
            return (
              <button
                key={name}
                type="button"
                className={nodeClassName(node)}
                style={{ left: `${position.x}px`, top: `${position.y}px` }}
                onPointerDown={(event) => onNodePointerDown?.(event, node, position, graphPoint(event))}
                onPointerMove={(event) => onNodePointerMove?.(event, node, position, graphPoint(event), clampPosition)}
                onPointerUp={(event) => onNodePointerUp?.(event, node, positions[name] || position)}
                onClick={(event) => {
                  event.stopPropagation();
                  onNodeClick?.(event, node);
                }}
              >
                {renderNodeContents(node)}
              </button>
            );
          })}
        </div>
      </div>
    </div>
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
  onCreateEdge,
}: {
  canvas: JsonObject | null;
  entry: string;
  selectedNodeName: string;
  selectedEdgeId: string;
  localPositions: Record<string, { x: number; y: number }>;
  edgeDraftFrom: string;
  onMoveNode: (name: string, position: { x: number; y: number }) => void;
  onMoveEnd: (name: string, position: { x: number; y: number }) => void;
  onSelectNode: (name: string) => void;
  onSelectEdge: (edge: JsonObject) => void;
  onSelectWorkflow: () => void;
  onAddNodeFromPalette: (implementation: string, position: { x: number; y: number }) => void;
  onCreateEdge: (from: string, to: string) => void;
}): React.ReactElement {
  const dragRef = React.useRef<{ nodeName: string; offsetX: number; offsetY: number; pointerId: number } | null>(null);
  const suppressClickRef = React.useRef(false);
  const nodes = ((canvas?.nodes || []) as JsonObject[]).filter((node) => typeof node?.name === "string");
  const edges = (canvas?.edges || []) as JsonObject[];
  const positions = Object.fromEntries(
    nodes.map((node) => [String(node.name), localPositions[String(node.name)] || { x: Number(node.x || 0), y: Number(node.y || 0) }])
  );
  return (
    <GraphCanvasBase
      nodes={nodes}
      edges={edges}
      positions={positions}
      emptyState={{ title: "No graph nodes yet", body: "Add a node or load another workflow to populate the visual graph surface." }}
      markerId="workflow-arrow"
      minWidth={680}
      minHeight={360}
      widthPadding={240}
      heightPadding={150}
      onStageClick={onSelectWorkflow}
      onShellDrop={onAddNodeFromPalette}
      edgeClassName={(edge) => `workflow-canvas-edge ${studioEdgeKey(edge) === selectedEdgeId ? "selected" : ""} ${edge.read_only ? "readonly" : ""}`}
      onEdgeClick={onSelectEdge}
      nodeClassName={(node) => {
        const name = String(node.name);
        return `workflow-canvas-node ${selectedNodeName === name ? "selected" : ""} ${entry === name ? "entry" : ""} ${edgeDraftFrom === name ? "edge-source" : ""}`;
      }}
      onNodePointerDown={(event, node, position, point) => {
        dragRef.current = { nodeName: String(node.name), offsetX: point.x - position.x, offsetY: point.y - position.y, pointerId: event.pointerId };
        suppressClickRef.current = false;
        event.currentTarget.setPointerCapture(event.pointerId);
      }}
      onNodePointerMove={(event, node, _position, point, clampPosition) => {
        const drag = dragRef.current;
        if (!drag || drag.nodeName !== String(node.name)) return;
        suppressClickRef.current = true;
        onMoveNode(String(node.name), clampPosition(point.x - drag.offsetX, point.y - drag.offsetY));
      }}
      onNodePointerUp={(event, node, position) => {
        if (dragRef.current?.pointerId === event.pointerId) {
          onMoveEnd(String(node.name), position);
          dragRef.current = null;
          event.currentTarget.releasePointerCapture(event.pointerId);
        }
      }}
      onNodeClick={(_event, node) => {
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
      }}
      renderNodeContents={(node) => (
        <>
          <strong>{String(node.name)}</strong>
          <span>{node.kind}</span>
          <StatusPill value={String(node.status || (entry === String(node.name) ? "entry" : "ready"))} />
        </>
      )}
    />
  );
}

function PlaygroundGraphTracePreview({
  canvas,
  traceItems,
  activeNodeId,
  onSelectNode,
}: {
  canvas: JsonObject | null;
  traceItems: JsonObject[];
  activeNodeId: string;
  onSelectNode: (nodeId: string) => void;
}): React.ReactElement {
  const nodes = ((canvas?.nodes || []) as JsonObject[]).filter((node) => typeof node?.name === "string");
  const edges = (canvas?.edges || []) as JsonObject[];
  const traceByNode = Object.fromEntries(traceItems.map((item: JsonObject) => [String(item.node_id), item]));
  const positions = Object.fromEntries(nodes.map((node) => [String(node.name), { x: Number(node.x || 0), y: Number(node.y || 0) }]));
  return (
    <GraphCanvasBase
      nodes={nodes}
      edges={edges}
      positions={positions}
      emptyState={{ title: "No graph preview", body: "This context did not expose canvas-ready graph nodes." }}
      markerId="playground-arrow"
      shellClassName="workflow-canvas-shell playground-trace-canvas"
      minWidth={680}
      minHeight={360}
      widthPadding={240}
      heightPadding={150}
      edgeClassName={(edge) => {
        const sourceTrace = traceByNode[String(edge.from || "")];
        const targetTrace = traceByNode[String(edge.to || "")];
        const traced = sourceTrace && targetTrace && Number(sourceTrace.order || 0) <= Number(targetTrace.order || 0);
        return `workflow-canvas-edge ${traced ? "executed" : ""}`;
      }}
      nodeClassName={(node) => {
        const trace = traceByNode[String(node.name)];
        const executed = Boolean(trace || node.executed);
        const active = activeNodeId === String(node.name);
        return `workflow-canvas-node playground-trace-node ${executed ? "executed" : "not-executed"} ${active ? "active" : ""} ${node.is_entry ? "entry" : ""}`;
      }}
      onNodeClick={(_event, node) => onSelectNode(String(node.name))}
      renderNodeContents={(node) => {
        const trace = traceByNode[String(node.name)];
        const executed = Boolean(trace || node.executed);
        return (
          <>
            <strong>{String(node.name)}</strong>
            <span>{node.kind || node.node_type || "node"}</span>
            <span className="trace-chip">{executed ? `#${formatValue(trace?.order || node.trace_order)}` : "Not run"}</span>
            <StatusPill value={String(trace?.status || node.status || (node.is_entry ? "entry" : "ready"))} />
          </>
        );
      }}
    />
  );
}

function normalizeText(value: string | undefined): string | null {
  const text = String(value || "").trim();
  return text ? text : null;
}

function parseBooleanString(value: string | undefined): boolean {
  return String(value || "false").toLowerCase() === "true";
}

function previewBatchRows(rowsText: string): Array<{ row_index: number; question: string; title: string }> {
  return String(rowsText || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      try {
        const payload = JSON.parse(line) as Record<string, unknown>;
        const question = String(payload.question || payload.text || payload.prompt || "");
        const title = String(payload.title || "");
        return { row_index: index, question: question || "[missing question]", title };
      } catch {
        return { row_index: index, question: line, title: "" };
      }
    });
}

function draftlessStepState(activeWorkflow: JsonObject | null): JsonObject[] {
  const source = activeWorkflow?.source || "builtin";
  const cloneDescription = source === "local" ? "Open a draft session for the local workflow." : "Create a draft from scratch, template, or clone before editing.";
  return [
    { key: "inspect", label: "Inspect", locked: false, description: "Review the workflow and choose a baseline run." },
    { key: "clone", label: "Create", locked: false, description: cloneDescription },
    { key: "edit", label: "Author", locked: true, description: "Locked until a draft session exists." },
    { key: "validate", label: "Validate", locked: true, description: "Locked until the authored draft can be checked inline." },
    { key: "run", label: "Run", locked: true, description: "Locked until validation passes." },
    { key: "compare", label: "Compare", locked: true, description: "Locked until a candidate run exists." },
    { key: "next-step", label: "Next step", locked: false, description: "The draft editor will explain what to do after each step." },
  ];
}

function decorateStepState(steps: JsonObject[], activeDraft: JsonObject | null, hasDraft: boolean): JsonObject[] {
  const rank: Record<string, number> = { inspect: 0, clone: 1, edit: 2, validate: 3, run: 4, compare: 5, "next-step": 6 };
  const currentKey = currentJourneyKey(activeDraft, hasDraft);
  return steps.map((step: JsonObject) => {
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

function currentJourneyKey(activeDraft: JsonObject | null, hasDraft: boolean): string {
  if (!hasDraft) return "clone";
  if (activeDraft?.compare) return "compare";
  if (activeDraft?.last_run_id) return "next-step";
  const validation = activeDraft?.validation;
  if (validation?.ok && !validation?.stale) return "run";
  if (validation && !validation.ok) return "edit";
  if (activeDraft?.status === "draft-dirty") return "validate";
  return "edit";
}

function stepBadgeLabel(step: JsonObject): string {
  if (step.state === "complete") return "Done";
  if (step.state === "current") return "Now";
  if (step.state === "locked") return "Locked";
  return "Next";
}

function buildActionErrorNotice(stage: string, error: unknown): { tone: string; title: string; body: string } {
  const message = error instanceof Error ? error.message : String(error);
  const hints: Record<string, string> = {
    clone: "Built-in workflows remain read-only until the draft creation step succeeds.",
    create: "Use one of the supported scratch, template, or clone modes to create a safe authored draft.",
    workflow: "Only the supported authored workflow fields can be changed from this surface.",
    node: "Stay inside the built-in safe node catalog and keep the graph connected when you change nodes.",
    edge: "Basic edge edits must keep the graph reachable and acyclic.",
    entry: "Choose an existing node or group as the workflow entry.",
    validate: "Fix the supported fields below, then validate again without losing the current draft context.",
    run: "The draft stays loaded. Re-validate the latest authored graph before you try another run.",
  };
  return {
    tone: "error",
    title: `Couldn't ${stage}`,
    body: `${message} ${hints[stage] || "Review the current step and try again."}`,
  };
}

function buildValidationStatus(activeDraft: JsonObject | null): { tone: string; title: string; body: string } {
  if (activeDraft?.preview_error) {
    return {
      tone: "warning",
      title: "Preview blocked",
      body: `${activeDraft.preview_error} Fix the supported fields below; your draft session remains intact.`,
    };
  }
  const validation = activeDraft?.validation;
  if (!validation) {
    return {
      tone: "warning",
      title: "Validate before run",
      body: "Validate inline before you run this draft. The run step stays locked until the latest validation passes.",
    };
  }
  if (validation.ok && validation.stale) {
    return {
      tone: "warning",
      title: "Validation is stale",
      body: "Newer edits changed the draft after the last passing validation. Validate once more before you run.",
    };
  }
  if (validation.ok) {
    return {
      tone: "success",
      title: "Validation passed",
      body: "The latest authored workflow is runnable. Next: run a candidate and compare it with the baseline.",
    };
  }
  return {
    tone: "warning",
    title: "Validation found issues",
    body: `${(validation.errors || []).join(" ")} Fix the supported fields below, then validate again.`,
  };
}

function buildValidationFixes(activeDraft: JsonObject | null): string[] {
  const rawErrors = [activeDraft?.preview_error, ...((activeDraft?.validation?.errors || []) as string[])].filter(Boolean) as string[];
  const notes = new Set<string>();
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

function buildDraftlessNextStep(activeWorkflow: JsonObject | null, latestRun: JsonObject | null): JsonObject {
  if (activeWorkflow?.source === "local") {
    return {
      key: "clone",
      title: "Open a draft session for the local workflow",
      detail: "Local workflows are reusable on disk, but the draft editor still uses a draft session so validation, run readiness, and resume state stay explicit.",
    };
  }
  if (latestRun?.run_id) {
    return {
      key: "inspect",
      title: "Inspect the latest run, then create a draft",
      detail: "Review the baseline context first, then create a local authored draft before making visual changes.",
    };
  }
  return {
    key: "clone",
    title: "Create a draft to begin",
    detail: "Choose a workflow from the catalog or starter modes, then create a local draft. Visual authoring unlocks after that step succeeds.",
  };
}

function defaultSourceOfTruth(): string[] {
  return [
    "Built-in workflows stay read-only until you clone them into a local workflow.",
    "Reusable local workflows remain JSON files on disk.",
    "Draft blueprint state, validation snapshots, and resume state live in SQLite until validate or run writes the local workflow file.",
  ];
}

function defaultAuthoringLimitations(): string[] {
  return [
    "Only shared safe-product workflow fields and graph mutations are exposed.",
    "Node implementations stay inside the built-in product workflow node catalog.",
    "Parallel-group and conditional-route editing stay read-only in this pass.",
    "API keys are not persisted as authored workflow fields from the WebUI.",
  ];
}

function formatRunContext(run: JsonObject | null): string {
  if (!run) return "—";
  const workflow = run.workflow?.title || run.workflow?.name;
  return [run.run_id, workflow, run.status].filter(Boolean).join(" · ");
}

function playgroundStepKey(step: JsonObject): string {
  return String(step.order || step.node_id || "step");
}

function SourceBadge({ source }: { source: string }): React.ReactElement {
  const normalized = String(source || "unknown").toLowerCase();
  const label = normalized === "builtin" ? "Built-in · read-only" : normalized === "local" ? "Local workflow" : source;
  return <span className={`source-pill ${normalized}`}>{label}</span>;
}

function RunLaunchResultCard({ result, navigate }: { result: JsonObject; navigate: (path: string) => void }): React.ReactElement {
  return (
    <section className="panel section-stack">
      <div className="section-header">
        <div>
          <h3>Latest launched run</h3>
          <p>Jump straight into detail, report, or compare while the context is fresh.</p>
        </div>
      </div>
      <div className="inline-action-card">
        <div>
          <strong>{result.run_id}</strong>
          <p className="helper-text">{result.command || "Run created"} · {result.provider || "provider-free"} · {result.status || "running"}</p>
        </div>
        <div className="button-row">
          <button className="primary-button" onClick={() => navigate(result.href)}>Inspect run</button>
          {result.report_href ? (
            <a className="secondary-link" href={result.report_href} target="_blank" rel="noreferrer">
              Open report
            </a>
          ) : null}
          {result.compare?.href ? (
            <button className="secondary-button" onClick={() => navigate(result.compare.href)}>
              Compare
            </button>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function RunCard({ run, onOpen }: { run: JsonObject; onOpen: () => void }): React.ReactElement {
  return (
    <section className="panel run-card">
      <div>
        <span className="eyebrow">Latest run</span>
        <h3>{run.workflow?.title || run.run_id}</h3>
        <p>{run.workflow?.name || run.provider}</p>
      </div>
      <div className="meta-row">
        <StatusPill value={run.status} />
        <span>{run.updated_at || "—"}</span>
      </div>
      <button className="primary-button" onClick={onOpen}>Inspect latest run</button>
    </section>
  );
}

function MetricCard({ label, value }: { label: string; value: any }): React.ReactElement {
  return (
    <article className="panel metric-card">
      <span className="eyebrow">{label}</span>
      <strong>{String(value ?? "—")}</strong>
    </article>
  );
}

function StatusPill({ value }: { value: string }): React.ReactElement {
  return <span className={`status-pill ${String(value || "unknown").replace(/[^a-z0-9-]/gi, "-").toLowerCase()}`}>{value || "unknown"}</span>;
}

function Message({ tone, title, body }: { tone: string; title: string; body: React.ReactNode }): React.ReactElement {
  return (
    <section className={`panel message ${tone}`}>
      <strong>{title}</strong>
      <p>{body}</p>
    </section>
  );
}

function LoadingCard({ label }: { label: string }): React.ReactElement {
  return (
    <section className="panel loading-card">
      <span className="spinner" />
      <span>{label}</span>
    </section>
  );
}

function EmptyState({ title, body }: { title: string; body: React.ReactNode }): React.ReactElement {
  return (
    <section className="empty-state">
      <strong>{title}</strong>
      <p>{body}</p>
    </section>
  );
}

function KeyValueGroup({ group }: { group: JsonObject }): React.ReactElement {
  return (
    <article className="info-card">
      <h4>{group.title}</h4>
      <dl className="key-value-list">
        {(group.items || []).map((item: JsonObject) => (
          <div key={item.label}>
            <dt>{item.label}</dt>
            <dd>{formatValue(item.value)}</dd>
          </div>
        ))}
      </dl>
    </article>
  );
}

function RunForecastTable({ rows, emptyState }: { rows: JsonObject[]; emptyState?: JsonObject }): React.ReactElement {
  if (!rows.length) {
    return <EmptyState title={emptyState?.title || "No forecasts"} body={emptyState?.body || "No forecast rows are available."} />;
  }
  return (
    <div className="table-wrap">
      <table className="data-table forecast-table">
        <thead>
          <tr>
            <th>Question</th>
            <th>Forecast</th>
            <th>Outcome</th>
            <th>Brier</th>
            <th>Resolution</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row: JsonObject) => (
            <tr key={row.question_id || row.question_title}>
              <td>
                <div className="table-primary">{row.question_title || row.question_id || "Untitled question"}</div>
                <div className="table-secondary">{row.question_id}</div>
                {row.question_text ? <div className="table-secondary clamp-2">{row.question_text}</div> : null}
              </td>
              <td>
                <div className="table-primary">{formatProbability(row.probability)}</div>
                <div className="table-secondary">Confidence: {formatValue(row.confidence)}</div>
                {row.tokens_used != null ? <div className="table-secondary">Tokens: {formatValue(row.tokens_used)}</div> : null}
              </td>
              <td>
                <div className="table-primary">{formatOutcome(row.outcome)}</div>
                <div className="table-secondary">Resolved: {formatBoolean(row.resolved)}</div>
              </td>
              <td>{formatValue(row.brier_score)}</td>
              <td>{formatTimestamp(row.resolution_date)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ArtifactList({ items }: { items: JsonObject[] }): React.ReactElement {
  if (!items.length) {
    return <EmptyState title="No artifact index" body="This run did not expose a file inventory." />;
  }
  return (
    <ul className="artifact-list">
      {items.map((item: JsonObject) => (
        <li key={item.name} className={item.available ? "" : "missing"}>
          <div>
            <strong>{item.label || item.name}</strong>
            <span>{item.path}</span>
          </div>
          <span className={`availability-pill ${item.available ? "available" : "missing"}`}>{item.available ? "Available" : "Missing"}</span>
        </li>
      ))}
    </ul>
  );
}

function ReportCard({ report }: { report?: JsonObject | null }): React.ReactElement {
  if (!report) {
    return <EmptyState title="No report metadata" body="This surface did not expose report availability information." />;
  }
  return (
    <section className={`report-card ${report.available ? "available" : "missing"}`}>
      <div>
        <strong>{report.label || "HTML report"}</strong>
        <p>{report.description || "No report description available."}</p>
      </div>
      {report.available ? (
        <a className="secondary-link" href={report.href} target="_blank" rel="noreferrer">Open report</a>
      ) : (
        <span className="availability-pill missing">Unavailable</span>
      )}
    </section>
  );
}

function CompareRunCard({ label, run }: { label: string; run?: JsonObject | null }): React.ReactElement {
  if (!run) {
    return (
      <article className="compare-run-card">
        <span className="eyebrow">{label}</span>
        <strong>Run unavailable</strong>
      </article>
    );
  }
  return (
    <article className="compare-run-card">
      <span className="eyebrow">{label}</span>
      <strong>{run.label || run.run_id}</strong>
      <div className="meta-row">
        <StatusPill value={run.status} />
        <span>{run.provider || "Unknown provider"}</span>
      </div>
      <span>{formatTimestamp(run.updated_at)}</span>
      <span>{run.report?.available ? "Report ready" : "No report"}</span>
    </article>
  );
}

function CompareQuestionTable({ rows }: { rows: JsonObject[] }): React.ReactElement {
  if (!rows.length) {
    return <EmptyState title="No shared question rows" body="Run another comparable candidate to unlock question-level review." />;
  }
  return (
    <div className="table-wrap">
      <table className="data-table forecast-table">
        <thead>
          <tr>
            <th>Question</th>
            <th>Coverage</th>
            <th>Baseline</th>
            <th>Candidate</th>
            <th>Brier shift</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row: JsonObject) => (
            <tr key={row.question_id} className={`tone-${row.tone || "neutral"}`}>
              <td>
                <div className="table-primary">{row.question_title || row.question_id}</div>
                {row.question_text ? <div className="table-secondary clamp-2">{row.question_text}</div> : null}
              </td>
              <td>{formatCoverage(row.status)}</td>
              <td>{formatProbability(row.baseline_probability)}</td>
              <td>{formatProbability(row.candidate_probability)}</td>
              <td>{formatSignedValue(row.brier_delta)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ArtifactPreview({ label, value }: { label: string; value: any }): React.ReactElement {
  return (
    <details className="artifact-preview">
      <summary>{label}</summary>
      {isEmptyValue(value) ? <p className="table-secondary">No structured payload available.</p> : <pre>{JSON.stringify(value, null, 2)}</pre>}
    </details>
  );
}

function formatValue(value: any): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") {
    if (Number.isInteger(value)) return value.toLocaleString();
    const digits = Math.abs(value) >= 1 ? 3 : 4;
    return value.toFixed(digits).replace(/0+$/, "").replace(/\.$/, "");
  }
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}T/.test(value)) return formatTimestamp(value);
  return String(value);
}

function formatProbability(value: any): string {
  if (typeof value !== "number") return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function formatSignedValue(value: any): string {
  if (typeof value !== "number") return "—";
  const formatted = formatValue(value);
  return value > 0 ? `+${formatted}` : formatted;
}

function formatBoolean(value: any): string {
  if (value === null || value === undefined) return "—";
  return value ? "Yes" : "No";
}

function formatOutcome(value: any): string {
  if (value === true) return "Yes";
  if (value === false) return "No";
  return "Unresolved";
}

function formatTimestamp(value: any): string {
  if (!value) return "—";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString();
}

function formatCoverage(value: any): string {
  if (!value) return "Unknown";
  return String(value).replace(/-/g, " ");
}

function isEmptyValue(value: any): boolean {
  if (value === null || value === undefined || value === "") return true;
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === "object") return Object.keys(value).length === 0;
  return false;
}

function defaultStepState(): JsonObject[] {
  return [
    { key: "inspect", label: "Inspect", locked: false, description: "Review the workflow and baseline context." },
    { key: "clone", label: "Create", locked: false, description: "Create or reopen a local draft session." },
    { key: "edit", label: "Author", locked: true, description: "Locked until a draft exists." },
    { key: "validate", label: "Validate", locked: true, description: "Validate inline before the run step unlocks." },
    { key: "run", label: "Run", locked: true, description: "Locked until validation passes." },
    { key: "compare", label: "Compare", locked: true, description: "Locked until a candidate run exists." },
    { key: "next-step", label: "Next step", locked: false, description: "The shell keeps your place in SQLite and explains what to do next." },
  ];
}

const root = document.getElementById("root");
if (root) {
  ReactDOMClient.createRoot(root).render(<App />);
}
