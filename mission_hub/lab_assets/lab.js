const state = {
  session: null, dashboard: null, threads: [], activeThread: null,
  checkpoints: [], chats: [], activeChat: null, settings: null, settingsWorking: null,
};
const $ = (value) => document.querySelector(value);
const $$ = (value) => Array.from(document.querySelectorAll(value));

function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character]);
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.session && options.method && options.method !== "GET") headers["X-CSRF-Token"] = state.session.csrf_token;
  const response = await fetch(path, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (response.status === 401) { window.location.replace("/login"); throw new Error("Authentication required"); }
  if (!response.ok) throw new Error(data.message || data.error || `Request failed (${response.status})`);
  return data;
}

function toast(message, isError = false) {
  const node = $("#toast"); node.textContent = message; node.classList.toggle("error", isError); node.classList.remove("hidden");
  window.clearTimeout(toast.timer); toast.timer = window.setTimeout(() => node.classList.add("hidden"), 3500);
}

function when(value) {
  if (!value) return "—";
  const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function shortHash(value) { return value ? `${value.slice(0, 10)}…${value.slice(-6)}` : "—"; }
function statusClass(value) {
  if (["succeeded", "active", "online", "ready"].includes(value)) return "good";
  if (["failed", "blocked", "error", "offline"].includes(value)) return "bad";
  if (["queued", "running", "leased", "paused", "maintenance", "legacy_stopped"].includes(value)) return "warn";
  return "neutral";
}

async function navigate(name) {
  $$(".view").forEach((node) => node.classList.toggle("active", node.id === name));
  $$("[data-nav]").forEach((node) => node.classList.toggle("active", node.dataset.nav === name));
  document.body.dataset.view = name;
  history.replaceState(null, "", `#${name}`);
  try {
    if (name === "threads") await loadThreads();
    if (name === "chat") await loadChats();
    if (name === "settings") await loadSettings();
  } catch (cause) { toast(cause.message, true); }
}

async function loadDashboard() {
  state.dashboard = await api("/lab/api/dashboard");
  renderDashboard();
}

function renderDashboard() {
  const data = state.dashboard;
  const live = data.current_job;
  const trainbox = data.machines.find((item) => item.id === "trainbox");
  const maintenance = Boolean(trainbox?.maintenance_mode);
  const hero = $("#statusHero");
  hero.className = `status-hero ${live ? "state-live" : maintenance ? "state-paused" : "state-idle"}`;
  $("#systemKicker").textContent = live ? "Pipeline activity detected" : maintenance ? "Safe hold · trainingbox maintenance" : "Mission Hub online · queue idle";
  $("#systemTitle").textContent = live ? `${live.job_type} is running.` : maintenance ? "The pipeline is holding safely." : "The pipeline is standing by.";
  $("#systemDetail").textContent = live ? `Mission Hub owns ${live.id}; its immutable run evidence will remain here when the work closes.` : "No model work is running. Configuration and evidence remain available while training authorization is disabled.";
  $("#trainingGate").textContent = data.safety.live_execution ? "Authorized" : "Disabled";
  $("#configHash").textContent = `config ${shortHash(data.config.sha256)}`;
  $("#heroFacts").innerHTML = [`config ${shortHash(data.config.sha256)}`, `${data.jobs.length} recorded jobs`, `${data.artifacts.length} recent artifacts`].map((item) => `<span>${escapeHTML(item)}</span>`).join("");
  updateUnread(data.unread_count);

  renderJobFeature(live, "active");
  renderJobFeature(data.last_job, "last");
  const campaign = data.active_campaign;
  $("#campaignName").textContent = campaign?.name || "No campaign";
  $("#campaignState").textContent = campaign?.state || "none";
  $("#campaignState").className = `status-pill ${statusClass(campaign?.state)}`;
  $("#campaignObjective").value = campaign?.objective || "";
  $("#campaignForm").dataset.campaignId = campaign?.id || "";

  $("#machineGrid").innerHTML = data.machines.map((machine) => {
    const observation = machine.last_observation || {};
    const online = Boolean(machine.last_seen_at);
    return `<article class="panel machine-card"><div class="machine-head"><div><p class="card-label">${escapeHTML(machine.role)}</p><h3>${escapeHTML(machine.config.display_name || machine.id)}</h3></div><span class="status-pill ${machine.maintenance_mode ? "warn" : online ? "good" : "neutral"}">${machine.maintenance_mode ? "maintenance" : online ? "observed" : "unknown"}</span></div><div class="machine-stats"><div><span>Host</span><strong>${escapeHTML(machine.hostname)}</strong></div><div><span>Last seen</span><strong>${escapeHTML(when(machine.last_seen_at))}</strong></div><div><span>Capability</span><strong>${escapeHTML((machine.config.capabilities || []).slice(0, 3).join(", ") || "control")}</strong></div></div></article>`;
  }).join("");
  $("#jobCount").textContent = `${data.jobs.length} recent records`;
  $("#jobTable").innerHTML = data.jobs.slice(0, 10).map((job) => `<div class="data-row"><strong>${escapeHTML(job.job_type)}</strong><span>${escapeHTML(job.id)}</span><span>${escapeHTML(when(job.updated_at))}</span><span class="status-pill ${statusClass(job.status)}">${escapeHTML(job.status)}</span></div>`).join("") || `<div class="data-row"><span>No jobs recorded.</span></div>`;
  $("#artifactList").innerHTML = data.artifacts.slice(0, 5).map((item) => `<div class="compact-item"><strong>${escapeHTML(item.kind)} · ${escapeHTML(shortHash(item.sha256))}</strong><span>${escapeHTML(item.lifecycle)} · ${escapeHTML(when(item.created_at))}</span></div>`).join("") || `<p class="muted">No registered artifacts yet.</p>`;
}

function renderJobFeature(job, prefix) {
  const title = $(`#${prefix}JobTitle`), meta = $(`#${prefix}JobMeta`), status = $(`#${prefix}JobStatus`);
  if (!job) { title.textContent = prefix === "active" ? "No active job" : "No completed job"; meta.textContent = prefix === "active" ? "The queue is quiet." : "No terminal work is recorded."; status.textContent = prefix === "active" ? "Idle" : "None"; status.className = "status-pill neutral"; return; }
  title.textContent = job.job_type;
  const model = job.model_names?.[0] || "deterministic / no model";
  meta.textContent = `${model} · ${job.id} · ${when(job.updated_at)}`;
  status.textContent = job.status; status.className = `status-pill ${statusClass(job.status)}`;
}

function updateUnread(count) {
  const badge = $("#unreadBadge"); badge.textContent = String(count); badge.classList.toggle("hidden", !count);
  $("#heroUnread").textContent = count ? `${count} unread` : "All read";
  $("#inboxTitle").textContent = count ? `${count} message${count === 1 ? "" : "s"} waiting` : "Nothing waiting";
  $("#inboxDetail").textContent = count ? "Open and mark them read" : "Open the shared message ledger";
}

async function loadThreads() {
  const data = await api("/lab/api/threads"); state.threads = data.items; updateUnread(data.unread_count); renderThreadList();
}

function renderThreadList() {
  $("#threadList").innerHTML = state.threads.map((thread) => `<button class="thread-item ${state.activeThread?.thread.id === thread.id ? "active" : ""}" data-thread-id="${escapeHTML(thread.id)}"><div class="thread-item-head"><strong>${escapeHTML(thread.subject)}</strong>${thread.unread_count ? '<span class="unread-dot"></span>' : ""}</div><p>${escapeHTML(when(thread.last_message_at || thread.created_at))} · ${thread.message_count} message${thread.message_count === 1 ? "" : "s"}</p></button>`).join("") || `<div class="empty-state"><h2>No threads yet</h2><p>Start the first operational conversation.</p></div>`;
  $$('[data-thread-id]').forEach((button) => button.addEventListener("click", () => openThread(button.dataset.threadId)));
}

async function openThread(id) {
  state.activeThread = await api(`/lab/api/threads/${id}`); renderThread(); await loadThreads();
  $("#threads").classList.add("thread-open");
}

function renderThread() {
  const { thread, messages } = state.activeThread;
  $("#threadEmpty").classList.add("hidden"); $("#threadConversation").classList.remove("hidden");
  $("#threadSubject").textContent = thread.subject; $("#threadTimestamp").textContent = `Opened ${when(thread.created_at)}`;
  $("#threadMessages").innerHTML = messages.map(messageHTML).join("");
  $("#threadMessages").scrollTop = $("#threadMessages").scrollHeight;
}

function messageHTML(message) {
  const label = { operator: "You", mission_hub: "Mission Hub", sol: "Sol", codex: "Codex", ninereeds: "Ninereeds", system: "System" }[message.sender || message.role] || message.sender || message.role;
  const kind = message.sender || message.role;
  return `<article class="message ${escapeHTML(kind)}"><div class="message-meta"><strong>${escapeHTML(label)}</strong><span>${escapeHTML(when(message.created_at))}</span></div><div class="message-body">${escapeHTML(message.body)}</div></article>`;
}

async function loadChats() {
  const [chats, checkpoints] = await Promise.all([api("/lab/api/chats"), api("/lab/api/checkpoints")]);
  state.chats = chats.items; state.checkpoints = checkpoints.items; renderChatList(); renderCheckpointOptions();
}

function renderChatList() {
  $("#chatList").innerHTML = state.chats.map((chat) => `<button class="thread-item ${state.activeChat?.thread.id === chat.id ? "active" : ""}" data-chat-id="${escapeHTML(chat.id)}"><div class="thread-item-head"><strong>${escapeHTML(chat.title)}</strong></div><p>${escapeHTML(shortHash(chat.checkpoint_sha256))} · ${chat.message_count || 0} turns</p></button>`).join("") || `<div class="empty-state"><h2>No chats yet</h2><p>Certified checkpoints will be listed here.</p></div>`;
  $$('[data-chat-id]').forEach((button) => button.addEventListener("click", () => openChat(button.dataset.chatId)));
}

function renderCheckpointOptions() {
  const eligible = state.checkpoints.filter((item) => item.byte_certified);
  $("#checkpointSelect").innerHTML = eligible.map((item) => `<option value="${escapeHTML(item.id)}">${escapeHTML(item.manifest.lineage_label || item.id)} · ${escapeHTML(shortHash(item.sha256))}</option>`).join("");
  $("#checkpointHelp").textContent = eligible.length ? `${eligible.length} byte-certified artifact${eligible.length === 1 ? "" : "s"}. Compatibility remains a separate probe.` : "No byte-certified checkpoint artifacts are registered yet.";
  $("#chatCreateForm button[type=submit]").disabled = !eligible.length;
}

async function openChat(id) { state.activeChat = await api(`/lab/api/chats/${id}`); renderChat(); renderChatList(); }
function renderChat() {
  const { thread, messages } = state.activeChat; $("#chatEmpty").classList.add("hidden"); $("#chatConversation").classList.remove("hidden");
  $("#chatTitle").textContent = thread.title; $("#chatCheckpoint").textContent = `${thread.checkpoint_artifact_id} · sha256 ${thread.checkpoint_sha256}`;
  $("#chatMessages").innerHTML = messages.map(messageHTML).join("") || `<div class="empty-state"><p>No turns recorded yet.</p></div>`;
}

async function loadSettings() {
  if (!state.settings) { state.settings = await api("/lab/api/settings"); state.settingsWorking = structuredClone(state.settings.draft?.payload || state.settings.active); }
  renderSettings();
}

function renderSettings() {
  const data = state.settingsWorking;
  $("#draftState").textContent = state.settings.draft ? "Draft saved" : "Active values";
  $("#draftState").className = `status-pill ${state.settings.draft ? "warn" : "good"}`;
  const models = data.models;
  const options = (selected, blank = true) => `${blank ? '<option value="">None</option>' : ""}${models.map((model) => `<option value="${escapeHTML(model.id)}" ${model.id === selected ? "selected" : ""}>${escapeHTML(model.id)}</option>`).join("")}`;
  $("#settingsJobs").innerHTML = data.jobs.map((job) => {
    const route = data.routes.find((item) => item.id === job.provider_route);
    const primary = route?.ordered_model_ids?.[0] || "", fallback = route?.ordered_model_ids?.[1] || "";
    return `<article class="setting-card" data-job-card="${escapeHTML(job.id)}"><div class="setting-head"><div><p class="eyebrow">${escapeHTML(job.executor_role)}</p><h2>${escapeHTML(job.id)}</h2><p class="muted">${escapeHTML(job.description)}</p></div><label class="toggle"><input type="checkbox" data-field="enabled" ${job.enabled ? "checked" : ""}> Enabled</label></div><div class="setting-grid"><label>Primary model<select data-field="primary_model">${options(primary)}</select></label><label>Fallback model<select data-field="fallback_model">${options(fallback)}</select></label><label>Route<input value="${escapeHTML(job.provider_route)}" disabled></label></div></article>`;
  }).join("");
  $("#settingsProviders").innerHTML = data.providers.map((provider) => `<article class="setting-card" data-provider-card="${escapeHTML(provider.id)}"><div class="setting-head"><div><p class="eyebrow">Provider</p><h2>${escapeHTML(provider.id)}</h2></div><label class="toggle"><input type="checkbox" data-provider-field="enabled" ${provider.enabled ? "checked" : ""}> Enabled</label></div><div class="setting-grid two"><label>Endpoint<input data-provider-field="endpoint" value="${escapeHTML(provider.endpoint)}"></label><label>Credential environment<input value="${escapeHTML(provider.credential_env || "None (local)")}" disabled></label></div></article>`).join("") + data.models.map((model) => `<article class="setting-card" data-model-card="${escapeHTML(model.id)}"><div class="setting-head"><div><p class="eyebrow">Model · ${escapeHTML(model.provider)}</p><h2>${escapeHTML(model.id)}</h2></div><label class="toggle"><input type="checkbox" data-model-field="enabled" ${model.enabled ? "checked" : ""}> Enabled</label></div><div class="setting-grid"><label>Exact model name<input data-model-field="exact_name" value="${escapeHTML(model.exact_name)}"></label><label>Context tokens<input type="number" data-model-field="context_tokens" value="${model.context_tokens}"></label><label>Output tokens<input type="number" data-model-field="output_tokens" value="${model.output_tokens}"></label></div></article>`).join("");
  $("#settingsPrompts").innerHTML = data.prompts.map((prompt) => `<article class="setting-card" data-prompt-card="${escapeHTML(prompt.id)}"><div class="setting-head"><div><p class="eyebrow">${escapeHTML(prompt.job_type)} · version ${prompt.version}</p><h2>${escapeHTML(prompt.id)}</h2></div><label class="toggle"><input type="checkbox" data-prompt-field="enabled" ${prompt.enabled ? "checked" : ""}> Enabled</label></div><div class="prompt-fields"><label>System prompt<textarea data-prompt-field="system">${escapeHTML(prompt.system)}</textarea></label><label>Prompt template<textarea data-prompt-field="template">${escapeHTML(prompt.template)}</textarea></label></div></article>`).join("");
  bindSettingsInputs();
}

function bindSettingsInputs() {
  $$('[data-job-card]').forEach((card) => card.addEventListener("change", (event) => {
    const job = state.settingsWorking.jobs.find((item) => item.id === card.dataset.jobCard); const field = event.target.dataset.field;
    if (field === "enabled") job.enabled = event.target.checked;
    if (field === "primary_model" || field === "fallback_model") { const route = state.settingsWorking.routes.find((item) => item.id === job.provider_route); if (!route) return; const primary = card.querySelector('[data-field="primary_model"]').value, fallback = card.querySelector('[data-field="fallback_model"]').value; route.ordered_model_ids = [primary, fallback].filter((item, index, values) => item && values.indexOf(item) === index); }
  }));
  $$('[data-provider-card]').forEach((card) => card.addEventListener("change", (event) => { const item = state.settingsWorking.providers.find((value) => value.id === card.dataset.providerCard); const field = event.target.dataset.providerField; if (field) item[field] = field === "enabled" ? event.target.checked : event.target.value; }));
  $$('[data-model-card]').forEach((card) => card.addEventListener("change", (event) => { const item = state.settingsWorking.models.find((value) => value.id === card.dataset.modelCard); const field = event.target.dataset.modelField; if (field) item[field] = field === "enabled" ? event.target.checked : ["context_tokens","output_tokens"].includes(field) ? Number(event.target.value) : event.target.value; }));
  $$('[data-prompt-card]').forEach((card) => card.addEventListener("change", (event) => { const item = state.settingsWorking.prompts.find((value) => value.id === card.dataset.promptCard); const field = event.target.dataset.promptField; if (field) item[field] = field === "enabled" ? event.target.checked : event.target.value; }));
}

async function initialize() {
  try {
    const data = await api("/lab/api/session"); state.session = data.session; $("#accountName").textContent = state.session.username;
    await loadDashboard();
    const requested = location.hash.slice(1); await navigate(["overview","threads","chat","settings"].includes(requested) ? requested : "overview");
    window.setInterval(() => loadDashboard().catch(() => {}), 15000);
  } catch (cause) { toast(cause.message, true); }
}

$$('[data-nav]').forEach((node) => node.addEventListener("click", () => navigate(node.dataset.nav)));
$("#refreshButton").addEventListener("click", () => loadDashboard().then(() => toast("Mission Hub state refreshed.")).catch((cause) => toast(cause.message, true)));
$("#logoutButton").addEventListener("click", async () => { await api("/lab/api/logout", { method: "POST", body: "{}" }); window.location.replace("/login"); });
$("#campaignForm").addEventListener("submit", async (event) => { event.preventDefault(); const id = event.currentTarget.dataset.campaignId; if (!id) return; try { await api(`/lab/api/campaigns/${id}/objective`, { method: "POST", body: JSON.stringify({ objective: $("#campaignObjective").value }) }); $("#campaignSaved").textContent = "Saved just now"; await loadDashboard(); } catch (cause) { toast(cause.message, true); } });
$("#newThreadButton").addEventListener("click", () => $("#threadDialog").showModal());
$("#threadForm").addEventListener("submit", async (event) => { event.preventDefault(); try { const created = await api("/lab/api/threads", { method: "POST", body: JSON.stringify({ subject: $("#threadSubjectInput").value, body: $("#threadBodyInput").value }) }); $("#threadDialog").close(); event.target.reset(); state.activeThread = created; renderThread(); await loadThreads(); } catch (cause) { toast(cause.message, true); } });
$("#replyForm").addEventListener("submit", async (event) => { event.preventDefault(); if (!state.activeThread) return; try { await api(`/lab/api/threads/${state.activeThread.thread.id}/messages`, { method: "POST", body: JSON.stringify({ body: $("#replyBody").value }) }); $("#replyBody").value = ""; await openThread(state.activeThread.thread.id); } catch (cause) { toast(cause.message, true); } });
$("#threadBack").addEventListener("click", () => $("#threads").classList.remove("thread-open"));
$("#newChatButton").addEventListener("click", async () => { if (!state.checkpoints.length) await loadChats(); $("#chatDialog").showModal(); });
$("#chatCreateForm").addEventListener("submit", async (event) => { event.preventDefault(); try { const created = await api("/lab/api/chats", { method: "POST", body: JSON.stringify({ title: $("#chatTitleInput").value, checkpoint_artifact_id: $("#checkpointSelect").value }) }); $("#chatDialog").close(); event.target.reset(); state.activeChat = created; renderChat(); await loadChats(); } catch (cause) { toast(cause.message, true); } });
$("#chatForm").addEventListener("submit", async (event) => { event.preventDefault(); if (!state.activeChat) return; try { state.activeChat = await api(`/lab/api/chats/${state.activeChat.thread.id}/messages`, { method: "POST", body: JSON.stringify({ body: $("#chatBody").value }) }); $("#chatBody").value = ""; renderChat(); toast("Turn and invocation record preserved."); } catch (cause) { toast(cause.message, true); } });
$$('[data-settings-tab]').forEach((button) => button.addEventListener("click", () => { $$('[data-settings-tab]').forEach((node) => node.classList.toggle("active", node === button)); $$(".settings-section").forEach((node) => node.classList.toggle("active", node.id === `settings${button.dataset.settingsTab[0].toUpperCase()}${button.dataset.settingsTab.slice(1)}`)); }));
$("#saveDraftButton").addEventListener("click", async () => { try { const result = await api("/lab/api/settings/draft", { method: "POST", body: JSON.stringify(state.settingsWorking) }); state.settings.draft = result.draft; renderSettings(); toast("Configuration draft saved to Mission Hub."); } catch (cause) { toast(cause.message, true); } });

initialize();
