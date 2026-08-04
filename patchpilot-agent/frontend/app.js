const config = window.MEWCODE_CONFIG || {};
const apiBase = (config.apiBaseUrl || "").replace(/\/$/, "");
const state = { scenarios: [], selected: null, run: null };
const $ = (selector) => document.querySelector(selector);

function bindLinks() {
  [["repository", config.repositoryUrl], ["portfolio", config.portfolioUrl]].forEach(([name, url]) => {
    document.querySelectorAll(`[data-link="${name}"]`).forEach((link) => {
      if (!url) return;
      link.href = url;
      link.hidden = false;
      link.target = "_blank";
      link.rel = "noreferrer";
    });
  });
}

async function request(path, options = {}) {
  const response = await fetch(`${apiBase}${path}`, { ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
  return payload;
}

function statusLabel(status) {
  return ({ "awaiting-approval": "等待写入批准", completed: "运行完成", rejected: "写入已拒绝" })[status] || status;
}

function renderScenarios() {
  $("#scenario-list").innerHTML = state.scenarios.map((item, index) => `
    <button class="scenario ${state.selected?.key === item.key ? "active" : ""}" data-key="${item.key}">
      <span>${String(index + 1).padStart(2, "0")}</span><div><b>${item.title}</b><small>${item.mode.toUpperCase()}</small></div><i>›</i>
    </button>`).join("");
  document.querySelectorAll(".scenario").forEach((button) => button.addEventListener("click", () => selectScenario(button.dataset.key)));
}

function selectScenario(key) {
  state.selected = state.scenarios.find((item) => item.key === key);
  state.run = null;
  renderScenarios();
  $("#empty-state").hidden = true;
  $("#task-view").hidden = false;
  $("#run-content").hidden = true;
  $("#task-mode").textContent = `${state.selected.fixture} / ${state.selected.mode}`;
  $("#task-title").textContent = state.selected.title;
  $("#task-prompt").textContent = state.selected.prompt;
  $("#task-goal").textContent = state.selected.goal;
  $("#tool-list").innerHTML = state.selected.expected_tools.map((tool) => `<span>${tool}</span>`).join("");
}

function renderRun() {
  const run = state.run;
  $("#run-content").hidden = false;
  $("#run-id").textContent = run.run_id;
  $("#run-status").textContent = statusLabel(run.status);
  $("#run-status").dataset.status = run.status;
  $("#trace-list").innerHTML = run.trace.map((event) => `
    <button class="trace-item ${event.status}" data-sequence="${event.sequence}"><span>${String(event.sequence).padStart(2, "0")}</span><div><b>${event.name}</b><p>${event.summary}</p><small>${event.kind} · ${event.duration_ms}ms</small></div></button>`).join("");
  document.querySelectorAll(".trace-item").forEach((item) => item.addEventListener("click", () => showEvent(Number(item.dataset.sequence))));
  $("#approval-bar").hidden = run.status !== "awaiting-approval";
  $("#summary-tools").textContent = `${run.tool_calls} tool calls`;
  $("#summary-context").textContent = `${run.context_tokens} context tokens`;
  const last = run.trace.at(-1);
  $("#output-view").textContent = run.final_answer || last?.output || "选择左侧事件查看工具输入与输出。";
}

function showEvent(sequence) {
  const event = state.run.trace.find((item) => item.sequence === sequence);
  $("#output-view").textContent = JSON.stringify({ input: event.input, output: event.output }, null, 2);
}

async function startRun() {
  const button = $("#start-run");
  button.disabled = true;
  button.textContent = "Agent 运行中...";
  try {
    state.run = await request("/api/runs", { method: "POST", body: JSON.stringify({ scenario_key: state.selected.key }) });
    renderRun();
  } catch (error) {
    alert(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "重新运行";
  }
}

async function decide(decision) {
  try {
    state.run = await request(`/api/runs/${state.run.run_id}/decision`, { method: "POST", body: JSON.stringify({ decision }) });
    renderRun();
    renderMetrics(await request("/api/dashboard"));
  } catch (error) {
    alert(error.message);
  }
}

function renderMetrics(data) {
  $("#metric-scenarios").textContent = data.scenario_count;
  $("#metric-runs").textContent = data.run_count;
  $("#metric-completed").textContent = data.completed_count;
  $("#metric-tools").textContent = data.tool_count;
}

async function boot() {
  bindLinks();
  $("#start-run").addEventListener("click", startRun);
  $("#approve-run").addEventListener("click", () => decide("approve"));
  $("#reject-run").addEventListener("click", () => decide("reject"));
  try {
    const [scenarios, dashboard] = await Promise.all([request("/api/scenarios"), request("/api/dashboard")]);
    state.scenarios = scenarios;
    $("#scenario-count").textContent = `${scenarios.length} TASKS`;
    renderScenarios();
    renderMetrics(dashboard);
  } catch (error) {
    $("#scenario-list").innerHTML = `<p class="load-error">API 连接失败：${error.message}</p>`;
  }
}

boot();
