/* eslint-disable */
"use strict";
(() => {
  // src/index.tsx
  var ReactDOMClient = ReactDOM;
  var { useEffect, useMemo, useState } = React;
  var bootstrap = window.__XRTM_WEBUI_BOOTSTRAP__ ?? {
    api_root: "/api",
    initial_path: window.location.pathname,
    initial_query: window.location.search.replace(/^\?/, ""),
    initial_error: null
  };
  function currentRoute() {
    return { path: window.location.pathname, search: window.location.search.replace(/^\?/, "") };
  }
  function isNavItemActive(routePath, href) {
    if (href === "/" || href === "/hub") return routePath === "/" || routePath === "/hub";
    if (href === "/start") return routePath === "/start" || /^\/workflows\/[^/]+$/.test(routePath);
    if (href === "/runs" || href === "/observatory") return routePath === "/runs" || routePath === "/observatory" || /^\/(?:runs|observatory)\/[^/]+(?:\/compare\/[^/]+)?$/.test(routePath);
    if (href === "/studio") return routePath === "/studio" || routePath === "/workbench" || /^\/workflows\/[^/]+$/.test(routePath);
    return routePath === href;
  }
  async function requestJson(url, init) {
    const response = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...init
    });
    const body = await response.text();
    const payload = body ? JSON.parse(body) : {};
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
  function App() {
    const [route, setRoute] = useState({ path: bootstrap.initial_path, search: bootstrap.initial_query });
    const [shellRefresh, setShellRefresh] = useState(0);
    const shell = useJsonResource(`${bootstrap.api_root}/app-shell`, [route.path, route.search, shellRefresh]);
    useEffect(() => {
      const onPopState = () => setRoute(currentRoute());
      window.addEventListener("popstate", onPopState);
      return () => window.removeEventListener("popstate", onPopState);
    }, []);
    const navigate = (path) => {
      window.history.pushState({}, "", path);
      setRoute(currentRoute());
    };
    const refreshShell = () => setShellRefresh((value) => value + 1);
    const appChrome = shell.data?.app || {};
    const nav = appChrome.nav ?? [
      { label: "Hub", href: "/hub" },
      { label: "Studio", href: "/studio" },
      { label: "Playground", href: "/playground" },
      { label: "Observatory", href: "/observatory" },
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
        label: "Local LLM",
        value: shell.data?.environment?.local_llm?.healthy ? "Healthy" : "Unavailable",
        status: shell.data?.environment?.local_llm?.healthy ? "healthy" : "unavailable",
        detail: shell.data?.environment?.local_llm?.base_url || shell.data?.environment?.local_llm?.error || "Unavailable"
      },
      { key: "app-db", label: "App DB", value: shell.data?.environment?.app_db || "\u2014" }
    ];
    let page;
    if (route.path === "/" || route.path === "/hub") {
      page = /* @__PURE__ */ React.createElement(HubPage, { shell: shell.data, navigate });
    } else if (route.path === "/start") {
      page = /* @__PURE__ */ React.createElement(StartPage, { shell: shell.data, navigate, onMutate: refreshShell });
    } else if (route.path === "/runs" || route.path === "/observatory") {
      page = /* @__PURE__ */ React.createElement(RunsPage, { route, navigate });
    } else if (route.path === "/playground") {
      page = /* @__PURE__ */ React.createElement(PlaygroundPage, { route, shell: shell.data, navigate, onMutate: refreshShell });
    } else if (route.path === "/operations") {
      page = /* @__PURE__ */ React.createElement(OperationsPage, { navigate, onMutate: refreshShell });
    } else if (route.path === "/advanced") {
      page = /* @__PURE__ */ React.createElement(AdvancedPage, null);
    } else if (route.path === "/studio" || route.path === "/workbench") {
      page = /* @__PURE__ */ React.createElement(WorkbenchPage, { route, shell: shell.data, navigate, onMutate: refreshShell });
    } else if (/^\/(?:runs|observatory)\/[^/]+\/compare\/[^/]+$/.test(route.path)) {
      const match = route.path.match(/^\/(?:runs|observatory)\/([^/]+)\/compare\/([^/]+)$/);
      page = /* @__PURE__ */ React.createElement(ComparePage, { candidateRunId: match[1], baselineRunId: match[2], navigate });
    } else if (/^\/workflows\/[^/]+$/.test(route.path)) {
      page = /* @__PURE__ */ React.createElement(WorkflowDetailPage, { workflowName: decodeURIComponent(route.path.split("/")[2]), navigate, onMutate: refreshShell });
    } else if (/^\/(?:runs|observatory)\/[^/]+$/.test(route.path)) {
      page = /* @__PURE__ */ React.createElement(RunDetailPage, { runId: route.path.split("/")[2], navigate, onMutate: refreshShell });
    } else {
      page = /* @__PURE__ */ React.createElement(WorkbenchPage, { route, shell: shell.data, navigate, onMutate: refreshShell });
    }
    return /* @__PURE__ */ React.createElement("div", { className: "app-shell" }, /* @__PURE__ */ React.createElement("section", { className: "panel shell-chrome" }, /* @__PURE__ */ React.createElement("header", { className: "topbar" }, /* @__PURE__ */ React.createElement("div", { className: "shell-copy-stack" }, /* @__PURE__ */ React.createElement("div", { className: "title-row" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, String(appChrome.name || "XRTM WebUI")), shell.data?.app?.version ? /* @__PURE__ */ React.createElement("span", { className: "version-pill" }, "v", String(shell.data.app.version)) : null), /* @__PURE__ */ React.createElement("h1", null, String(appChrome.subtitle || "Local forecasting cockpit")), /* @__PURE__ */ React.createElement("p", { className: "shell-copy" }, String(appChrome.summary || "File-backed runs, local workflows, and resumable SQLite state in one muted local shell.")), /* @__PURE__ */ React.createElement("div", { className: "meta-row shell-trust-row" }, trustCues.map((cue) => /* @__PURE__ */ React.createElement("span", { key: cue, className: "shell-trust-pill" }, cue)))), /* @__PURE__ */ React.createElement("div", { className: "shell-nav-stack" }, /* @__PURE__ */ React.createElement("div", { className: "title-row" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Primary lanes")), /* @__PURE__ */ React.createElement("nav", { className: "topnav", "aria-label": "Primary" }, nav.map((item) => {
      const active = isNavItemActive(route.path, String(item.href || "/"));
      return /* @__PURE__ */ React.createElement(
        "a",
        {
          key: item.href,
          className: active ? "nav-link active" : "nav-link",
          href: item.href,
          "aria-current": active ? "page" : void 0,
          onClick: (event) => {
            event.preventDefault();
            navigate(item.href);
          }
        },
        item.label
      );
    })))), shell.data ? /* @__PURE__ */ React.createElement("section", { className: "environment-strip", "aria-label": "Environment status" }, environmentCards.map((card) => /* @__PURE__ */ React.createElement("article", { key: String(card.key || card.label), className: "environment-card" }, /* @__PURE__ */ React.createElement("div", { className: "environment-card-head" }, /* @__PURE__ */ React.createElement("strong", null, card.label), card.status ? /* @__PURE__ */ React.createElement(StatusPill, { value: String(card.status) }) : null), /* @__PURE__ */ React.createElement("span", { className: "environment-card-value", title: String(card.value || "\u2014") }, card.value || "\u2014"), card.detail ? /* @__PURE__ */ React.createElement("span", { className: "environment-card-detail", title: String(card.detail) }, card.detail) : null))) : null), bootstrap.initial_error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Initial error", body: bootstrap.initial_error }) : null, shell.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "App shell error", body: shell.error }) : null, shell.loading && !shell.data ? /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading app shell" }) : null, /* @__PURE__ */ React.createElement("div", { className: "page-stack" }, page));
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
    const nextActions = hub.next_actions || [];
    const counts = hub.counts || shell?.overview?.counts || {};
    const latestRun = hub.latest_run || shell?.overview?.latest_run;
    const resumeTarget = hub.resume_target || shell?.overview?.resume_target || {};
    return /* @__PURE__ */ React.createElement("main", { className: "page-grid" }, /* @__PURE__ */ React.createElement("section", { className: "panel hero-panel" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, hero.eyebrow || "Hub"), /* @__PURE__ */ React.createElement("h2", null, hero.title || "Local-first Hub"), /* @__PURE__ */ React.createElement("p", null, hero.summary || "Start from a template, run locally, and inspect file-backed results without login or account setup."), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => navigate(String(doors[0]?.primary_cta?.href || "/playground")) }, String(doors[0]?.primary_cta?.label || "Open Playground")), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(String(doors[1]?.primary_cta?.href || "/studio")) }, String(doors[1]?.primary_cta?.label || "Open Studio")), resumeTarget.href ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(String(resumeTarget.href)) }, String(resumeTarget.label || "Resume")) : null)), /* @__PURE__ */ React.createElement("section", { className: "stats-grid" }, /* @__PURE__ */ React.createElement(MetricCard, { label: "Indexed runs", value: counts.runs ?? 0 }), /* @__PURE__ */ React.createElement(MetricCard, { label: "Workflows", value: counts.workflows ?? 0 }), /* @__PURE__ */ React.createElement(MetricCard, { label: "Starter templates", value: counts.templates ?? templates.length }), /* @__PURE__ */ React.createElement(MetricCard, { label: "Resume lane", value: resumeTarget.kind || "hub" })), /* @__PURE__ */ React.createElement("section", { className: "split-grid" }, doors.map((door) => /* @__PURE__ */ React.createElement("article", { key: String(door.key || door.label), className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, door.label), /* @__PURE__ */ React.createElement("h3", null, door.title)), /* @__PURE__ */ React.createElement(StatusPill, { value: String(door.status || "local") })), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, door.summary), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, door.primary_cta ? /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => navigate(String(door.primary_cta.href)) }, String(door.primary_cta.label)) : null, door.secondary_cta ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(String(door.secondary_cta.href)) }, String(door.secondary_cta.label)) : null)))), /* @__PURE__ */ React.createElement("section", { className: "split-grid" }, /* @__PURE__ */ React.createElement("section", { className: "panel section-stack", id: "workflow-config-fields" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Templates"), /* @__PURE__ */ React.createElement("h3", null, "Starter gallery"), /* @__PURE__ */ React.createElement("p", null, "Template cards reuse the existing workflow authoring catalog and open local-first routes."))), /* @__PURE__ */ React.createElement("div", { className: "workflow-list workflow-catalog" }, templates.map((template) => /* @__PURE__ */ React.createElement("article", { key: String(template.template_id), className: "workflow-tile" }, /* @__PURE__ */ React.createElement("div", { className: "workflow-tile-head" }, /* @__PURE__ */ React.createElement("strong", null, template.title), /* @__PURE__ */ React.createElement(StatusPill, { value: String(template.workflow_kind || "workflow") })), /* @__PURE__ */ React.createElement("span", { className: "workflow-note" }, template.description), /* @__PURE__ */ React.createElement("div", { className: "meta-row" }, (template.tags || []).slice(0, 3).map((tag) => /* @__PURE__ */ React.createElement("span", { key: tag }, tag))), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => navigate(String(template.playground_href || `/playground?context=template&template=${template.template_id}`)) }, "Open Playground"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(String(template.studio_href || `/studio?mode=template&template=${template.template_id}`)) }, "Open Studio"))))), !templates.length ? /* @__PURE__ */ React.createElement(EmptyState, { title: "No starter templates found", body: "The Hub could not load starter templates from the authoring catalog." }) : null), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Workflow catalog"), /* @__PURE__ */ React.createElement("h3", null, "Existing workflows"), /* @__PURE__ */ React.createElement("p", null, "Open a workflow in Playground for one-question exploration or Studio to inspect/create a local draft."))), /* @__PURE__ */ React.createElement("div", { className: "workflow-list workflow-catalog" }, workflows.map((workflow) => /* @__PURE__ */ React.createElement("article", { key: String(workflow.name), className: "workflow-tile" }, /* @__PURE__ */ React.createElement("div", { className: "workflow-tile-head" }, /* @__PURE__ */ React.createElement("strong", null, workflow.title || workflow.name), /* @__PURE__ */ React.createElement(SourceBadge, { source: String(workflow.source || "builtin") })), /* @__PURE__ */ React.createElement("span", null, workflow.name), /* @__PURE__ */ React.createElement("span", { className: "workflow-note" }, workflow.description || "Reusable workflow from the registry."), /* @__PURE__ */ React.createElement("dl", { className: "context-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Runtime"), /* @__PURE__ */ React.createElement("dd", null, workflow.runtime_provider || "mock")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Questions"), /* @__PURE__ */ React.createElement("dd", null, formatValue(workflow.question_limit)))), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => navigate(String(workflow.playground_href || `/playground?context=workflow&workflow=${workflow.name}`)) }, "Open Playground"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(String(workflow.studio_href || `/studio?workflow=${workflow.name}`)) }, "Open Studio"))))), !workflows.length ? /* @__PURE__ */ React.createElement(EmptyState, { title: "No workflows indexed", body: "Refresh the local workflow registry or create a draft in Studio." }) : null)), /* @__PURE__ */ React.createElement("section", { className: "split-grid" }, /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Recent activity"), /* @__PURE__ */ React.createElement("h3", null, "Latest local run"))), latestRun ? /* @__PURE__ */ React.createElement(RunCard, { run: latestRun, onOpen: () => navigate(`/runs/${latestRun.run_id}`) }) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No runs yet", body: "Open Playground or the first-success quickstart to create a local run history entry." })), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Local readiness"), /* @__PURE__ */ React.createElement("h3", null, "Status without account assumptions"))), /* @__PURE__ */ React.createElement("div", { className: "card-grid" }, readiness.map((item) => /* @__PURE__ */ React.createElement("article", { key: String(item.key || item.label), className: "info-card" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("strong", null, item.label), /* @__PURE__ */ React.createElement(StatusPill, { value: String(item.status || "ready") })), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, item.value), /* @__PURE__ */ React.createElement("span", { className: "workflow-note" }, item.detail)))), /* @__PURE__ */ React.createElement("div", { className: "action-list" }, nextActions.map((action) => /* @__PURE__ */ React.createElement("div", { key: String(action.label), className: "inline-action-card" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, action.label), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, action.description)), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(String(action.href)) }, "Open")))))));
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
    const [provider, setProvider] = useState("mock");
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
    useEffect(() => {
      const items = workflows.data?.items || [];
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
    return /* @__PURE__ */ React.createElement("main", { className: "page-grid" }, /* @__PURE__ */ React.createElement("section", { className: "panel hero-panel" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Start"), /* @__PURE__ */ React.createElement("h2", null, "Run first success without leaving the WebUI"), /* @__PURE__ */ React.createElement("p", null, "Use the provider-free quickstart, launch a bounded demo, or run a named workflow with the same product services used by the CLI."), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: launchRun, disabled: Boolean(busy) || mode === "workflow" && !selectedWorkflow }, busy || (mode === "start" ? "Run quickstart" : mode === "demo" ? "Run demo" : "Run workflow")), selectedWorkflow ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(`/workflows/${encodeURIComponent(selectedWorkflow)}`) }, "Open workflow detail") : null, shell?.overview?.latest_run?.run_id ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(`/runs/${shell.overview.latest_run.run_id}`) }, "Inspect latest run") : null)), notice ? /* @__PURE__ */ React.createElement(Message, { tone: notice.tone, title: notice.title, body: notice.body }) : null, result ? /* @__PURE__ */ React.createElement(RunLaunchResultCard, { result, navigate }) : null, /* @__PURE__ */ React.createElement("div", { className: "split-grid" }, /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Run controls"), /* @__PURE__ */ React.createElement("p", null, "Start small with the released baseline, then move to demo or named workflow execution."))), /* @__PURE__ */ React.createElement(
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
      mode !== "start" ? /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Provider"), /* @__PURE__ */ React.createElement("select", { value: provider, onChange: (event) => setProvider(event.target.value) }, /* @__PURE__ */ React.createElement("option", { value: "mock" }, "Provider-free baseline"), /* @__PURE__ */ React.createElement("option", { value: "local-llm" }, "Local OpenAI-compatible endpoint"))) : null,
      /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Question limit"), /* @__PURE__ */ React.createElement("input", { value: limit, onChange: (event) => setLimit(event.target.value) })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Baseline run"), /* @__PURE__ */ React.createElement("select", { value: baselineRunId, onChange: (event) => setBaselineRunId(event.target.value) }, /* @__PURE__ */ React.createElement("option", { value: "" }, "None"), (runs.data?.items || []).map((run) => /* @__PURE__ */ React.createElement("option", { key: run.run_id, value: run.run_id }, run.run_id))))),
      mode !== "start" && provider === "local-llm" ? /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Base URL"), /* @__PURE__ */ React.createElement("input", { value: baseUrl, placeholder: "http://localhost:8000/v1", onChange: (event) => setBaseUrl(event.target.value) })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Model"), /* @__PURE__ */ React.createElement("input", { value: model, placeholder: "your-model-id", onChange: (event) => setModel(event.target.value) }))) : null,
      mode !== "start" ? /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Max tokens"), /* @__PURE__ */ React.createElement("input", { value: maxTokens, onChange: (event) => setMaxTokens(event.target.value) })) : null,
      /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "User attribution"), /* @__PURE__ */ React.createElement("input", { value: user, placeholder: "Optional analyst or operator name", onChange: (event) => setUser(event.target.value) }))
    )), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Environment health"), /* @__PURE__ */ React.createElement("p", null, "Readiness, provider status, and the currently selected workflow stay visible before you launch anything."))), /* @__PURE__ */ React.createElement("div", { className: "stats-grid" }, /* @__PURE__ */ React.createElement(MetricCard, { label: "Ready checks passing", value: (health.data?.checks || []).filter((item) => item.ok).length }), /* @__PURE__ */ React.createElement(MetricCard, { label: "Checks total", value: (health.data?.checks || []).length }), /* @__PURE__ */ React.createElement(MetricCard, { label: "Local LLM healthy", value: String(Boolean(providers.data?.local_llm?.healthy)) })), health.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Health unavailable", body: health.error }) : null, (health.data?.checks || []).length ? /* @__PURE__ */ React.createElement("div", { className: "card-grid" }, (health.data?.checks || []).map((item) => /* @__PURE__ */ React.createElement("article", { key: item.name, className: "info-card" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("strong", null, item.name), /* @__PURE__ */ React.createElement(StatusPill, { value: item.ok ? "ready" : "failed" })), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, item.detail)))) : null, /* @__PURE__ */ React.createElement("div", { className: "provider-status-grid" }, /* @__PURE__ */ React.createElement("article", { className: "info-card" }, /* @__PURE__ */ React.createElement("h4", null, "Provider-free baseline"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, "Works out of the box for first success and deterministic smoke validation.")), /* @__PURE__ */ React.createElement("article", { className: "info-card" }, /* @__PURE__ */ React.createElement("h4", null, "Local OpenAI-compatible"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, providers.data?.local_llm?.healthy ? `Healthy at ${providers.data?.local_llm?.base_url || "configured endpoint"}.` : providers.data?.local_llm?.status || "Currently unavailable."))))), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Workflow guide"), /* @__PURE__ */ React.createElement("p", null, "Inspect the selected workflow before running it so the graph and expected artifacts stay explicit."))), workflowDetail.loading && !workflowDetail.data ? /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading workflow detail" }) : null, workflowDetail.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Workflow detail unavailable", body: workflowDetail.error }) : null, workflowDetail.data ? /* @__PURE__ */ React.createElement("div", { className: "split-grid" }, /* @__PURE__ */ React.createElement("section", { className: "section-stack" }, /* @__PURE__ */ React.createElement("article", { className: "info-card" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, workflowDetail.data.workflow?.title || workflowDetail.data.workflow?.name), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, workflowDetail.data.workflow?.description || "No description available.")), /* @__PURE__ */ React.createElement("span", { className: `source-pill ${workflowDetail.data.workflow?.source || "builtin"}` }, workflowDetail.data.workflow?.source || "builtin")), /* @__PURE__ */ React.createElement("dl", { className: "context-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Runtime provider"), /* @__PURE__ */ React.createElement("dd", null, workflowDetail.data.workflow?.runtime_provider || "mock")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Question limit"), /* @__PURE__ */ React.createElement("dd", null, workflowDetail.data.workflow?.question_limit || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Kind"), /* @__PURE__ */ React.createElement("dd", null, workflowDetail.data.workflow?.workflow_kind || "workflow")))), /* @__PURE__ */ React.createElement("article", { className: "info-card" }, /* @__PURE__ */ React.createElement("h4", null, "Explain"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, workflowExplain.data?.explanation?.summary || "Choose a workflow to load its explanation."), (workflowExplain.data?.explanation?.runtime_requirements || []).length ? /* @__PURE__ */ React.createElement("ul", { className: "guidance-list" }, (workflowExplain.data?.explanation?.runtime_requirements || []).map((item) => /* @__PURE__ */ React.createElement("li", { key: item }, item))) : null)), /* @__PURE__ */ React.createElement("section", { className: "section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "canvas-grid" }, (workflowDetail.data.canvas?.nodes || []).map((node) => /* @__PURE__ */ React.createElement("article", { key: node.name, className: "canvas-node" }, /* @__PURE__ */ React.createElement("strong", null, node.name), /* @__PURE__ */ React.createElement("span", null, node.kind), /* @__PURE__ */ React.createElement("span", null, node.description || node.implementation || "No description"), /* @__PURE__ */ React.createElement(StatusPill, { value: node.status || "ready" })))))) : null));
  }
  function WorkflowDetailPage({
    workflowName,
    navigate,
    onMutate
  }) {
    const detail = useJsonResource(`${bootstrap.api_root}/workflows/${encodeURIComponent(workflowName)}`, [workflowName]);
    const explain = useJsonResource(`${bootstrap.api_root}/workflows/${encodeURIComponent(workflowName)}/explain`, [workflowName]);
    const runs = useJsonResource(`${bootstrap.api_root}/runs`, [workflowName]);
    const [provider, setProvider] = useState("");
    const [limit, setLimit] = useState("");
    const [baselineRunId, setBaselineRunId] = useState("");
    const [busy, setBusy] = useState(null);
    const [notice, setNotice] = useState(null);
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
          body: JSON.stringify({})
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
        const payload = {
          workflow_name: workflowName,
          write_report: true
        };
        if (provider) payload.provider = provider;
        if (limit) payload.limit = Number(limit);
        if (baselineRunId) payload.baseline_run_id = baselineRunId;
        const response = await requestJson(`${bootstrap.api_root}/runs`, { method: "POST", body: JSON.stringify(payload) });
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
    return /* @__PURE__ */ React.createElement("main", { className: "page-grid" }, /* @__PURE__ */ React.createElement("section", { className: "panel hero-panel" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Workflow"), /* @__PURE__ */ React.createElement("h2", null, detail.data.workflow?.title || detail.data.workflow?.name), /* @__PURE__ */ React.createElement("p", null, detail.data.workflow?.description || explain.data?.explanation?.summary || "Inspect, validate, and run this workflow from the WebUI."), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: runWorkflow, disabled: Boolean(busy) }, busy === "Running workflow" ? busy : "Run workflow"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: validateWorkflow, disabled: Boolean(busy) }, busy === "Validating workflow" ? busy : "Validate"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate("/start") }, "Back to start"))), notice ? /* @__PURE__ */ React.createElement(Message, { tone: notice.tone, title: notice.title, body: notice.body }) : null, /* @__PURE__ */ React.createElement("div", { className: "split-grid" }, /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Execution settings"), /* @__PURE__ */ React.createElement("p", null, "Override the released provider or question limit when you want a bounded comparison run."))), /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Provider"), /* @__PURE__ */ React.createElement("select", { value: provider, onChange: (event) => setProvider(event.target.value) }, /* @__PURE__ */ React.createElement("option", { value: "mock" }, "Provider-free baseline"), /* @__PURE__ */ React.createElement("option", { value: "local-llm" }, "Local OpenAI-compatible endpoint"))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Question limit"), /* @__PURE__ */ React.createElement("input", { value: limit, onChange: (event) => setLimit(event.target.value) }))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Baseline run for compare"), /* @__PURE__ */ React.createElement("select", { value: baselineRunId, onChange: (event) => setBaselineRunId(event.target.value) }, /* @__PURE__ */ React.createElement("option", { value: "" }, "None"), (runs.data?.items || []).map((run) => /* @__PURE__ */ React.createElement("option", { key: run.run_id, value: run.run_id }, run.run_id)))), /* @__PURE__ */ React.createElement("article", { className: "info-card" }, /* @__PURE__ */ React.createElement("h4", null, "Explain"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, explain.data?.explanation?.summary || "Workflow explanation unavailable."), /* @__PURE__ */ React.createElement("ul", { className: "guidance-list" }, (explain.data?.explanation?.expected_artifacts || []).map((item) => /* @__PURE__ */ React.createElement("li", { key: item }, item))))), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Canvas"), /* @__PURE__ */ React.createElement("p", null, "Graph nodes stay visible so you can inspect the release-safe workflow shape before running it."))), /* @__PURE__ */ React.createElement("div", { className: "canvas-grid" }, (detail.data.canvas?.nodes || []).map((node) => /* @__PURE__ */ React.createElement("article", { key: node.name, className: "canvas-node" }, /* @__PURE__ */ React.createElement("strong", null, node.name), /* @__PURE__ */ React.createElement("span", null, node.kind), /* @__PURE__ */ React.createElement("span", null, node.description || node.implementation || "No description"), /* @__PURE__ */ React.createElement(StatusPill, { value: node.status || "ready" })))))));
  }
  function OperationsPage({ navigate, onMutate }) {
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
    useEffect(() => {
      const items = runs.data?.items || [];
      if (!selectedArtifactRun && items.length) {
        setSelectedArtifactRun(String(items[0].run_id || ""));
      }
    }, [selectedArtifactRun, runs.data]);
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
            limit: template === "starter" ? void 0 : Number(profileLimit),
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
          body: JSON.stringify({ limit: Number(profileLimit), provider: profileProvider })
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
          body: JSON.stringify({ keep: Number(cleanupKeep) })
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
          body: JSON.stringify({ keep: Number(cleanupKeep), confirm: "delete" })
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
    return /* @__PURE__ */ React.createElement("main", { className: "page-grid" }, /* @__PURE__ */ React.createElement("section", { className: "panel hero-panel" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Operations"), /* @__PURE__ */ React.createElement("h2", null, "Operate profiles, monitors, and artifact retention locally"), /* @__PURE__ */ React.createElement("p", null, "These controls cover the day-to-day operator loop without asking you to remember CLI flags.")), notice ? /* @__PURE__ */ React.createElement(Message, { tone: notice.tone, title: notice.title, body: notice.body }) : null, /* @__PURE__ */ React.createElement("div", { className: "split-grid" }, /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Profiles"), /* @__PURE__ */ React.createElement("p", null, "Create repeatable local run presets, then launch them from the same page."))), /* @__PURE__ */ React.createElement("div", { className: "form-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Name"), /* @__PURE__ */ React.createElement("input", { value: profileName, onChange: (event) => setProfileName(event.target.value) })), /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Provider"), /* @__PURE__ */ React.createElement("select", { value: profileProvider, onChange: (event) => setProfileProvider(event.target.value) }, /* @__PURE__ */ React.createElement("option", { value: "mock" }, "Provider-free baseline"), /* @__PURE__ */ React.createElement("option", { value: "local-llm" }, "Local OpenAI-compatible endpoint"))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Question limit"), /* @__PURE__ */ React.createElement("input", { value: profileLimit, onChange: (event) => setProfileLimit(event.target.value) }))), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => void createProfile("custom"), disabled: Boolean(busy) }, "Save profile"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => void createProfile("starter"), disabled: Boolean(busy) }, "Save starter profile"))), /* @__PURE__ */ React.createElement("div", { className: "action-list" }, (profiles.data?.items || []).map((profile) => /* @__PURE__ */ React.createElement("div", { key: profile.name, className: "inline-action-card" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, profile.name), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, profile.provider, " \xB7 ", profile.limit, " questions")), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => setSelectedProfile(profile.name) }, "Show"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => void runProfile(profile.name) }, "Run"))))), profileDetail.data?.profile ? /* @__PURE__ */ React.createElement("article", { className: "info-card" }, /* @__PURE__ */ React.createElement("h4", null, "Selected profile"), /* @__PURE__ */ React.createElement("dl", { className: "context-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Provider"), /* @__PURE__ */ React.createElement("dd", null, profileDetail.data.profile.provider)), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Limit"), /* @__PURE__ */ React.createElement("dd", null, profileDetail.data.profile.limit)), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Runs dir"), /* @__PURE__ */ React.createElement("dd", null, profileDetail.data.profile.runs_dir)))) : null), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Monitors"), /* @__PURE__ */ React.createElement("p", null, "Start a monitor, run a cycle, and manage its lifecycle from one place."))), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => void createMonitor(), disabled: Boolean(busy) }, "Start monitor")), /* @__PURE__ */ React.createElement("div", { className: "action-list" }, (monitors.data?.items || []).map((monitor) => /* @__PURE__ */ React.createElement("div", { key: monitor.run_id, className: "inline-action-card" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, monitor.run_id), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, monitor.status, " \xB7 ", monitor.provider || "provider-free")), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => setSelectedMonitor(monitor.run_id) }, "Show"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => void mutateMonitor(monitor.run_id, "run-once") }, "Run once"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => void mutateMonitor(monitor.run_id, "pause") }, "Pause"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => void mutateMonitor(monitor.run_id, "resume") }, "Resume"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => void mutateMonitor(monitor.run_id, "halt") }, "Halt"))))), monitorDetail.data?.monitor ? /* @__PURE__ */ React.createElement("article", { className: "info-card" }, /* @__PURE__ */ React.createElement("h4", null, "Selected monitor"), /* @__PURE__ */ React.createElement("dl", { className: "context-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Status"), /* @__PURE__ */ React.createElement("dd", null, monitorDetail.data.monitor.status)), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Cycles"), /* @__PURE__ */ React.createElement("dd", null, monitorDetail.data.monitor.cycles)), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Watches"), /* @__PURE__ */ React.createElement("dd", null, (monitorDetail.data.monitor.watches || []).length)))) : null)), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Artifacts and retention"), /* @__PURE__ */ React.createElement("p", null, "Inspect artifact inventory for any run, preview cleanup, then confirm deletion explicitly."))), /* @__PURE__ */ React.createElement("div", { className: "three-column-grid" }, /* @__PURE__ */ React.createElement("section", { className: "section-stack" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Run"), /* @__PURE__ */ React.createElement("select", { value: selectedArtifactRun, onChange: (event) => setSelectedArtifactRun(event.target.value) }, (runs.data?.items || []).map((run) => /* @__PURE__ */ React.createElement("option", { key: run.run_id, value: run.run_id }, run.run_id)))), artifactDetail.data ? /* @__PURE__ */ React.createElement("ul", { className: "artifact-list" }, (artifactDetail.data.artifacts || []).map((item) => /* @__PURE__ */ React.createElement("li", { key: item.name }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, item.name), /* @__PURE__ */ React.createElement("span", null, item.path)), /* @__PURE__ */ React.createElement("span", { className: `availability-pill ${item.exists ? "available" : "missing"}` }, item.exists ? "Present" : "Missing")))) : null), /* @__PURE__ */ React.createElement("section", { className: "section-stack" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Keep newest run directories"), /* @__PURE__ */ React.createElement("input", { value: cleanupKeep, onChange: (event) => setCleanupKeep(event.target.value) })), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => void previewCleanup(), disabled: Boolean(busy) }, "Preview cleanup"), /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => void runCleanup(), disabled: Boolean(busy) }, "Delete previewed runs"))), /* @__PURE__ */ React.createElement("section", { className: "section-stack" }, cleanupPreview ? /* @__PURE__ */ React.createElement("article", { className: "info-card" }, /* @__PURE__ */ React.createElement("h4", null, "Cleanup preview"), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, cleanupPreview.count || 0, " run directories would be removed while keeping the newest ", cleanupPreview.keep, "."), /* @__PURE__ */ React.createElement("ul", { className: "guidance-list compact-list" }, (cleanupPreview.items || []).map((item) => /* @__PURE__ */ React.createElement("li", { key: item.run_id }, item.run_id)))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No cleanup preview yet", body: "Preview retention first so deletion stays explicit." })))));
  }
  function AdvancedPage() {
    const cards = [
      {
        title: "Validation and corpora",
        status: "advanced",
        body: "Validation suites, corpora preparation, and release-gate validation remain advanced lanes with explicit safety and runtime rules."
      },
      {
        title: "Benchmark and stress",
        status: "advanced",
        body: "Benchmark compare, cache, and stress flows need heavier validation and should not be mistaken for first-success paths."
      },
      {
        title: "Performance and competition",
        status: "experimental",
        body: "Performance budgets and competition dry-runs are visible here so advanced users can see the lane without overselling it to newcomers."
      }
    ];
    return /* @__PURE__ */ React.createElement("main", { className: "page-grid" }, /* @__PURE__ */ React.createElement("section", { className: "panel hero-panel" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Advanced"), /* @__PURE__ */ React.createElement("h2", null, "Visible advanced lanes with honest status labels"), /* @__PURE__ */ React.createElement("p", null, "The product should not hide advanced capabilities, but it also should not present them as newcomer defaults.")), /* @__PURE__ */ React.createElement("section", { className: "card-grid" }, cards.map((card) => /* @__PURE__ */ React.createElement("article", { key: card.title, className: "info-card" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("strong", null, card.title), /* @__PURE__ */ React.createElement(StatusPill, { value: card.status })), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, card.body)))));
  }
  function RunsPage({ route, navigate }) {
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
    return /* @__PURE__ */ React.createElement("main", { className: "page-grid" }, /* @__PURE__ */ React.createElement("section", { className: "panel hero-panel page-lead" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Observatory"), /* @__PURE__ */ React.createElement("h2", null, resource.data?.surface?.title || "Observatory run inspector"), /* @__PURE__ */ React.createElement("p", null, resource.data?.surface?.summary || "Filter file-backed run history, drill into results, and continue through reports, exports, and comparisons."), /* @__PURE__ */ React.createElement(
      "form",
      {
        className: "filter-row",
        onSubmit: (event) => {
          event.preventDefault();
          const next = new URLSearchParams();
          if (query) next.set("q", query);
          if (status) next.set("status", status);
          if (provider) next.set("provider", provider);
          navigate(next.toString() ? `/runs?${next.toString()}` : "/runs");
        }
      },
      /* @__PURE__ */ React.createElement("input", { placeholder: "Search runs or workflow names", value: query, onChange: (event) => setQuery(event.target.value) }),
      /* @__PURE__ */ React.createElement("input", { placeholder: "Status", value: status, onChange: (event) => setStatus(event.target.value) }),
      /* @__PURE__ */ React.createElement("input", { placeholder: "Provider", value: provider, onChange: (event) => setProvider(event.target.value) }),
      /* @__PURE__ */ React.createElement("button", { className: "secondary-button", type: "submit" }, "Filter")
    )), (resource.data?.summary_cards || []).length ? /* @__PURE__ */ React.createElement("section", { className: "stats-grid" }, (resource.data?.summary_cards || []).map((card) => /* @__PURE__ */ React.createElement(MetricCard, { key: card.label, label: card.label, value: card.value }))) : null, resource.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Runs unavailable", body: resource.error }) : null, resource.loading ? /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading runs" }) : null, /* @__PURE__ */ React.createElement("section", { className: "panel" }, /* @__PURE__ */ React.createElement("table", { className: "data-table" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", null, /* @__PURE__ */ React.createElement("th", null, "Run"), /* @__PURE__ */ React.createElement("th", null, "Workflow"), /* @__PURE__ */ React.createElement("th", null, "Status"), /* @__PURE__ */ React.createElement("th", null, "Provider"), /* @__PURE__ */ React.createElement("th", null, "Updated"))), /* @__PURE__ */ React.createElement("tbody", null, (resource.data?.items || []).map((run) => /* @__PURE__ */ React.createElement("tr", { key: run.run_id }, /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement("a", { href: `/runs/${run.run_id}`, onClick: (event) => {
      event.preventDefault();
      navigate(`/runs/${run.run_id}`);
    } }, run.run_id)), /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement("div", { className: "table-primary" }, run.observatory?.label || run.workflow?.title || run.workflow?.name || "Unknown workflow"), /* @__PURE__ */ React.createElement("div", { className: "table-secondary" }, run.observatory?.summary || run.workflow?.name || "\u2014")), /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement(StatusPill, { value: run.status })), /* @__PURE__ */ React.createElement("td", null, run.provider), /* @__PURE__ */ React.createElement("td", null, run.updated_at || "\u2014"))))), !resource.loading && !(resource.data?.items || []).length ? /* @__PURE__ */ React.createElement(
      EmptyState,
      {
        title: resource.data?.empty_state?.title || "No runs match the current filter",
        body: resource.data?.empty_state?.body || "Try clearing filters or running a workflow from the workbench."
      }
    ) : null));
  }
  function RunDetailPage({
    runId,
    navigate,
    onMutate
  }) {
    const resource = useJsonResource(`${bootstrap.api_root}/runs/${runId}`, [runId]);
    const [busy, setBusy] = useState(null);
    const [notice, setNotice] = useState(null);
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
    return /* @__PURE__ */ React.createElement("main", { className: "page-grid detail-shell" }, notice ? /* @__PURE__ */ React.createElement(Message, { tone: notice.tone, title: notice.title, body: notice.body }) : null, /* @__PURE__ */ React.createElement("section", { className: "panel hero-panel detail-hero" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Observatory / Run inspector"), /* @__PURE__ */ React.createElement("h2", null, run.hero?.title || run.workflow?.title || run.run_id), /* @__PURE__ */ React.createElement("p", null, run.hero?.summary || run.observatory?.summary || "Inspect the latest run summary, question rows, trace, and artifacts."), /* @__PURE__ */ React.createElement("div", { className: "meta-row" }, /* @__PURE__ */ React.createElement(StatusPill, { value: run.run?.status }), /* @__PURE__ */ React.createElement("span", null, run.run?.provider || "Unknown provider"), /* @__PURE__ */ React.createElement("span", null, run.run?.updated_at || run.run?.completed_at || "\u2014")), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => navigate(run.observatory?.runs_href || "/runs") }, "Back to Observatory"), run.recommended_compare ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(run.recommended_compare.href) }, "Compare with ", run.recommended_compare.run_id) : null, report.available ? /* @__PURE__ */ React.createElement("a", { className: "secondary-link", href: report.href, target: "_blank", rel: "noreferrer" }, "Open HTML report") : null, /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: generateReport, disabled: busy === "Generating report" }, busy === "Generating report" ? busy : report.available ? "Regenerate report" : "Generate report"), (run.artifacts?.exports || [
      { label: "Export JSON", href: `${bootstrap.api_root}/runs/${runId}/export?format=json` },
      { label: "Export CSV", href: `${bootstrap.api_root}/runs/${runId}/export?format=csv` }
    ]).map((item) => /* @__PURE__ */ React.createElement("a", { key: item.label, className: "secondary-link", href: item.href }, item.label)))), /* @__PURE__ */ React.createElement("section", { className: "stats-grid" }, (run.summary_cards || []).map((card) => /* @__PURE__ */ React.createElement(MetricCard, { key: card.label, label: card.label, value: card.value }))), /* @__PURE__ */ React.createElement("div", { className: "detail-grid" }, /* @__PURE__ */ React.createElement("div", { className: "detail-main" }, /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Readable summary"), /* @__PURE__ */ React.createElement("p", null, "Grouped metadata keeps the run context visible without opening raw JSON."))), /* @__PURE__ */ React.createElement("div", { className: "info-grid" }, (run.metadata_groups || []).map((group) => /* @__PURE__ */ React.createElement(KeyValueGroup, { key: group.title, group })))), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Probability & result summary"), /* @__PURE__ */ React.createElement("p", null, "Forecast probabilities, resolution coverage, and existing run result fields in one Observatory review block."))), (run.probability_summary?.cards || []).length ? /* @__PURE__ */ React.createElement("div", { className: "stats-grid" }, (run.probability_summary?.cards || []).map((card) => /* @__PURE__ */ React.createElement(MetricCard, { key: card.label, label: card.label, value: card.label.toLowerCase().includes("probability") ? formatProbability(card.value) : card.value }))) : null, (run.probability_summary?.groups || []).some((group) => (group.items || []).length) ? /* @__PURE__ */ React.createElement("div", { className: "info-grid" }, (run.probability_summary?.groups || []).filter((group) => (group.items || []).length).map((group) => /* @__PURE__ */ React.createElement(KeyValueGroup, { key: group.title, group }))) : /* @__PURE__ */ React.createElement(EmptyState, { title: run.probability_summary?.empty_state?.title || "No probability rows", body: run.probability_summary?.empty_state?.body || "This run does not include probability rows." })), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Score summary"), /* @__PURE__ */ React.createElement("p", null, "Existing eval/train outputs stay explicit when they are present."))), (run.score_summary?.groups || []).length ? /* @__PURE__ */ React.createElement("div", { className: "info-grid" }, (run.score_summary?.groups || []).map((group) => /* @__PURE__ */ React.createElement(KeyValueGroup, { key: group.title, group }))) : /* @__PURE__ */ React.createElement(EmptyState, { title: run.score_summary?.empty_state?.title || "No score outputs", body: run.score_summary?.empty_state?.body || "This run does not include evaluation or training score fields." })), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Results snapshot"), /* @__PURE__ */ React.createElement("p", null, "Core quality, training, and usage metrics in one place."))), (run.result_groups || []).length ? /* @__PURE__ */ React.createElement("div", { className: "info-grid" }, (run.result_groups || []).map((group) => /* @__PURE__ */ React.createElement(KeyValueGroup, { key: group.title, group }))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No result summary yet", body: "This run does not include evaluation or training summary fields." })), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Forecast table"), /* @__PURE__ */ React.createElement("p", null, "Question titles, forecast values, and scoring context for quick review.")), /* @__PURE__ */ React.createElement("span", { className: "section-count" }, run.forecast_table?.count || 0, " rows")), /* @__PURE__ */ React.createElement(RunForecastTable, { rows: run.forecast_table?.rows || [], emptyState: run.forecast_table?.empty_state }))), /* @__PURE__ */ React.createElement("aside", { className: "detail-sidebar" }, /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Guided actions"), /* @__PURE__ */ React.createElement("p", null, "Jump to the next useful surface from this run."))), /* @__PURE__ */ React.createElement("div", { className: "action-stack" }, (run.guided_actions || []).map((action) => /* @__PURE__ */ React.createElement("button", { key: action.label, className: "secondary-button action-button", onClick: () => navigate(action.href) }, action.label)))), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Report & artifacts"), /* @__PURE__ */ React.createElement("p", null, "Use the report when available; fall back to raw files when it is not."))), /* @__PURE__ */ React.createElement(ReportCard, { report }), /* @__PURE__ */ React.createElement(ArtifactList, { items: run.artifacts?.items || [] }), (run.artifacts?.exports || []).length ? /* @__PURE__ */ React.createElement("div", { className: "button-row" }, (run.artifacts?.exports || []).map((item) => /* @__PURE__ */ React.createElement("a", { key: item.label, className: "secondary-link", href: item.href }, item.label))) : null, Object.keys(run.artifacts?.raw || {}).length ? /* @__PURE__ */ React.createElement("details", { className: "artifact-preview" }, /* @__PURE__ */ React.createElement("summary", null, "Raw structured payloads"), Object.entries(run.artifacts?.raw || {}).map(([key, value]) => /* @__PURE__ */ React.createElement(ArtifactPreview, { key, label: key, value }))) : null), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Compare next"), /* @__PURE__ */ React.createElement("p", null, "Pick a baseline to understand whether the candidate moved the right metrics."))), (run.baseline_candidates || []).length ? /* @__PURE__ */ React.createElement("div", { className: "action-list" }, (run.baseline_candidates || []).map((item) => /* @__PURE__ */ React.createElement("button", { key: item.run_id, className: "secondary-button action-button", onClick: () => navigate(item.href) }, item.label || item.run_id))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No comparison candidates", body: "Run another workflow revision to unlock side-by-side comparison." })), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Execution trace"), /* @__PURE__ */ React.createElement("p", null, "Ordered graph trace or sandbox inspection steps where the run persisted them."))), (run.execution_trace?.items || []).length ? /* @__PURE__ */ React.createElement("ul", { className: "timeline-list" }, (run.execution_trace?.items || []).map((item, index) => /* @__PURE__ */ React.createElement("li", { key: `${item.node_id}-${index}` }, /* @__PURE__ */ React.createElement("strong", null, item.order, ". ", item.label || item.node_id), /* @__PURE__ */ React.createElement("span", null, item.node_id, " \xB7 ", item.node_type || "node", " \xB7 ", item.status || "observed"), item.preview ? /* @__PURE__ */ React.createElement("span", { className: "table-secondary" }, item.preview) : null))) : /* @__PURE__ */ React.createElement(EmptyState, { title: run.execution_trace?.empty_state?.title || "No execution trace", body: run.execution_trace?.empty_state?.body || "This run did not persist graph trace rows." })), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Uncertainty"), /* @__PURE__ */ React.createElement("p", null, "Shown only when the artifacts include enough uncertainty or reliability data."))), run.uncertainty_summary?.available ? /* @__PURE__ */ React.createElement("div", { className: "info-grid" }, (run.uncertainty_summary?.groups || []).map((group) => /* @__PURE__ */ React.createElement(KeyValueGroup, { key: group.title, group }))) : /* @__PURE__ */ React.createElement(EmptyState, { title: run.uncertainty_summary?.empty_state?.title || "Uncertainty unavailable", body: run.uncertainty_summary?.empty_state?.body || "No uncertainty fields were present in the current read model." })))));
  }
  function ComparePage({ candidateRunId, baselineRunId, navigate }) {
    const resource = useJsonResource(`${bootstrap.api_root}/runs/${candidateRunId}/compare/${baselineRunId}`, [candidateRunId, baselineRunId]);
    if (resource.error) {
      return /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Comparison unavailable", body: resource.error });
    }
    if (resource.loading || !resource.data) {
      return /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading comparison" });
    }
    const compare = resource.data;
    return /* @__PURE__ */ React.createElement("main", { className: "page-grid compare-shell" }, /* @__PURE__ */ React.createElement("section", { className: `panel hero-panel compare-hero ${compare.verdict?.tone || "neutral"}` }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Compare"), /* @__PURE__ */ React.createElement("h2", null, compare.verdict?.headline || compare.verdict?.label || "Comparison ready"), /* @__PURE__ */ React.createElement("p", null, compare.verdict?.summary || "Review grouped metrics and question-level changes before choosing the next step."), /* @__PURE__ */ React.createElement("div", { className: "compare-run-grid" }, /* @__PURE__ */ React.createElement(CompareRunCard, { label: "Candidate", run: compare.run_pair?.candidate }), /* @__PURE__ */ React.createElement(CompareRunCard, { label: "Baseline", run: compare.run_pair?.baseline })), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(`/runs/${candidateRunId}`) }, "Inspect candidate run"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(`/runs/${baselineRunId}`) }, "Inspect baseline run"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate("/workbench") }, "Back to workbench"))), /* @__PURE__ */ React.createElement("section", { className: "stats-grid" }, (compare.summary_cards || []).map((card) => /* @__PURE__ */ React.createElement(MetricCard, { key: card.label, label: card.label, value: card.value }))), /* @__PURE__ */ React.createElement("div", { className: "compare-grid" }, /* @__PURE__ */ React.createElement("div", { className: "compare-main" }, /* @__PURE__ */ React.createElement("section", { className: `panel verdict-panel ${compare.verdict?.tone || "neutral"}` }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Verdict"), /* @__PURE__ */ React.createElement("h3", null, compare.verdict?.label || "No verdict yet"), /* @__PURE__ */ React.createElement("p", null, compare.verdict?.next_step || "Open the run detail pages to continue reviewing."), /* @__PURE__ */ React.createElement("div", { className: "action-list" }, (compare.next_actions || []).map((action) => /* @__PURE__ */ React.createElement("button", { key: action.label, className: "secondary-button action-button", onClick: () => navigate(action.href) }, /* @__PURE__ */ React.createElement("span", null, action.label), action.description ? /* @__PURE__ */ React.createElement("small", null, action.description) : null)))), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Metric comparison"), /* @__PURE__ */ React.createElement("p", null, "High-level metrics grouped by profile, coverage, efficiency, and quality."))), (compare.row_groups || []).map((group) => /* @__PURE__ */ React.createElement("section", { key: group.title, className: "compare-group" }, /* @__PURE__ */ React.createElement("h4", null, group.title), /* @__PURE__ */ React.createElement("table", { className: "data-table" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", null, /* @__PURE__ */ React.createElement("th", null, "Metric"), /* @__PURE__ */ React.createElement("th", null, "Baseline"), /* @__PURE__ */ React.createElement("th", null, "Candidate"), /* @__PURE__ */ React.createElement("th", null, "Interpretation"))), /* @__PURE__ */ React.createElement("tbody", null, (group.rows || []).map((row) => /* @__PURE__ */ React.createElement("tr", { key: row.metric, className: `tone-${row.tone || "neutral"}` }, /* @__PURE__ */ React.createElement("td", null, row.label || row.metric), /* @__PURE__ */ React.createElement("td", null, formatValue(row.left)), /* @__PURE__ */ React.createElement("td", null, formatValue(row.right)), /* @__PURE__ */ React.createElement("td", null, row.interpretation)))))))), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Question-level changes"), /* @__PURE__ */ React.createElement("p", null, "Question titles stay visible so coverage gaps and score shifts are easy to read."))), /* @__PURE__ */ React.createElement(CompareQuestionTable, { rows: compare.question_rows || [] }))), /* @__PURE__ */ React.createElement("aside", { className: "compare-sidebar" }, /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Report availability"), /* @__PURE__ */ React.createElement("p", null, "Open each run report directly when it exists."))), /* @__PURE__ */ React.createElement(ReportCard, { report: compare.run_pair?.candidate?.report }), /* @__PURE__ */ React.createElement(ReportCard, { report: compare.run_pair?.baseline?.report })))));
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
    const traceByNodeId = useMemo(() => Object.fromEntries(orderedTrace.map((item) => [String(item.node_id), item])), [orderedTrace]);
    const graphTraceArtifact = lastResult?.graph_trace_artifact || {};
    const readyToRun = Boolean(questionPrompt.trim() && (contextType === "workflow" ? workflowName : templateId));
    const latestRun = shell?.overview?.latest_run;
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
    return /* @__PURE__ */ React.createElement("main", { className: "page-grid playground-shell" }, resource.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Playground unavailable", body: resource.error }) : null, notice ? /* @__PURE__ */ React.createElement(Message, { tone: notice.tone, title: notice.title, body: notice.body }) : null, resource.loading && !resource.data ? /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading playground" }) : null, /* @__PURE__ */ React.createElement("section", { className: "panel hero-panel playground-hero" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Playground"), /* @__PURE__ */ React.createElement("h2", null, "Run one bounded exploratory question without opening the workbench canvas"), /* @__PURE__ */ React.createElement("p", null, "Choose a workflow or starter template, ask one custom question, then inspect ordered step outputs from the shared sandbox backend. This surface is for exploratory execution only; safe authoring still lives in the workbench."), /* @__PURE__ */ React.createElement("div", { className: "meta-row" }, /* @__PURE__ */ React.createElement("span", null, lastResult?.labeling?.display_label || "Exploratory playground session"), /* @__PURE__ */ React.createElement(StatusPill, { value: String(lastResult?.run?.status || session?.status || "playground-ready") }), /* @__PURE__ */ React.createElement("span", null, contextPreview?.title || contextPreview?.reference_name || "Choose a context")), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: runPlayground, disabled: Boolean(busy) || !readyToRun }, busy === "Running playground session" ? busy : "Run exploratory session"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: persistPlaygroundState, disabled: Boolean(busy) }, busy === "Updating playground state" ? busy : "Update playground state"), lastResult?.run_id ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(`/runs/${lastResult.run_id}`) }, "Inspect full run") : latestRun?.run_id ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(`/runs/${latestRun.run_id}`) }, "Inspect latest run") : null, /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate("/workbench") }, "Open workbench"))), /* @__PURE__ */ React.createElement("section", { className: "playground-grid" }, /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "1. Context"), /* @__PURE__ */ React.createElement("h3", null, "Choose workflow or starter template")), /* @__PURE__ */ React.createElement("p", { className: "section-copy" }, "The playground reuses the same workflow registry and starter templates as the shared authoring stack.")), /* @__PURE__ */ React.createElement("div", { className: "creation-mode-row" }, [
      { key: "workflow", label: "Workflow", detail: "Reuse a saved workflow directly." },
      { key: "template", label: "Template", detail: "Start from a starter template without opening the workbench." }
    ].map((item) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: item.key,
        type: "button",
        className: contextType === item.key ? "workflow-tile active" : "workflow-tile",
        onClick: () => setContextType(item.key)
      },
      /* @__PURE__ */ React.createElement("strong", null, item.label),
      /* @__PURE__ */ React.createElement("span", { className: "workflow-note" }, item.detail)
    ))), contextType === "workflow" ? /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Workflow"), /* @__PURE__ */ React.createElement("select", { value: workflowName, onChange: (event) => setWorkflowName(event.target.value) }, workflows.map((item) => /* @__PURE__ */ React.createElement("option", { key: item.name, value: item.name }, item.title || item.name)))) : /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Starter template"), /* @__PURE__ */ React.createElement("select", { value: templateId, onChange: (event) => setTemplateId(event.target.value) }, templates.map((item) => /* @__PURE__ */ React.createElement("option", { key: item.template_id, value: item.template_id }, item.title))))), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "2. Question"), /* @__PURE__ */ React.createElement("h3", null, "Enter one custom question")), /* @__PURE__ */ React.createElement("p", { className: "section-copy" }, "Keep the loop bounded: one custom exploratory question only in this WebUI pass.")), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Question prompt"), /* @__PURE__ */ React.createElement("textarea", { className: "text-area-input", value: questionPrompt, onChange: (event) => setQuestionPrompt(event.target.value), placeholder: "Will the exploratory workflow produce a useful answer for this question?" })), /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Optional title"), /* @__PURE__ */ React.createElement("input", { value: questionTitle, onChange: (event) => setQuestionTitle(event.target.value), placeholder: "Auto-derived from the prompt when blank" })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Optional resolution criteria"), /* @__PURE__ */ React.createElement("input", { value: resolutionCriteria, onChange: (event) => setResolutionCriteria(event.target.value), placeholder: "Short read-only context for later inspection" }))))), /* @__PURE__ */ React.createElement("section", { className: "playground-grid" }, /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "3. Preview"), /* @__PURE__ */ React.createElement("h3", null, "Selected playground context"))), resource.data?.context_error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Context unavailable", body: resource.data.context_error }) : contextPreview ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("div", { className: "surface-card" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, contextPreview.title || contextPreview.reference_name), /* @__PURE__ */ React.createElement("p", null, contextPreview.description || "No context description available.")), /* @__PURE__ */ React.createElement("span", { className: "source-pill local" }, contextPreview.context_type)), /* @__PURE__ */ React.createElement("dl", { className: "context-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Reference"), /* @__PURE__ */ React.createElement("dd", null, contextPreview.reference_name)), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Runtime"), /* @__PURE__ */ React.createElement("dd", null, contextPreview.runtime?.provider || "mock")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Question limit"), /* @__PURE__ */ React.createElement("dd", null, formatValue(contextPreview.questions_limit))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Entry node"), /* @__PURE__ */ React.createElement("dd", null, contextPreview.entry || "\u2014")))), /* @__PURE__ */ React.createElement("section", { className: "guidance-section" }, /* @__PURE__ */ React.createElement("h3", null, "Graph node identity"), /* @__PURE__ */ React.createElement(
      PlaygroundGraphTracePreview,
      {
        canvas: contextPreview.canvas || {},
        traceItems: [],
        activeNodeId: "",
        onSelectNode: () => void 0
      }
    )), /* @__PURE__ */ React.createElement("section", { className: "guidance-section" }, /* @__PURE__ */ React.createElement("h3", null, "Playground contract"), /* @__PURE__ */ React.createElement("ul", { className: "guidance-list" }, (resource.data?.guidance?.limitations || []).map((item) => /* @__PURE__ */ React.createElement("li", { key: item }, item))))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "Choose a context", body: "Select a workflow or starter template to preview the playground context." })), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "4. Status"), /* @__PURE__ */ React.createElement("h3", null, "Journey + next step"))), /* @__PURE__ */ React.createElement("ol", { className: "step-list step-rail" }, (resource.data?.step_state || []).map((step) => /* @__PURE__ */ React.createElement("li", { key: step.key, className: `step-item${step.locked ? " locked" : ""}` }, /* @__PURE__ */ React.createElement("div", { className: "step-head" }, /* @__PURE__ */ React.createElement("strong", null, step.label), /* @__PURE__ */ React.createElement("span", { className: `step-status ${step.locked ? "locked" : "current"}` }, step.locked ? "Locked" : "Ready")), /* @__PURE__ */ React.createElement("span", null, step.description)))), /* @__PURE__ */ React.createElement("section", { className: "next-step-card" }, /* @__PURE__ */ React.createElement("strong", null, resource.data?.guidance?.next_step?.title || "Run one exploratory session"), /* @__PURE__ */ React.createElement("p", null, resource.data?.guidance?.next_step?.detail || "Update the playground state, then run one exploratory question.")), lastResult?.save_back ? /* @__PURE__ */ React.createElement("details", { className: "artifact-preview" }, /* @__PURE__ */ React.createElement("summary", null, "Prepared save-back state (read-only)"), /* @__PURE__ */ React.createElement(ArtifactPreview, { label: "Workflow state", value: lastResult.save_back.workflow }), /* @__PURE__ */ React.createElement(ArtifactPreview, { label: "Profile state", value: lastResult.save_back.profile })) : null)), lastResult ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("section", { className: "stats-grid" }, (lastResult.summary_cards || []).map((card) => /* @__PURE__ */ React.createElement(MetricCard, { key: String(card.label), label: String(card.label), value: card.value }))), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "5. Graph trace"), /* @__PURE__ */ React.createElement("h3", null, "Executed nodes linked to graph identity")), /* @__PURE__ */ React.createElement(StatusPill, { value: String(resultTrace.source_label || "No trace rows") })), graphTraceArtifact.available === false && resultTrace.source === "sandbox" ? /* @__PURE__ */ React.createElement(
      Message,
      {
        tone: "warning",
        title: graphTraceArtifact.empty_state?.title || "No graph trace artifact",
        body: graphTraceArtifact.empty_state?.body || "Showing sandbox inspection steps without claiming a persisted graph_trace.jsonl artifact."
      }
    ) : null, /* @__PURE__ */ React.createElement(
      PlaygroundGraphTracePreview,
      {
        canvas: lastResult.canvas || contextPreview?.canvas || {},
        traceItems: orderedTrace,
        activeNodeId: String(activeStep?.node_id || ""),
        onSelectNode: selectTraceNode
      }
    ), orderedTrace.length ? /* @__PURE__ */ React.createElement("ol", { className: "node-trace-list" }, orderedTrace.map((item) => /* @__PURE__ */ React.createElement("li", { key: `${item.canvas_node_id || item.node_id}-${item.order}` }, /* @__PURE__ */ React.createElement("span", { className: "trace-order" }, formatValue(item.order)), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, item.label || item.node_id), /* @__PURE__ */ React.createElement("span", null, item.canvas_node_id || `node:${item.node_id}`, " \xB7 ", item.node_id, " \xB7 ", item.status || "observed"))))) : /* @__PURE__ */ React.createElement(
      EmptyState,
      {
        title: resultTrace.empty_state?.title || graphTraceArtifact.empty_state?.title || "No execution trace",
        body: resultTrace.empty_state?.body || graphTraceArtifact.empty_state?.body || "This playground run did not persist trace rows."
      }
    )), /* @__PURE__ */ React.createElement("section", { className: "playground-grid" }, /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "6. Inspect"), /* @__PURE__ */ React.createElement("h3", null, "Ordered step outputs")), /* @__PURE__ */ React.createElement("span", { className: "section-count" }, steps.length, " steps")), /* @__PURE__ */ React.createElement("div", { className: "playground-step-list" }, steps.map((step) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: playgroundStepKey(step),
        type: "button",
        className: playgroundStepKey(step) === playgroundStepKey(activeStep || {}) ? "playground-step-button active" : "playground-step-button",
        onClick: () => setSelectedStepKey(playgroundStepKey(step))
      },
      /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("strong", null, formatValue(step.order), ". ", step.label || step.node_id), /* @__PURE__ */ React.createElement(StatusPill, { value: String(step.status || "completed") })),
      /* @__PURE__ */ React.createElement("span", { className: "workflow-note" }, traceByNodeId[String(step.node_id)]?.canvas_node_id || `node:${step.node_id}`, " \xB7 ", step.node_id, " \xB7 ", step.node_type || "node"),
      /* @__PURE__ */ React.createElement("span", null, step.output_preview || "No preview available.")
    )))), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Selected step"), /* @__PURE__ */ React.createElement("h3", null, activeStep?.label || activeStep?.node_id || "Read-only step detail"))), activeStep ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("dl", { className: "context-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Node ID"), /* @__PURE__ */ React.createElement("dd", null, activeStep.node_id)), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Node type"), /* @__PURE__ */ React.createElement("dd", null, activeStep.node_type || "node")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Status"), /* @__PURE__ */ React.createElement("dd", null, activeStep.status || "completed")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Order"), /* @__PURE__ */ React.createElement("dd", null, formatValue(activeStep.order))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Latency (seconds)"), /* @__PURE__ */ React.createElement("dd", null, formatValue(activeStep.latency_seconds))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Route"), /* @__PURE__ */ React.createElement("dd", null, formatValue(activeStep.route)))), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, activeStep.output_preview || "No step preview available."), /* @__PURE__ */ React.createElement(ArtifactPreview, { label: "Structured output", value: activeStep.output }), /* @__PURE__ */ React.createElement(ArtifactList, { items: (activeStep.artifacts || []).map((item) => ({ ...item, label: item.name, available: true })) }), /* @__PURE__ */ React.createElement("div", { className: "json-stack" }, Object.entries(activeStep.artifact_payloads || {}).map(([key, value]) => /* @__PURE__ */ React.createElement(ArtifactPreview, { key, label: key, value })))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No step output yet", body: "Run the playground session to inspect ordered node outputs here." }))), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Latest exploratory run"), /* @__PURE__ */ React.createElement("h3", null, lastResult.run_id))), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, lastResult.run_summary?.summary || lastResult.labeling?.notes?.[0] || "Use the playground for exploratory local analysis, not release-grade evidence."), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => navigate(`/runs/${lastResult.run_id}`) }, "Open run detail"), lastResult.report?.available ? /* @__PURE__ */ React.createElement("a", { className: "secondary-link", href: lastResult.report.href, target: "_blank", rel: "noreferrer" }, "Open report") : null))) : null);
  }
  function WorkbenchPage({ route, shell, navigate, onMutate }) {
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
    const [edgeDraftFrom, setEdgeDraftFrom] = useState("");
    const [localPositions, setLocalPositions] = useState({});
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
    useEffect(() => {
      setActionNotice(null);
    }, [draftId, selectedWorkflow]);
    useEffect(() => {
      setCreateForm((current) => ({
        ...current,
        source_workflow_name: current.source_workflow_name || selectedWorkflow,
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
      setInspectorMode("workflow");
      setSelectedEdgeId("");
      setEdgeDraftFrom("");
    }
    function selectNodeInspector(name) {
      setSelectedNodeName(name);
      setSelectedEdgeId("");
      setInspectorMode("node");
    }
    function selectEdgeInspector(edge) {
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
    return /* @__PURE__ */ React.createElement("main", { className: "workbench-layout" }, /* @__PURE__ */ React.createElement("aside", { className: "panel step-panel" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Journey"), /* @__PURE__ */ React.createElement("h2", null, "Inspect \u2192 create \u2192 author"), /* @__PURE__ */ React.createElement("ol", { className: "step-list step-rail" }, stepState.map((step) => /* @__PURE__ */ React.createElement("li", { key: step.key, className: `step-item step-${step.state || "upcoming"}${step.locked ? " locked" : ""}` }, /* @__PURE__ */ React.createElement("div", { className: "step-head" }, /* @__PURE__ */ React.createElement("strong", null, step.label), /* @__PURE__ */ React.createElement("span", { className: `step-status ${step.state || "upcoming"}` }, stepBadgeLabel(step))), /* @__PURE__ */ React.createElement("span", null, step.description))))), /* @__PURE__ */ React.createElement("section", { className: "workbench-main" }, workflow.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Workflow unavailable", body: workflow.error }) : null, draft.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Draft unavailable", body: draft.error }) : null, workflows.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Workflow catalog unavailable", body: workflows.error }) : null, authoringCatalog.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Authoring catalog unavailable", body: authoringCatalog.error }) : null, actionNotice ? /* @__PURE__ */ React.createElement(Message, { tone: actionNotice.tone, title: actionNotice.title, body: actionNotice.body }) : null, busy ? /* @__PURE__ */ React.createElement(LoadingCard, { label: busy }) : null, draftId && draft.loading && !draft.data ? /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading draft" }) : null, !draftId && (workflow.loading || authoringCatalog.loading) && !workflow.data ? /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading workflow authoring surface" }) : null, /* @__PURE__ */ React.createElement("section", { className: "panel hero-panel workbench-hero" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, surfaceLabel), /* @__PURE__ */ React.createElement("h2", null, draftId ? "Drag-drop the bounded workflow graph IDE" : "Create a new authored workflow or clone one into a local draft"), /* @__PURE__ */ React.createElement("p", null, draftId ? isStudio ? "Move nodes locally, drag safe palette nodes onto the canvas, create/remove edges, edit supported config, validate, save, and run through the Studio API without arbitrary plugin or code editing." : "The legacy workbench route stays compatible with the same safe authoring backend while Studio is the primary graph IDE surface." : "Start from scratch, a template, or an existing workflow. Draft state stays local and resumable while the reusable workflow file remains coherent on disk."), /* @__PURE__ */ React.createElement("div", { className: "meta-row" }, /* @__PURE__ */ React.createElement(SourceBadge, { source: activeWorkflow?.source || "builtin" }), activeDraft?.creation_mode ? /* @__PURE__ */ React.createElement("span", null, "Mode: ", activeDraft.creation_mode) : null, activeDraft?.draft_workflow_name ? /* @__PURE__ */ React.createElement("span", null, "Draft: ", activeDraft.draft_workflow_name) : null, activeDraft?.baseline_run_id ? /* @__PURE__ */ React.createElement("span", null, "Baseline: ", activeDraft.baseline_run_id) : overviewLatestRun?.run_id ? /* @__PURE__ */ React.createElement("span", null, "Suggested baseline: ", overviewLatestRun.run_id) : null, activeDraft?.last_run_id ? /* @__PURE__ */ React.createElement("span", null, "Candidate: ", activeDraft.last_run_id) : null), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, overviewLatestRun?.run_id ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(`/runs/${overviewLatestRun.run_id}`) }, "Inspect latest run") : /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate("/runs") }, "Browse runs"), activeDraft?.last_run_id ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(`/runs/${activeDraft.last_run_id}`) }, "Inspect candidate run") : null)), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "1. Create draft"), /* @__PURE__ */ React.createElement("h3", null, "Start from scratch, template, or clone")), /* @__PURE__ */ React.createElement("p", { className: "section-copy" }, "Creation routes all flow through the shared backend authoring service and still land in the local draft + workflow file model.")), /* @__PURE__ */ React.createElement("div", { className: "creation-mode-row" }, creationModes.map((mode) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: mode.key,
        className: creationMode === mode.key ? "workflow-tile active" : "workflow-tile",
        onClick: () => setCreationMode(String(mode.key || "clone")),
        type: "button"
      },
      /* @__PURE__ */ React.createElement("strong", null, mode.label),
      /* @__PURE__ */ React.createElement("span", { className: "workflow-note" }, mode.detail)
    ))), /* @__PURE__ */ React.createElement("div", { className: "split-grid" }, /* @__PURE__ */ React.createElement("section", { className: "surface-card section-stack" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Draft workflow name"), /* @__PURE__ */ React.createElement("input", { value: createForm.draft_workflow_name || "", onChange: (event) => setCreateForm((current) => ({ ...current, draft_workflow_name: event.target.value })), placeholder: "my-authored-workflow" })), creationMode === "clone" ? /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Source workflow"), /* @__PURE__ */ React.createElement("select", { value: createForm.source_workflow_name || selectedWorkflow, onChange: (event) => setCreateForm((current) => ({ ...current, source_workflow_name: event.target.value })) }, (workflows.data?.items || []).map((item) => /* @__PURE__ */ React.createElement("option", { key: item.name, value: item.name }, item.title || item.name)))) : null, creationMode === "template" ? /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Starter template"), /* @__PURE__ */ React.createElement("select", { value: createForm.template_id || "", onChange: (event) => setCreateForm((current) => ({ ...current, template_id: event.target.value })) }, templates.map((item) => /* @__PURE__ */ React.createElement("option", { key: item.template_id, value: item.template_id }, item.title)))) : null, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Title"), /* @__PURE__ */ React.createElement("input", { value: createForm.title || "", onChange: (event) => setCreateForm((current) => ({ ...current, title: event.target.value })), placeholder: "Optional display title" })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Description"), /* @__PURE__ */ React.createElement("textarea", { className: "text-area-input", value: createForm.description || "", onChange: (event) => setCreateForm((current) => ({ ...current, description: event.target.value })), placeholder: "Optional authoring summary" })), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: createDraftFromMode, disabled: Boolean(busy) || creationDisabled }, "Create draft"), !draftId && activeWorkflow?.name ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(`/workflows/${encodeURIComponent(activeWorkflow.name)}`) }, "Open workflow detail") : null)), /* @__PURE__ */ React.createElement("section", { className: "surface-card section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, activeWorkflow?.title || activeWorkflow?.name || selectedWorkflow), /* @__PURE__ */ React.createElement("p", null, activeWorkflow?.description || "Select a workflow or choose a starter mode.")), /* @__PURE__ */ React.createElement(SourceBadge, { source: activeWorkflow?.source || "builtin" })), activeDraft ? /* @__PURE__ */ React.createElement("dl", { className: "context-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Draft mode"), /* @__PURE__ */ React.createElement("dd", null, activeDraft.creation_mode || "clone")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Source"), /* @__PURE__ */ React.createElement("dd", null, activeDraft.source_workflow_name || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Local workflow"), /* @__PURE__ */ React.createElement("dd", null, activeDraft.draft_workflow_name || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Status"), /* @__PURE__ */ React.createElement("dd", null, activeDraft.status || "\u2014"))) : activeWorkflow ? /* @__PURE__ */ React.createElement("dl", { className: "context-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Workflow kind"), /* @__PURE__ */ React.createElement("dd", null, activeWorkflow.workflow_kind || activeWorkflow.kind || "workflow")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Questions"), /* @__PURE__ */ React.createElement("dd", null, activeWorkflow.question_limit || workflow.data?.blueprint?.questions?.limit || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Runtime"), /* @__PURE__ */ React.createElement("dd", null, activeWorkflow.runtime_provider || workflow.data?.blueprint?.runtime?.provider || "mock")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Action"), /* @__PURE__ */ React.createElement("dd", null, creationMode === "clone" ? "Clone this workflow into a local authored draft." : creationMode === "template" ? "Create a new workflow from the selected starter template." : "Create a fresh safe starter workflow and begin authoring."))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "Select a workflow", body: "The workbench will show the current workflow summary here before you create a draft." }))), /* @__PURE__ */ React.createElement("div", { className: "workflow-list workflow-catalog" }, (workflows.data?.items || []).map((item) => /* @__PURE__ */ React.createElement(
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
    )))), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "2. Workflow fields"), /* @__PURE__ */ React.createElement("h3", null, "Edit supported core fields through the shared authoring layer")), /* @__PURE__ */ React.createElement("p", { className: "section-copy" }, "Title, description, workflow kind, bounded runtime settings, scoring, and artifact toggles stay inside the safe product contract.")), !draftId ? /* @__PURE__ */ React.createElement(EmptyState, { title: "Create a draft to unlock field editing", body: "Once a draft exists, this form edits the authored workflow fields that the shared backend service supports." }) : /* @__PURE__ */ React.createElement("div", { className: "form-grid guided-form" }, /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Title"), /* @__PURE__ */ React.createElement("input", { value: coreForm.title || "", onChange: (event) => setCoreForm((current) => ({ ...current, title: event.target.value })) })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Workflow kind"), /* @__PURE__ */ React.createElement("input", { value: coreForm.workflow_kind || "", onChange: (event) => setCoreForm((current) => ({ ...current, workflow_kind: event.target.value })), list: "workflow-kind-options" }))), /* @__PURE__ */ React.createElement("datalist", { id: "workflow-kind-options" }, (authoringCatalog.data?.workflow_kind_options || []).map((item) => /* @__PURE__ */ React.createElement("option", { key: item, value: item }))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Description"), /* @__PURE__ */ React.createElement("textarea", { className: "text-area-input", value: coreForm.description || "", onChange: (event) => setCoreForm((current) => ({ ...current, description: event.target.value })) })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Tags"), /* @__PURE__ */ React.createElement("input", { value: coreForm.tags || "", onChange: (event) => setCoreForm((current) => ({ ...current, tags: event.target.value })), placeholder: "starter, local, benchmark" })), /* @__PURE__ */ React.createElement("div", { className: "three-column-grid compact-form-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Questions limit"), /* @__PURE__ */ React.createElement("input", { type: "number", min: 1, max: 25, value: coreForm.questions_limit || "", onChange: (event) => setCoreForm((current) => ({ ...current, questions_limit: event.target.value })) })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Runtime provider"), /* @__PURE__ */ React.createElement("select", { value: coreForm.runtime_provider || "mock", onChange: (event) => setCoreForm((current) => ({ ...current, runtime_provider: event.target.value })) }, (authoringCatalog.data?.runtime_provider_options || []).map((item) => /* @__PURE__ */ React.createElement("option", { key: item, value: item }, item)))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Max tokens"), /* @__PURE__ */ React.createElement("input", { type: "number", min: 1, value: coreForm.runtime_max_tokens || "", onChange: (event) => setCoreForm((current) => ({ ...current, runtime_max_tokens: event.target.value })) }))), /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Runtime base URL"), /* @__PURE__ */ React.createElement("input", { value: coreForm.runtime_base_url || "", onChange: (event) => setCoreForm((current) => ({ ...current, runtime_base_url: event.target.value })), placeholder: "http://127.0.0.1:11434/v1" })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Runtime model"), /* @__PURE__ */ React.createElement("input", { value: coreForm.runtime_model || "", onChange: (event) => setCoreForm((current) => ({ ...current, runtime_model: event.target.value })), placeholder: "phi-4-mini" }))), /* @__PURE__ */ React.createElement("div", { className: "three-column-grid compact-form-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Write HTML report"), /* @__PURE__ */ React.createElement("select", { value: coreForm.artifacts_write_report || "true", onChange: (event) => setCoreForm((current) => ({ ...current, artifacts_write_report: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "true" }, "true"), /* @__PURE__ */ React.createElement("option", { value: "false" }, "false"))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Write blueprint copy"), /* @__PURE__ */ React.createElement("select", { value: coreForm.artifacts_write_blueprint_copy || "true", onChange: (event) => setCoreForm((current) => ({ ...current, artifacts_write_blueprint_copy: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "true" }, "true"), /* @__PURE__ */ React.createElement("option", { value: "false" }, "false"))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Write graph trace"), /* @__PURE__ */ React.createElement("select", { value: coreForm.artifacts_write_graph_trace || "true", onChange: (event) => setCoreForm((current) => ({ ...current, artifacts_write_graph_trace: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "true" }, "true"), /* @__PURE__ */ React.createElement("option", { value: "false" }, "false")))), /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Write eval"), /* @__PURE__ */ React.createElement("select", { value: coreForm.scoring_write_eval || "true", onChange: (event) => setCoreForm((current) => ({ ...current, scoring_write_eval: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "true" }, "true"), /* @__PURE__ */ React.createElement("option", { value: "false" }, "false"))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Write train backtest"), /* @__PURE__ */ React.createElement("select", { value: coreForm.scoring_write_train_backtest || "true", onChange: (event) => setCoreForm((current) => ({ ...current, scoring_write_train_backtest: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "true" }, "true"), /* @__PURE__ */ React.createElement("option", { value: "false" }, "false")))), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: applyCoreFields, disabled: Boolean(busy) }, "Apply workflow fields")))), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack studio-ide-panel" }, /* @__PURE__ */ React.createElement("div", { className: "section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "3. Studio graph IDE"), /* @__PURE__ */ React.createElement("h3", null, "Drag nodes, drop safe palette items, select nodes/edges, then validate")), /* @__PURE__ */ React.createElement("p", { className: "section-copy" }, "Node positions are local UI state for this session; the workflow schema currently persists graph topology and config, not canvas coordinates.")), !draftId ? /* @__PURE__ */ React.createElement(EmptyState, { title: "Create a draft to unlock graph authoring", body: "The canvas becomes editable as soon as you open a draft session." }) : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("div", { className: "studio-toolbar" }, /* @__PURE__ */ React.createElement("button", { className: inspectorMode === "workflow" ? "secondary-button active" : "secondary-button", onClick: selectWorkflowInspector }, "Workflow inspector"), /* @__PURE__ */ React.createElement("button", { className: inspectorMode === "node" ? "secondary-button active" : "secondary-button", onClick: () => selectedNodeName && selectNodeInspector(selectedNodeName), disabled: !selectedNodeName }, "Node inspector"), /* @__PURE__ */ React.createElement("button", { className: inspectorMode === "edge" ? "secondary-button active" : "secondary-button", onClick: () => selectedEdge && selectEdgeInspector(selectedEdge), disabled: !selectedEdge }, "Edge inspector"), edgeDraftFrom ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button active", onClick: () => setEdgeDraftFrom("") }, "Creating edge from ", edgeDraftFrom, " \xB7 cancel") : selectedNode ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => setEdgeDraftFrom(String(selectedNode.name)) }, "Start edge from selected node") : null), /* @__PURE__ */ React.createElement("section", { className: "node-palette", "aria-label": "Studio node palette" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Node palette"), /* @__PURE__ */ React.createElement("p", null, "Click to add downstream of the selected node, or drag a built-in safe node onto the canvas.")), /* @__PURE__ */ React.createElement("div", { className: "node-palette-grid" }, nodeCatalog.map((item) => /* @__PURE__ */ React.createElement(
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
    )))), /* @__PURE__ */ React.createElement(
      WorkflowCanvasSurface,
      {
        canvas: activeCanvas,
        entry: String(activeGraph.entry || ""),
        selectedNodeName: inspectorMode === "node" ? selectedNodeName : "",
        selectedEdgeId: inspectorMode === "edge" ? selectedEdgeId : "",
        localPositions,
        edgeDraftFrom,
        onMoveNode: (name, position) => setLocalPositions((current) => ({ ...current, [name]: position })),
        onSelectNode: selectNodeInspector,
        onSelectEdge: selectEdgeInspector,
        onSelectWorkflow: selectWorkflowInspector,
        onAddNodeFromPalette: (implementation, position) => void addPaletteNode(implementation, position),
        onCreateEdge: (from, to) => void createEdgeFromCanvas(from, to)
      }
    ), /* @__PURE__ */ React.createElement("div", { className: "three-column-grid authoring-grid" }, /* @__PURE__ */ React.createElement("section", { className: "surface-card section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, "Context inspector"), /* @__PURE__ */ React.createElement("p", null, inspectorMode === "workflow" ? "Workflow config uses the same safe mutation action as the field form above." : inspectorMode === "edge" ? selectedEdge ? `Inspect ${selectedEdge.from} \u2192 ${selectedEdge.to}.` : "Select an edge from the canvas or list." : selectedNode ? `Edit ${selectedNode.name} inline.` : "Select a node from the canvas to edit it.")), inspectorMode === "workflow" ? /* @__PURE__ */ React.createElement(StatusPill, { value: "workflow" }) : inspectorMode === "edge" ? /* @__PURE__ */ React.createElement(StatusPill, { value: selectedEdge?.read_only ? "read-only edge" : "edge" }) : selectedNode ? /* @__PURE__ */ React.createElement(StatusPill, { value: selectedNode.kind || "node" }) : null), inspectorMode === "workflow" ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("dl", { className: "context-list compact-context-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Workflow"), /* @__PURE__ */ React.createElement("dd", null, activeDraft?.draft_workflow_name || activeWorkflow?.name || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Entry"), /* @__PURE__ */ React.createElement("dd", null, activeGraph.entry || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Revision"), /* @__PURE__ */ React.createElement("dd", null, activeDraft?.revision ?? "\u2014"))), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => document.getElementById("workflow-config-fields")?.scrollIntoView({ behavior: "smooth", block: "start" }) }, "Jump to workflow config")) : inspectorMode === "edge" ? selectedEdge ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("dl", { className: "context-list compact-context-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "From"), /* @__PURE__ */ React.createElement("dd", null, selectedEdge.from || selectedEdge.source || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "To"), /* @__PURE__ */ React.createElement("dd", null, selectedEdge.to || selectedEdge.target || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Kind"), /* @__PURE__ */ React.createElement("dd", null, selectedEdge.kind || "edge")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Editable"), /* @__PURE__ */ React.createElement("dd", null, selectedEdge.read_only ? "No" : "Yes"))), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => void removeEdge(String(selectedEdge.from), String(selectedEdge.to)), disabled: Boolean(busy) || Boolean(selectedEdge.read_only) }, "Remove selected edge")) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No edge selected", body: "Pick an edge from the canvas curve or edge list to inspect it." }) : selectedNode ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("dl", { className: "context-list compact-context-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Implementation"), /* @__PURE__ */ React.createElement("dd", null, selectedNode.implementation || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Runtime"), /* @__PURE__ */ React.createElement("dd", null, selectedNode.runtime || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Entry"), /* @__PURE__ */ React.createElement("dd", null, selectedNode.is_entry ? "Yes" : "No"))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Description"), /* @__PURE__ */ React.createElement("textarea", { className: "text-area-input", value: nodeForm.description || "", onChange: (event) => setNodeForm((current) => ({ ...current, description: event.target.value })) })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Runtime label"), /* @__PURE__ */ React.createElement("input", { value: nodeForm.runtime || "", onChange: (event) => setNodeForm((current) => ({ ...current, runtime: event.target.value })), placeholder: "Optional runtime tag" })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Optional"), /* @__PURE__ */ React.createElement("select", { value: nodeForm.optional || "false", onChange: (event) => setNodeForm((current) => ({ ...current, optional: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "false" }, "false"), /* @__PURE__ */ React.createElement("option", { value: "true" }, "true"))), (selectedNode.aggregate_weights || []).map((item) => {
      const key = `weight:${String(item.name)}`;
      return /* @__PURE__ */ React.createElement("label", { key }, /* @__PURE__ */ React.createElement("span", null, item.name, " weight"), /* @__PURE__ */ React.createElement("input", { type: "number", min: 0, max: 100, value: nodeForm[key] || "", onChange: (event) => setNodeForm((current) => ({ ...current, [key]: event.target.value })) }));
    }), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: applyNodeUpdates, disabled: Boolean(busy) }, "Apply node changes"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => void setEntry(String(selectedNode.name)), disabled: Boolean(busy) || selectedNode.is_entry }, "Set as entry"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => setEdgeDraftFrom(String(selectedNode.name)), disabled: Boolean(busy) }, "Start edge here"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: removeSelectedNode, disabled: Boolean(busy) }, "Remove node"))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No node selected", body: "Pick a node from the canvas to edit its supported fields." })), /* @__PURE__ */ React.createElement("section", { className: "surface-card section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, "Add safe node"), /* @__PURE__ */ React.createElement("p", null, "Palette click/drop uses the same add-node mutation; this form gives explicit names and edge wiring."))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Node name"), /* @__PURE__ */ React.createElement("input", { value: addNodeForm.node_name || "", onChange: (event) => setAddNodeForm((current) => ({ ...current, node_name: event.target.value })), placeholder: "question_context_2" })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Implementation"), /* @__PURE__ */ React.createElement("select", { value: addNodeForm.implementation || "", onChange: (event) => setAddNodeForm((current) => ({ ...current, implementation: event.target.value })) }, nodeCatalog.map((item) => /* @__PURE__ */ React.createElement("option", { key: item.implementation, value: item.implementation }, item.name, " \xB7 ", item.kind)))), /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Incoming from"), /* @__PURE__ */ React.createElement("select", { value: addNodeForm.incoming_from || "", onChange: (event) => setAddNodeForm((current) => ({ ...current, incoming_from: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "" }, "None"), graphTargets.map((target) => /* @__PURE__ */ React.createElement("option", { key: target.name, value: target.name }, target.name)))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Outgoing to"), /* @__PURE__ */ React.createElement("select", { value: addNodeForm.outgoing_to || "", onChange: (event) => setAddNodeForm((current) => ({ ...current, outgoing_to: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "" }, "None"), graphTargets.map((target) => /* @__PURE__ */ React.createElement("option", { key: target.name, value: target.name }, target.name))))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Description"), /* @__PURE__ */ React.createElement("textarea", { className: "text-area-input", value: addNodeForm.description || "", onChange: (event) => setAddNodeForm((current) => ({ ...current, description: event.target.value })) })), /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Runtime label"), /* @__PURE__ */ React.createElement("input", { value: addNodeForm.runtime || "", onChange: (event) => setAddNodeForm((current) => ({ ...current, runtime: event.target.value })), placeholder: "Optional runtime tag" })), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Optional"), /* @__PURE__ */ React.createElement("select", { value: addNodeForm.optional || "false", onChange: (event) => setAddNodeForm((current) => ({ ...current, optional: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "false" }, "false"), /* @__PURE__ */ React.createElement("option", { value: "true" }, "true")))), /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => void addNode(), disabled: Boolean(busy) || !addNodeForm.node_name || !addNodeForm.implementation }, "Add node")), /* @__PURE__ */ React.createElement("section", { className: "surface-card section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, "Edges + advanced graph context"), /* @__PURE__ */ React.createElement("p", null, "Add or remove simple edges here. Parallel groups and routes stay visible for review."))), /* @__PURE__ */ React.createElement("div", { className: "two-field-grid" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "From"), /* @__PURE__ */ React.createElement("select", { value: addEdgeForm.from_node || "", onChange: (event) => setAddEdgeForm((current) => ({ ...current, from_node: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "" }, "Select"), graphTargets.map((target) => /* @__PURE__ */ React.createElement("option", { key: target.name, value: target.name }, target.name)))), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "To"), /* @__PURE__ */ React.createElement("select", { value: addEdgeForm.to_node || "", onChange: (event) => setAddEdgeForm((current) => ({ ...current, to_node: event.target.value })) }, /* @__PURE__ */ React.createElement("option", { value: "" }, "Select"), graphTargets.map((target) => /* @__PURE__ */ React.createElement("option", { key: target.name, value: target.name }, target.name))))), /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => void addEdge(), disabled: Boolean(busy) || !addEdgeForm.from_node || !addEdgeForm.to_node }, "Add edge"), /* @__PURE__ */ React.createElement("div", { className: "edge-list" }, graphEdges.map((edge, index) => /* @__PURE__ */ React.createElement("div", { key: `${edge.from}-${edge.to}-${index}`, className: studioEdgeKey(edge) === selectedEdgeId ? "edge-row selected" : "edge-row", onClick: () => selectEdgeInspector(edge) }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, edge.from), /* @__PURE__ */ React.createElement("span", null, edge.to)), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => void removeEdge(String(edge.from), String(edge.to)), disabled: Boolean(busy) }, "Remove")))), Object.keys(activeGraph.parallel_groups || {}).length || Object.keys(activeGraph.conditional_routes || {}).length ? /* @__PURE__ */ React.createElement("div", { className: "guidance-section minor-divider" }, Object.keys(activeGraph.parallel_groups || {}).length ? /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, "Parallel groups"), /* @__PURE__ */ React.createElement("ul", { className: "guidance-list compact-list" }, Object.entries(activeGraph.parallel_groups).map(([name, members]) => /* @__PURE__ */ React.createElement("li", { key: name }, /* @__PURE__ */ React.createElement("strong", null, name), /* @__PURE__ */ React.createElement("span", null, Array.isArray(members) ? members.join(", ") : ""))))) : null, Object.keys(activeGraph.conditional_routes || {}).length ? /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, "Conditional routes"), /* @__PURE__ */ React.createElement("ul", { className: "guidance-list compact-list" }, Object.entries(activeGraph.conditional_routes).map(([name, route2]) => /* @__PURE__ */ React.createElement("li", { key: name }, /* @__PURE__ */ React.createElement("strong", null, name), /* @__PURE__ */ React.createElement("span", null, JSON.stringify(route2)))))) : null) : null)))), /* @__PURE__ */ React.createElement("section", { className: "panel" }, /* @__PURE__ */ React.createElement("div", { className: "section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "4. Save, validate + run"), /* @__PURE__ */ React.createElement("h3", null, "Save/validate inline, then run only when the authored draft is safe")), /* @__PURE__ */ React.createElement("p", { className: "section-copy" }, "Studio mutations preview validation immediately; this save/validate action persists the reusable workflow before run readiness is unlocked.")), !draftId ? /* @__PURE__ */ React.createElement(EmptyState, { title: "No draft to validate yet", body: "Create or open a draft session first. Then this panel will keep validation, fixes, and run readiness together." }) : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(Message, { tone: validationStatus.tone, title: validationStatus.title, body: validationStatus.body }), validationFixes.length ? /* @__PURE__ */ React.createElement("ul", { className: "teaching-list" }, validationFixes.map((note) => /* @__PURE__ */ React.createElement("li", { key: note }, note))) : null, /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: validateDraft, disabled: Boolean(busy) }, "Save + validate draft"), /* @__PURE__ */ React.createElement("button", { className: "primary-button", disabled: Boolean(busy) || runDisabled, onClick: runDraft }, "Run candidate")))), /* @__PURE__ */ React.createElement("section", { className: "panel" }, /* @__PURE__ */ React.createElement("div", { className: "section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "5. Compare + next step"), /* @__PURE__ */ React.createElement("h3", null, "Keep validate, run, and compare inside the same authoring loop")), /* @__PURE__ */ React.createElement("p", { className: "section-copy" }, "Once the candidate finishes, compare it immediately or jump into the run detail from the same workbench surface.")), activeDraft?.compare ? /* @__PURE__ */ React.createElement("div", { className: "compare-outcome" }, /* @__PURE__ */ React.createElement(Message, { tone: "success", title: `Compare verdict: ${activeDraft.compare.verdict?.label || "ready"}`, body: activeDraft.compare.verdict?.summary || "Open the comparison to inspect detailed metric deltas." }), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, (activeDraft.compare.next_actions || []).map((action, index) => /* @__PURE__ */ React.createElement("button", { key: action.href || action.label || index, className: index === 0 ? "primary-button" : "secondary-button", onClick: () => navigate(action.href) }, action.label)))) : activeDraft?.last_run_id ? /* @__PURE__ */ React.createElement(Message, { tone: "success", title: "Candidate run completed", body: "Inspect the candidate run now. Add a baseline if you want to compare it before deciding on the next edit." }) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No candidate run yet", body: "Once validation passes and you run a candidate, this panel will explain whether to compare, iterate, or stop." }))), /* @__PURE__ */ React.createElement("aside", { className: "panel guidance-panel" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Next step"), /* @__PURE__ */ React.createElement("section", { className: "next-step-card" }, /* @__PURE__ */ React.createElement("strong", null, nextStep.title), /* @__PURE__ */ React.createElement("p", null, nextStep.detail)), /* @__PURE__ */ React.createElement("section", { className: "guidance-section" }, /* @__PURE__ */ React.createElement("h3", null, "Authoring contract"), /* @__PURE__ */ React.createElement("ul", { className: "guidance-list" }, safeEditLimitations.map((item) => /* @__PURE__ */ React.createElement("li", { key: item }, item)))), /* @__PURE__ */ React.createElement("section", { className: "guidance-section" }, /* @__PURE__ */ React.createElement("h3", null, "Supported safe edits"), /* @__PURE__ */ React.createElement("ul", { className: "guidance-list compact-list" }, safeEditSupport.map((item) => /* @__PURE__ */ React.createElement("li", { key: item.key }, /* @__PURE__ */ React.createElement("strong", null, item.label), /* @__PURE__ */ React.createElement("span", null, item.detail))))), /* @__PURE__ */ React.createElement("section", { className: "guidance-section" }, /* @__PURE__ */ React.createElement("h3", null, "What stays authoritative"), /* @__PURE__ */ React.createElement("ul", { className: "guidance-list" }, sourceOfTruth.map((item) => /* @__PURE__ */ React.createElement("li", { key: item }, item))))));
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
    onCreateEdge
  }) {
    const stageRef = React.useRef(null);
    const dragRef = React.useRef(null);
    const suppressClickRef = React.useRef(false);
    const nodes = (canvas?.nodes || []).filter((node) => typeof node?.name === "string");
    const edges = canvas?.edges || [];
    if (!nodes.length) {
      return /* @__PURE__ */ React.createElement(EmptyState, { title: "No graph nodes yet", body: "Add a node or load another workflow to populate the visual graph surface." });
    }
    const positionForNode = (node) => {
      const name = String(node.name);
      return localPositions[name] || { x: Number(node.x || 0), y: Number(node.y || 0) };
    };
    const width = Math.max(680, ...nodes.map((node) => positionForNode(node).x + 240));
    const height = Math.max(360, ...nodes.map((node) => positionForNode(node).y + 150));
    const positions = Object.fromEntries(nodes.map((node) => [String(node.name), positionForNode(node)]));
    const relativePoint = (event) => {
      const rect = stageRef.current?.getBoundingClientRect();
      if (!rect) return { x: 0, y: 0 };
      return { x: event.clientX - rect.left, y: event.clientY - rect.top };
    };
    const clampPosition = (x, y) => ({
      x: Math.max(0, Math.min(width - 180, Math.round(x))),
      y: Math.max(0, Math.min(height - 90, Math.round(y)))
    });
    return /* @__PURE__ */ React.createElement(
      "div",
      {
        className: "workflow-canvas-shell",
        onDragOver: (event) => {
          if (Array.from(event.dataTransfer.types).includes("application/xrtm-node-implementation")) {
            event.preventDefault();
            event.dataTransfer.dropEffect = "copy";
          }
        },
        onDrop: (event) => {
          const implementation = event.dataTransfer.getData("application/xrtm-node-implementation");
          if (!implementation) return;
          event.preventDefault();
          const point = relativePoint(event);
          onAddNodeFromPalette(implementation, clampPosition(point.x - 82, point.y - 34));
        }
      },
      /* @__PURE__ */ React.createElement(
        "div",
        {
          ref: stageRef,
          className: "workflow-canvas-stage",
          style: { height: `${height}px`, width: `${width}px` },
          onClick: (event) => {
            if (event.currentTarget === event.target) onSelectWorkflow();
          }
        },
        /* @__PURE__ */ React.createElement("svg", { className: "workflow-canvas-svg", viewBox: `0 0 ${width} ${height}`, preserveAspectRatio: "xMinYMin meet", onClick: onSelectWorkflow }, /* @__PURE__ */ React.createElement("defs", null, /* @__PURE__ */ React.createElement("marker", { id: "workflow-arrow", markerWidth: "8", markerHeight: "8", refX: "7", refY: "4", orient: "auto" }, /* @__PURE__ */ React.createElement("path", { d: "M0,0 L8,4 L0,8 z", fill: "#91a5ca" }))), edges.map((edge, index) => {
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
          return /* @__PURE__ */ React.createElement("g", { key: `${edge.from}-${edge.to}-${index}`, className: "workflow-canvas-edge-hit", onClick: (event) => {
            event.stopPropagation();
            onSelectEdge(edge);
          } }, /* @__PURE__ */ React.createElement("path", { className: `workflow-canvas-edge ${edgeId === selectedEdgeId ? "selected" : ""} ${edge.read_only ? "readonly" : ""}`, d: `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`, markerEnd: "url(#workflow-arrow)" }), edge.label ? /* @__PURE__ */ React.createElement("text", { className: "workflow-canvas-label", x: midX, y: midY - 6 }, String(edge.label)) : null);
        })),
        nodes.map((node) => {
          const name = String(node.name);
          const position = positionForNode(node);
          return /* @__PURE__ */ React.createElement(
            "button",
            {
              key: name,
              type: "button",
              className: `workflow-canvas-node ${selectedNodeName === name ? "selected" : ""} ${entry === name ? "entry" : ""} ${edgeDraftFrom === name ? "edge-source" : ""}`,
              style: { left: `${position.x}px`, top: `${position.y}px` },
              onPointerDown: (event) => {
                const point = relativePoint(event);
                dragRef.current = { nodeName: name, offsetX: point.x - position.x, offsetY: point.y - position.y, pointerId: event.pointerId };
                suppressClickRef.current = false;
                event.currentTarget.setPointerCapture(event.pointerId);
              },
              onPointerMove: (event) => {
                const drag = dragRef.current;
                if (!drag || drag.nodeName !== name) return;
                const point = relativePoint(event);
                suppressClickRef.current = true;
                onMoveNode(name, clampPosition(point.x - drag.offsetX, point.y - drag.offsetY));
              },
              onPointerUp: (event) => {
                if (dragRef.current?.pointerId === event.pointerId) {
                  dragRef.current = null;
                  event.currentTarget.releasePointerCapture(event.pointerId);
                }
              },
              onClick: (event) => {
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
              }
            },
            /* @__PURE__ */ React.createElement("strong", null, name),
            /* @__PURE__ */ React.createElement("span", null, node.kind),
            /* @__PURE__ */ React.createElement(StatusPill, { value: node.status || (entry === name ? "entry" : "ready") })
          );
        })
      )
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
    if (!nodes.length) {
      return /* @__PURE__ */ React.createElement(EmptyState, { title: "No graph preview", body: "This context did not expose canvas-ready graph nodes." });
    }
    const width = Math.max(360, ...nodes.map((node) => Number(node.x || 0) + 220));
    const height = Math.max(220, ...nodes.map((node) => Number(node.y || 0) + 120));
    const positions = Object.fromEntries(nodes.map((node) => [String(node.name), { x: Number(node.x || 0), y: Number(node.y || 0) }]));
    return /* @__PURE__ */ React.createElement("div", { className: "workflow-canvas-shell playground-trace-canvas" }, /* @__PURE__ */ React.createElement("div", { className: "workflow-canvas-stage", style: { height: `${height}px` } }, /* @__PURE__ */ React.createElement("svg", { className: "workflow-canvas-svg", viewBox: `0 0 ${width} ${height}`, preserveAspectRatio: "xMinYMin meet" }, /* @__PURE__ */ React.createElement("defs", null, /* @__PURE__ */ React.createElement("marker", { id: "playground-arrow", markerWidth: "8", markerHeight: "8", refX: "7", refY: "4", orient: "auto" }, /* @__PURE__ */ React.createElement("path", { d: "M0,0 L8,4 L0,8 z", fill: "#91a5ca" }))), edges.map((edge, index) => {
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
      return /* @__PURE__ */ React.createElement("g", { key: `${edge.from}-${edge.to}-${index}` }, /* @__PURE__ */ React.createElement(
        "path",
        {
          className: `workflow-canvas-edge ${traced ? "executed" : ""}`,
          d: `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`,
          markerEnd: "url(#playground-arrow)"
        }
      ), edge.label ? /* @__PURE__ */ React.createElement("text", { className: "workflow-canvas-label", x: midX, y: midY - 6 }, String(edge.label)) : null);
    })), nodes.map((node) => {
      const trace = traceByNode[String(node.name)];
      const executed = Boolean(trace || node.executed);
      const active = activeNodeId === String(node.name);
      return /* @__PURE__ */ React.createElement(
        "button",
        {
          key: node.name,
          type: "button",
          className: `workflow-canvas-node playground-trace-node ${executed ? "executed" : "not-executed"} ${active ? "active" : ""} ${node.is_entry ? "entry" : ""}`,
          style: { left: `${Number(node.x || 0)}px`, top: `${Number(node.y || 0)}px` },
          onClick: () => onSelectNode(String(node.name))
        },
        /* @__PURE__ */ React.createElement("strong", null, node.name),
        /* @__PURE__ */ React.createElement("span", null, node.kind || node.node_type || "node"),
        /* @__PURE__ */ React.createElement("span", { className: "trace-chip" }, executed ? `#${formatValue(trace?.order || node.trace_order)}` : "Not run"),
        /* @__PURE__ */ React.createElement(StatusPill, { value: String(trace?.status || node.status || (node.is_entry ? "entry" : "ready")) })
      );
    })));
  }
  function normalizeText(value) {
    const text = String(value || "").trim();
    return text ? text : null;
  }
  function parseBooleanString(value) {
    return String(value || "false").toLowerCase() === "true";
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
      { key: "next-step", label: "Next step", locked: false, description: "The workbench will explain what to do after each step." }
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
  function buildDraftlessNextStep(activeWorkflow, latestRun) {
    if (activeWorkflow?.source === "local") {
      return {
        key: "clone",
        title: "Open a draft session for the local workflow",
        detail: "Local workflows are reusable on disk, but the workbench still uses a draft session so validation, run readiness, and resume state stay explicit."
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
    return /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Latest launched run"), /* @__PURE__ */ React.createElement("p", null, "Jump straight into detail, report, or compare while the context is fresh."))), /* @__PURE__ */ React.createElement("div", { className: "inline-action-card" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, result.run_id), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, result.command || "Run created", " \xB7 ", result.provider || "provider-free", " \xB7 ", result.status || "running")), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => navigate(result.href) }, "Inspect run"), result.report_href ? /* @__PURE__ */ React.createElement("a", { className: "secondary-link", href: result.report_href, target: "_blank", rel: "noreferrer" }, "Open report") : null, result.compare?.href ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(result.compare.href) }, "Compare") : null)));
  }
  function RunCard({ run, onOpen }) {
    return /* @__PURE__ */ React.createElement("section", { className: "panel run-card" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Latest run"), /* @__PURE__ */ React.createElement("h3", null, run.workflow?.title || run.run_id), /* @__PURE__ */ React.createElement("p", null, run.workflow?.name || run.provider)), /* @__PURE__ */ React.createElement("div", { className: "meta-row" }, /* @__PURE__ */ React.createElement(StatusPill, { value: run.status }), /* @__PURE__ */ React.createElement("span", null, run.updated_at || "\u2014")), /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: onOpen }, "Inspect latest run"));
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
  function ReportCard({ report }) {
    if (!report) {
      return /* @__PURE__ */ React.createElement(EmptyState, { title: "No report metadata", body: "This surface did not expose report availability information." });
    }
    return /* @__PURE__ */ React.createElement("section", { className: `report-card ${report.available ? "available" : "missing"}` }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, report.label || "HTML report"), /* @__PURE__ */ React.createElement("p", null, report.description || "No report description available.")), report.available ? /* @__PURE__ */ React.createElement("a", { className: "secondary-link", href: report.href, target: "_blank", rel: "noreferrer" }, "Open report") : /* @__PURE__ */ React.createElement("span", { className: "availability-pill missing" }, "Unavailable"));
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
