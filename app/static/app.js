const state = {
  project: null,
  sourceSvg: null,
  design: null,
  designSvg: null,
  designId: null,
  jobId: null,
  candidates: [],
  validation: [],
  issues: [],
  fixes: [],
  counts: null,
  finalAnswer: "",
  done: false,
  busy: false,
  selectedRoom: null,
  fixtures: new Set(["WC", "BASIN", "SHOWER"]),
  profiles: [],
  eventSource: null,
  pollTimer: null,
  traceCount: 0,
};

const $ = (selector) => document.querySelector(selector);
const canvas = $("#canvas");

function init() {
  bind();
  loadHealthAndProfiles().then(() => loadSample());
}

function bind() {
  $("#sample-button").addEventListener("click", loadSample);
  $("#empty-sample").addEventListener("click", loadSample);
  $("#file-input").addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    if (file) uploadFile(file);
    event.target.value = "";
  });
  $("#design-button").addEventListener("click", startDesign);
  $("#approve-button").addEventListener("click", approveDesign);
  $("#approve-top").addEventListener("click", approveDesign);
  $("#tab-design").addEventListener("click", () => showCanvas("design"));
  $("#tab-plan").addEventListener("click", () => showCanvas("plan"));
  $("#profile-select").addEventListener("change", () => {
    if (state.design) showToast("Rule pack change applies to the next design.");
  });
  canvas.addEventListener("click", (event) => {
    const room = event.target.closest("[data-room-id]");
    if (room && !state.busy) selectRoom(room.dataset.roomId);
  });
}

async function loadHealthAndProfiles() {
  try {
    const health = await api("/api/health");
    setProvider(health);
    const data = await api("/api/profiles");
    state.profiles = data.profiles || [];
    const select = $("#profile-select");
    select.innerHTML = "";
    for (const profile of state.profiles) {
      const option = document.createElement("option");
      option.value = profile.id;
      option.textContent = profile.name;
      select.appendChild(option);
    }
    if (state.profiles[0]) select.value = state.profiles[0].id;
  } catch (error) {
    setProvider({ provider: "unavailable", model: "", ready: false });
    showToast(error.message, true);
  }
}

function setProvider(health) {
  const badge = $("#provider-badge");
  badge.className = "badge";
  if (!health.ready) {
    badge.textContent = "Provider unavailable";
    badge.classList.add("bad");
  } else if (health.provider === "meta") {
    badge.textContent = `Meta · ${health.model}`;
    badge.classList.add("good");
  } else if (health.provider === "openrouter") {
    badge.textContent = `OpenRouter · ${health.model}`;
  } else {
    badge.textContent = "Fake · offline demo";
    badge.classList.add("warn");
  }
  $("#model-info").textContent = health.ready
    ? `${health.provider} / ${health.model}. The provider is selected by the API key strategy in .env.`
    : health.error || "Provider configuration is incomplete.";
}

async function loadSample() {
  if (state.busy) return;
  setBusy(true);
  setAgentStatus("Loading sample plan…");
  try {
    const project = await api("/api/projects/sample?name=apartment", { method: "POST" });
    setProject(project);
  } catch (error) {
    showToast(error.message, true);
    setAgentStatus("Could not load the sample plan.", "error");
  } finally {
    setBusy(false);
    updateDesignButton();
  }
}

async function uploadFile(file) {
  if (state.busy) return;
  setBusy(true);
  setAgentStatus("Reading the DXF…");
  const form = new FormData();
  form.append("file", file);
  try {
    const project = await api("/api/projects", { method: "POST", body: form });
    setProject(project);
    showToast("Plan loaded.");
  } catch (error) {
    showToast(error.message, true);
    setAgentStatus("The DXF could not be read.", "error");
  } finally {
    setBusy(false);
    updateDesignButton();
  }
}

function setProject(project) {
  state.project = project;
  state.sourceSvg = project.svg;
  state.design = null;
  state.designSvg = null;
  state.designId = null;
  state.jobId = null;
  state.candidates = [];
  state.validation = [];
  state.issues = [];
  state.fixes = [];
  state.counts = null;
  state.finalAnswer = "";
  state.done = false;
  state.selectedRoom = null;

  renderProjectSummary(project);
  renderRooms(project.rooms);
  renderShafts(project.shafts);
  renderFixtures();
  renderCanvas(project.svg);
  renderTraceEmpty();
  renderValidationPlaceholder();
  $("#final-answer").classList.add("hidden");
  $("#layouts-card").classList.add("hidden");
  $("#counts").innerHTML = "";
  $("#approve-button").disabled = true;
  $("#approve-top").disabled = true;
  $("#download-link").classList.add("hidden");
  $("#canvas-caption").textContent = `${project.name} · ${project.rooms.length} room(s) · ${project.units}`;
  showCanvas("design");
  const first =
    project.rooms.find((room) => room.wet_area) || project.rooms[0] || null;
  if (first) selectRoom(first.id);
  setAgentStatus("Plan ready. Choose a room and fixtures, then run the agent.");
}

function renderProjectSummary(project) {
  const el = $("#project-summary");
  const warnings = project.warnings?.length
    ? `<div class="hint tiny" style="margin-top:6px">${escapeHtml(project.warnings.join(" "))}</div>`
    : "";
  el.innerHTML = `<strong>${escapeHtml(project.name)}</strong><br>${project.rooms.length} room(s) · ${project.units} · scale ${project.source_scale} mm/unit${warnings}`;
  el.classList.remove("hidden");
}

function renderRooms(rooms) {
  const list = $("#room-list");
  list.innerHTML = "";
  if (!rooms.length) {
    list.innerHTML = `<p class="hint">No closed rooms found. Draw a closed polyline on A-ROOM and re-upload.</p>`;
    return;
  }
  rooms.forEach((room) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "room-card";
    button.dataset.roomId = room.id;
    button.innerHTML = `
      <span>
        <span class="room-name">${escapeHtml(room.name || `Room ${room.id}`)}</span>
        <span class="room-meta">${room.width_mm.toFixed(0)} × ${room.height_mm.toFixed(0)} mm</span>
      </span>
      <span class="room-area">${room.area_m2.toFixed(2)} m²</span>`;
    button.addEventListener("click", () => selectRoom(room.id));
    list.appendChild(button);
  });
}

function selectRoom(roomId) {
  state.selectedRoom = roomId;
  document.querySelectorAll(".room-card").forEach((card) => {
    card.classList.toggle("active", card.dataset.roomId === roomId);
  });
  document.querySelectorAll("#canvas .room").forEach((polygon) => {
    polygon.classList.toggle("selected", polygon.dataset.roomId === roomId);
  });
  updateDesignButton();
}

function renderShafts(shafts) {
  const select = $("#shaft-select");
  select.innerHTML = "";
  if (!shafts.length) {
    const option = document.createElement("option");
    option.textContent = "No shaft detected";
    option.value = "";
    select.appendChild(option);
    return;
  }
  shafts.forEach((shaft) => {
    const option = document.createElement("option");
    option.value = shaft.id;
    option.textContent = `${shaft.id} · ${shaft.width_mm} × ${shaft.depth_mm} mm`;
    select.appendChild(option);
  });
}

function renderFixtures() {
  const list = $("#fixture-list");
  list.innerHTML = "";
  for (const type of ["WC", "BASIN", "SHOWER", "FLOOR_DRAIN"]) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chip" + (state.fixtures.has(type) ? " active" : "");
    button.textContent = type === "FLOOR_DRAIN" ? "Floor drain" : type;
    button.addEventListener("click", () => {
      if (state.fixtures.has(type)) state.fixtures.delete(type);
      else state.fixtures.add(type);
      renderFixtures();
      updateDesignButton();
    });
    list.appendChild(button);
  }
}

function updateDesignButton() {
  const enabled =
    Boolean(state.project) &&
    Boolean(state.selectedRoom) &&
    state.fixtures.size > 0 &&
    !state.busy;
  $("#design-button").disabled = !enabled;
  $("#design-button").textContent = state.busy ? "Designing…" : "Design bathroom";
}

async function startDesign() {
  if (!state.project || !state.selectedRoom || state.fixtures.size === 0) return;
  resetRun();
  setBusy(true);
  setAgentStatus("Agent is inspecting the plan…", "running");
  addTrace("agent", "starting the design workflow");
  const body = {
    room_id: state.selectedRoom,
    fixtures: Array.from(state.fixtures),
    shaft_id: $("#shaft-select").value || null,
    profile_id: $("#profile-select").value,
    provider: null,
  };
  try {
    const start = await api(
      `/api/projects/${state.project.project_id}/design`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    );
    state.jobId = start.job_id;
    state.designId = start.design_id;
    setProvider({ ready: true, provider: start.provider, model: start.model });
    connectEvents(start.job_id);
  } catch (error) {
    showToast(error.message, true);
    setAgentStatus("The agent could not start.", "error");
    setBusy(false);
  }
}

function connectEvents(jobId) {
  if (state.eventSource) state.eventSource.close();
  const source = new EventSource(`/api/jobs/${jobId}/events`);
  state.eventSource = source;
  source.onmessage = (event) => {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch {
      return;
    }
    handleEvent(data);
  };
  source.onerror = () => {
    if (state.done) {
      source.close();
      return;
    }
    source.close();
    pollJob(jobId);
  };
}

function handleEvent(event) {
  if (event.type === "tool_call") {
    setAgentStatus(`Running ${event.tool}…`, "running");
    addTrace(event.tool, "running");
  } else if (event.type === "tool_result") {
    const detail = summarizeTool(event.tool, event.output);
    addTrace(event.tool, detail, !event.success);
    if (event.tool === "list_layout_options" && event.output?.candidates) {
      state.candidates = event.output.candidates;
      renderCandidates(state.candidates, null);
    }
    if ((event.tool === "validate_design" || event.tool === "apply_fix") && event.output?.counts) {
      state.counts = event.output.counts;
      state.issues = event.output.issues || [];
      state.fixes = event.output.fixes || [];
      renderValidation();
    }
    if (event.tool === "route_drainage" && event.output?.count) {
      setAgentStatus(`Routed ${event.output.count} branch pipe(s). Reviewing constraints…`, "running");
    }
    if (event.tool === "explain_design" && event.output?.explanation) {
      state.finalAnswer = event.output.explanation;
      renderFinalAnswer();
    }
  } else if (event.type === "assistant" && event.content) {
    addTrace("agent", truncate(event.content, 160));
  } else if (event.type === "final") {
    state.finalAnswer = event.content || state.finalAnswer;
    renderFinalAnswer();
    setAgentStatus("Agent finished. Review the validation and approve if it looks right.", "done");
  } else if (event.type === "snapshot") {
    applySnapshot(event);
  } else if (event.type === "error") {
    setAgentStatus(event.message || "Agent error.", "error");
    showToast(event.message || "Agent error.", true);
  }
}

function applySnapshot(data) {
  state.done = true;
  state.busy = false;
  state.design = data.design || null;
  state.designSvg = data.svg || state.sourceSvg;
  state.designId = data.design_id || state.designId;
  state.candidates = data.candidates || state.candidates;
  state.issues = data.issues || [];
  state.fixes = data.fixes || [];
  state.validation = data.validation || [];
  state.counts = data.counts || state.counts;
  state.finalAnswer = data.final_answer || state.finalAnswer;
  if (data.provider) setProvider({ ready: true, provider: data.provider, model: data.model });
  if (state.eventSource) {
    state.eventSource.close();
    state.eventSource = null;
  }
  if (state.pollTimer) {
    clearTimeout(state.pollTimer);
    state.pollTimer = null;
  }
  renderFinalAnswer();
  renderCandidates(state.candidates, state.design?.layout_id);
  renderValidation();
  if (state.designSvg) renderCanvas(state.designSvg);
  if (state.design) {
    showCanvas("design");
    $("#canvas-caption").textContent = `${state.design.layout_id || "design"} · ${state.design.pipes.length} pipe(s) · ${state.design.fixtures.length} fixture(s)`;
  }
  const canApprove = Boolean(state.design) && state.counts?.ERROR === 0;
  $("#approve-button").disabled = !canApprove || !state.done;
  $("#approve-top").disabled = $("#approve-button").disabled;
  setAgentStatus(
    state.done
      ? canApprove
        ? "Design complete. Review warnings, then approve or apply a fix."
        : "Design has errors. Apply a fix before export."
      : "Still working…",
    state.done ? (canApprove ? "done" : "error") : "running"
  );
  updateDesignButton();
}

function pollJob(jobId) {
  if (state.done) return;
  state.pollTimer = setTimeout(async () => {
    try {
      const job = await api(`/api/jobs/${jobId}`);
      if (job.done) {
        if (job.result) applySnapshot(job.result);
        else {
          setAgentStatus(job.error || "The job stopped.", "error");
          setBusy(false);
        }
      } else {
        pollJob(jobId);
      }
    } catch (error) {
      setAgentStatus(error.message, "error");
      setBusy(false);
    }
  }, 1000);
}

function summarizeTool(name, output) {
  if (!output) return "no output";
  if (output.error) return output.error;
  if (name === "inspect_plan") return `${output.rooms?.length || 0} rooms, ${output.shafts?.length || 0} shafts`;
  if (name === "list_layout_options") return `${output.count || 0} layout candidates`;
  if (name === "select_layout") return `${output.layout_id} · ${output.pattern}`;
  if (name === "route_drainage") return `${output.count || 0} branch pipes`;
  if (name === "validate_design" || name === "apply_fix") {
    const counts = output.counts || {};
    return `${counts.PASS || 0} pass · ${counts.WARNING || 0} warn · ${counts.ERROR || 0} error`;
  }
  if (name === "explain_design") return "deterministic summary ready";
  return "ok";
}

function renderCandidates(candidates, selectedId) {
  const card = $("#layouts-card");
  const list = $("#candidates");
  if (!candidates?.length) {
    card.classList.add("hidden");
    return;
  }
  card.classList.remove("hidden");
  list.innerHTML = "";
  candidates.forEach((candidate) => {
    const item = document.createElement("div");
    item.className = "candidate" + (candidate.id === selectedId ? " selected" : "");
    const violations = candidate.violations?.length
      ? `<div class="candidate-hint bad">${escapeHtml(candidate.violations.join("; "))}</div>`
      : `<div class="candidate-hint">${escapeHtml(candidate.rationale_hint || "")}</div>`;
    item.innerHTML = `
      <div class="candidate-head">
        <span>${escapeHtml(candidate.pattern)} · ${escapeHtml(candidate.id)}</span>
        <span>${Number(candidate.score).toFixed(0)}</span>
      </div>${violations}`;
    list.appendChild(item);
  });
}

function renderValidation() {
  const box = $("#validation");
  const counts = state.counts || { PASS: 0, WARNING: 0, ERROR: 0 };
  $("#counts").innerHTML = `
    <span class="count pass">${counts.PASS} pass</span>
    <span class="count warn">${counts.WARNING} warn</span>
    <span class="count err">${counts.ERROR} error</span>`;
  if (!state.design) {
    box.innerHTML = `<p class="hint">Run the agent to validate the design against the selected rule pack.</p>`;
    return;
  }
  const issues = [...(state.issues || [])].sort((a, b) => {
    const rank = { ERROR: 0, WARNING: 1, PASS: 2 };
    return rank[a.severity] - rank[b.severity];
  });
  const fixes = state.fixes || [];
  if (!issues.length) {
    box.innerHTML = `<div class="issue"><div class="issue-head"><span>No issues</span><span class="rule">README</span></div><div class="source">The design passes the current checks. The rule-pack warning still applies.</div></div>`;
  } else {
    box.innerHTML = issues.map((issue) => `
      <div class="issue ${issue.severity.toLowerCase()}">
        <div class="issue-head"><span>${escapeHtml(issue.message)}</span><span class="rule">${escapeHtml(issue.rule_id)}</span></div>
        <div class="source">${escapeHtml(issue.source || "")}${issue.measured != null ? ` · measured ${issue.measured}` : ""}${issue.required != null ? ` · required ${issue.required}` : ""}</div>
      </div>`).join("");
  }
  if (fixes.length) {
    const wrap = document.createElement("div");
    wrap.className = "issue";
    wrap.innerHTML = `<div class="issue-head"><span>Recommended fixes</span><span class="rule">${fixes.length}</span></div>`;
    fixes.slice(0, 4).forEach((fix) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "fix-button";
      button.style.marginTop = "6px";
      button.textContent = `${fix.kind.replaceAll("_", " ").toLowerCase()} · ${fix.description}`;
      button.addEventListener("click", () => applyFix(fix.id));
      wrap.appendChild(button);
    });
    box.appendChild(wrap);
  }
}

function renderValidationPlaceholder() {
  $("#validation").innerHTML = `<p class="hint">Run the agent to validate the design against the selected rule pack.</p>`;
}

function renderFinalAnswer() {
  const box = $("#final-answer");
  if (!state.finalAnswer) {
    box.classList.add("hidden");
    return;
  }
  box.textContent = state.finalAnswer;
  box.classList.remove("hidden");
}

async function applyFix(fixId) {
  if (!state.designId || state.busy) return;
  setBusy(true);
  try {
    const data = await api(`/api/designs/${state.designId}/fix`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fix_id: fixId }),
    });
    applySnapshot(data);
    showToast("Fix applied and the design was revalidated.");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(false);
    updateDesignButton();
  }
}

async function approveDesign() {
  if (!state.designId) return;
  $("#approve-button").disabled = true;
  $("#approve-top").disabled = true;
  setAgentStatus("Preparing the export…", "running");
  try {
    const data = await api(`/api/designs/${state.designId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approver_name: $("#approver").value || "Engineer" }),
    });
    applySnapshot(data);
    if (data.download_url) {
      const link = $("#download-link");
      link.href = data.download_url;
      link.classList.remove("hidden");
    }
    showToast("Approved. DXF exported.");
  } catch (error) {
    showToast(error.message, true);
    setAgentStatus("Export blocked. Review the validation errors.", "error");
    $("#approve-button").disabled = false;
    $("#approve-top").disabled = false;
  }
}

function showCanvas(view) {
  $("#tab-design").classList.toggle("active", view === "design");
  $("#tab-plan").classList.toggle("active", view === "plan");
  const svg = view === "design" ? state.designSvg || state.sourceSvg : state.sourceSvg;
  if (svg) renderCanvas(svg);
}

function renderCanvas(svg) {
  canvas.innerHTML = svg;
  const selected = state.selectedRoom;
  if (selected) {
    canvas.querySelectorAll(".room").forEach((polygon) => {
      polygon.classList.toggle("selected", polygon.dataset.roomId === selected);
    });
  }
}

function renderTraceEmpty() {
  state.traceCount = 0;
  $("#trace").innerHTML = `<div class="trace-empty">Tool calls will appear here.</div>`;
}

function addTrace(tool, detail, failed = false) {
  const trace = $("#trace");
  trace.querySelector(".trace-empty")?.remove();
  const row = document.createElement("div");
  row.className = "trace-row" + (failed ? " fail" : "");
  row.innerHTML = `<span class="tool">${escapeHtml(tool)}</span><span class="detail">${escapeHtml(detail || "")}</span>`;
  trace.appendChild(row);
  state.traceCount += 1;
  while (trace.children.length > 40) trace.firstElementChild.remove();
  trace.scrollTop = trace.scrollHeight;
}

function setAgentStatus(text, kind = "idle") {
  $("#agent-status").textContent = text;
  const dot = $("#agent-dot");
  dot.className = "agent-dot " + kind;
  const badge = $("#status-badge");
  badge.className = "badge";
  if (kind === "running") {
    badge.textContent = "Agent working";
    badge.classList.add("warn");
  } else if (kind === "done") {
    badge.textContent = "Complete";
    badge.classList.add("good");
  } else if (kind === "error") {
    badge.textContent = "Needs attention";
    badge.classList.add("bad");
  } else {
    badge.textContent = "Ready";
    badge.classList.add("muted");
  }
}

function resetRun() {
  state.done = false;
  state.candidates = [];
  state.validation = [];
  state.issues = [];
  state.fixes = [];
  state.counts = null;
  state.finalAnswer = "";
  state.design = null;
  state.designSvg = null;
  state.designId = null;
  $("#final-answer").classList.add("hidden");
  $("#layouts-card").classList.add("hidden");
  $("#counts").innerHTML = "";
  $("#approve-button").disabled = true;
  $("#approve-top").disabled = true;
  $("#download-link").classList.add("hidden");
  renderTraceEmpty();
  renderValidationPlaceholder();
  if (state.pollTimer) clearTimeout(state.pollTimer);
}

function setBusy(value) {
  state.busy = value;
  updateDesignButton();
}

function showToast(message, isError = false) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.className = "toast" + (isError ? " error" : "");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.add("hidden"), 4200);
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const text = await response.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { detail: text };
  }
  if (!response.ok) {
    const detail = data.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.message || JSON.stringify(detail || data);
    throw new Error(message || `HTTP ${response.status}`);
  }
  return data;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function truncate(value, length) {
  const text = String(value ?? "");
  return text.length > length ? text.slice(0, length - 1) + "…" : text;
}

window.addEventListener("DOMContentLoaded", init);
