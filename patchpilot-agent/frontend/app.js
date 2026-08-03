const config = window.PATCHPILOT_CONFIG || {};
const apiBase = (config.apiBaseUrl || "").replace(/\/$/, "");

const state = { scenarios: [], selected: null, run: null };
const $ = (selector) => document.querySelector(selector);

function bindPublicLinks() {
  [["repository", config.repositoryUrl], ["portfolio", config.portfolioUrl]].forEach(([name, url]) => {
    document.querySelectorAll(`[data-link="${name}"]`).forEach((link) => {
      if (!url) return;
      link.href = url;
      link.hidden = false;
    });
  });
}

async function request(path, options = {}) {
  const response = await fetch(`${apiBase}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
  return payload;
}

function statusLabel(status) {
  return ({
    "awaiting-approval": "等待审批",
    completed: "验证通过",
    rejected: "已拒绝",
    failed: "验证失败",
    patching: "应用补丁",
    testing: "执行测试",
    reviewing: "安全审查",
  })[status] || status;
}

function renderScenarioList() {
  $("#scenario-list").innerHTML = state.scenarios.map((item, index) => `
    <button class="scenario ${state.selected?.key === item.key ? "active" : ""}" data-key="${item.key}">
      <span>${String(index + 1).padStart(2, "0")}</span>
      <div><b>${item.title}</b><small>${item.language} · ${item.risk.toUpperCase()} RISK</small></div>
      <i>›</i>
    </button>`).join("");
  document.querySelectorAll(".scenario").forEach((button) => button.addEventListener("click", () => selectScenario(button.dataset.key)));
}

function selectScenario(key) {
  state.selected = state.scenarios.find((item) => item.key === key);
  state.run = null;
  renderScenarioList();
  $("#empty-state").hidden = true;
  $("#task-view").hidden = false;
  $("#run-content").hidden = true;
  $("#task-repo").textContent = state.selected.repository;
  $("#task-title").textContent = state.selected.title;
  $("#task-issue").textContent = state.selected.issue;
  $("#acceptance-list").innerHTML = state.selected.acceptance.map((item) => `<li>${item}</li>`).join("");
  $("#start-run").disabled = false;
  $("#start-run").textContent = "生成维护方案";
}

function renderRun() {
  const run = state.run;
  $("#run-content").hidden = false;
  $("#run-id").textContent = run.run_id;
  $("#run-status").textContent = statusLabel(run.status);
  $("#run-status").dataset.status = run.status;
  $("#trace-list").innerHTML = run.trace.map((event) => `
    <div class="trace-item ${event.status}"><span>${String(event.sequence).padStart(2, "0")}</span><div><b>${event.actor}</b><p>${event.message}</p><small>${event.tool || event.stage} · ${event.duration_ms}ms</small></div></div>`).join("");
  $("#diff-view").textContent = run.applied_diff || run.proposed_diff || "尚未生成补丁";
  $("#approval-bar").hidden = run.status !== "awaiting-approval";
  $("#test-result").hidden = !run.test_result;
  if (run.test_result) {
    $("#test-label").textContent = run.test_result.passed ? "✓ 测试通过" : "× 测试失败";
    $("#test-label").className = run.test_result.passed ? "passed" : "failed";
    $("#test-meta").textContent = `${run.test_result.duration_ms}ms · exit ${run.test_result.exit_code}`;
    $("#test-output").textContent = run.test_result.output;
  }
}

async function startRun() {
  const button = $("#start-run");
  button.disabled = true;
  button.textContent = "分析仓库中…";
  try {
    state.run = await request("/api/runs", { method: "POST", body: JSON.stringify({ scenario_key: state.selected.key, session_id: "public-demo" }) });
    renderRun();
  } catch (error) {
    alert(error.message);
  } finally {
    button.textContent = "重新生成方案";
    button.disabled = false;
  }
}

async function decide(decision) {
  $("#approve-run").disabled = true;
  $("#reject-run").disabled = true;
  try {
    state.run = await request(`/api/runs/${state.run.run_id}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, operator: "public-reviewer" }),
    });
    renderRun();
    const dashboard = await request("/api/dashboard");
    renderMetrics(dashboard);
  } catch (error) {
    alert(error.message);
  } finally {
    $("#approve-run").disabled = false;
    $("#reject-run").disabled = false;
  }
}

function renderMetrics(data) {
  $("#metric-scenarios").textContent = data.scenario_count;
  $("#metric-runs").textContent = data.run_count;
  $("#metric-completed").textContent = data.completed_count;
}

async function boot() {
  bindPublicLinks();
  $("#start-run").addEventListener("click", startRun);
  $("#approve-run").addEventListener("click", () => decide("approve"));
  $("#reject-run").addEventListener("click", () => decide("reject"));
  try {
    const [scenarios, dashboard] = await Promise.all([request("/api/scenarios"), request("/api/dashboard")]);
    state.scenarios = scenarios;
    $("#scenario-count").textContent = `${scenarios.length} TASKS`;
    renderScenarioList();
    renderMetrics(dashboard);
  } catch (error) {
    $("#scenario-list").innerHTML = `<p class="load-error">API 连接失败：${error.message}</p>`;
  }
}

boot();

