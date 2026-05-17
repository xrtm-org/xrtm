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

const ReactDOMClient = ReactDOM as typeof import("react-dom/client") & typeof import("react-dom");
const { useEffect, useMemo, useState } = React;
const bootstrap = window.__XRTM_WEBUI_BOOTSTRAP__ ?? {
  api_root: "/api",
  initial_path: window.location.pathname,
  initial_query: window.location.search.replace(/^\?/, ""),
  initial_error: null,
};

function currentRoute(): Route {
  return { path: window.location.pathname, search: window.location.search.replace(/^\?/, "") };
}

function routePath(route: Route): string {
  return route.search ? `${route.path}?${route.search}` : route.path;
}

function isNavItemActive(routePath: string, href: string): boolean {
  if (href === "/" || href === "/hub") return routePath === "/" || routePath === "/hub";
  if (href === "/start") return routePath === "/start" || /^\/workflows\/[^/]+$/.test(routePath);
  if (href === "/runs" || href === "/observatory") return routePath === "/runs" || routePath === "/observatory" || /^\/(?:runs|observatory)\/[^/]+(?:\/compare\/[^/]+)?$/.test(routePath);
  if (href === "/studio") return routePath === "/studio" || routePath === "/workbench" || /^\/workflows\/[^/]+$/.test(routePath);
  return routePath === href;
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

function App(): React.ReactElement {
  const [route, setRoute] = useState<Route>({ path: bootstrap.initial_path, search: bootstrap.initial_query });
  const [shellRefresh, setShellRefresh] = useState(0);
  const shell = useJsonResource(`${bootstrap.api_root}/app-shell`, [route.path, route.search, shellRefresh]);

  useEffect(() => {
    const onPopState = () => setRoute(currentRoute());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = (path: string) => {
    window.history.pushState({}, "", path);
    setRoute(currentRoute());
  };
  const refreshShell = () => setShellRefresh((value) => value + 1);

  const appChrome = (shell.data?.app || {}) as JsonObject;
  const nav = appChrome.nav ?? [
    { label: "Hub", href: "/hub" },
    { label: "Studio", href: "/studio" },
    { label: "Playground", href: "/playground" },
    { label: "Observatory", href: "/observatory" },
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

  let page: React.ReactElement;
  if (route.path === "/" || route.path === "/hub") {
    page = <HubPage shell={shell.data} navigate={navigate} />;
  } else if (route.path === "/start") {
    page = <StartPage shell={shell.data} navigate={navigate} onMutate={refreshShell} />;
  } else if (route.path === "/runs" || route.path === "/observatory") {
    page = <RunsPage route={route} navigate={navigate} />;
  } else if (route.path === "/playground") {
    page = <PlaygroundPage route={route} shell={shell.data} navigate={navigate} onMutate={refreshShell} />;
  } else if (route.path === "/operations") {
    page = <OperationsPage navigate={navigate} onMutate={refreshShell} />;
  } else if (route.path === "/advanced") {
    page = <AdvancedPage />;
  } else if (route.path === "/studio" || route.path === "/workbench") {
    page = <WorkbenchPage route={route} shell={shell.data} navigate={navigate} onMutate={refreshShell} />;
  } else if (/^\/(?:runs|observatory)\/[^/]+\/compare\/[^/]+$/.test(route.path)) {
    const match = route.path.match(/^\/(?:runs|observatory)\/([^/]+)\/compare\/([^/]+)$/)!;
    page = <ComparePage candidateRunId={match[1]} baselineRunId={match[2]} navigate={navigate} />;
  } else if (/^\/workflows\/[^/]+$/.test(route.path)) {
    page = <WorkflowDetailPage workflowName={decodeURIComponent(route.path.split("/")[2])} navigate={navigate} onMutate={refreshShell} />;
  } else if (/^\/(?:runs|observatory)\/[^/]+$/.test(route.path)) {
    page = <RunDetailPage runId={route.path.split("/")[2]} navigate={navigate} onMutate={refreshShell} />;
  } else {
    page = <WorkbenchPage route={route} shell={shell.data} navigate={navigate} onMutate={refreshShell} />;
  }

  return (
    <div className="app-shell">
      <section className="panel shell-chrome">
        <header className="topbar">
          <div className="shell-copy-stack">
            <div className="title-row">
              <span className="eyebrow">{String(appChrome.name || "XRTM WebUI")}</span>
              {shell.data?.app?.version ? <span className="version-pill">v{String(shell.data.app.version)}</span> : null}
            </div>
            <h1>{String(appChrome.subtitle || "Local forecasting cockpit")}</h1>
            <p className="shell-copy">
              {String(appChrome.summary || "File-backed runs, local workflows, and resumable SQLite state in one muted local shell.")}
            </p>
            <div className="meta-row shell-trust-row">
              {trustCues.map((cue) => (
                <span key={cue} className="shell-trust-pill">{cue}</span>
              ))}
            </div>
          </div>
          <div className="shell-nav-stack">
            <div className="title-row">
              <span className="eyebrow">Primary lanes</span>
            </div>
            <nav className="topnav" aria-label="Primary">
              {nav.map((item: JsonObject) => {
                const active = isNavItemActive(route.path, String(item.href || "/"));
                return (
                  <a
                    key={item.href}
                    className={active ? "nav-link active" : "nav-link"}
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    onClick={(event) => {
                      event.preventDefault();
                      navigate(item.href);
                    }}
                  >
                    {item.label}
                  </a>
                );
              })}
            </nav>
          </div>
        </header>
        {shell.data ? (
          <section className="environment-strip" aria-label="Environment status">
            {environmentCards.map((card) => (
              <article key={String(card.key || card.label)} className="environment-card">
                <div className="environment-card-head">
                  <strong>{card.label}</strong>
                  {card.status ? <StatusPill value={String(card.status)} /> : null}
                </div>
                <span className="environment-card-value" title={String(card.value || "—")}>{card.value || "—"}</span>
                {card.detail ? <span className="environment-card-detail" title={String(card.detail)}>{card.detail}</span> : null}
              </article>
            ))}
          </section>
        ) : null}
      </section>
      {bootstrap.initial_error ? <Message tone="error" title="Initial error" body={bootstrap.initial_error} /> : null}
      {shell.error ? <Message tone="error" title="App shell error" body={shell.error} /> : null}
      {shell.loading && !shell.data ? <LoadingCard label="Loading app shell" /> : null}
      <div className="page-stack">{page}</div>
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
  const nextActions = (hub.next_actions || []) as JsonObject[];
  const counts = (hub.counts || shell?.overview?.counts || {}) as JsonObject;
  const latestRun = (hub.latest_run || shell?.overview?.latest_run) as JsonObject | null;
  const resumeTarget = (hub.resume_target || shell?.overview?.resume_target || {}) as JsonObject;

  return (
    <main className="page-grid">
      <section className="panel hero-panel">
        <span className="eyebrow">{hero.eyebrow || "Hub"}</span>
        <h2>{hero.title || "Local-first Hub"}</h2>
        <p>{hero.summary || "Start from a template, run locally, and inspect file-backed results without login or account setup."}</p>
        <div className="button-row">
          <button className="primary-button" onClick={() => navigate(String(doors[0]?.primary_cta?.href || "/playground"))}>
            {String(doors[0]?.primary_cta?.label || "Open Playground")}
          </button>
          <button className="secondary-button" onClick={() => navigate(String(doors[1]?.primary_cta?.href || "/studio"))}>
            {String(doors[1]?.primary_cta?.label || "Open Studio")}
          </button>
          {resumeTarget.href ? (
            <button className="secondary-button" onClick={() => navigate(String(resumeTarget.href))}>
              {String(resumeTarget.label || "Resume")}
            </button>
          ) : null}
        </div>
      </section>

      <section className="stats-grid">
        <MetricCard label="Indexed runs" value={counts.runs ?? 0} />
        <MetricCard label="Workflows" value={counts.workflows ?? 0} />
        <MetricCard label="Starter templates" value={counts.templates ?? templates.length} />
        <MetricCard label="Resume lane" value={resumeTarget.kind || "hub"} />
      </section>

      <section className="split-grid">
        {doors.map((door) => (
          <article key={String(door.key || door.label)} className="panel section-stack">
            <div className="surface-header">
              <div>
                <span className="eyebrow">{door.label}</span>
                <h3>{door.title}</h3>
              </div>
              <StatusPill value={String(door.status || "local")} />
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
      </section>

      <section className="split-grid">
        <section className="panel section-stack" id="workflow-config-fields">
          <div className="section-header">
            <div>
              <span className="eyebrow">Templates</span>
              <h3>Starter gallery</h3>
              <p>Template cards reuse the existing workflow authoring catalog and open local-first routes.</p>
            </div>
          </div>
          <div className="workflow-list workflow-catalog">
            {templates.map((template) => (
              <article key={String(template.template_id)} className="workflow-tile">
                <div className="workflow-tile-head">
                  <strong>{template.title}</strong>
                  <StatusPill value={String(template.workflow_kind || "workflow")} />
                </div>
                <span className="workflow-note">{template.description}</span>
                <div className="meta-row">
                  {((template.tags || []) as string[]).slice(0, 3).map((tag) => <span key={tag}>{tag}</span>)}
                </div>
                <div className="button-row">
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
          {!templates.length ? <EmptyState title="No starter templates found" body="The Hub could not load starter templates from the authoring catalog." /> : null}
        </section>

        <section className="panel section-stack">
          <div className="section-header">
            <div>
              <span className="eyebrow">Workflow catalog</span>
              <h3>Existing workflows</h3>
              <p>Open a workflow in Playground for one-question exploration or Studio to inspect/create a local draft.</p>
            </div>
          </div>
          <div className="workflow-list workflow-catalog">
            {workflows.map((workflow) => (
              <article key={String(workflow.name)} className="workflow-tile">
                <div className="workflow-tile-head">
                  <strong>{workflow.title || workflow.name}</strong>
                  <SourceBadge source={String(workflow.source || "builtin")} />
                </div>
                <span>{workflow.name}</span>
                <span className="workflow-note">{workflow.description || "Reusable workflow from the registry."}</span>
                <dl className="context-list">
                  <div><dt>Runtime</dt><dd>{workflow.runtime_provider || "mock"}</dd></div>
                  <div><dt>Questions</dt><dd>{formatValue(workflow.question_limit)}</dd></div>
                </dl>
                <div className="button-row">
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
          {!workflows.length ? <EmptyState title="No workflows indexed" body="Refresh the local workflow registry or create a draft in Studio." /> : null}
        </section>
      </section>

      <section className="split-grid">
        <section className="panel section-stack">
          <div className="section-header">
            <div>
              <span className="eyebrow">Recent activity</span>
              <h3>Latest local run</h3>
            </div>
          </div>
          {latestRun ? (
            <RunCard run={latestRun} onOpen={() => navigate(`/runs/${latestRun.run_id}`)} />
          ) : (
            <EmptyState title="No runs yet" body="Open Playground or the first-success quickstart to create a local run history entry." />
          )}
        </section>

        <section className="panel section-stack">
          <div className="section-header">
            <div>
              <span className="eyebrow">Local readiness</span>
              <h3>Status without account assumptions</h3>
            </div>
          </div>
          <div className="card-grid">
            {readiness.map((item) => (
              <article key={String(item.key || item.label)} className="info-card">
                <div className="surface-header">
                  <strong>{item.label}</strong>
                  <StatusPill value={String(item.status || "ready")} />
                </div>
                <p className="helper-text">{item.value}</p>
                <span className="workflow-note">{item.detail}</span>
              </article>
            ))}
          </div>
          <div className="action-list">
            {nextActions.map((action) => (
              <div key={String(action.label)} className="inline-action-card">
                <div>
                  <strong>{action.label}</strong>
                  <p className="helper-text">{action.description}</p>
                </div>
                <button className="secondary-button" onClick={() => navigate(String(action.href))}>Open</button>
              </div>
            ))}
          </div>
        </section>
      </section>
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

  useEffect(() => {
    const items = (runs.data?.items || []) as JsonObject[];
    if (!selectedArtifactRun && items.length) {
      setSelectedArtifactRun(String(items[0].run_id || ""));
    }
  }, [selectedArtifactRun, runs.data]);

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
          limit: template === "starter" ? undefined : Number(profileLimit),
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
        body: JSON.stringify({ limit: Number(profileLimit), provider: profileProvider }),
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
        body: JSON.stringify({ keep: Number(cleanupKeep) }),
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
        body: JSON.stringify({ keep: Number(cleanupKeep), confirm: "delete" }),
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
    <main className="page-grid">
      <section className="panel hero-panel">
        <span className="eyebrow">Operations</span>
        <h2>Operate profiles, monitors, and artifact retention locally</h2>
        <p>These controls cover the day-to-day operator loop without asking you to remember CLI flags.</p>
      </section>
      {notice ? <Message tone={notice.tone} title={notice.title} body={notice.body} /> : null}

      <div className="split-grid">
        <section className="panel section-stack">
          <div className="section-header">
            <div>
              <h3>Profiles</h3>
              <p>Create repeatable local run presets, then launch them from the same page.</p>
            </div>
          </div>
          <div className="form-grid">
            <label>
              <span>Name</span>
              <input value={profileName} onChange={(event) => setProfileName(event.target.value)} />
            </label>
            <div className="two-field-grid">
              <label>
                <span>Provider</span>
                <select value={profileProvider} onChange={(event) => setProfileProvider(event.target.value)}>
                  <option value="mock">Provider-free baseline</option>
                  <option value="local-llm">Local OpenAI-compatible endpoint</option>
                </select>
              </label>
              <label>
                <span>Question limit</span>
                <input value={profileLimit} onChange={(event) => setProfileLimit(event.target.value)} />
              </label>
            </div>
            <div className="button-row">
              <button className="primary-button" onClick={() => void createProfile("custom")} disabled={Boolean(busy)}>
                Save profile
              </button>
              <button className="secondary-button" onClick={() => void createProfile("starter")} disabled={Boolean(busy)}>
                Save starter profile
              </button>
            </div>
          </div>
          <div className="action-list">
            {(profiles.data?.items || []).map((profile: JsonObject) => (
              <div key={profile.name} className="inline-action-card">
                <div>
                  <strong>{profile.name}</strong>
                  <p className="helper-text">{profile.provider} · {profile.limit} questions</p>
                </div>
                <div className="button-row">
                  <button className="secondary-button" onClick={() => setSelectedProfile(profile.name)}>Show</button>
                  <button className="secondary-button" onClick={() => void runProfile(profile.name)}>Run</button>
                </div>
              </div>
            ))}
          </div>
          {profileDetail.data?.profile ? (
            <article className="info-card">
              <h4>Selected profile</h4>
              <dl className="context-list">
                <div>
                  <dt>Provider</dt>
                  <dd>{profileDetail.data.profile.provider}</dd>
                </div>
                <div>
                  <dt>Limit</dt>
                  <dd>{profileDetail.data.profile.limit}</dd>
                </div>
                <div>
                  <dt>Runs dir</dt>
                  <dd>{profileDetail.data.profile.runs_dir}</dd>
                </div>
              </dl>
            </article>
          ) : null}
        </section>

        <section className="panel section-stack">
          <div className="section-header">
            <div>
              <h3>Monitors</h3>
              <p>Start a monitor, run a cycle, and manage its lifecycle from one place.</p>
            </div>
          </div>
          <div className="button-row">
            <button className="primary-button" onClick={() => void createMonitor()} disabled={Boolean(busy)}>
              Start monitor
            </button>
          </div>
          <div className="action-list">
            {(monitors.data?.items || []).map((monitor: JsonObject) => (
              <div key={monitor.run_id} className="inline-action-card">
                <div>
                  <strong>{monitor.run_id}</strong>
                  <p className="helper-text">{monitor.status} · {monitor.provider || "provider-free"}</p>
                </div>
                <div className="button-row">
                  <button className="secondary-button" onClick={() => setSelectedMonitor(monitor.run_id)}>Show</button>
                  <button className="secondary-button" onClick={() => void mutateMonitor(monitor.run_id, "run-once")}>Run once</button>
                  <button className="secondary-button" onClick={() => void mutateMonitor(monitor.run_id, "pause")}>Pause</button>
                  <button className="secondary-button" onClick={() => void mutateMonitor(monitor.run_id, "resume")}>Resume</button>
                  <button className="secondary-button" onClick={() => void mutateMonitor(monitor.run_id, "halt")}>Halt</button>
                </div>
              </div>
            ))}
          </div>
          {monitorDetail.data?.monitor ? (
            <article className="info-card">
              <h4>Selected monitor</h4>
              <dl className="context-list">
                <div>
                  <dt>Status</dt>
                  <dd>{monitorDetail.data.monitor.status}</dd>
                </div>
                <div>
                  <dt>Cycles</dt>
                  <dd>{monitorDetail.data.monitor.cycles}</dd>
                </div>
                <div>
                  <dt>Watches</dt>
                  <dd>{(monitorDetail.data.monitor.watches || []).length}</dd>
                </div>
              </dl>
            </article>
          ) : null}
        </section>
      </div>

      <section className="panel section-stack">
        <div className="section-header">
          <div>
            <h3>Artifacts and retention</h3>
            <p>Inspect artifact inventory for any run, preview cleanup, then confirm deletion explicitly.</p>
          </div>
        </div>
        <div className="three-column-grid">
          <section className="section-stack">
            <label>
              <span>Run</span>
              <select value={selectedArtifactRun} onChange={(event) => setSelectedArtifactRun(event.target.value)}>
                {(runs.data?.items || []).map((run: JsonObject) => (
                  <option key={run.run_id} value={run.run_id}>
                    {run.run_id}
                  </option>
                ))}
              </select>
            </label>
            {artifactDetail.data ? (
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
            ) : null}
          </section>
          <section className="section-stack">
            <label>
              <span>Keep newest run directories</span>
              <input value={cleanupKeep} onChange={(event) => setCleanupKeep(event.target.value)} />
            </label>
            <div className="button-row">
              <button className="secondary-button" onClick={() => void previewCleanup()} disabled={Boolean(busy)}>
                Preview cleanup
              </button>
              <button className="primary-button" onClick={() => void runCleanup()} disabled={Boolean(busy)}>
                Delete previewed runs
              </button>
            </div>
          </section>
          <section className="section-stack">
            {cleanupPreview ? (
              <article className="info-card">
                <h4>Cleanup preview</h4>
                <p className="helper-text">{cleanupPreview.count || 0} run directories would be removed while keeping the newest {cleanupPreview.keep}.</p>
                <ul className="guidance-list compact-list">
                  {(cleanupPreview.items || []).map((item: JsonObject) => (
                    <li key={item.run_id}>{item.run_id}</li>
                  ))}
                </ul>
              </article>
            ) : (
              <EmptyState title="No cleanup preview yet" body="Preview retention first so deletion stays explicit." />
            )}
          </section>
        </div>
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
    },
    {
      title: "Benchmark and stress",
      status: "advanced",
      body: "Benchmark compare, cache, and stress flows need heavier validation and should not be mistaken for first-success paths.",
    },
    {
      title: "Performance and competition",
      status: "experimental",
      body: "Performance budgets and competition dry-runs are visible here so advanced users can see the lane without overselling it to newcomers.",
    },
  ];

  return (
    <main className="page-grid">
      <section className="panel hero-panel">
        <span className="eyebrow">Advanced</span>
        <h2>Visible advanced lanes with honest status labels</h2>
        <p>The product should not hide advanced capabilities, but it also should not present them as newcomer defaults.</p>
      </section>
      <section className="card-grid">
        {cards.map((card) => (
          <article key={card.title} className="info-card">
            <div className="surface-header">
              <strong>{card.title}</strong>
              <StatusPill value={card.status} />
            </div>
            <p className="helper-text">{card.body}</p>
          </article>
        ))}
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

  useEffect(() => {
    setQuery(params.get("q") || "");
    setStatus(params.get("status") || "");
    setProvider(params.get("provider") || "");
  }, [params]);

  return (
    <main className="page-grid">
      <section className="panel hero-panel page-lead">
        <span className="eyebrow">Observatory</span>
        <h2>{resource.data?.surface?.title || "Observatory run inspector"}</h2>
        <p>{resource.data?.surface?.summary || "Filter file-backed run history, drill into results, and continue through reports, exports, and comparisons."}</p>
        <form
          className="filter-row"
          onSubmit={(event) => {
            event.preventDefault();
            const next = new URLSearchParams();
            if (query) next.set("q", query);
            if (status) next.set("status", status);
            if (provider) next.set("provider", provider);
            navigate(next.toString() ? `/runs?${next.toString()}` : "/runs");
          }}
        >
          <input placeholder="Search runs or workflow names" value={query} onChange={(event) => setQuery(event.target.value)} />
          <input placeholder="Status" value={status} onChange={(event) => setStatus(event.target.value)} />
          <input placeholder="Provider" value={provider} onChange={(event) => setProvider(event.target.value)} />
          <button className="secondary-button" type="submit">Filter</button>
        </form>
      </section>
      {(resource.data?.summary_cards || []).length ? (
        <section className="stats-grid">
          {(resource.data?.summary_cards || []).map((card: JsonObject) => <MetricCard key={card.label} label={card.label} value={card.value} />)}
        </section>
      ) : null}
      {resource.error ? <Message tone="error" title="Runs unavailable" body={resource.error} /> : null}
      {resource.loading ? <LoadingCard label="Loading runs" /> : null}
      <section className="panel">
        <table className="data-table">
          <thead>
            <tr>
              <th>Run</th>
              <th>Workflow</th>
              <th>Status</th>
              <th>Provider</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {(resource.data?.items || []).map((run: JsonObject) => (
              <tr key={run.run_id}>
                <td><a href={`/runs/${run.run_id}`} onClick={(event) => { event.preventDefault(); navigate(`/runs/${run.run_id}`); }}>{run.run_id}</a></td>
                <td>
                  <div className="table-primary">{run.observatory?.label || run.workflow?.title || run.workflow?.name || "Unknown workflow"}</div>
                  <div className="table-secondary">{run.observatory?.summary || run.workflow?.name || "—"}</div>
                </td>
                <td><StatusPill value={run.status} /></td>
                <td>{run.provider}</td>
                <td>{run.updated_at || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!resource.loading && !(resource.data?.items || []).length ? (
          <EmptyState
            title={resource.data?.empty_state?.title || "No runs match the current filter"}
            body={resource.data?.empty_state?.body || "Try clearing filters or running a workflow from the workbench."}
          />
        ) : null}
      </section>
    </main>
  );
}

function RunDetailPage({
  runId,
  navigate,
  onMutate,
}: {
  runId: string;
  navigate: (path: string) => void;
  onMutate: () => void;
}): React.ReactElement {
  const resource = useJsonResource(`${bootstrap.api_root}/runs/${runId}`, [runId]);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: string; title: string; body: string } | null>(null);

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
          <button className="primary-button" onClick={() => navigate(run.observatory?.runs_href || "/runs")}>Back to Observatory</button>
          {run.recommended_compare ? (
            <button className="secondary-button" onClick={() => navigate(run.recommended_compare.href)}>
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
                <button key={action.label} className="secondary-button action-button" onClick={() => navigate(action.href)}>
                  {action.label}
                </button>
              ))}
            </div>
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
                  <button key={item.run_id} className="secondary-button action-button" onClick={() => navigate(item.href)}>
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

function ComparePage({ candidateRunId, baselineRunId, navigate }: { candidateRunId: string; baselineRunId: string; navigate: (path: string) => void }): React.ReactElement {
  const resource = useJsonResource(`${bootstrap.api_root}/runs/${candidateRunId}/compare/${baselineRunId}`, [candidateRunId, baselineRunId]);
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
          <button className="secondary-button" onClick={() => navigate(`/runs/${candidateRunId}`)}>Inspect candidate run</button>
          <button className="secondary-button" onClick={() => navigate(`/runs/${baselineRunId}`)}>Inspect baseline run</button>
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
                <button key={action.label} className="secondary-button action-button" onClick={() => navigate(action.href)}>
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
  const traceByNodeId = useMemo(() => Object.fromEntries(orderedTrace.map((item: JsonObject) => [String(item.node_id), item])), [orderedTrace]);
  const graphTraceArtifact = (lastResult?.graph_trace_artifact || {}) as JsonObject;
  const readyToRun = Boolean(questionPrompt.trim() && (contextType === "workflow" ? workflowName : templateId));
  const latestRun = shell?.overview?.latest_run as JsonObject | null;

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

      <section className="panel hero-panel playground-hero">
        <span className="eyebrow">Playground</span>
        <h2>Run one bounded exploratory question without opening the workbench canvas</h2>
        <p>
          Choose a workflow or starter template, ask one custom question, then inspect ordered step outputs from the shared sandbox backend.
          This surface is for exploratory execution only; safe authoring still lives in the workbench.
        </p>
        <div className="meta-row">
          <span>{lastResult?.labeling?.display_label || "Exploratory playground session"}</span>
          <StatusPill value={String(lastResult?.run?.status || session?.status || "playground-ready")} />
          <span>{contextPreview?.title || contextPreview?.reference_name || "Choose a context"}</span>
        </div>
        <div className="button-row">
          <button className="primary-button" onClick={runPlayground} disabled={Boolean(busy) || !readyToRun}>
            {busy === "Running playground session" ? busy : "Run exploratory session"}
          </button>
          <button className="secondary-button" onClick={persistPlaygroundState} disabled={Boolean(busy)}>
            {busy === "Updating playground state" ? busy : "Update playground state"}
          </button>
          {lastResult?.run_id ? (
            <button className="secondary-button" onClick={() => navigate(`/runs/${lastResult.run_id}`)}>
              Inspect full run
            </button>
          ) : latestRun?.run_id ? (
            <button className="secondary-button" onClick={() => navigate(`/runs/${latestRun.run_id}`)}>
              Inspect latest run
            </button>
          ) : null}
          <button className="secondary-button" onClick={() => navigate("/workbench")}>Open workbench</button>
        </div>
      </section>

      <section className="playground-grid">
        <section className="panel section-stack">
          <div className="section-heading">
            <div>
              <span className="eyebrow">1. Context</span>
              <h3>Choose workflow or starter template</h3>
            </div>
            <p className="section-copy">The playground reuses the same workflow registry and starter templates as the shared authoring stack.</p>
          </div>
          <div className="creation-mode-row">
            {[
              { key: "workflow", label: "Workflow", detail: "Reuse a saved workflow directly." },
              { key: "template", label: "Template", detail: "Start from a starter template without opening the workbench." },
            ].map((item) => (
              <button
                key={item.key}
                type="button"
                className={contextType === item.key ? "workflow-tile active" : "workflow-tile"}
                onClick={() => setContextType(item.key)}
              >
                <strong>{item.label}</strong>
                <span className="workflow-note">{item.detail}</span>
              </button>
            ))}
          </div>
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
              <span>Starter template</span>
              <select value={templateId} onChange={(event) => setTemplateId(event.target.value)}>
                {templates.map((item: JsonObject) => (
                  <option key={item.template_id} value={item.template_id}>{item.title}</option>
                ))}
              </select>
            </label>
          )}
        </section>

        <section className="panel section-stack">
          <div className="section-heading">
            <div>
              <span className="eyebrow">2. Question</span>
              <h3>Enter one custom question</h3>
            </div>
            <p className="section-copy">Keep the loop bounded: one custom exploratory question only in this WebUI pass.</p>
          </div>
          <label>
            <span>Question prompt</span>
            <textarea className="text-area-input" value={questionPrompt} onChange={(event) => setQuestionPrompt(event.target.value)} placeholder="Will the exploratory workflow produce a useful answer for this question?" />
          </label>
          <div className="two-field-grid">
            <label>
              <span>Optional title</span>
              <input value={questionTitle} onChange={(event) => setQuestionTitle(event.target.value)} placeholder="Auto-derived from the prompt when blank" />
            </label>
            <label>
              <span>Optional resolution criteria</span>
              <input value={resolutionCriteria} onChange={(event) => setResolutionCriteria(event.target.value)} placeholder="Short read-only context for later inspection" />
            </label>
          </div>
        </section>
      </section>

      <section className="playground-grid">
        <section className="panel section-stack">
          <div className="section-heading">
            <div>
              <span className="eyebrow">3. Preview</span>
              <h3>Selected playground context</h3>
            </div>
          </div>
          {resource.data?.context_error ? (
            <Message tone="error" title="Context unavailable" body={resource.data.context_error} />
          ) : contextPreview ? (
            <>
              <div className="surface-card">
                <div className="surface-header">
                  <div>
                    <strong>{contextPreview.title || contextPreview.reference_name}</strong>
                    <p>{contextPreview.description || "No context description available."}</p>
                  </div>
                  <span className="source-pill local">{contextPreview.context_type}</span>
                </div>
                <dl className="context-list">
                  <div><dt>Reference</dt><dd>{contextPreview.reference_name}</dd></div>
                  <div><dt>Runtime</dt><dd>{contextPreview.runtime?.provider || "mock"}</dd></div>
                  <div><dt>Question limit</dt><dd>{formatValue(contextPreview.questions_limit)}</dd></div>
                  <div><dt>Entry node</dt><dd>{contextPreview.entry || "—"}</dd></div>
                </dl>
              </div>
              <section className="guidance-section">
                <h3>Graph node identity</h3>
                <PlaygroundGraphTracePreview
                  canvas={(contextPreview.canvas || {}) as JsonObject}
                  traceItems={[]}
                  activeNodeId=""
                  onSelectNode={() => undefined}
                />
              </section>
              <section className="guidance-section">
                <h3>Playground contract</h3>
                <ul className="guidance-list">
                  {((resource.data?.guidance?.limitations || []) as string[]).map((item) => <li key={item}>{item}</li>)}
                </ul>
              </section>
            </>
          ) : (
            <EmptyState title="Choose a context" body="Select a workflow or starter template to preview the playground context." />
          )}
        </section>

        <section className="panel section-stack">
          <div className="section-heading">
            <div>
              <span className="eyebrow">4. Status</span>
              <h3>Journey + next step</h3>
            </div>
          </div>
          <ol className="step-list step-rail">
            {((resource.data?.step_state || []) as JsonObject[]).map((step: JsonObject) => (
              <li key={step.key} className={`step-item${step.locked ? " locked" : ""}`}>
                <div className="step-head">
                  <strong>{step.label}</strong>
                  <span className={`step-status ${step.locked ? "locked" : "current"}`}>{step.locked ? "Locked" : "Ready"}</span>
                </div>
                <span>{step.description}</span>
              </li>
            ))}
          </ol>
          <section className="next-step-card">
            <strong>{resource.data?.guidance?.next_step?.title || "Run one exploratory session"}</strong>
            <p>{resource.data?.guidance?.next_step?.detail || "Update the playground state, then run one exploratory question."}</p>
          </section>
          {lastResult?.save_back ? (
            <details className="artifact-preview">
              <summary>Prepared save-back state (read-only)</summary>
              <ArtifactPreview label="Workflow state" value={lastResult.save_back.workflow} />
              <ArtifactPreview label="Profile state" value={lastResult.save_back.profile} />
            </details>
          ) : null}
        </section>
      </section>

      {lastResult ? (
        <>
          <section className="stats-grid">
            {((lastResult.summary_cards || []) as JsonObject[]).map((card: JsonObject) => (
              <MetricCard key={String(card.label)} label={String(card.label)} value={card.value} />
            ))}
          </section>

          <section className="panel section-stack">
            <div className="section-heading">
              <div>
                <span className="eyebrow">5. Graph trace</span>
                <h3>Executed nodes linked to graph identity</h3>
              </div>
              <StatusPill value={String(resultTrace.source_label || "No trace rows")} />
            </div>
            {graphTraceArtifact.available === false && resultTrace.source === "sandbox" ? (
              <Message
                tone="warning"
                title={graphTraceArtifact.empty_state?.title || "No graph trace artifact"}
                body={graphTraceArtifact.empty_state?.body || "Showing sandbox inspection steps without claiming a persisted graph_trace.jsonl artifact."}
              />
            ) : null}
            <PlaygroundGraphTracePreview
              canvas={((lastResult.canvas || contextPreview?.canvas || {}) as JsonObject)}
              traceItems={orderedTrace}
              activeNodeId={String(activeStep?.node_id || "")}
              onSelectNode={selectTraceNode}
            />
            {orderedTrace.length ? (
              <ol className="node-trace-list">
                {orderedTrace.map((item: JsonObject) => (
                  <li key={`${item.canvas_node_id || item.node_id}-${item.order}`}>
                    <span className="trace-order">{formatValue(item.order)}</span>
                    <div>
                      <strong>{item.label || item.node_id}</strong>
                      <span>{item.canvas_node_id || `node:${item.node_id}`} · {item.node_id} · {item.status || "observed"}</span>
                    </div>
                  </li>
                ))}
              </ol>
            ) : (
              <EmptyState
                title={resultTrace.empty_state?.title || graphTraceArtifact.empty_state?.title || "No execution trace"}
                body={resultTrace.empty_state?.body || graphTraceArtifact.empty_state?.body || "This playground run did not persist trace rows."}
              />
            )}
          </section>

          <section className="playground-grid">
            <section className="panel section-stack">
              <div className="section-heading">
                <div>
                  <span className="eyebrow">6. Inspect</span>
                  <h3>Ordered step outputs</h3>
                </div>
                <span className="section-count">{steps.length} steps</span>
              </div>
              <div className="playground-step-list">
                {steps.map((step) => (
                  <button
                    key={playgroundStepKey(step)}
                    type="button"
                    className={playgroundStepKey(step) === playgroundStepKey(activeStep || {}) ? "playground-step-button active" : "playground-step-button"}
                    onClick={() => setSelectedStepKey(playgroundStepKey(step))}
                  >
                    <div className="surface-header">
                      <strong>{formatValue(step.order)}. {step.label || step.node_id}</strong>
                      <StatusPill value={String(step.status || "completed")} />
                    </div>
                    <span className="workflow-note">{traceByNodeId[String(step.node_id)]?.canvas_node_id || `node:${step.node_id}`} · {step.node_id} · {step.node_type || "node"}</span>
                    <span>{step.output_preview || "No preview available."}</span>
                  </button>
                ))}
              </div>
            </section>

            <section className="panel section-stack">
              <div className="section-heading">
                <div>
                  <span className="eyebrow">Selected step</span>
                  <h3>{activeStep?.label || activeStep?.node_id || "Read-only step detail"}</h3>
                </div>
              </div>
              {activeStep ? (
                <>
                  <dl className="context-list">
                    <div><dt>Node ID</dt><dd>{activeStep.node_id}</dd></div>
                    <div><dt>Node type</dt><dd>{activeStep.node_type || "node"}</dd></div>
                    <div><dt>Status</dt><dd>{activeStep.status || "completed"}</dd></div>
                    <div><dt>Order</dt><dd>{formatValue(activeStep.order)}</dd></div>
                    <div><dt>Latency (seconds)</dt><dd>{formatValue(activeStep.latency_seconds)}</dd></div>
                    <div><dt>Route</dt><dd>{formatValue(activeStep.route)}</dd></div>
                  </dl>
                  <p className="helper-text">{activeStep.output_preview || "No step preview available."}</p>
                  <ArtifactPreview label="Structured output" value={activeStep.output} />
                  <ArtifactList items={((activeStep.artifacts || []) as JsonObject[]).map((item: JsonObject) => ({ ...item, label: item.name, available: true }))} />
                  <div className="json-stack">
                    {Object.entries((activeStep.artifact_payloads || {}) as Record<string, any>).map(([key, value]) => (
                      <ArtifactPreview key={key} label={key} value={value} />
                    ))}
                  </div>
                </>
              ) : (
                <EmptyState title="No step output yet" body="Run the playground session to inspect ordered node outputs here." />
              )}
            </section>
          </section>

          <section className="panel section-stack">
            <div className="section-heading">
              <div>
                <span className="eyebrow">Latest exploratory run</span>
                <h3>{lastResult.run_id}</h3>
              </div>
            </div>
            <p className="helper-text">{lastResult.run_summary?.summary || lastResult.labeling?.notes?.[0] || "Use the playground for exploratory local analysis, not release-grade evidence."}</p>
            <div className="button-row">
              <button className="primary-button" onClick={() => navigate(`/runs/${lastResult.run_id}`)}>Open run detail</button>
              {lastResult.report?.available ? <a className="secondary-link" href={lastResult.report.href} target="_blank" rel="noreferrer">Open report</a> : null}
            </div>
          </section>
        </>
      ) : null}
    </main>
  );
}

function WorkbenchPage({ route, shell, navigate, onMutate }: { route: Route; shell: JsonObject | null; navigate: (path: string) => void; onMutate: () => void }): React.ReactElement {
  const params = useMemo(() => new URLSearchParams(route.search), [route.search]);
  const draftId = params.get("draft");
  const requestedTemplate = params.get("template") || params.get("template_id");
  const requestedMode = params.get("mode");
  const selectedWorkflow = params.get("workflow") || shell?.overview?.latest_run?.workflow?.name || "demo-provider-free";
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
  const [edgeDraftFrom, setEdgeDraftFrom] = useState("");
  const [localPositions, setLocalPositions] = useState<Record<string, { x: number; y: number }>>({});

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

  useEffect(() => {
    setActionNotice(null);
  }, [draftId, selectedWorkflow]);

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
    setInspectorMode("workflow");
    setSelectedEdgeId("");
    setEdgeDraftFrom("");
  }

  function selectNodeInspector(name: string) {
    setSelectedNodeName(name);
    setSelectedEdgeId("");
    setInspectorMode("node");
  }

  function selectEdgeInspector(edge: JsonObject) {
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

  return (
    <main className="workbench-layout">
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
      <section className="workbench-main">
        {workflow.error ? <Message tone="error" title="Workflow unavailable" body={workflow.error} /> : null}
        {draft.error ? <Message tone="error" title="Draft unavailable" body={draft.error} /> : null}
        {workflows.error ? <Message tone="error" title="Workflow catalog unavailable" body={workflows.error} /> : null}
        {authoringCatalog.error ? <Message tone="error" title="Authoring catalog unavailable" body={authoringCatalog.error} /> : null}
        {actionNotice ? <Message tone={actionNotice.tone} title={actionNotice.title} body={actionNotice.body} /> : null}
        {busy ? <LoadingCard label={busy} /> : null}
        {draftId && draft.loading && !draft.data ? <LoadingCard label="Loading draft" /> : null}
        {!draftId && (workflow.loading || authoringCatalog.loading) && !workflow.data ? <LoadingCard label="Loading workflow authoring surface" /> : null}

        <section className="panel hero-panel workbench-hero">
          <span className="eyebrow">{surfaceLabel}</span>
          <h2>{draftId ? "Drag-drop the bounded workflow graph IDE" : "Create a new authored workflow or clone one into a local draft"}</h2>
          <p>
            {draftId
              ? isStudio
                ? "Move nodes locally, drag safe palette nodes onto the canvas, create/remove edges, edit supported config, validate, save, and run through the Studio API without arbitrary plugin or code editing."
                : "The legacy workbench route stays compatible with the same safe authoring backend while Studio is the primary graph IDE surface."
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
            {overviewLatestRun?.run_id ? (
              <button className="secondary-button" onClick={() => navigate(`/runs/${overviewLatestRun.run_id}`)}>Inspect latest run</button>
            ) : (
              <button className="secondary-button" onClick={() => navigate("/runs")}>Browse runs</button>
            )}
            {activeDraft?.last_run_id ? <button className="secondary-button" onClick={() => navigate(`/runs/${activeDraft.last_run_id}`)}>Inspect candidate run</button> : null}
          </div>
        </section>

        <section className="panel section-stack">
          <div className="section-heading">
            <div>
              <span className="eyebrow">1. Create draft</span>
              <h3>Start from scratch, template, or clone</h3>
            </div>
            <p className="section-copy">Creation routes all flow through the shared backend authoring service and still land in the local draft + workflow file model.</p>
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
              {activeDraft ? (
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
                <EmptyState title="Select a workflow" body="The workbench will show the current workflow summary here before you create a draft." />
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

        <section className="panel section-stack studio-ide-panel">
          <div className="section-heading">
            <div>
              <span className="eyebrow">3. Studio graph IDE</span>
              <h3>Drag nodes, drop safe palette items, select nodes/edges, then validate</h3>
            </div>
            <p className="section-copy">Node positions are local UI state for this session; the workflow schema currently persists graph topology and config, not canvas coordinates.</p>
          </div>
          {!draftId ? (
            <EmptyState title="Create a draft to unlock graph authoring" body="The canvas becomes editable as soon as you open a draft session." />
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
                  <span className="eyebrow">Node palette</span>
                  <p>Click to add downstream of the selected node, or drag a built-in safe node onto the canvas.</p>
                </div>
                <div className="node-palette-grid">
                  {nodeCatalog.map((item: JsonObject) => (
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
              </section>

              <WorkflowCanvasSurface
                canvas={activeCanvas}
                entry={String(activeGraph.entry || "")}
                selectedNodeName={inspectorMode === "node" ? selectedNodeName : ""}
                selectedEdgeId={inspectorMode === "edge" ? selectedEdgeId : ""}
                localPositions={localPositions}
                edgeDraftFrom={edgeDraftFrom}
                onMoveNode={(name, position) => setLocalPositions((current) => ({ ...current, [name]: position }))}
                onSelectNode={selectNodeInspector}
                onSelectEdge={selectEdgeInspector}
                onSelectWorkflow={selectWorkflowInspector}
                onAddNodeFromPalette={(implementation, position) => void addPaletteNode(implementation, position)}
                onCreateEdge={(from, to) => void createEdgeFromCanvas(from, to)}
              />

              <div className="three-column-grid authoring-grid">
                <section className="surface-card section-stack">
                  <div className="surface-header">
                    <div>
                      <strong>Context inspector</strong>
                      <p>
                        {inspectorMode === "workflow"
                          ? "Workflow config uses the same safe mutation action as the field form above."
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
                      <button className="secondary-button" onClick={() => document.getElementById("workflow-config-fields")?.scrollIntoView({ behavior: "smooth", block: "start" })}>Jump to workflow config</button>
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

                <section className="surface-card section-stack">
                  <div className="surface-header">
                    <div>
                      <strong>Add safe node</strong>
                      <p>Palette click/drop uses the same add-node mutation; this form gives explicit names and edge wiring.</p>
                    </div>
                  </div>
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
                </section>

                <section className="surface-card section-stack">
                  <div className="surface-header">
                    <div>
                      <strong>Edges + advanced graph context</strong>
                      <p>Add or remove simple edges here. Parallel groups and routes stay visible for review.</p>
                    </div>
                  </div>
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
                      <div key={`${edge.from}-${edge.to}-${index}`} className={studioEdgeKey(edge) === selectedEdgeId ? "edge-row selected" : "edge-row"} onClick={() => selectEdgeInspector(edge)}>
                        <div>
                          <strong>{edge.from}</strong>
                          <span>{edge.to}</span>
                        </div>
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
                </section>
              </div>
            </>
          )}
        </section>

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
                <button className="primary-button" disabled={Boolean(busy) || runDisabled} onClick={runDraft}>Run candidate</button>
              </div>
            </>
          )}
        </section>

        <section className="panel">
          <div className="section-heading">
            <div>
              <span className="eyebrow">5. Compare + next step</span>
              <h3>Keep validate, run, and compare inside the same authoring loop</h3>
            </div>
            <p className="section-copy">Once the candidate finishes, compare it immediately or jump into the run detail from the same workbench surface.</p>
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
      </section>
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
    </main>
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
  onSelectNode: (name: string) => void;
  onSelectEdge: (edge: JsonObject) => void;
  onSelectWorkflow: () => void;
  onAddNodeFromPalette: (implementation: string, position: { x: number; y: number }) => void;
  onCreateEdge: (from: string, to: string) => void;
}): React.ReactElement {
  const stageRef = React.useRef<HTMLDivElement | null>(null);
  const dragRef = React.useRef<{ nodeName: string; offsetX: number; offsetY: number; pointerId: number } | null>(null);
  const suppressClickRef = React.useRef(false);
  const nodes = ((canvas?.nodes || []) as JsonObject[]).filter((node) => typeof node?.name === "string");
  const edges = (canvas?.edges || []) as JsonObject[];
  if (!nodes.length) {
    return <EmptyState title="No graph nodes yet" body="Add a node or load another workflow to populate the visual graph surface." />;
  }
  const positionForNode = (node: JsonObject) => {
    const name = String(node.name);
    return localPositions[name] || { x: Number(node.x || 0), y: Number(node.y || 0) };
  };
  const width = Math.max(680, ...nodes.map((node) => positionForNode(node).x + 240));
  const height = Math.max(360, ...nodes.map((node) => positionForNode(node).y + 150));
  const positions = Object.fromEntries(nodes.map((node) => [String(node.name), positionForNode(node)]));
  const relativePoint = (event: { clientX: number; clientY: number }) => {
    const rect = stageRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  };
  const clampPosition = (x: number, y: number) => ({
    x: Math.max(0, Math.min(width - 180, Math.round(x))),
    y: Math.max(0, Math.min(height - 90, Math.round(y))),
  });
  return (
    <div
      className="workflow-canvas-shell"
      onDragOver={(event) => {
        if (Array.from(event.dataTransfer.types).includes("application/xrtm-node-implementation")) {
          event.preventDefault();
          event.dataTransfer.dropEffect = "copy";
        }
      }}
      onDrop={(event) => {
        const implementation = event.dataTransfer.getData("application/xrtm-node-implementation");
        if (!implementation) return;
        event.preventDefault();
        const point = relativePoint(event);
        onAddNodeFromPalette(implementation, clampPosition(point.x - 82, point.y - 34));
      }}
    >
      <div
        ref={stageRef}
        className="workflow-canvas-stage"
        style={{ height: `${height}px`, width: `${width}px` }}
        onClick={(event) => {
          if (event.currentTarget === event.target) onSelectWorkflow();
        }}
      >
        <svg className="workflow-canvas-svg" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMinYMin meet" onClick={onSelectWorkflow}>
          <defs>
            <marker id="workflow-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
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
            const edgeId = studioEdgeKey(edge);
            return (
              <g key={`${edge.from}-${edge.to}-${index}`} className="workflow-canvas-edge-hit" onClick={(event) => { event.stopPropagation(); onSelectEdge(edge); }}>
                <path className={`workflow-canvas-edge ${edgeId === selectedEdgeId ? "selected" : ""} ${edge.read_only ? "readonly" : ""}`} d={`M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`} markerEnd="url(#workflow-arrow)" />
                {edge.label ? <text className="workflow-canvas-label" x={midX} y={midY - 6}>{String(edge.label)}</text> : null}
              </g>
            );
          })}
        </svg>
        {nodes.map((node) => {
          const name = String(node.name);
          const position = positionForNode(node);
          return (
            <button
              key={name}
              type="button"
              className={`workflow-canvas-node ${selectedNodeName === name ? "selected" : ""} ${entry === name ? "entry" : ""} ${edgeDraftFrom === name ? "edge-source" : ""}`}
              style={{ left: `${position.x}px`, top: `${position.y}px` }}
              onPointerDown={(event) => {
                const point = relativePoint(event);
                dragRef.current = { nodeName: name, offsetX: point.x - position.x, offsetY: point.y - position.y, pointerId: event.pointerId };
                suppressClickRef.current = false;
                event.currentTarget.setPointerCapture(event.pointerId);
              }}
              onPointerMove={(event) => {
                const drag = dragRef.current;
                if (!drag || drag.nodeName !== name) return;
                const point = relativePoint(event);
                suppressClickRef.current = true;
                onMoveNode(name, clampPosition(point.x - drag.offsetX, point.y - drag.offsetY));
              }}
              onPointerUp={(event) => {
                if (dragRef.current?.pointerId === event.pointerId) {
                  dragRef.current = null;
                  event.currentTarget.releasePointerCapture(event.pointerId);
                }
              }}
              onClick={(event) => {
                event.stopPropagation();
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
            >
              <strong>{name}</strong>
              <span>{node.kind}</span>
              <StatusPill value={node.status || (entry === name ? "entry" : "ready")} />
            </button>
          );
        })}
      </div>
    </div>
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
  if (!nodes.length) {
    return <EmptyState title="No graph preview" body="This context did not expose canvas-ready graph nodes." />;
  }
  const width = Math.max(360, ...nodes.map((node) => Number(node.x || 0) + 220));
  const height = Math.max(220, ...nodes.map((node) => Number(node.y || 0) + 120));
  const positions = Object.fromEntries(nodes.map((node) => [String(node.name), { x: Number(node.x || 0), y: Number(node.y || 0) }]));
  return (
    <div className="workflow-canvas-shell playground-trace-canvas">
      <div className="workflow-canvas-stage" style={{ height: `${height}px` }}>
        <svg className="workflow-canvas-svg" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMinYMin meet">
          <defs>
            <marker id="playground-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 z" fill="#91a5ca" />
            </marker>
          </defs>
          {edges.map((edge, index) => {
            const from = positions[String(edge.from || "")];
            const to = positions[String(edge.to || "")];
            if (!from || !to) return null;
            const sourceTrace = traceByNode[String(edge.from || "")];
            const targetTrace = traceByNode[String(edge.to || "")];
            const traced = sourceTrace && targetTrace && Number(sourceTrace.order || 0) <= Number(targetTrace.order || 0);
            const x1 = from.x + 164;
            const y1 = from.y + 34;
            const x2 = to.x;
            const y2 = to.y + 34;
            const midX = (x1 + x2) / 2;
            const midY = (y1 + y2) / 2;
            return (
              <g key={`${edge.from}-${edge.to}-${index}`}>
                <path
                  className={`workflow-canvas-edge ${traced ? "executed" : ""}`}
                  d={`M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`}
                  markerEnd="url(#playground-arrow)"
                />
                {edge.label ? <text className="workflow-canvas-label" x={midX} y={midY - 6}>{String(edge.label)}</text> : null}
              </g>
            );
          })}
        </svg>
        {nodes.map((node) => {
          const trace = traceByNode[String(node.name)];
          const executed = Boolean(trace || node.executed);
          const active = activeNodeId === String(node.name);
          return (
            <button
              key={node.name}
              type="button"
              className={`workflow-canvas-node playground-trace-node ${executed ? "executed" : "not-executed"} ${active ? "active" : ""} ${node.is_entry ? "entry" : ""}`}
              style={{ left: `${Number(node.x || 0)}px`, top: `${Number(node.y || 0)}px` }}
              onClick={() => onSelectNode(String(node.name))}
            >
              <strong>{node.name}</strong>
              <span>{node.kind || node.node_type || "node"}</span>
              <span className="trace-chip">{executed ? `#${formatValue(trace?.order || node.trace_order)}` : "Not run"}</span>
              <StatusPill value={String(trace?.status || node.status || (node.is_entry ? "entry" : "ready"))} />
            </button>
          );
        })}
      </div>
    </div>
  );
}

function normalizeText(value: string | undefined): string | null {
  const text = String(value || "").trim();
  return text ? text : null;
}

function parseBooleanString(value: string | undefined): boolean {
  return String(value || "false").toLowerCase() === "true";
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
    { key: "next-step", label: "Next step", locked: false, description: "The workbench will explain what to do after each step." },
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
      notes.add("Enter every supported weight as a number from 0 to 100; the workbench will normalize them after validation.");
    }
    if (lower.includes("unsupported edit field")) {
      notes.add("Stay inside the listed authoring controls. The workbench does not expose arbitrary JSON or unsupported implementation edits.");
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
      detail: "Local workflows are reusable on disk, but the workbench still uses a draft session so validation, run readiness, and resume state stay explicit.",
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
