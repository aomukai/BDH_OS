const state = {
  dashboard: null,
  artifacts: [],
  campaigns: [],
  messagesBox: "inbox",
  builds: [],
  currentBuild: null,
  git: null,
  auth: null,
  trainbox: null,
  control: null,
  viewMode: localStorage.getItem("lab:viewMode") || "desktop",
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (response.status === 401) {
    window.location.href = "/login";
    throw new Error("Authentication required");
  }
  if (!response.ok) throw new Error(data.error || response.statusText);
  return data;
}

async function loadTrainboxStatus(force = false) {
  const suffix = force ? "?refresh=1" : "";
  const data = await api(`/api/trainbox/status${suffix}`);
  state.trainbox = data.trainbox;
  renderTrainbox();
}

async function loadControlStatus(force = false) {
  const suffix = force ? "?refresh=1" : "";
  const data = await api(`/api/control/status${suffix}`);
  state.control = data.control;
  renderControl();
}

function fmtTime(value) {
  if (!value) return "Unknown";
  return new Date(value * 1000).toLocaleString();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function repoUrl(path) {
  return `/repo/${path.split("/").map(encodeURIComponent).join("/")}`;
}

function isHtmlArtifact(artifact) {
  return artifact.path.toLowerCase().endsWith(".html") || artifact.media_type.includes("html");
}

function card(title, value, meta, artifact) {
  const action = artifact ? `<button class="ghost" data-artifact="${artifact.id}">Open</button>` : "";
  return `
    <article class="panel">
      <div class="item-head">
        <h2>${escapeHtml(title)}</h2>
        ${action}
      </div>
      <p class="value">${escapeHtml(value || "None")}</p>
      <p class="meta">${escapeHtml(meta || "")}</p>
    </article>
  `;
}

async function loadStatus() {
  const data = await api("/api/status");
  state.dashboard = data.dashboard;
  state.git = data.git;
  renderDashboard();
  renderSettings(data.git);
}

async function loadArtifacts() {
  const data = await api("/api/artifacts");
  state.artifacts = data.artifacts;
}

async function loadCampaigns() {
  const data = await api("/api/campaigns");
  state.campaigns = data.campaigns;
  renderCampaigns();
}

async function loadTimeline() {
  const limit = $("#timelineLimit").value;
  const data = await api(`/api/timeline?limit=${encodeURIComponent(limit)}`);
  renderTimeline(data.events);
}

async function loadMessages() {
  const data = await api(`/api/messages?box=${state.messagesBox}`);
  renderMessages(data.messages);
}

async function loadBuilds() {
  const data = await api("/api/builds");
  state.builds = data.builds;
  state.currentBuild = data.current;
  renderBuilds();
}

async function loadAuthStatus() {
  const data = await api("/api/auth/status");
  state.auth = data.auth;
  renderAuthStatus();
}

function renderDashboard() {
  const d = state.dashboard || {};
  $("#dashboardGrid").innerHTML = [
    card("Current campaign", d.current_campaign?.title, d.current_campaign?.summary, null),
    card("Current epoch", d.current_epoch ? `Epoch ${d.current_epoch}` : "None", `${d.campaign_count || 0} campaigns indexed`, null),
    card("Latest report", d.latest_report?.title, d.latest_report?.path, d.latest_report),
    card("Latest MRI", d.latest_mri?.title, d.latest_mri?.path, d.latest_mri),
    card("Latest 3D map", d.latest_graph?.title, d.latest_graph?.path, d.latest_graph),
    card("Latest Atlas", d.latest_atlas?.title, d.latest_atlas?.path, d.latest_atlas),
    card("Current bottleneck", d.current_bottleneck || "Not detected", "From latest decision artifact", null),
    card("Last orchestrator decision", d.last_orchestrator_decision?.title, d.last_orchestrator_decision?.path, d.last_orchestrator_decision),
    card("Published chat build", d.current_published_chat_build?.label, d.current_published_chat_build?.path, null),
    card("Indexed artifacts", String(d.artifact_count || 0), "Historical files in this workstation clone", null),
  ].join("");
}

function renderTrainbox() {
  const snapshot = state.trainbox || {};
  const status = snapshot.status;
  const freshness = $("#trainboxFreshness");
  if (!snapshot.reachable || !status) {
    freshness.textContent = "Offline";
    freshness.className = "badge status-bad";
    $("#trainboxGrid").innerHTML = `
      <article class="panel trainbox-offline">
        <h3>Trainbox unavailable</h3>
        <p class="value">No live status</p>
        <p class="meta">${escapeHtml(snapshot.error?.message || "The restricted status endpoint did not respond.")}</p>
      </article>
    `;
    return;
  }

  const healthy = snapshot.ok && !snapshot.stale;
  freshness.textContent = snapshot.stale ? "Stale" : "Live";
  freshness.className = `badge ${healthy ? "status-good" : "status-warn"}`;
  const gpus = status.gpu?.gpus || [];
  const gpuSummary = gpus.length
    ? gpus.map((gpu) => `GPU ${gpu.index}: ${gpu["utilization.gpu"]}% · ${gpu["temperature.gpu"]}°C · ${gpu["memory.free"]} MiB free`).join(" | ")
    : "No GPU telemetry";
  const activeServices = Object.entries(status.services || {})
    .filter(([, active]) => active === true)
    .map(([name]) => name.replaceAll("_active", "").replaceAll("_", " "))
    .join(", ");
  const pipeline = status.pipeline || {};
  const repo = status.repo || {};
  const system = status.system || {};

  $("#trainboxGrid").innerHTML = [
    liveCard(
      "Machine",
      healthy ? "Online" : "Attention",
      `${status.hostname || "trainbox"} · uptime ${fmtDuration(system.uptime_seconds)} · ${Math.round(snapshot.latency_ms || 0)} ms`
    ),
    liveCard(
      "Pipeline",
      pipeline.current_phase_id || "Unknown phase",
      `Next: ${pipeline.next_safe_action || "unknown"} · ${pipeline.wake_reason || "no wake reason"}`
    ),
    liveCard(
      "GPUs",
      `${gpus.length} × RTX 3060`,
      gpuSummary
    ),
    liveCard(
      "Repository",
      repo.head || "Unknown",
      `${repo.branch || "unknown"} · ${repo.clean ? "clean" : "dirty"} · ahead ${repo.ahead ?? "?"} / behind ${repo.behind ?? "?"}`
    ),
    liveCard(
      "Capacity",
      `${fmtBytes(system.memory?.available_bytes)} RAM free`,
      `${fmtBytes(system.disk?.free_bytes)} disk free · swap ${fmtBytes(system.memory?.swap_free_bytes)} free`
    ),
    liveCard(
      "Services",
      status.ok ? "Healthy" : "Attention",
      activeServices || "No active services reported"
    ),
  ].join("");
}

function renderControl() {
  const control = state.control || {};
  const local = control.local || {};
  const remote = control.trainbox || {};
  const services = control.services || {};
  const badge = $("#controlFreshness");
  badge.textContent = control.ok ? "Healthy" : "Attention";
  badge.className = `badge ${control.ok ? "status-good" : "status-warn"}`;

  const count = (snapshot, status) => Number(snapshot.counts?.[status] || 0);
  const active = (snapshot) =>
    count(snapshot, "queued") + count(snapshot, "claimed") + count(snapshot, "retry_wait");
  const terminal = (snapshot) =>
    count(snapshot, "completed") + count(snapshot, "blocked") + count(snapshot, "dead_letter");
  const recent = [...(local.latest_receipts || []), ...(remote.latest_receipts || [])]
    .sort((a, b) => String(b.updated_at || "").localeCompare(String(a.updated_at || "")))[0];
  const supervisorServices = ["supervisor", "supervisor_path", "supervisor_timer"];
  const healthyServices = supervisorServices.filter((name) => services[name]).length;

  $("#controlGrid").innerHTML = [
    liveCard(
      "Workstation ledger",
      local.ok ? `${active(local)} active` : "Unavailable",
      `${terminal(local)} terminal · ${count(local, "blocked")} blocked · ${count(local, "dead_letter")} dead-letter`
    ),
    liveCard(
      "Trainbox worker ledger",
      remote.ok ? `${active(remote)} active` : "Unavailable",
      `${terminal(remote)} terminal · ${count(remote, "blocked")} blocked · ${count(remote, "dead_letter")} dead-letter`
    ),
    liveCard(
      "Supervisor",
      `${healthyServices}/${supervisorServices.length} units active`,
      `service ${services.supervisor ? "ready" : "idle"} · path ${services.supervisor_path ? "active" : "down"} · timer ${services.supervisor_timer ? "active" : "down"}`
    ),
    liveCard(
      "Latest receipt",
      recent?.plan_id || "None",
      recent ? `${recent.status || "unknown"} · ${recent.updated_at || "unknown time"} · attempts ${recent.attempt_count ?? "?"}` : "No plans recorded"
    ),
  ].join("");
}

function liveCard(title, value, meta) {
  return `
    <article class="panel live-panel">
      <h3>${escapeHtml(title)}</h3>
      <p class="value">${escapeHtml(value || "Unknown")}</p>
      <p class="meta">${escapeHtml(meta || "")}</p>
    </article>
  `;
}

function fmtDuration(seconds) {
  if (!Number.isFinite(Number(seconds))) return "unknown";
  const total = Math.max(0, Number(seconds));
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (days) return `${days}d ${hours}h`;
  if (hours) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

function fmtBytes(bytes) {
  if (!Number.isFinite(Number(bytes))) return "unknown";
  const value = Number(bytes);
  if (value >= 1024 ** 3) return `${(value / 1024 ** 3).toFixed(1)} GiB`;
  if (value >= 1024 ** 2) return `${(value / 1024 ** 2).toFixed(1)} MiB`;
  return `${value} B`;
}

function renderTimeline(events) {
  $("#timelineList").innerHTML = events.map((event) => `
    <details>
      <summary>${escapeHtml(event.title)}</summary>
      <p class="meta">${escapeHtml(event.kind)} · ${fmtTime(event.timestamp)}</p>
      ${event.artifact_id ? `<button class="ghost" data-artifact="${event.artifact_id}">Open artifact</button>` : ""}
      <pre>${escapeHtml(JSON.stringify(event.details, null, 2))}</pre>
    </details>
  `).join("");
}

function renderCampaigns() {
  $("#campaignCount").textContent = `${state.campaigns.length} indexed`;
  $("#campaignList").innerHTML = state.campaigns.map((campaign) => `
    <article class="item">
      <div class="item-head">
        <div>
          <h3>${escapeHtml(campaign.title)}</h3>
          <p class="meta">${escapeHtml(campaign.summary || "No summary")}</p>
        </div>
        <span class="badge">${campaign.artifacts.length} artifacts</span>
      </div>
      <div class="stack">
        ${campaign.artifacts.slice(0, 8).map(artifactRow).join("")}
      </div>
    </article>
  `).join("");
}

function artifactRow(artifact) {
  return `
    <div class="item-head">
      <span><span class="badge ${artifact.type}">${escapeHtml(artifact.type)}</span> ${escapeHtml(artifact.title)}</span>
      <button class="ghost" data-artifact="${artifact.id}">Open</button>
    </div>
  `;
}

function renderMessages(messages) {
  $("#messageList").innerHTML = messages.map((message) => `
    <article class="item">
      <div class="item-head">
        <div>
          <h3>${escapeHtml(message.title)}</h3>
          <p class="meta">${fmtTime(message.timestamp)} · ${escapeHtml(message.path)}</p>
        </div>
        <div class="message-badges">
          <span class="badge">${escapeHtml(message.box)}</span>
          ${message.status ? `<span class="badge message-status status-${escapeHtml(message.status.replaceAll("_", "-"))}">${escapeHtml(message.status.replaceAll("_", " "))}</span>` : ""}
          ${message.disposition ? `<span class="badge">${escapeHtml(message.disposition.replaceAll("_", " "))}</span>` : ""}
        </div>
      </div>
      <div class="markdown">${markdownToHtml(message.body)}</div>
      ${message.correlation_id ? `<p class="meta">Reply to ${escapeHtml(message.correlation_id)}</p>` : ""}
      ${message.requires_interactive ? `<p class="message-attention">Interactive Codex review required.</p>` : ""}
    </article>
  `).join("");
}

function renderBuilds() {
  const current = state.currentBuild?.checkpoint_artifact_id;
  $("#buildSelect").innerHTML = state.builds.map((build) => `
    <option value="${build.checkpoint_artifact_id}" ${build.checkpoint_artifact_id === current ? "selected" : ""}>
      ${escapeHtml(build.label)}
    </option>
  `).join("");
}

function renderSettings(git) {
  $("#syncStatus").innerHTML = `
    <dt>Branch</dt><dd>${escapeHtml(git.branch || "Unknown")}</dd>
    <dt>Dirty</dt><dd>${git.dirty ? "Yes" : "No"}</dd>
    <dt>Pull</dt><dd>${git.pull_enabled ? `${git.pull_interval_seconds}s` : "Disabled"}</dd>
    <dt>Last pull</dt><dd>${git.last_pull ? escapeHtml(git.last_pull.reason || "Done") : "None"}</dd>
  `;
  $("#notificationState").textContent = "Notification" in window ? Notification.permission : "Unavailable";
  $("#displayStatus").innerHTML = `
    <dt>Mode</dt><dd>${escapeHtml(state.viewMode)}</dd>
    <dt>Stored</dt><dd>localStorage</dd>
    <dt>Width</dt><dd>${window.innerWidth}px</dd>
  `;
}

function renderAuthStatus() {
  const auth = state.auth || {};
  $("#authStatus").innerHTML = `
    <dt>Enabled</dt><dd>${auth.enabled ? "Yes" : "No"}</dd>
    <dt>Mode</dt><dd>${escapeHtml(auth.mode || "none")}</dd>
    <dt>Updated</dt><dd>${auth.updated_at ? fmtTime(auth.updated_at) : "Never"}</dd>
  `;
}

function applyViewMode(mode) {
  state.viewMode = mode === "desktop" ? "desktop" : "phone";
  localStorage.setItem("lab:viewMode", state.viewMode);
  document.body.classList.toggle("lab-view-phone", state.viewMode === "phone");
  document.body.classList.toggle("lab-view-desktop", state.viewMode === "desktop");
  $$(".view-mode-toggle [data-mode]").forEach((button) => {
    button.classList.toggle("active", button.dataset.mode === state.viewMode);
  });
  if (state.git) renderSettings(state.git);
}

function markdownToHtml(markdown) {
  const lines = String(markdown || "").split(/\r?\n/);
  const out = [];
  let inCode = false;
  let listOpen = false;
  for (const line of lines) {
    if (line.startsWith("```")) {
      if (inCode) out.push("</code></pre>");
      else out.push("<pre><code>");
      inCode = !inCode;
      continue;
    }
    if (inCode) {
      out.push(`${escapeHtml(line)}\n`);
      continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      if (!listOpen) out.push("<ul>");
      listOpen = true;
      out.push(`<li>${inlineMarkdown(line.replace(/^\s*[-*]\s+/, ""))}</li>`);
      continue;
    }
    if (listOpen) {
      out.push("</ul>");
      listOpen = false;
    }
    if (/^###\s+/.test(line)) out.push(`<h3>${inlineMarkdown(line.slice(4))}</h3>`);
    else if (/^##\s+/.test(line)) out.push(`<h2>${inlineMarkdown(line.slice(3))}</h2>`);
    else if (/^#\s+/.test(line)) out.push(`<h1>${inlineMarkdown(line.slice(2))}</h1>`);
    else if (line.trim()) out.push(`<p>${inlineMarkdown(line)}</p>`);
  }
  if (listOpen) out.push("</ul>");
  if (inCode) out.push("</code></pre>");
  return out.join("");
}

function inlineMarkdown(text) {
  return escapeHtml(text)
    .replaceAll(/`([^`]+)`/g, "<code>$1</code>")
    .replaceAll(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

async function openArtifact(id) {
  const artifact = state.artifacts.find((item) => item.id === id) || (await api(`/api/artifacts/${id}`)).artifact;
  const url = repoUrl(artifact.path);
  if (isHtmlArtifact(artifact)) {
    window.open(url, "_blank", "noopener");
    return;
  }
  $("#viewerType").textContent = artifact.type;
  $("#viewerTitle").textContent = artifact.title;
  $("#viewer").classList.add("open");
  if (artifact.type === "report" || artifact.media_type.startsWith("text/markdown")) {
    const text = await fetch(url).then((r) => r.text());
    $("#viewerBody").innerHTML = `<article class="markdown">${markdownToHtml(text)}</article>`;
  } else if (artifact.media_type.startsWith("image/")) {
    $("#viewerBody").innerHTML = `<img src="${url}" alt="${escapeHtml(artifact.title)}">`;
  } else if (artifact.media_type.includes("json") || artifact.type === "trace" || artifact.type === "hub") {
    const text = await fetch(url).then((r) => r.text());
    $("#viewerBody").innerHTML = `<pre>${escapeHtml(formatJson(text))}</pre>`;
  } else {
    $("#viewerBody").innerHTML = `<p class="meta">${escapeHtml(artifact.path)}</p><a class="command" href="${url}">Download</a>`;
  }
}

function formatJson(text) {
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}

function bindEvents() {
  applyViewMode(state.viewMode);

  $$(".view-mode-toggle [data-mode]").forEach((button) => {
    button.addEventListener("click", () => applyViewMode(button.dataset.mode));
  });

  $$(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      $$(".tab").forEach((item) => item.classList.remove("active"));
      $$(".view").forEach((item) => item.classList.remove("active"));
      tab.classList.add("active");
      $(`#${tab.dataset.view}`).classList.add("active");
    });
  });

  document.body.addEventListener("click", (event) => {
    const button = event.target.closest("[data-artifact]");
    if (button) openArtifact(button.dataset.artifact);
  });

  $("#closeViewer").addEventListener("click", () => $("#viewer").classList.remove("open"));
  $("#timelineLimit").addEventListener("change", loadTimeline);

  $$(".segmented [data-box]").forEach((button) => {
    button.addEventListener("click", () => {
      $$(".segmented [data-box]").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      state.messagesBox = button.dataset.box;
      loadMessages();
    });
  });

  $("#messageForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    await api("/api/messages/outbox", {
      method: "POST",
      body: JSON.stringify({ title: $("#messageTitle").value, body: $("#messageBody").value }),
    });
    $("#messageTitle").value = "";
    $("#messageBody").value = "";
    state.messagesBox = "outbox";
    await loadMessages();
  });

  $("#authForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const password = $("#authPassword").value;
    $("#authMessage").textContent = "";
    try {
      const data = await api("/api/auth/password", {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      state.auth = data.auth;
      $("#authPassword").value = "";
      $("#authMessage").textContent = "Password saved. New browser sessions will use the login page.";
      renderAuthStatus();
    } catch (error) {
      $("#authMessage").textContent = error.message;
    }
  });

  $("#syncButton").addEventListener("click", async () => {
    $("#syncButton").disabled = true;
    try {
      await api("/api/git/pull", { method: "POST", body: "{}" });
      await loadTrainboxStatus(true);
      await refreshAll();
    } finally {
      $("#syncButton").disabled = false;
    }
  });

  $("#publishBuild").addEventListener("click", async () => {
    const checkpoint = $("#buildSelect").value;
    if (!checkpoint) return;
    await api("/api/builds/publish", {
      method: "POST",
      body: JSON.stringify({ checkpoint_artifact_id: checkpoint }),
    });
    await loadBuilds();
    await loadStatus();
  });

  $("#chatForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const prompt = $("#chatPrompt").value.trim();
    if (!prompt) return;
    appendChat("user", prompt);
    $("#chatPrompt").value = "";
    const mode = $("#chatMode").value;
    const data = await api(`/api/chat/${mode}`, { method: "POST", body: JSON.stringify({ prompt }) });
    appendChat("system", data.reply || data.response?.reply || JSON.stringify(data.response || data, null, 2));
  });

  $("#searchForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = await api(`/api/search?q=${encodeURIComponent($("#searchInput").value)}`);
    $("#searchResults").innerHTML = data.results.map((result) => {
      const item = result.item;
      const artifactAction = result.kind === "artifact" ? `<button class="ghost" data-artifact="${item.id}">Open</button>` : "";
      return `
        <article class="item">
          <div class="item-head">
            <div>
              <h3>${escapeHtml(item.title)}</h3>
              <p class="meta">${escapeHtml(result.kind)} · ${escapeHtml(item.path || item.id)}</p>
            </div>
            ${artifactAction}
          </div>
        </article>
      `;
    }).join("");
  });

  $("#enableNotifications").addEventListener("click", async () => {
    if ("Notification" in window) {
      await Notification.requestPermission();
      $("#notificationState").textContent = Notification.permission;
    }
  });

  window.addEventListener("resize", () => {
    if ($("#displayStatus") && state.git) renderSettings(state.git);
  });
}

function appendChat(kind, text) {
  const div = document.createElement("div");
  div.className = `bubble ${kind}`;
  div.textContent = text;
  $("#chatLog").append(div);
  div.scrollIntoView({ block: "end" });
}

async function refreshAll() {
  await loadStatus();
  await loadArtifacts();
  await Promise.all([
    loadTrainboxStatus(),
    loadControlStatus(),
    loadCampaigns(),
    loadTimeline(),
    loadMessages(),
    loadBuilds(),
    loadAuthStatus(),
  ]);
}

function connectEvents() {
  const events = new EventSource("/api/events");
  events.onmessage = () => {};
  for (const name of ["artifacts_indexed", "message_outbox", "git_pull", "build_published"]) {
    events.addEventListener(name, async (event) => {
      const payload = JSON.parse(event.data);
      if ("Notification" in window && Notification.permission === "granted") {
        new Notification("The Lab", { body: `${name.replaceAll("_", " ")} updated` });
      }
      await refreshAll();
      console.debug("Lab event", payload);
    });
  }
}

async function boot() {
  bindEvents();
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/service-worker.js").catch(() => {});
  }
  await refreshAll();
  connectEvents();
  window.setInterval(() => loadTrainboxStatus(true).catch(() => {}), 15000);
  window.setInterval(() => loadControlStatus(true).catch(() => {}), 15000);
  window.setInterval(() => loadMessages().catch(() => {}), 10000);
}

boot().catch((error) => {
  document.body.insertAdjacentHTML("afterbegin", `<p class="panel">${escapeHtml(error.message)}</p>`);
});
