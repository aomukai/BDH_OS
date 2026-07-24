const state = {
  dashboard: null,
  artifacts: [],
  campaigns: [],
  messagesBox: "inbox",
  builds: [],
  currentBuild: null,
  git: null,
  auth: null,
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
  if (!response.ok) throw new Error(data.error || response.statusText);
  return data;
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
    card("Running jobs", (d.running_jobs || []).length ? d.running_jobs.join(", ") : "None", "The Lab does not inspect remote training processes", null),
  ].join("");
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
        <span class="badge">${escapeHtml(message.box)}</span>
      </div>
      <div class="markdown">${markdownToHtml(message.body)}</div>
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
  await Promise.all([loadCampaigns(), loadTimeline(), loadMessages(), loadBuilds(), loadAuthStatus()]);
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
}

boot().catch((error) => {
  document.body.insertAdjacentHTML("afterbegin", `<p class="panel">${escapeHtml(error.message)}</p>`);
});
