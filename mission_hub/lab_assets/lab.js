const state = {
  session: null, dashboard: null, threads: [], activeThread: null,
  checkpoints: [], chats: [], activeChat: null, settings: null, settingsWorking: null,
  codexModels: [], codexModelsMessage: "Codex model catalog has not been checked yet.",
  settingsReview: null,
};
const $ = (value) => document.querySelector(value);
const $$ = (value) => Array.from(document.querySelectorAll(value));

const JOB_PRESENTATION = {
  "campaign.decide": { category: "Campaign planning", title: "Propose the next campaign step", summary: "Ask a planning model to recommend what Ninereeds should do next.", help: "The result is a written proposal based on the current campaign evidence. Nothing is started automatically: you review and approve any action separately." },
  "corpus.build": { category: "Training material", title: "Build a training dataset", summary: "Assemble selected source material into a fixed, traceable dataset.", help: "This copies only declared inputs into an immutable corpus artifact and records exactly what went into it." },
  "corpus.transform": { category: "Training material", title: "Transform a training dataset", summary: "Filter, mix, or remove duplicates from an existing dataset.", help: "This performs a repeatable data operation without asking a language model to rewrite the material." },
  "corpus.validate": { category: "Training material", title: "Check a training dataset", summary: "Verify that a dataset follows its declared format and limits.", help: "This produces a validation report. It does not train a model or change the source dataset." },
  "executor.generate": { category: "Training material", title: "Generate new training material", summary: "Ask a selected model to create bounded, structured material.", help: "The model output and provider transcript are preserved together. Large mechanical data changes belong in the transform job instead." },
  "model.train": { category: "Model development", title: "Train Ninereeds", summary: "Create a new checkpoint from one declared parent and dataset.", help: "This is the main GPU training job. Inputs, settings, logs, and produced checkpoint are recorded as one traceable run." },
  "model.evaluate": { category: "Model development", title: "Evaluate a checkpoint", summary: "Run a fixed evaluation suite against one candidate checkpoint.", help: "This measures a checkpoint and records a report; it does not alter or publish the checkpoint." },
  "checkpoint.certify": { category: "Model development", title: "Record a checkpoint's identity", summary: "Hash checkpoint files and create an immutable identity record.", help: "Certification proves which exact bytes exist. It deliberately does not load the model or claim that it works." },
  "checkpoint.probe": { category: "Model development", title: "Test whether a checkpoint loads", summary: "Perform a bounded compatibility check without changing checkpoint status.", help: "Use this after identity certification to learn whether the runtime can safely open and inspect the checkpoint." },
  "checkpoint.publish": { category: "Model development", title: "Publish an approved checkpoint", summary: "Record that an evaluated checkpoint is an approved project artifact.", help: "This is an explicit lifecycle decision. It records the chosen checkpoint and location; it does not train anything." },
  "system.healthcheck": { category: "System & safety", title: "Check the training computer", summary: "Read bounded machine, deployment, disk, and GPU facts.", help: "This is a read-only health report. It does not change software, start training, or load a model." },
  "system.artifact_roundtrip": { category: "System & safety", title: "Test file transfer", summary: "Prove that one small registered artifact can cross the machine boundary.", help: "This commissioning test reads a known file and returns a deterministic receipt so paths and hashes can be verified." },
  "system.gpu_probe": { category: "System & safety", title: "Test the GPUs safely", summary: "Run a tightly bounded arithmetic test on selected GPUs.", help: "This checks basic CUDA execution within configured memory, time, device, and temperature limits. It never loads Ninereeds." },
  "maintenance.retention_preview": { category: "System & safety", title: "Preview archive cleanup", summary: "List evidence that a retention policy would remove without deleting it.", help: "This is deliberately non-destructive. A separate approved action would be required to remove anything." },
};
const JOB_CATEGORY_ORDER = ["Campaign planning", "Training material", "Model development", "System & safety"];
const PROVIDER_NAMES = { "codex-headless": "OpenAI · headless Codex", "deepseek-official": "DeepSeek", "openrouter": "OpenRouter", "trainbox-local": "Trainingbox local server" };
const ROUTE_PRESENTATION = {
  deterministic: { title: "Fixed project code", summary: "Repeatable jobs that do not call a language model." },
  "local-generation": { title: "Training-material generation", summary: "The ordered model path used to generate new structured material." },
  "strategic-decision": { title: "Campaign planning", summary: "The ordered model path used to propose the next campaign step." },
};
const FALLBACK_CLASSES = {
  operational_transient: "Connection or machine temporarily unavailable",
  capability_transient: "Provider temporarily unavailable or rate-limited",
  repairable_output: "Model output can receive one bounded repair",
};

function helpTip(text) {
  return `<button type="button" class="help-tip" aria-label="More information" data-tooltip="${escapeHTML(text)}">?</button>`;
}

function friendlyIdentifier(value) {
  return String(value || "").split(/[.-]/).filter(Boolean).map((word) => word[0]?.toUpperCase() + word.slice(1)).join(" ");
}

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
  const staleDeployments = data.deployments.filter((item) => item.status === "active" && item.config_snapshot_id !== data.config.active.id);
  const hero = $("#statusHero");
  hero.className = `status-hero ${live ? "state-live" : maintenance ? "state-paused" : "state-idle"}`;
  $("#systemKicker").textContent = live ? "Pipeline activity detected" : maintenance ? "Safe hold · trainingbox maintenance" : "Mission Hub online · queue idle";
  $("#systemTitle").textContent = live ? `${live.job_type} is running.` : maintenance ? "The pipeline is holding safely." : "The pipeline is standing by.";
  $("#systemDetail").textContent = live ? `Mission Hub owns ${live.id}; its immutable run evidence will remain here when the work closes.` : staleDeployments.length ? `${staleDeployments.map((item) => item.role).join(", ")} deployment configuration requires synchronization. The safety locks prevent it from accepting work meanwhile.` : "No model work is running. Configuration and evidence remain available while training authorization is disabled.";
  $("#trainingGate").textContent = data.safety.live_execution ? "Authorized" : "Disabled";
  $("#configHash").textContent = `config ${shortHash(data.config.sha256)}`;
  $("#heroFacts").innerHTML = [`config ${shortHash(data.config.sha256)}`, `${data.jobs.length} recorded jobs`, staleDeployments.length ? `${staleDeployments.length} deployment sync pending` : `${data.artifacts.length} recent artifacts`].map((item) => `<span>${escapeHTML(item)}</span>`).join("");
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
    const deployment = data.deployments.find((item) => item.machine_id === machine.id && item.status === "active");
    const synced = deployment?.config_snapshot_id === data.config.active.id;
    return `<article class="panel machine-card"><div class="machine-head"><div><p class="card-label">${escapeHTML(machine.role)}</p><h3>${escapeHTML(machine.config.display_name || machine.id)}</h3></div><span class="status-pill ${!synced ? "bad" : machine.maintenance_mode ? "warn" : online ? "good" : "neutral"}">${!synced ? "sync required" : machine.maintenance_mode ? "maintenance" : online ? "observed" : "unknown"}</span></div><div class="machine-stats"><div><span>Host</span><strong>${escapeHTML(machine.hostname)}</strong></div><div><span>Deployment</span><strong>${synced ? "Config matched" : "Config mismatch"}</strong></div><div><span>Last seen</span><strong>${escapeHTML(when(machine.last_seen_at))}</strong></div></div></article>`;
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
  try { const catalog = await api("/lab/api/codex/models"); state.codexModels = catalog.items || []; state.codexModelsMessage = catalog.message; }
  catch (cause) { state.codexModelsMessage = "Codex model discovery is temporarily unavailable."; }
  renderSettings();
}

function codexModelId(slug) { return `codex-${slug}`; }
function ensureCodexModel(modelId) {
  if (!modelId.startsWith("codex-") || state.settingsWorking.models.some((item) => item.id === modelId)) return;
  const catalog = state.codexModels.find((item) => codexModelId(item.id) === modelId);
  if (!catalog) return;
  state.settingsWorking.models.push({ id: modelId, provider: "codex-headless", exact_name: catalog.id, enabled: false, local: false, context_tokens: catalog.context_tokens || 128000, output_tokens: 8192, structured_output: true, runtime: "codex exec", weights: "", device: "remote" });
}

function renderSettings() {
  const data = state.settingsWorking;
  $("#draftState").textContent = state.settings.draft ? "Draft saved" : "Active values";
  $("#draftState").className = `status-pill ${state.settings.draft ? "warn" : "good"}`;
  $("#reviewDraftButton").disabled = !state.settings.draft;
  const models = data.models;
  const selectableModels = [...models];
  state.codexModels.forEach((catalog) => { const id = codexModelId(catalog.id); if (!selectableModels.some((model) => model.id === id)) selectableModels.push({ id, provider: "codex-headless", exact_name: catalog.id, catalog_name: catalog.name }); });
  const options = (selected) => `<option value="">No model</option>${selectableModels.map((model) => `<option value="${escapeHTML(model.id)}" ${model.id === selected ? "selected" : ""}>${escapeHTML(model.catalog_name || friendlyIdentifier(model.id))} · ${escapeHTML(PROVIDER_NAMES[model.provider] || friendlyIdentifier(model.provider))}</option>`).join("")}`;
  const jobCards = data.jobs.map((job) => {
    const route = data.routes.find((item) => item.id === job.provider_route);
    const primary = route?.ordered_model_ids?.[0] || "", fallback = route?.ordered_model_ids?.[1] || "";
    const presentation = JOB_PRESENTATION[job.id] || { category: "Other", title: friendlyIdentifier(job.id), summary: job.description, help: job.description };
    const modelControls = job.provider_route === "deterministic" ? `<div class="deterministic-note"><strong>No language model is used</strong><span>This job runs fixed, repeatable project code. There is no primary or fallback model to choose.</span></div>` : `<div class="setting-grid"><label>Try this model first ${helpTip("The first model Mission Hub will ask when this job needs language-model work.")}<select data-field="primary_model">${options(primary)}</select></label><label>If that model fails ${helpTip("Mission Hub may try this second model only for the failure types allowed by the route contract.")}<select data-field="fallback_model">${options(fallback)}</select></label><label>Execution path ${helpTip("The internal safety route that controls fallback and resource limits. It is shown for traceability and edited elsewhere.")}<input value="${escapeHTML(job.provider_route)}" disabled></label></div>`;
    return { category: presentation.category, html: `<article class="setting-card" data-job-card="${escapeHTML(job.id)}"><div class="setting-head"><div><p class="technical-id">${escapeHTML(job.id)} · runs on ${escapeHTML(job.executor_role === "trainbox" ? "trainingbox" : "this computer")}</p><h2>${escapeHTML(presentation.title)} ${helpTip(presentation.help)}</h2><p class="muted">${escapeHTML(presentation.summary)}</p></div><label class="toggle"><input type="checkbox" data-field="enabled" ${job.enabled ? "checked" : ""}> Available for use</label></div>${modelControls}</article>` };
  });
  $("#settingsJobs").innerHTML = [...JOB_CATEGORY_ORDER, "Other"].map((category) => {
    const cards = jobCards.filter((item) => item.category === category);
    return cards.length ? `<details class="settings-group" ${category === "Campaign planning" ? "open" : ""}><summary><span>${escapeHTML(category)}</span><em>${cards.length} job${cards.length === 1 ? "" : "s"}</em></summary><div class="settings-group-body">${cards.map((item) => item.html).join("")}</div></details>` : "";
  }).join("");
  $("#settingsRoutes").innerHTML = `<div class="settings-actionbar"><div><h2>Execution limits</h2><p>These paths govern model order, fallback, token ceilings, and spending independently of any one job.</p></div></div><div class="settings-card-stack">${data.routes.map((route) => {
    const presentation = ROUTE_PRESENTATION[route.id] || { title: friendlyIdentifier(route.id), summary: "A bounded Mission Hub execution path." };
    const selected = route.ordered_model_ids.map((id) => models.find((model) => model.id === id)?.exact_name || id).join(" → ") || "No language model";
    const fallback = route.id === "deterministic" ? "" : `<div class="fallback-grid"><p>Try the fallback model only after:</p>${Object.entries(FALLBACK_CLASSES).map(([value, label]) => `<label class="toggle"><input type="checkbox" data-route-fallback="${escapeHTML(value)}" ${route.fallback_failure_classes.includes(value) ? "checked" : ""}> ${escapeHTML(label)}</label>`).join("")}</div>`;
    return `<article class="setting-card" data-route-card="${escapeHTML(route.id)}"><div class="setting-head"><div><p class="technical-id">${escapeHTML(route.id)}</p><h2>${escapeHTML(presentation.title)} ${helpTip(presentation.summary)}</h2><p class="muted">Current order: ${escapeHTML(selected)}. Choose primary and fallback models on the relevant job card.</p></div><label class="toggle"><input type="checkbox" data-route-field="enabled" ${route.enabled ? "checked" : ""}> Available for use</label></div><div class="setting-grid two"><label>Total token ceiling ${helpTip("The maximum combined token allowance for one routed request. Zero means this path performs no model call.")}<input type="number" min="0" data-route-field="max_total_tokens" value="${route.max_total_tokens}"></label><label>Maximum cost in USD ${helpTip("The hard spending ceiling for one request on this path. Zero is appropriate only for deterministic or local work.")}<input type="number" min="0" step="0.01" data-route-field="max_cost_usd" value="${route.max_cost_usd}"></label></div>${fallback}</article>`;
  }).join("")}</div>`;
  const providerCards = data.providers.map((provider) => {
    const local = provider.kind === "local_openai_compatible";
    const codex = provider.kind === "codex_cli";
    const auth = codex ? "Existing ChatGPT login used by Codex CLI" : provider.credential_env ? `API key read from ${provider.credential_env}` : "No credential configured";
    const location = codex ? "A non-interactive Codex process on this computer." : local ? "A model server running inside the private machine boundary." : auth;
    const endpointLabel = codex ? "Codex program" : "API address";
    const endpointHelp = codex ? "The exact executable Mission Hub will start in non-interactive mode. Editing this creates an inert draft." : "The exact network endpoint Mission Hub contacts. Changing it creates a draft; no request is sent from this screen.";
    const codexCatalog = codex ? `<div class="codex-catalog"><div class="catalog-heading"><strong>Models available to this Codex login</strong><span>${escapeHTML(state.codexModelsMessage)}</span></div>${state.codexModels.map((model) => { const configured = models.some((item) => item.id === codexModelId(model.id)); return `<div class="catalog-model"><div><strong>${escapeHTML(model.name)}</strong><span>${escapeHTML(model.description)}</span><em>${escapeHTML(model.reasoning_levels?.length ? `Reasoning: ${model.reasoning_levels.join(", ")}` : "")}</em></div><button type="button" class="quiet-button" data-add-codex-model="${escapeHTML(codexModelId(model.id))}" ${configured ? "disabled" : ""}>${configured ? "Added" : "Add"}</button></div>`; }).join("") || '<p class="muted">No selectable models were returned.</p>'}</div>` : "";
    return `<article class="setting-card" data-provider-card="${escapeHTML(provider.id)}"><div class="setting-head"><div><p class="technical-id">${escapeHTML(provider.id)}</p><h2>${escapeHTML(PROVIDER_NAMES[provider.id] || friendlyIdentifier(provider.id))}</h2><p class="muted">${escapeHTML(location)}</p></div><label class="toggle"><input type="checkbox" data-provider-field="enabled" ${provider.enabled ? "checked" : ""}> Available for use</label></div><div class="setting-grid two"><label>${endpointLabel} ${helpTip(endpointHelp)}<input data-provider-field="endpoint" value="${escapeHTML(provider.endpoint)}"></label><label>Authentication ${helpTip(codex ? "Codex keeps and refreshes the ChatGPT account credential outside the Lab. The Lab never displays or copies it." : "Secrets are supplied to the service as environment variables and are never shown or saved in the Lab.")}<input value="${escapeHTML(auth)}" disabled></label></div>${codex ? '<p class="provider-note">Runs with <code>codex exec</code>, without an interactive terminal. Each job still supplies its own bounded prompt, output contract, timeout, sandbox, and model.</p>' : ""}${codexCatalog}</article>`;
  }).join("");
  const modelCards = data.models.map((model) => `<article class="setting-card" data-model-card="${escapeHTML(model.id)}"><div class="setting-head"><div><p class="technical-id">${escapeHTML(model.id)} · ${escapeHTML(PROVIDER_NAMES[model.provider] || friendlyIdentifier(model.provider))}</p><h2>${escapeHTML(friendlyIdentifier(model.id))}</h2><p class="muted">The exact model version requested from this service.</p></div><label class="toggle"><input type="checkbox" data-model-field="enabled" ${model.enabled ? "checked" : ""}> Available for use</label></div><div class="setting-grid"><label>Provider's exact model name ${helpTip("Copy this identifier exactly from the provider. Similar-looking names may refer to different models.")}<input data-model-field="exact_name" value="${escapeHTML(model.exact_name)}"></label><label>Maximum context ${helpTip("The largest combined prompt and conversation the model can accept, measured in tokens.")}<input type="number" min="1" data-model-field="context_tokens" value="${model.context_tokens}"></label><label>Maximum answer ${helpTip("The most tokens Mission Hub may allow the model to generate in one response.")}<input type="number" min="1" data-model-field="output_tokens" value="${model.output_tokens}"></label></div></article>`).join("");
  $("#settingsProviders").innerHTML = `<div class="settings-actionbar"><div><h2>Model services</h2><p>Connections tell Mission Hub where models live. Secrets stay outside the Lab.</p></div><button id="addProviderButton" class="quiet-button">Add a service</button></div><div class="settings-card-stack">${providerCards}</div><div class="settings-actionbar sub"><div><h2>Models</h2><p>Each selectable model belongs to one service above.</p></div><button id="addModelButton" class="quiet-button">Add a model</button></div><div class="settings-card-stack">${modelCards || '<p class="muted">No models configured.</p>'}</div>`;
  $("#settingsPrompts").innerHTML = data.prompts.map((prompt) => { const presentation = JOB_PRESENTATION[prompt.job_type]; return `<article class="setting-card" data-prompt-card="${escapeHTML(prompt.id)}"><div class="setting-head"><div><p class="technical-id">${escapeHTML(prompt.id)} · version ${prompt.version}</p><h2>${escapeHTML(presentation?.title || friendlyIdentifier(prompt.job_type))}</h2><p class="muted">These are the instructions sent when this job asks a language model for help.</p></div><label class="toggle"><input type="checkbox" data-prompt-field="enabled" ${prompt.enabled ? "checked" : ""}> Available for use</label></div><div class="prompt-fields"><label>Role and rules ${helpTip("Stable instructions that define the model's role, boundaries, and required behavior.")}<textarea data-prompt-field="system">${escapeHTML(prompt.system)}</textarea></label><label>Task template ${helpTip("The job-specific request. Placeholders are filled from the approved job input when it runs.")}<textarea data-prompt-field="template">${escapeHTML(prompt.template)}</textarea></label></div></article>`; }).join("");
  bindSettingsInputs();
}

function reviewValue(value) {
  if (value === null || value === undefined || value === "") return "none";
  if (typeof value === "boolean") return value ? "on" : "off";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function renderSettingsReview() {
  const review = state.settingsReview;
  $("#reviewSummary").innerHTML = `<div><span>Draft</span><strong>${escapeHTML(review.draft.id.replace("draft-", ""))}</strong></div><div><span>Changed values</span><strong>${review.change_count}</strong></div><div><span>Activation readiness</span><strong>${review.ready_for_activation ? "Ready for release work" : `${review.blockers.length} blocker${review.blockers.length === 1 ? "" : "s"}`}</strong></div>`;
  const issues = (items, empty) => items.map((item) => `<div class="review-item"><strong>${escapeHTML(friendlyIdentifier(item.code))}</strong><span>${escapeHTML(item.message)}</span></div>`).join("") || `<div class="review-empty">${escapeHTML(empty)}</div>`;
  $("#reviewBlockers").innerHTML = issues(review.blockers, "No semantic blockers found.");
  $("#reviewWarnings").innerHTML = issues(review.warnings, "No warnings found.");
  $("#reviewBlockerCount").textContent = String(review.blockers.length);
  $("#reviewWarningCount").textContent = String(review.warnings.length);
  $("#reviewChanges").innerHTML = review.changes.map((change) => `<div class="review-change"><strong>${escapeHTML(`${change.section}/${change.id}.${change.field}`)}</strong><span>${escapeHTML(reviewValue(change.before))} → ${escapeHTML(reviewValue(change.after))}</span></div>`).join("");
  $("#reviewRequirements").innerHTML = review.requirements.map((item) => `<div class="review-requirement">${escapeHTML(item.label)}</div>`).join("");
  $("#reviewAcknowledgement").checked = false;
}

async function openSettingsReview() {
  state.settingsReview = await api("/lab/api/settings/review");
  renderSettingsReview();
  $("#reviewDialog").showModal();
}

function bindSettingsInputs() {
  $$('[data-job-card]').forEach((card) => card.addEventListener("change", (event) => {
    const job = state.settingsWorking.jobs.find((item) => item.id === card.dataset.jobCard); const field = event.target.dataset.field;
    if (field === "enabled") job.enabled = event.target.checked;
    if (field === "primary_model" || field === "fallback_model") { const route = state.settingsWorking.routes.find((item) => item.id === job.provider_route); if (!route) return; const primary = card.querySelector('[data-field="primary_model"]').value, fallback = card.querySelector('[data-field="fallback_model"]').value; ensureCodexModel(primary); ensureCodexModel(fallback); route.ordered_model_ids = [primary, fallback].filter((item, index, values) => item && values.indexOf(item) === index); }
  }));
  $$('[data-provider-card]').forEach((card) => card.addEventListener("change", (event) => { const item = state.settingsWorking.providers.find((value) => value.id === card.dataset.providerCard); const field = event.target.dataset.providerField; if (field) item[field] = field === "enabled" ? event.target.checked : event.target.value; }));
  $$('[data-route-card]').forEach((card) => card.addEventListener("change", (event) => {
    const item = state.settingsWorking.routes.find((value) => value.id === card.dataset.routeCard);
    const field = event.target.dataset.routeField;
    if (field) item[field] = field === "enabled" ? event.target.checked : Number(event.target.value);
    if (event.target.dataset.routeFallback) item.fallback_failure_classes = Array.from(card.querySelectorAll('[data-route-fallback]')).filter((input) => input.checked).map((input) => input.dataset.routeFallback);
  }));
  $$('[data-model-card]').forEach((card) => card.addEventListener("change", (event) => { const item = state.settingsWorking.models.find((value) => value.id === card.dataset.modelCard); const field = event.target.dataset.modelField; if (field) item[field] = field === "enabled" ? event.target.checked : ["context_tokens","output_tokens"].includes(field) ? Number(event.target.value) : event.target.value; }));
  $$('[data-prompt-card]').forEach((card) => card.addEventListener("change", (event) => { const item = state.settingsWorking.prompts.find((value) => value.id === card.dataset.promptCard); const field = event.target.dataset.promptField; if (field) item[field] = field === "enabled" ? event.target.checked : event.target.value; }));
  $("#addProviderButton")?.addEventListener("click", () => $("#providerDialog").showModal());
  $("#addModelButton")?.addEventListener("click", () => { $("#modelProviderInput").innerHTML = state.settingsWorking.providers.map((provider) => `<option value="${escapeHTML(provider.id)}">${escapeHTML(PROVIDER_NAMES[provider.id] || friendlyIdentifier(provider.id))}</option>`).join(""); $("#modelDialog").showModal(); });
  $$('[data-add-codex-model]').forEach((button) => button.addEventListener("click", () => { ensureCodexModel(button.dataset.addCodexModel); renderSettings(); toast("Codex model added to the unsaved draft."); }));
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
$("#reviewDraftButton").addEventListener("click", () => openSettingsReview().catch((cause) => toast(cause.message, true)));
$("#reviewForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.settingsReview || !$("#reviewAcknowledgement").checked) return;
  try {
    const result = await api("/lab/api/settings/commissioning-request", { method: "POST", body: JSON.stringify({ draft_id: state.settingsReview.draft.id, acknowledgement: "reviewed_not_activated" }) });
    $("#reviewDialog").close();
    await navigate("threads");
    await openThread(result.thread.thread.id);
    toast("Commissioning request recorded. Nothing was activated.");
  } catch (cause) { toast(cause.message, true); }
});
$$('[data-close-dialog]').forEach((button) => button.addEventListener("click", () => $(`#${button.dataset.closeDialog}`).close()));
$("#providerForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const id = $("#providerIdInput").value.trim().toLowerCase();
  if (state.settingsWorking.providers.some((item) => item.id === id)) { toast("That service name is already in use.", true); return; }
  const local = $("#providerLocalInput").checked;
  state.settingsWorking.providers.push({ id, kind: local ? "local_openai_compatible" : "openai_compatible", enabled: false, endpoint: $("#providerEndpointInput").value.trim(), credential_env: $("#providerCredentialInput").value.trim(), timeout_seconds: 3600, max_attempts: 1, concurrency: 1 });
  $("#providerDialog").close(); event.target.reset(); renderSettings(); toast("Service added to the unsaved draft.");
});
$("#modelForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const id = $("#modelIdInput").value.trim().toLowerCase();
  if (state.settingsWorking.models.some((item) => item.id === id)) { toast("That model name is already in use.", true); return; }
  const provider = $("#modelProviderInput").value;
  const local = state.settingsWorking.providers.find((item) => item.id === provider)?.kind === "local_openai_compatible";
  state.settingsWorking.models.push({ id, provider, exact_name: $("#modelExactNameInput").value.trim(), enabled: false, local, context_tokens: Number($("#modelContextInput").value), output_tokens: Number($("#modelOutputInput").value), structured_output: true, runtime: local ? "openai-compatible local service" : "api", weights: "", device: local ? "local-service" : "remote" });
  $("#modelDialog").close(); event.target.reset(); renderSettings(); toast("Model added to the unsaved draft.");
});
$$('[data-settings-tab]').forEach((button) => button.addEventListener("click", () => { $$('[data-settings-tab]').forEach((node) => node.classList.toggle("active", node === button)); $$(".settings-section").forEach((node) => node.classList.toggle("active", node.id === `settings${button.dataset.settingsTab[0].toUpperCase()}${button.dataset.settingsTab.slice(1)}`)); }));
$("#saveDraftButton").addEventListener("click", async () => { try { const result = await api("/lab/api/settings/draft", { method: "POST", body: JSON.stringify(state.settingsWorking) }); state.settings.draft = result.draft; renderSettings(); toast("Configuration draft saved to Mission Hub."); } catch (cause) { toast(cause.message, true); } });

initialize();
