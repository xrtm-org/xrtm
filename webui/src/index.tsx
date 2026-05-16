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

  const nav = shell.data?.app?.nav ?? [
    { label: "Overview", href: "/" },
    { label: "Runs", href: "/runs" },
    { label: "Workbench", href: "/workbench" },
  ];

  let page: React.ReactElement;
  if (route.path === "/") {
    page = <OverviewPage shell={shell.data} navigate={navigate} />;
  } else if (route.path === "/start") {
    page = <StartPage shell={shell.data} navigate={navigate} onMutate={refreshShell} />;
  } else if (route.path === "/runs") {
    page = <RunsPage route={route} navigate={navigate} />;
  } else if (route.path === "/operations") {
    page = <OperationsPage navigate={navigate} onMutate={refreshShell} />;
  } else if (route.path === "/advanced") {
    page = <AdvancedPage />;
  } else if (/^\/runs\/[^/]+\/compare\/[^/]+$/.test(route.path)) {
    const match = route.path.match(/^\/runs\/([^/]+)\/compare\/([^/]+)$/)!;
    page = <ComparePage candidateRunId={match[1]} baselineRunId={match[2]} navigate={navigate} />;
  } else if (/^\/workflows\/[^/]+$/.test(route.path)) {
    page = <WorkflowDetailPage workflowName={decodeURIComponent(route.path.split("/")[2])} navigate={navigate} onMutate={refreshShell} />;
  } else if (/^\/runs\/[^/]+$/.test(route.path)) {
    page = <RunDetailPage runId={route.path.split("/")[2]} navigate={navigate} onMutate={refreshShell} />;
  } else {
    page = <WorkbenchPage route={route} shell={shell.data} navigate={navigate} onMutate={refreshShell} />;
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <span className="eyebrow">XRTM WebUI</span>
          <h1>Local forecasting workbench</h1>
        </div>
        <nav className="topnav" aria-label="Primary">
          {nav.map((item: JsonObject) => (
            <a
              key={item.href}
              className={route.path === item.href ? "nav-link active" : "nav-link"}
              href={item.href}
              onClick={(event) => {
                event.preventDefault();
                navigate(item.href);
              }}
            >
              {item.label}
            </a>
          ))}
        </nav>
      </header>
      {bootstrap.initial_error ? <Message tone="error" title="Initial error" body={bootstrap.initial_error} /> : null}
      {shell.error ? <Message tone="error" title="App shell error" body={shell.error} /> : null}
      {shell.loading && !shell.data ? <LoadingCard label="Loading app shell" /> : null}
      {shell.data ? (
        <section className="environment-strip">
          <div>
            <strong>Runs</strong>
            <span>{shell.data.environment?.runs_dir}</span>
          </div>
          <div>
            <strong>Workflows</strong>
            <span>{shell.data.environment?.workflows_dir}</span>
          </div>
          <div>
            <strong>Local LLM</strong>
            <span>{String(shell.data.environment?.local_llm?.healthy)}</span>
          </div>
          <div>
            <strong>App DB</strong>
            <span>{shell.data.environment?.app_db}</span>
          </div>
        </section>
      ) : null}
      {page}
    </div>
  );
}

function OverviewPage({ shell, navigate }: { shell: JsonObject | null; navigate: (path: string) => void }): React.ReactElement {
  const overview = shell?.overview;
  if (!overview) {
    return <LoadingCard label="Loading overview" />;
  }
  return (
    <main className="page-grid">
      <section className="panel hero-panel">
        <span className="eyebrow">Overview</span>
        <h2>{overview.hero?.title}</h2>
        <p>{overview.hero?.summary}</p>
        <div className="button-row">
          <button className="primary-button" onClick={() => navigate(overview.resume_target?.href || "/start")}>
            {overview.resume_target?.label || "Resume"}
          </button>
          <button className="secondary-button" onClick={() => navigate("/start")}>Open start</button>
          <button className="secondary-button" onClick={() => navigate("/workbench")}>Open workbench</button>
        </div>
      </section>
      <section className="stats-grid">
        <MetricCard label="Indexed runs" value={overview.counts?.runs ?? 0} />
        <MetricCard label="Indexed workflows" value={overview.counts?.workflows ?? 0} />
        <MetricCard label="Latest action" value={overview.resume_target?.kind || "workbench"} />
      </section>
      {overview.latest_run ? <RunCard run={overview.latest_run} onOpen={() => navigate(`/runs/${overview.latest_run.run_id}`)} /> : null}
      {overview.empty_state ? (
        <section className="panel">
          <h3>{overview.empty_state.title}</h3>
          <p>{overview.empty_state.summary}</p>
          <button className="primary-button" onClick={() => navigate(overview.empty_state.primary_cta?.href || "/start")}>
            {overview.empty_state.primary_cta?.label || "Open workbench"}
          </button>
        </section>
      ) : null}
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
    if (!selectedWorkflow && (workflows.data?.items || []).length) {
      setSelectedWorkflow(workflows.data.items[0].name);
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
    if (!selectedArtifactRun && (runs.data?.items || []).length) {
      setSelectedArtifactRun(runs.data.items[0].run_id);
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
      <section className="panel">
        <span className="eyebrow">Runs</span>
        <h2>Inspect canonical run history</h2>
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
                <td>{run.workflow?.title || run.workflow?.name || "Unknown workflow"}</td>
                <td><StatusPill value={run.status} /></td>
                <td>{run.provider}</td>
                <td>{run.updated_at || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!resource.loading && !(resource.data?.items || []).length ? <EmptyState title="No runs match the current filter" body="Try clearing filters or running a workflow from the workbench." /> : null}
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
        <span className="eyebrow">Run detail</span>
        <h2>{run.hero?.title || run.workflow?.title || run.run_id}</h2>
        <p>{run.hero?.summary || "Inspect the latest run summary, question rows, and artifacts."}</p>
        <div className="meta-row">
          <StatusPill value={run.run?.status} />
          <span>{run.run?.provider || "Unknown provider"}</span>
          <span>{run.run?.updated_at || run.run?.completed_at || "—"}</span>
        </div>
        <div className="button-row">
          <button className="primary-button" onClick={() => navigate("/workbench")}>Back to workbench</button>
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
          <a className="secondary-link" href={`${bootstrap.api_root}/runs/${runId}/export?format=json`}>Export JSON</a>
          <a className="secondary-link" href={`${bootstrap.api_root}/runs/${runId}/export?format=csv`}>Export CSV</a>
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
                <h3>Node timeline</h3>
                <p>Execution order and final state of each graph step.</p>
              </div>
            </div>
            {(run.graph_trace || []).length ? (
              <ul className="timeline-list">
                {(run.graph_trace || []).map((item: JsonObject, index: number) => (
                  <li key={`${item.node}-${index}`}>
                    <strong>{item.node}</strong>
                    <span>{item.status || "observed"}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="No graph trace" body="This run did not persist graph trace rows." />
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

function WorkbenchPage({ route, shell, navigate, onMutate }: { route: Route; shell: JsonObject | null; navigate: (path: string) => void; onMutate: () => void }): React.ReactElement {
  const params = useMemo(() => new URLSearchParams(route.search), [route.search]);
  const draftId = params.get("draft");
  const selectedWorkflow = params.get("workflow") || shell?.overview?.latest_run?.workflow?.name || "demo-provider-free";
  const workflows = useJsonResource(`${bootstrap.api_root}/workflows`, [route.search]);
  const draft = useJsonResource(draftId ? `${bootstrap.api_root}/drafts/${draftId}` : null, [draftId]);
  const workflow = useJsonResource(!draftId ? `${bootstrap.api_root}/workflows/${selectedWorkflow}` : null, [selectedWorkflow, draftId]);
  const [formValues, setFormValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<{ tone: string; title: string; body: string } | null>(null);

  useEffect(() => {
    if (draft.data?.draft_values) {
      setFormValues(draft.data.draft_values);
    }
  }, [draft.data]);

  useEffect(() => {
    setActionNotice(null);
  }, [draftId, selectedWorkflow]);

  const activeDraft = draft.data;
  const activeWorkflow = activeDraft ? activeDraft.workflow : workflow.data?.workflow;
  const activeSafeEdit = activeDraft ? activeDraft.safe_edit : workflow.data?.safe_edit;
  const activeCanvas = activeDraft ? activeDraft.canvas : workflow.data?.canvas;
  const overviewLatestRun = shell?.overview?.latest_run || null;
  const safeEditSupport = (activeDraft?.guidance?.supported_edits || activeSafeEdit?.supported_edits || []) as JsonObject[];
  const safeEditLimitations = (activeDraft?.guidance?.limitations || activeSafeEdit?.limitations || []) as string[];
  const sourceOfTruth = (activeDraft?.guidance?.source_of_truth || defaultSourceOfTruth()) as string[];
  const nextStep = (activeDraft?.guidance?.next_step || buildDraftlessNextStep(activeWorkflow, overviewLatestRun)) as JsonObject;
  const stepState = draftId
    ? decorateStepState((activeDraft?.step_state || defaultStepState()) as JsonObject[], activeDraft, true)
    : decorateStepState(draftlessStepState(activeWorkflow), null, false);
  const validationStatus = buildValidationStatus(activeDraft);
  const validationFixes = buildValidationFixes(activeDraft);
  const runDisabled = !(activeDraft?.validation?.ok && !activeDraft?.validation?.stale);
  const draftActionLabel = activeWorkflow?.source === "local" ? "Open local draft session" : "Clone into local draft";
  const draftActionSummary = activeWorkflow?.source === "local"
    ? "This workflow already lives in your local workspace, but edits still flow through a draft session so validation and resume state stay explicit."
    : "Built-in workflows are reference blueprints. Clone one into a local draft before editing any field.";

  async function createDraft(sourceWorkflowName: string) {
    setBusy("Creating local draft");
    setActionNotice(null);
    try {
      const payload: JsonObject = { source_workflow_name: sourceWorkflowName };
      if (shell?.overview?.latest_run?.run_id) {
        payload.baseline_run_id = shell.overview.latest_run.run_id;
      }
      const created = await requestJson(`${bootstrap.api_root}/drafts`, { method: "POST", body: JSON.stringify(payload) });
      onMutate();
      navigate(`/workbench?draft=${created.id}`);
    } catch (error) {
      setActionNotice(buildActionErrorNotice("clone", error));
    } finally {
      setBusy(null);
    }
  }

  async function persistDraft(nextValues: Record<string, string>) {
    if (!draftId) return null;
    return requestJson(`${bootstrap.api_root}/drafts/${draftId}`, {
      method: "PATCH",
      body: JSON.stringify({ values: nextValues }),
    });
  }

  async function saveDraft() {
    if (!draftId) return;
    setBusy("Saving safe edit");
    setActionNotice(null);
    try {
      await persistDraft(formValues);
      draft.reload();
      onMutate();
      setActionNotice({
        tone: "success",
        title: "Draft saved",
        body: "Safe-edit values are stored in SQLite. Next: validate the cloned workflow before running a candidate.",
      });
    } catch (error) {
      setActionNotice(buildActionErrorNotice("save", error));
    } finally {
      setBusy(null);
    }
  }

  async function validateDraft() {
    if (!draftId) return;
    setBusy("Validating safe edit");
    setActionNotice(null);
    try {
      await persistDraft(formValues);
      const result = await requestJson(`${bootstrap.api_root}/drafts/${draftId}/validate`, { method: "POST", body: JSON.stringify({}) });
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
                : "The latest safe edits validated successfully. Next: run a candidate and compare it with the baseline.",
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
      await persistDraft(formValues);
      const response = await requestJson(`${bootstrap.api_root}/drafts/${draftId}/run`, { method: "POST", body: JSON.stringify({}) });
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

  function updateFormValue(key: string, value: string) {
    setActionNotice(null);
    setFormValues((current) => ({ ...current, [key]: value }));
  }

  return (
    <main className="workbench-layout">
      <aside className="panel step-panel">
        <span className="eyebrow">Journey</span>
        <h2>Inspect → clone → safe edit</h2>
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
        {actionNotice ? <Message tone={actionNotice.tone} title={actionNotice.title} body={actionNotice.body} /> : null}
        {busy ? <LoadingCard label={busy} /> : null}
        {draftId && draft.loading && !draft.data ? <LoadingCard label="Loading draft" /> : null}
        {!draftId && workflow.loading && !workflow.data ? <LoadingCard label="Loading workflow" /> : null}

        <section className="panel hero-panel workbench-hero">
          <span className="eyebrow">Workbench</span>
          <h2>{draftId ? "Guide one safe draft from inspection to comparison" : "Choose a workflow, then unlock safe edits with a local draft"}</h2>
          <p>
            {draftId
              ? "Stay in context while you inspect the baseline, validate inline, run a candidate, and decide what to do next."
              : "Built-in workflows stay read-only until you clone them. Draft values live in SQLite so you can validate and iterate without losing context."}
          </p>
          <div className="meta-row">
            <SourceBadge source={activeWorkflow?.source || "builtin"} />
            {activeDraft?.draft_workflow_name ? <span>Draft: {activeDraft.draft_workflow_name}</span> : null}
            {activeDraft?.baseline_run_id ? <span>Baseline: {activeDraft.baseline_run_id}</span> : overviewLatestRun?.run_id ? <span>Suggested baseline: {overviewLatestRun.run_id}</span> : null}
            {activeDraft?.last_run_id ? <span>Candidate: {activeDraft.last_run_id}</span> : null}
          </div>
          <div className="button-row">
            {!draftId ? (
              <>
                <button className="primary-button" onClick={() => createDraft(activeWorkflow?.name || selectedWorkflow)}>{draftActionLabel}</button>
                {overviewLatestRun?.run_id ? (
                  <button className="secondary-button" onClick={() => navigate(`/runs/${overviewLatestRun.run_id}`)}>Inspect latest run</button>
                ) : (
                  <button className="secondary-button" onClick={() => navigate("/runs")}>Browse runs</button>
                )}
              </>
            ) : (
              <>
                {activeDraft?.baseline_run_id ? (
                  <button className="secondary-button" onClick={() => navigate(`/runs/${activeDraft.baseline_run_id}`)}>Inspect baseline</button>
                ) : (
                  <button className="secondary-button" onClick={() => navigate("/runs")}>Choose a baseline</button>
                )}
                {activeDraft?.last_run_id ? <button className="secondary-button" onClick={() => navigate(`/runs/${activeDraft.last_run_id}`)}>Inspect candidate run</button> : null}
              </>
            )}
          </div>
        </section>

        <section className="panel">
          <div className="section-heading">
            <div>
              <span className="eyebrow">1. Inspect + clone</span>
              <h3>Pick a workflow and keep the baseline in view</h3>
            </div>
            <p className="section-copy">{draftActionSummary}</p>
          </div>
          <div className="inspect-grid">
            <article className="surface-card">
              <div className="surface-header">
                <div>
                  <strong>{activeWorkflow?.title || activeWorkflow?.name || selectedWorkflow}</strong>
                  <p>{activeWorkflow?.description || "Select a workflow from the catalog."}</p>
                </div>
                <SourceBadge source={activeWorkflow?.source || "builtin"} />
              </div>
              <p className="helper-text">{draftActionSummary}</p>
              {!draftId ? (
                <button className="primary-button" onClick={() => createDraft(activeWorkflow?.name || selectedWorkflow)}>{draftActionLabel}</button>
              ) : (
                  <dl className="context-list">
                    <div>
                      <dt>Source</dt>
                      <dd>{activeDraft?.source_workflow_name || "—"}</dd>
                    </div>
                    <div>
                      <dt>Local draft</dt>
                      <dd>{activeDraft?.draft_workflow_name || "—"}</dd>
                    </div>
                    <div>
                      <dt>Status</dt>
                      <dd>{activeDraft?.status || "—"}</dd>
                    </div>
                  </dl>
                )}
            </article>
            <article className="surface-card">
              <div className="surface-header">
                <div>
                  <strong>Baseline context</strong>
                  <p>Inspect first so the next edit has a clear comparison target.</p>
                </div>
              </div>
              {activeDraft?.baseline_run || overviewLatestRun ? (
                <dl className="context-list">
                  <div>
                    <dt>Run</dt>
                    <dd>{formatRunContext(activeDraft?.baseline_run || overviewLatestRun)}</dd>
                  </div>
                  <div>
                    <dt>Workflow</dt>
                    <dd>{activeDraft?.baseline_run?.workflow?.title || activeDraft?.baseline_run?.workflow?.name || overviewLatestRun?.workflow?.title || overviewLatestRun?.workflow?.name || "—"}</dd>
                  </div>
                  <div>
                    <dt>Action</dt>
                    <dd>{activeDraft?.baseline_run_id ? "Compare against this baseline after your candidate run." : "Use the latest run as a suggested baseline when you clone."}</dd>
                  </div>
                </dl>
              ) : (
                <EmptyState title="No baseline yet" body="Run history is empty. You can still create a draft, then inspect the first candidate run after it completes." />
              )}
            </article>
          </div>
          <div className="workflow-list workflow-catalog">
            {(workflows.data?.items || []).map((item: JsonObject) => (
              <button
                key={item.name}
                className={item.name === activeWorkflow?.name ? "workflow-tile active" : "workflow-tile"}
                onClick={() => navigate(`/workbench?workflow=${encodeURIComponent(item.name)}`)}
              >
                <div className="workflow-tile-head">
                  <strong>{item.title}</strong>
                  <SourceBadge source={item.source} />
                </div>
                <span>{item.name}</span>
                <span className="workflow-note">{item.source === "builtin" ? "Read-only until cloned" : "Local workflow available for a draft session"}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="section-heading">
            <div>
              <span className="eyebrow">2. Safe edit</span>
              <h3>Change only the fields this product contract supports</h3>
            </div>
            <p className="section-copy">Question limits, report output, and supported aggregate weights are editable. No arbitrary JSON editor is exposed.</p>
          </div>
          <div className="supported-edit-list">
            {safeEditSupport.map((edit: JsonObject) => (
              <article key={edit.key} className="supported-edit-card">
                <strong>{edit.label}</strong>
                <p>{edit.detail}</p>
              </article>
            ))}
          </div>
          {!draftId ? (
            <EmptyState
              title="Editing stays locked until you create a draft"
              body="Choose Clone into local draft first. Built-in workflows remain read-only reference blueprints until the clone step succeeds."
            />
          ) : (
            <>
              {activeDraft?.preview_error ? (
                <Message tone="warning" title="Safe edit needs attention" body={`${activeDraft.preview_error} Fix the supported fields below; your draft session is still preserved in SQLite.`} />
              ) : null}
              <div className="form-grid guided-form">
                <label>
                  <span>Questions limit</span>
                  <span className="field-help">Safe range {activeSafeEdit?.questions_limit?.min || 1}–{activeSafeEdit?.questions_limit?.max || 25}. This only changes the cloned workflow.</span>
                  <input
                    type="number"
                    min={activeSafeEdit?.questions_limit?.min || 1}
                    max={activeSafeEdit?.questions_limit?.max || 25}
                    value={formValues.questions_limit || ""}
                    onChange={(event) => updateFormValue("questions_limit", event.target.value)}
                  />
                </label>
                <label>
                  <span>Write HTML report</span>
                  <span className="field-help">Choose whether the candidate run writes report.html.</span>
                  <select
                    value={formValues.artifacts_write_report || "true"}
                    onChange={(event) => updateFormValue("artifacts_write_report", event.target.value)}
                  >
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </select>
                </label>
                {(activeSafeEdit?.aggregate_weight_editors || []).map((editor: JsonObject) => (
                  <div key={editor.node} className="weight-editor">
                    <div>
                      <h4>{editor.node}</h4>
                      <p className="field-help">Adjust upstream candidate weights only. Weights are normalized when the draft is validated.</p>
                    </div>
                    {editor.contributors.map((contributor: JsonObject) => {
                      const key = `weight:${editor.node}:${contributor.name}`;
                      return (
                        <label key={key}>
                          <span>{contributor.name}</span>
                          <input
                            type="number"
                            min={0}
                            max={100}
                            value={formValues[key] || ""}
                            onChange={(event) => updateFormValue(key, event.target.value)}
                          />
                        </label>
                      );
                    })}
                  </div>
                ))}
              </div>
            </>
          )}
        </section>

        <section className="panel">
          <div className="section-heading">
            <div>
              <span className="eyebrow">3. Validate + run</span>
              <h3>Validate inline, then run only when the latest draft is safe</h3>
            </div>
            <p className="section-copy">Validation stays inside the edit flow so you can fix problems without losing the current draft context.</p>
          </div>
          {!draftId ? (
            <EmptyState title="No draft to validate yet" body="Clone or reopen a local draft session first. Then this panel will keep validation, fixes, and run readiness together." />
          ) : (
            <>
              <Message tone={validationStatus.tone} title={validationStatus.title} body={validationStatus.body} />
              {validationFixes.length ? (
                <ul className="teaching-list">
                  {validationFixes.map((note) => <li key={note}>{note}</li>)}
                </ul>
              ) : null}
              <div className="button-row">
                <button className="secondary-button" onClick={saveDraft}>Save draft</button>
                <button className="primary-button" onClick={validateDraft}>Save + validate</button>
                <button className="primary-button" disabled={runDisabled} onClick={runDraft}>Run candidate</button>
              </div>
            </>
          )}
        </section>

        <section className="panel">
          <div className="section-heading">
            <div>
              <span className="eyebrow">4. Compare + next step</span>
              <h3>Use the outcome to decide what happens next</h3>
            </div>
            <p className="section-copy">Success states should teach the next action: inspect the candidate, compare it with the baseline, or keep iterating.</p>
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

        <section className="panel">
          <div className="section-heading">
            <div>
              <span className="eyebrow">Canvas</span>
              <h3>See the workflow before you change it</h3>
            </div>
            <p className="section-copy">The canvas stays visible so inspection and editing happen against the same workflow structure.</p>
          </div>
          <div className="canvas-grid">
            {(activeCanvas?.nodes || []).map((node: JsonObject) => (
              <article key={node.name} className="canvas-node">
                <strong>{node.name}</strong>
                <span>{node.kind}</span>
                <span>{node.description || node.implementation || "No description"}</span>
                <StatusPill value={node.status || "not-run"} />
              </article>
            ))}
          </div>
        </section>
      </section>
      <aside className="panel guidance-panel">
        <span className="eyebrow">Next step</span>
        <section className="next-step-card">
          <strong>{nextStep.title}</strong>
          <p>{nextStep.detail}</p>
        </section>
        <section className="guidance-section">
          <h3>Safe-edit contract</h3>
          <ul className="guidance-list">
            {safeEditLimitations.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </section>
        <section className="guidance-section">
          <h3>Supported fields</h3>
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

function draftlessStepState(activeWorkflow: JsonObject | null): JsonObject[] {
  const source = activeWorkflow?.source || "builtin";
  const cloneDescription = source === "local" ? "Open a draft session for the local workflow." : "Clone the built-in workflow before editing.";
  return [
    { key: "inspect", label: "Inspect", locked: false, description: "Review the workflow and choose a baseline run." },
    { key: "clone", label: "Clone", locked: false, description: cloneDescription },
    { key: "edit", label: "Safe edit", locked: true, description: "Locked until a draft session exists." },
    { key: "validate", label: "Validate", locked: true, description: "Locked until the safe edit can be checked inline." },
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
    clone: "Built-in workflows remain read-only until the clone step succeeds.",
    save: "Only the supported safe-edit fields can be stored in the draft session.",
    validate: "Fix the supported fields below, then validate again without losing the current draft context.",
    run: "The draft stays loaded. Re-validate the latest safe edit before you try another run.",
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
      body: "Save and validate inline before you run this draft. The run step stays locked until the latest validation passes.",
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
      body: "The latest safe edit is runnable. Next: run a candidate and compare it with the baseline.",
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
      notes.add("Stay inside the listed safe-edit fields. The workbench does not expose arbitrary JSON or implementation edits.");
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
      title: "Inspect the latest run, then clone",
      detail: "Review the baseline context first, then clone the built-in workflow into a local draft before making a safe edit.",
    };
  }
  return {
    key: "clone",
    title: "Clone a workflow to begin",
    detail: "Choose a workflow from the catalog and create a local draft. Safe edits only unlock after that step succeeds.",
  };
}

function defaultSourceOfTruth(): string[] {
  return [
    "Built-in workflows stay read-only until you clone them into a local workflow.",
    "Reusable local workflows remain JSON files on disk.",
    "Draft values, validation snapshots, and resume state live in SQLite.",
  ];
}

function formatRunContext(run: JsonObject | null): string {
  if (!run) return "—";
  const workflow = run.workflow?.title || run.workflow?.name;
  return [run.run_id, workflow, run.status].filter(Boolean).join(" · ");
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
    { key: "clone", label: "Clone", locked: false, description: "Create or reopen a local draft session." },
    { key: "edit", label: "Safe edit", locked: true, description: "Locked until a draft exists." },
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
