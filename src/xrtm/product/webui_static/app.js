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
    const nav = shell.data?.app?.nav ?? [
      { label: "Overview", href: "/" },
      { label: "Runs", href: "/runs" },
      { label: "Workbench", href: "/workbench" }
    ];
    let page;
    if (route.path === "/") {
      page = /* @__PURE__ */ React.createElement(OverviewPage, { shell: shell.data, navigate });
    } else if (route.path === "/runs") {
      page = /* @__PURE__ */ React.createElement(RunsPage, { route, navigate });
    } else if (/^\/runs\/[^/]+\/compare\/[^/]+$/.test(route.path)) {
      const match = route.path.match(/^\/runs\/([^/]+)\/compare\/([^/]+)$/);
      page = /* @__PURE__ */ React.createElement(ComparePage, { candidateRunId: match[1], baselineRunId: match[2], navigate });
    } else if (/^\/runs\/[^/]+$/.test(route.path)) {
      page = /* @__PURE__ */ React.createElement(RunDetailPage, { runId: route.path.split("/")[2], navigate });
    } else {
      page = /* @__PURE__ */ React.createElement(WorkbenchPage, { route, shell: shell.data, navigate, onMutate: refreshShell });
    }
    return /* @__PURE__ */ React.createElement("div", { className: "app-shell" }, /* @__PURE__ */ React.createElement("header", { className: "topbar" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "XRTM WebUI"), /* @__PURE__ */ React.createElement("h1", null, "Local forecasting workbench")), /* @__PURE__ */ React.createElement("nav", { className: "topnav", "aria-label": "Primary" }, nav.map((item) => /* @__PURE__ */ React.createElement(
      "a",
      {
        key: item.href,
        className: route.path === item.href ? "nav-link active" : "nav-link",
        href: item.href,
        onClick: (event) => {
          event.preventDefault();
          navigate(item.href);
        }
      },
      item.label
    )))), bootstrap.initial_error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Initial error", body: bootstrap.initial_error }) : null, shell.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "App shell error", body: shell.error }) : null, shell.loading && !shell.data ? /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading app shell" }) : null, shell.data ? /* @__PURE__ */ React.createElement("section", { className: "environment-strip" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, "Runs"), /* @__PURE__ */ React.createElement("span", null, shell.data.environment?.runs_dir)), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, "Workflows"), /* @__PURE__ */ React.createElement("span", null, shell.data.environment?.workflows_dir)), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, "Local LLM"), /* @__PURE__ */ React.createElement("span", null, String(shell.data.environment?.local_llm?.healthy))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, "App DB"), /* @__PURE__ */ React.createElement("span", null, shell.data.environment?.app_db))) : null, page);
  }
  function OverviewPage({ shell, navigate }) {
    const overview = shell?.overview;
    if (!overview) {
      return /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading overview" });
    }
    return /* @__PURE__ */ React.createElement("main", { className: "page-grid" }, /* @__PURE__ */ React.createElement("section", { className: "panel hero-panel" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Overview"), /* @__PURE__ */ React.createElement("h2", null, overview.hero?.title), /* @__PURE__ */ React.createElement("p", null, overview.hero?.summary), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => navigate(overview.resume_target?.href || "/workbench") }, overview.resume_target?.label || "Resume"), /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate("/workbench") }, "Open workbench"))), /* @__PURE__ */ React.createElement("section", { className: "stats-grid" }, /* @__PURE__ */ React.createElement(MetricCard, { label: "Indexed runs", value: overview.counts?.runs ?? 0 }), /* @__PURE__ */ React.createElement(MetricCard, { label: "Indexed workflows", value: overview.counts?.workflows ?? 0 }), /* @__PURE__ */ React.createElement(MetricCard, { label: "Latest action", value: overview.resume_target?.kind || "workbench" })), overview.latest_run ? /* @__PURE__ */ React.createElement(RunCard, { run: overview.latest_run, onOpen: () => navigate(`/runs/${overview.latest_run.run_id}`) }) : null, overview.empty_state ? /* @__PURE__ */ React.createElement("section", { className: "panel" }, /* @__PURE__ */ React.createElement("h3", null, overview.empty_state.title), /* @__PURE__ */ React.createElement("p", null, overview.empty_state.summary), /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => navigate(overview.empty_state.primary_cta?.href || "/workbench") }, overview.empty_state.primary_cta?.label || "Open workbench")) : null);
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
    return /* @__PURE__ */ React.createElement("main", { className: "page-grid" }, /* @__PURE__ */ React.createElement("section", { className: "panel" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Runs"), /* @__PURE__ */ React.createElement("h2", null, "Inspect canonical run history"), /* @__PURE__ */ React.createElement(
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
    )), resource.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Runs unavailable", body: resource.error }) : null, resource.loading ? /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading runs" }) : null, /* @__PURE__ */ React.createElement("section", { className: "panel" }, /* @__PURE__ */ React.createElement("table", { className: "data-table" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", null, /* @__PURE__ */ React.createElement("th", null, "Run"), /* @__PURE__ */ React.createElement("th", null, "Workflow"), /* @__PURE__ */ React.createElement("th", null, "Status"), /* @__PURE__ */ React.createElement("th", null, "Provider"), /* @__PURE__ */ React.createElement("th", null, "Updated"))), /* @__PURE__ */ React.createElement("tbody", null, (resource.data?.items || []).map((run) => /* @__PURE__ */ React.createElement("tr", { key: run.run_id }, /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement("a", { href: `/runs/${run.run_id}`, onClick: (event) => {
      event.preventDefault();
      navigate(`/runs/${run.run_id}`);
    } }, run.run_id)), /* @__PURE__ */ React.createElement("td", null, run.workflow?.title || run.workflow?.name || "Unknown workflow"), /* @__PURE__ */ React.createElement("td", null, /* @__PURE__ */ React.createElement(StatusPill, { value: run.status })), /* @__PURE__ */ React.createElement("td", null, run.provider), /* @__PURE__ */ React.createElement("td", null, run.updated_at || "\u2014"))))), !resource.loading && !(resource.data?.items || []).length ? /* @__PURE__ */ React.createElement(EmptyState, { title: "No runs match the current filter", body: "Try clearing filters or running a workflow from the workbench." }) : null));
  }
  function RunDetailPage({ runId, navigate }) {
    const resource = useJsonResource(`${bootstrap.api_root}/runs/${runId}`, [runId]);
    if (resource.error) {
      return /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Run detail unavailable", body: resource.error });
    }
    if (resource.loading || !resource.data) {
      return /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading run detail" });
    }
    const run = resource.data;
    const report = run.artifacts?.report || {};
    return /* @__PURE__ */ React.createElement("main", { className: "page-grid detail-shell" }, /* @__PURE__ */ React.createElement("section", { className: "panel hero-panel detail-hero" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Run detail"), /* @__PURE__ */ React.createElement("h2", null, run.hero?.title || run.workflow?.title || run.run_id), /* @__PURE__ */ React.createElement("p", null, run.hero?.summary || "Inspect the latest run summary, question rows, and artifacts."), /* @__PURE__ */ React.createElement("div", { className: "meta-row" }, /* @__PURE__ */ React.createElement(StatusPill, { value: run.run?.status }), /* @__PURE__ */ React.createElement("span", null, run.run?.provider || "Unknown provider"), /* @__PURE__ */ React.createElement("span", null, run.run?.updated_at || run.run?.completed_at || "\u2014")), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => navigate("/workbench") }, "Back to workbench"), run.recommended_compare ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(run.recommended_compare.href) }, "Compare with ", run.recommended_compare.run_id) : null, report.available ? /* @__PURE__ */ React.createElement("a", { className: "secondary-link", href: report.href, target: "_blank", rel: "noreferrer" }, "Open HTML report") : null)), /* @__PURE__ */ React.createElement("section", { className: "stats-grid" }, (run.summary_cards || []).map((card) => /* @__PURE__ */ React.createElement(MetricCard, { key: card.label, label: card.label, value: card.value }))), /* @__PURE__ */ React.createElement("div", { className: "detail-grid" }, /* @__PURE__ */ React.createElement("div", { className: "detail-main" }, /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Readable summary"), /* @__PURE__ */ React.createElement("p", null, "Grouped metadata keeps the run context visible without opening raw JSON."))), /* @__PURE__ */ React.createElement("div", { className: "info-grid" }, (run.metadata_groups || []).map((group) => /* @__PURE__ */ React.createElement(KeyValueGroup, { key: group.title, group })))), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Results snapshot"), /* @__PURE__ */ React.createElement("p", null, "Core quality, training, and usage metrics in one place."))), (run.result_groups || []).length ? /* @__PURE__ */ React.createElement("div", { className: "info-grid" }, (run.result_groups || []).map((group) => /* @__PURE__ */ React.createElement(KeyValueGroup, { key: group.title, group }))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No result summary yet", body: "This run does not include evaluation or training summary fields." })), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Forecast table"), /* @__PURE__ */ React.createElement("p", null, "Question titles, forecast values, and scoring context for quick review.")), /* @__PURE__ */ React.createElement("span", { className: "section-count" }, run.forecast_table?.count || 0, " rows")), /* @__PURE__ */ React.createElement(RunForecastTable, { rows: run.forecast_table?.rows || [], emptyState: run.forecast_table?.empty_state }))), /* @__PURE__ */ React.createElement("aside", { className: "detail-sidebar" }, /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Guided actions"), /* @__PURE__ */ React.createElement("p", null, "Jump to the next useful surface from this run."))), /* @__PURE__ */ React.createElement("div", { className: "action-stack" }, (run.guided_actions || []).map((action) => /* @__PURE__ */ React.createElement("button", { key: action.label, className: "secondary-button action-button", onClick: () => navigate(action.href) }, action.label)))), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Report & artifacts"), /* @__PURE__ */ React.createElement("p", null, "Use the report when available; fall back to raw files when it is not."))), /* @__PURE__ */ React.createElement(ReportCard, { report }), /* @__PURE__ */ React.createElement(ArtifactList, { items: run.artifacts?.items || [] }), Object.keys(run.artifacts?.raw || {}).length ? /* @__PURE__ */ React.createElement("details", { className: "artifact-preview" }, /* @__PURE__ */ React.createElement("summary", null, "Raw structured payloads"), Object.entries(run.artifacts?.raw || {}).map(([key, value]) => /* @__PURE__ */ React.createElement(ArtifactPreview, { key, label: key, value }))) : null), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Compare next"), /* @__PURE__ */ React.createElement("p", null, "Pick a baseline to understand whether the candidate moved the right metrics."))), (run.baseline_candidates || []).length ? /* @__PURE__ */ React.createElement("div", { className: "action-list" }, (run.baseline_candidates || []).map((item) => /* @__PURE__ */ React.createElement("button", { key: item.run_id, className: "secondary-button action-button", onClick: () => navigate(item.href) }, item.label || item.run_id))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No comparison candidates", body: "Run another workflow revision to unlock side-by-side comparison." })), /* @__PURE__ */ React.createElement("section", { className: "panel section-stack" }, /* @__PURE__ */ React.createElement("div", { className: "section-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", null, "Node timeline"), /* @__PURE__ */ React.createElement("p", null, "Execution order and final state of each graph step."))), (run.graph_trace || []).length ? /* @__PURE__ */ React.createElement("ul", { className: "timeline-list" }, (run.graph_trace || []).map((item, index) => /* @__PURE__ */ React.createElement("li", { key: `${item.node}-${index}` }, /* @__PURE__ */ React.createElement("strong", null, item.node), /* @__PURE__ */ React.createElement("span", null, item.status || "observed")))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No graph trace", body: "This run did not persist graph trace rows." })))));
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
  function WorkbenchPage({ route, shell, navigate, onMutate }) {
    const params = useMemo(() => new URLSearchParams(route.search), [route.search]);
    const draftId = params.get("draft");
    const selectedWorkflow = params.get("workflow") || shell?.overview?.latest_run?.workflow?.name || "demo-provider-free";
    const workflows = useJsonResource(`${bootstrap.api_root}/workflows`, [route.search]);
    const draft = useJsonResource(draftId ? `${bootstrap.api_root}/drafts/${draftId}` : null, [draftId]);
    const workflow = useJsonResource(!draftId ? `${bootstrap.api_root}/workflows/${selectedWorkflow}` : null, [selectedWorkflow, draftId]);
    const [formValues, setFormValues] = useState({});
    const [busy, setBusy] = useState(null);
    const [actionNotice, setActionNotice] = useState(null);
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
    const safeEditSupport = activeDraft?.guidance?.supported_edits || activeSafeEdit?.supported_edits || [];
    const safeEditLimitations = activeDraft?.guidance?.limitations || activeSafeEdit?.limitations || [];
    const sourceOfTruth = activeDraft?.guidance?.source_of_truth || defaultSourceOfTruth();
    const nextStep = activeDraft?.guidance?.next_step || buildDraftlessNextStep(activeWorkflow, overviewLatestRun);
    const stepState = draftId ? decorateStepState(activeDraft?.step_state || defaultStepState(), activeDraft, true) : decorateStepState(draftlessStepState(activeWorkflow), null, false);
    const validationStatus = buildValidationStatus(activeDraft);
    const validationFixes = buildValidationFixes(activeDraft);
    const runDisabled = !(activeDraft?.validation?.ok && !activeDraft?.validation?.stale);
    const draftActionLabel = activeWorkflow?.source === "local" ? "Open local draft session" : "Clone into local draft";
    const draftActionSummary = activeWorkflow?.source === "local" ? "This workflow already lives in your local workspace, but edits still flow through a draft session so validation and resume state stay explicit." : "Built-in workflows are reference blueprints. Clone one into a local draft before editing any field.";
    async function createDraft(sourceWorkflowName) {
      setBusy("Creating local draft");
      setActionNotice(null);
      try {
        const payload = { source_workflow_name: sourceWorkflowName };
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
    async function persistDraft(nextValues) {
      if (!draftId) return null;
      return requestJson(`${bootstrap.api_root}/drafts/${draftId}`, {
        method: "PATCH",
        body: JSON.stringify({ values: nextValues })
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
          body: "Safe-edit values are stored in SQLite. Next: validate the cloned workflow before running a candidate."
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
          validation?.ok ? {
            tone: validation.stale ? "warning" : "success",
            title: validation.stale ? "Validation needs a refresh" : "Validation passed",
            body: validation.stale ? "A newer edit changed the draft after validation. Validate once more before you run." : "The latest safe edits validated successfully. Next: run a candidate and compare it with the baseline."
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
    function updateFormValue(key, value) {
      setActionNotice(null);
      setFormValues((current) => ({ ...current, [key]: value }));
    }
    return /* @__PURE__ */ React.createElement("main", { className: "workbench-layout" }, /* @__PURE__ */ React.createElement("aside", { className: "panel step-panel" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Journey"), /* @__PURE__ */ React.createElement("h2", null, "Inspect \u2192 clone \u2192 safe edit"), /* @__PURE__ */ React.createElement("ol", { className: "step-list step-rail" }, stepState.map((step) => /* @__PURE__ */ React.createElement("li", { key: step.key, className: `step-item step-${step.state || "upcoming"}${step.locked ? " locked" : ""}` }, /* @__PURE__ */ React.createElement("div", { className: "step-head" }, /* @__PURE__ */ React.createElement("strong", null, step.label), /* @__PURE__ */ React.createElement("span", { className: `step-status ${step.state || "upcoming"}` }, stepBadgeLabel(step))), /* @__PURE__ */ React.createElement("span", null, step.description))))), /* @__PURE__ */ React.createElement("section", { className: "workbench-main" }, workflow.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Workflow unavailable", body: workflow.error }) : null, draft.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Draft unavailable", body: draft.error }) : null, workflows.error ? /* @__PURE__ */ React.createElement(Message, { tone: "error", title: "Workflow catalog unavailable", body: workflows.error }) : null, actionNotice ? /* @__PURE__ */ React.createElement(Message, { tone: actionNotice.tone, title: actionNotice.title, body: actionNotice.body }) : null, busy ? /* @__PURE__ */ React.createElement(LoadingCard, { label: busy }) : null, draftId && draft.loading && !draft.data ? /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading draft" }) : null, !draftId && workflow.loading && !workflow.data ? /* @__PURE__ */ React.createElement(LoadingCard, { label: "Loading workflow" }) : null, /* @__PURE__ */ React.createElement("section", { className: "panel hero-panel workbench-hero" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Workbench"), /* @__PURE__ */ React.createElement("h2", null, draftId ? "Guide one safe draft from inspection to comparison" : "Choose a workflow, then unlock safe edits with a local draft"), /* @__PURE__ */ React.createElement("p", null, draftId ? "Stay in context while you inspect the baseline, validate inline, run a candidate, and decide what to do next." : "Built-in workflows stay read-only until you clone them. Draft values live in SQLite so you can validate and iterate without losing context."), /* @__PURE__ */ React.createElement("div", { className: "meta-row" }, /* @__PURE__ */ React.createElement(SourceBadge, { source: activeWorkflow?.source || "builtin" }), activeDraft?.draft_workflow_name ? /* @__PURE__ */ React.createElement("span", null, "Draft: ", activeDraft.draft_workflow_name) : null, activeDraft?.baseline_run_id ? /* @__PURE__ */ React.createElement("span", null, "Baseline: ", activeDraft.baseline_run_id) : overviewLatestRun?.run_id ? /* @__PURE__ */ React.createElement("span", null, "Suggested baseline: ", overviewLatestRun.run_id) : null, activeDraft?.last_run_id ? /* @__PURE__ */ React.createElement("span", null, "Candidate: ", activeDraft.last_run_id) : null), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, !draftId ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => createDraft(activeWorkflow?.name || selectedWorkflow) }, draftActionLabel), overviewLatestRun?.run_id ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(`/runs/${overviewLatestRun.run_id}`) }, "Inspect latest run") : /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate("/runs") }, "Browse runs")) : /* @__PURE__ */ React.createElement(React.Fragment, null, activeDraft?.baseline_run_id ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(`/runs/${activeDraft.baseline_run_id}`) }, "Inspect baseline") : /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate("/runs") }, "Choose a baseline"), activeDraft?.last_run_id ? /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: () => navigate(`/runs/${activeDraft.last_run_id}`) }, "Inspect candidate run") : null))), /* @__PURE__ */ React.createElement("section", { className: "panel" }, /* @__PURE__ */ React.createElement("div", { className: "section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "1. Inspect + clone"), /* @__PURE__ */ React.createElement("h3", null, "Pick a workflow and keep the baseline in view")), /* @__PURE__ */ React.createElement("p", { className: "section-copy" }, draftActionSummary)), /* @__PURE__ */ React.createElement("div", { className: "inspect-grid" }, /* @__PURE__ */ React.createElement("article", { className: "surface-card" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, activeWorkflow?.title || activeWorkflow?.name || selectedWorkflow), /* @__PURE__ */ React.createElement("p", null, activeWorkflow?.description || "Select a workflow from the catalog.")), /* @__PURE__ */ React.createElement(SourceBadge, { source: activeWorkflow?.source || "builtin" })), /* @__PURE__ */ React.createElement("p", { className: "helper-text" }, draftActionSummary), !draftId ? /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: () => createDraft(activeWorkflow?.name || selectedWorkflow) }, draftActionLabel) : /* @__PURE__ */ React.createElement("dl", { className: "context-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Source"), /* @__PURE__ */ React.createElement("dd", null, activeDraft?.source_workflow_name || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Local draft"), /* @__PURE__ */ React.createElement("dd", null, activeDraft?.draft_workflow_name || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Status"), /* @__PURE__ */ React.createElement("dd", null, activeDraft?.status || "\u2014")))), /* @__PURE__ */ React.createElement("article", { className: "surface-card" }, /* @__PURE__ */ React.createElement("div", { className: "surface-header" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("strong", null, "Baseline context"), /* @__PURE__ */ React.createElement("p", null, "Inspect first so the next edit has a clear comparison target."))), activeDraft?.baseline_run || overviewLatestRun ? /* @__PURE__ */ React.createElement("dl", { className: "context-list" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Run"), /* @__PURE__ */ React.createElement("dd", null, formatRunContext(activeDraft?.baseline_run || overviewLatestRun))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Workflow"), /* @__PURE__ */ React.createElement("dd", null, activeDraft?.baseline_run?.workflow?.title || activeDraft?.baseline_run?.workflow?.name || overviewLatestRun?.workflow?.title || overviewLatestRun?.workflow?.name || "\u2014")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("dt", null, "Action"), /* @__PURE__ */ React.createElement("dd", null, activeDraft?.baseline_run_id ? "Compare against this baseline after your candidate run." : "Use the latest run as a suggested baseline when you clone."))) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No baseline yet", body: "Run history is empty. You can still create a draft, then inspect the first candidate run after it completes." }))), /* @__PURE__ */ React.createElement("div", { className: "workflow-list workflow-catalog" }, (workflows.data?.items || []).map((item) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: item.name,
        className: item.name === activeWorkflow?.name ? "workflow-tile active" : "workflow-tile",
        onClick: () => navigate(`/workbench?workflow=${encodeURIComponent(item.name)}`)
      },
      /* @__PURE__ */ React.createElement("div", { className: "workflow-tile-head" }, /* @__PURE__ */ React.createElement("strong", null, item.title), /* @__PURE__ */ React.createElement(SourceBadge, { source: item.source })),
      /* @__PURE__ */ React.createElement("span", null, item.name),
      /* @__PURE__ */ React.createElement("span", { className: "workflow-note" }, item.source === "builtin" ? "Read-only until cloned" : "Local workflow available for a draft session")
    )))), /* @__PURE__ */ React.createElement("section", { className: "panel" }, /* @__PURE__ */ React.createElement("div", { className: "section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "2. Safe edit"), /* @__PURE__ */ React.createElement("h3", null, "Change only the fields this product contract supports")), /* @__PURE__ */ React.createElement("p", { className: "section-copy" }, "Question limits, report output, and supported aggregate weights are editable. No arbitrary JSON editor is exposed.")), /* @__PURE__ */ React.createElement("div", { className: "supported-edit-list" }, safeEditSupport.map((edit) => /* @__PURE__ */ React.createElement("article", { key: edit.key, className: "supported-edit-card" }, /* @__PURE__ */ React.createElement("strong", null, edit.label), /* @__PURE__ */ React.createElement("p", null, edit.detail)))), !draftId ? /* @__PURE__ */ React.createElement(
      EmptyState,
      {
        title: "Editing stays locked until you create a draft",
        body: "Choose Clone into local draft first. Built-in workflows remain read-only reference blueprints until the clone step succeeds."
      }
    ) : /* @__PURE__ */ React.createElement(React.Fragment, null, activeDraft?.preview_error ? /* @__PURE__ */ React.createElement(Message, { tone: "warning", title: "Safe edit needs attention", body: `${activeDraft.preview_error} Fix the supported fields below; your draft session is still preserved in SQLite.` }) : null, /* @__PURE__ */ React.createElement("div", { className: "form-grid guided-form" }, /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Questions limit"), /* @__PURE__ */ React.createElement("span", { className: "field-help" }, "Safe range ", activeSafeEdit?.questions_limit?.min || 1, "\u2013", activeSafeEdit?.questions_limit?.max || 25, ". This only changes the cloned workflow."), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "number",
        min: activeSafeEdit?.questions_limit?.min || 1,
        max: activeSafeEdit?.questions_limit?.max || 25,
        value: formValues.questions_limit || "",
        onChange: (event) => updateFormValue("questions_limit", event.target.value)
      }
    )), /* @__PURE__ */ React.createElement("label", null, /* @__PURE__ */ React.createElement("span", null, "Write HTML report"), /* @__PURE__ */ React.createElement("span", { className: "field-help" }, "Choose whether the candidate run writes report.html."), /* @__PURE__ */ React.createElement(
      "select",
      {
        value: formValues.artifacts_write_report || "true",
        onChange: (event) => updateFormValue("artifacts_write_report", event.target.value)
      },
      /* @__PURE__ */ React.createElement("option", { value: "true" }, "true"),
      /* @__PURE__ */ React.createElement("option", { value: "false" }, "false")
    )), (activeSafeEdit?.aggregate_weight_editors || []).map((editor) => /* @__PURE__ */ React.createElement("div", { key: editor.node, className: "weight-editor" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h4", null, editor.node), /* @__PURE__ */ React.createElement("p", { className: "field-help" }, "Adjust upstream candidate weights only. Weights are normalized when the draft is validated.")), editor.contributors.map((contributor) => {
      const key = `weight:${editor.node}:${contributor.name}`;
      return /* @__PURE__ */ React.createElement("label", { key }, /* @__PURE__ */ React.createElement("span", null, contributor.name), /* @__PURE__ */ React.createElement(
        "input",
        {
          type: "number",
          min: 0,
          max: 100,
          value: formValues[key] || "",
          onChange: (event) => updateFormValue(key, event.target.value)
        }
      ));
    })))))), /* @__PURE__ */ React.createElement("section", { className: "panel" }, /* @__PURE__ */ React.createElement("div", { className: "section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "3. Validate + run"), /* @__PURE__ */ React.createElement("h3", null, "Validate inline, then run only when the latest draft is safe")), /* @__PURE__ */ React.createElement("p", { className: "section-copy" }, "Validation stays inside the edit flow so you can fix problems without losing the current draft context.")), !draftId ? /* @__PURE__ */ React.createElement(EmptyState, { title: "No draft to validate yet", body: "Clone or reopen a local draft session first. Then this panel will keep validation, fixes, and run readiness together." }) : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(Message, { tone: validationStatus.tone, title: validationStatus.title, body: validationStatus.body }), validationFixes.length ? /* @__PURE__ */ React.createElement("ul", { className: "teaching-list" }, validationFixes.map((note) => /* @__PURE__ */ React.createElement("li", { key: note }, note))) : null, /* @__PURE__ */ React.createElement("div", { className: "button-row" }, /* @__PURE__ */ React.createElement("button", { className: "secondary-button", onClick: saveDraft }, "Save draft"), /* @__PURE__ */ React.createElement("button", { className: "primary-button", onClick: validateDraft }, "Save + validate"), /* @__PURE__ */ React.createElement("button", { className: "primary-button", disabled: runDisabled, onClick: runDraft }, "Run candidate")))), /* @__PURE__ */ React.createElement("section", { className: "panel" }, /* @__PURE__ */ React.createElement("div", { className: "section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "4. Compare + next step"), /* @__PURE__ */ React.createElement("h3", null, "Use the outcome to decide what happens next")), /* @__PURE__ */ React.createElement("p", { className: "section-copy" }, "Success states should teach the next action: inspect the candidate, compare it with the baseline, or keep iterating.")), activeDraft?.compare ? /* @__PURE__ */ React.createElement("div", { className: "compare-outcome" }, /* @__PURE__ */ React.createElement(Message, { tone: "success", title: `Compare verdict: ${activeDraft.compare.verdict?.label || "ready"}`, body: activeDraft.compare.verdict?.summary || "Open the comparison to inspect detailed metric deltas." }), /* @__PURE__ */ React.createElement("div", { className: "button-row" }, (activeDraft.compare.next_actions || []).map((action, index) => /* @__PURE__ */ React.createElement("button", { key: action.href || action.label || index, className: index === 0 ? "primary-button" : "secondary-button", onClick: () => navigate(action.href) }, action.label)))) : activeDraft?.last_run_id ? /* @__PURE__ */ React.createElement(Message, { tone: "success", title: "Candidate run completed", body: "Inspect the candidate run now. Add a baseline if you want to compare it before deciding on the next edit." }) : /* @__PURE__ */ React.createElement(EmptyState, { title: "No candidate run yet", body: "Once validation passes and you run a candidate, this panel will explain whether to compare, iterate, or stop." })), /* @__PURE__ */ React.createElement("section", { className: "panel" }, /* @__PURE__ */ React.createElement("div", { className: "section-heading" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Canvas"), /* @__PURE__ */ React.createElement("h3", null, "See the workflow before you change it")), /* @__PURE__ */ React.createElement("p", { className: "section-copy" }, "The canvas stays visible so inspection and editing happen against the same workflow structure.")), /* @__PURE__ */ React.createElement("div", { className: "canvas-grid" }, (activeCanvas?.nodes || []).map((node) => /* @__PURE__ */ React.createElement("article", { key: node.name, className: "canvas-node" }, /* @__PURE__ */ React.createElement("strong", null, node.name), /* @__PURE__ */ React.createElement("span", null, node.kind), /* @__PURE__ */ React.createElement("span", null, node.description || node.implementation || "No description"), /* @__PURE__ */ React.createElement(StatusPill, { value: node.status || "not-run" })))))), /* @__PURE__ */ React.createElement("aside", { className: "panel guidance-panel" }, /* @__PURE__ */ React.createElement("span", { className: "eyebrow" }, "Next step"), /* @__PURE__ */ React.createElement("section", { className: "next-step-card" }, /* @__PURE__ */ React.createElement("strong", null, nextStep.title), /* @__PURE__ */ React.createElement("p", null, nextStep.detail)), /* @__PURE__ */ React.createElement("section", { className: "guidance-section" }, /* @__PURE__ */ React.createElement("h3", null, "Safe-edit contract"), /* @__PURE__ */ React.createElement("ul", { className: "guidance-list" }, safeEditLimitations.map((item) => /* @__PURE__ */ React.createElement("li", { key: item }, item)))), /* @__PURE__ */ React.createElement("section", { className: "guidance-section" }, /* @__PURE__ */ React.createElement("h3", null, "Supported fields"), /* @__PURE__ */ React.createElement("ul", { className: "guidance-list compact-list" }, safeEditSupport.map((item) => /* @__PURE__ */ React.createElement("li", { key: item.key }, /* @__PURE__ */ React.createElement("strong", null, item.label), /* @__PURE__ */ React.createElement("span", null, item.detail))))), /* @__PURE__ */ React.createElement("section", { className: "guidance-section" }, /* @__PURE__ */ React.createElement("h3", null, "What stays authoritative"), /* @__PURE__ */ React.createElement("ul", { className: "guidance-list" }, sourceOfTruth.map((item) => /* @__PURE__ */ React.createElement("li", { key: item }, item))))));
  }
  function draftlessStepState(activeWorkflow) {
    const source = activeWorkflow?.source || "builtin";
    const cloneDescription = source === "local" ? "Open a draft session for the local workflow." : "Clone the built-in workflow before editing.";
    return [
      { key: "inspect", label: "Inspect", locked: false, description: "Review the workflow and choose a baseline run." },
      { key: "clone", label: "Clone", locked: false, description: cloneDescription },
      { key: "edit", label: "Safe edit", locked: true, description: "Locked until a draft session exists." },
      { key: "validate", label: "Validate", locked: true, description: "Locked until the safe edit can be checked inline." },
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
      clone: "Built-in workflows remain read-only until the clone step succeeds.",
      save: "Only the supported safe-edit fields can be stored in the draft session.",
      validate: "Fix the supported fields below, then validate again without losing the current draft context.",
      run: "The draft stays loaded. Re-validate the latest safe edit before you try another run."
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
        body: "Save and validate inline before you run this draft. The run step stays locked until the latest validation passes."
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
        body: "The latest safe edit is runnable. Next: run a candidate and compare it with the baseline."
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
        notes.add("Stay inside the listed safe-edit fields. The workbench does not expose arbitrary JSON or implementation edits.");
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
        title: "Inspect the latest run, then clone",
        detail: "Review the baseline context first, then clone the built-in workflow into a local draft before making a safe edit."
      };
    }
    return {
      key: "clone",
      title: "Clone a workflow to begin",
      detail: "Choose a workflow from the catalog and create a local draft. Safe edits only unlock after that step succeeds."
    };
  }
  function defaultSourceOfTruth() {
    return [
      "Built-in workflows stay read-only until you clone them into a local workflow.",
      "Reusable local workflows remain JSON files on disk.",
      "Draft values, validation snapshots, and resume state live in SQLite."
    ];
  }
  function formatRunContext(run) {
    if (!run) return "\u2014";
    const workflow = run.workflow?.title || run.workflow?.name;
    return [run.run_id, workflow, run.status].filter(Boolean).join(" \xB7 ");
  }
  function SourceBadge({ source }) {
    const normalized = String(source || "unknown").toLowerCase();
    const label = normalized === "builtin" ? "Built-in \xB7 read-only" : normalized === "local" ? "Local workflow" : source;
    return /* @__PURE__ */ React.createElement("span", { className: `source-pill ${normalized}` }, label);
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
      { key: "clone", label: "Clone", locked: false, description: "Create or reopen a local draft session." },
      { key: "edit", label: "Safe edit", locked: true, description: "Locked until a draft exists." },
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
