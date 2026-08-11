const state = {
  session: null, dashboard: null, threads: [], activeThread: null,
  checkpoints: [], chats: [], activeChat: null, settings: null, settingsWorking: null,
  catalogModels: [], providerCatalogs: [],
  settingsReview: null,
  observatory: null, retention: null,
  dashboardClockOffsetMs: 0,
  nextDueRefreshAt: 0,
};
const $ = (value) => document.querySelector(value);
const $$ = (value) => Array.from(document.querySelectorAll(value));
const BASE_TAB_TITLE = document.title;

const JOB_PRESENTATION = {
  "operations.respond": { category: "Operations", title: "On-call operator", summary: "Answer your operational threads and apply a safe repair when one is available.", help: "Choose the primary and fallback models for your direct line. Fallback is used for configured failures such as model capacity or rate limits; all state changes still pass through Mission Hub's allowlisted actions." },
  "campaign.decide": { category: "Campaign planning", title: "Decide the next campaign step", summary: "Ask the principal strategic role to choose what Ninereeds does next.", help: "The evidence-bound result is recorded as an authoritative decision. Mission Hub executes physical follow-up through its verified control paths; subordinate workflow gates cannot downgrade it into a proposal." },
  "corpus.build": { category: "Training material", title: "Build a training dataset", summary: "Assemble selected source material into a fixed, traceable dataset.", help: "This copies only declared inputs into an immutable corpus artifact and records exactly what went into it." },
  "corpus.transform": { category: "Training material", title: "Transform a training dataset", summary: "Filter, mix, or remove duplicates from an existing dataset.", help: "This performs a repeatable data operation without asking a language model to rewrite the material." },
  "corpus.validate": { category: "Training material", title: "Check a training dataset", summary: "Verify that a dataset follows its declared format and limits.", help: "This produces a validation report. It does not train a model or change the source dataset." },
  "executor.generate": { category: "Training material", title: "Generate new training material", summary: "Ask a selected model to create bounded, structured material.", help: "The model output and provider transcript are preserved together. Large mechanical data changes belong in the transform job instead." },
  "model.train": { category: "Model development", title: "Train Ninereeds", summary: "Create a new checkpoint from one declared parent and dataset.", help: "This is the main GPU training job. Inputs, settings, logs, and produced checkpoint are recorded as one traceable run." },
  "model.evaluate": { category: "Model development", title: "Evaluate a checkpoint", summary: "Run behavioral chat probes and MRI activation analysis against one checkpoint.", help: "Chat behavior and MRI evidence are the evaluation basis. Loss is recorded only as telemetry and can never rank, admit, reject, continue, or roll back a checkpoint." },
  "model.chat": { category: "Model development", title: "Chat with one checkpoint", summary: "Generate a logged conversation turn from an exact Ninereeds artifact.", help: "Every turn pins the checkpoint hash, complete rendered context, prompt format, generation settings, job, output, and timestamps. It never changes the checkpoint." },
  "checkpoint.certify": { category: "Model development", title: "Record a checkpoint's identity", summary: "Hash checkpoint files and create an immutable identity record.", help: "Certification proves which exact bytes exist. It deliberately does not load the model or claim that it works." },
  "checkpoint.probe": { category: "Model development", title: "Test whether a checkpoint loads", summary: "Perform a bounded compatibility check without changing checkpoint status.", help: "Use this after identity certification to learn whether the runtime can safely open and inspect the checkpoint." },
  "checkpoint.compare": { category: "Model development", title: "Compare learned checkpoint state", summary: "Check whether two checkpoints have identical learned tensors and optimizer state.", help: "Run metadata and container bytes are intentionally excluded. Campaign 34 uses this to prove that observation did not alter learning." },
  "checkpoint.publish": { category: "Model development", title: "Publish an approved checkpoint", summary: "Record that an evaluated checkpoint is an approved project artifact.", help: "This is an explicit lifecycle decision. It records the chosen checkpoint and location; it does not train anything." },
  "system.healthcheck": { category: "System & safety", title: "Check the training computer", summary: "Read bounded machine, deployment, disk, and GPU facts.", help: "This is a read-only health report. It does not change software, start training, or load a model." },
  "system.artifact_roundtrip": { category: "System & safety", title: "Test file transfer", summary: "Prove that one small registered artifact can cross the machine boundary.", help: "This commissioning test reads a known file and returns a deterministic receipt so paths and hashes can be verified." },
  "system.gpu_probe": { category: "System & safety", title: "Test the GPUs safely", summary: "Run a tightly bounded arithmetic test on selected GPUs.", help: "This checks basic CUDA execution within configured memory, time, device, and temperature limits. It never loads Ninereeds." },
  "maintenance.retention_preview": { category: "System & safety", title: "Preview archive cleanup", summary: "List evidence that a retention policy would remove without deleting it.", help: "This is deliberately non-destructive. A separate approved action would be required to remove anything." },
  "visual.plan": { category: "Visual learning", title: "Design a visual lesson", summary: "Turn one teaching goal into a bounded image or multi-card specification.", help: "This defines lesson-critical visible facts, canonical text, continuity, provenance, and budgets. It does not generate an image or train Ninereeds." },
  "visual.generate": { category: "Visual learning", title: "Generate image candidates", summary: "Render a bounded candidate set from an approved visual plan.", help: "The configured image generator records its exact revision, prompt, seed, dimensions, and attempt history. Generated pixels remain candidates." },
  "visual.inspect": { category: "Visual learning", title: "Inspect generated images", summary: "Run mechanical checks and a blind visual-observation model.", help: "This checks content, correctness, cleanliness, style, counts, relations, and uncertainty. The observer cannot approve an asset." },
  "visual.caption": { category: "Visual learning", title: "Propose image captions", summary: "Create grounded accessibility and teaching captions from verified facts.", help: "Captions remain separate canonical text and cannot replace or alter the pixels. Caption proposals have no acceptance authority." },
  "visual.decide": { category: "Visual learning", title: "Triage visual evidence", summary: "Propose accept, check-again, or reject from the evidence packet.", help: "This policy model reads structured evidence, not hidden pixels. Mechanical hard gates override it, and it cannot admit an image." },
  "visual.review": { category: "Visual learning", title: "Independently review pixels", summary: "Verify the image and decide its exact permitted teaching uses.", help: "The final reviewer sees pixels and evidence. It cannot rewrite whether the original image request succeeded or authorize training." },
  "visual.pack_finalize": { category: "Visual learning", title: "Finalize an accepted visual pack", summary: "Atomically assemble fully reviewed assets and canonical text.", help: "Every member must have the required independent review. This produces an immutable pack but does not train a model." },
  "visual.encode": { category: "Visual learning", title: "Encode accepted images", summary: "Derive frozen SigLIP2 features keyed by pixels, revision, and preprocessing.", help: "Features are derived data. Any encoder, processor, layer, or resampler change creates a different cache identity." },
  "visual.experience_compile": { category: "Visual learning", title: "Compile a multimodal experience", summary: "Order accepted images and canonical text into learner events.", help: "This creates observe, text, page-turn, question, correction, delay, and recall events. It does not authorize weight updates." },
  "model.visual_train": { category: "Visual learning", title: "Train visual grounding", summary: "Run an authorized projector or Cortex visual-learning block.", help: "The first scope trains only the visual projector/resampler against a frozen language baseline. Checkpoint promotion remains separate." },
};
const JOB_CATEGORY_ORDER = ["Operations", "Campaign planning", "Training material", "Visual learning", "Model development", "System & safety"];
const PROVIDER_NAMES = { "codex-headless": "OpenAI · headless Codex", "deepseek-official": "DeepSeek", "openrouter": "OpenRouter", "trainbox-local": "Trainingbox local server", "trainbox-vision": "Trainingbox visual runtime" };
const ROUTE_PRESENTATION = {
  deterministic: { title: "Fixed project code", summary: "Repeatable jobs that do not call a language model." },
  "operational-response": { title: "On-call conversation", summary: "The ordered primary and fallback models used for operator↔Sol threads." },
  "local-generation": { title: "Training-material generation", summary: "The ordered model path used to generate new structured material." },
  "strategic-decision": { title: "Campaign planning", summary: "The ordered model path used to propose the next campaign step." },
  "visual-planning": { title: "Visual lesson planning", summary: "Models that turn a teaching goal into a bounded visual specification." },
  "visual-generation": { title: "Image generation", summary: "Pinned local image generators used to render candidate pixels." },
  "visual-observation": { title: "Image inspection", summary: "Vision-language models that produce blind structured visual evidence." },
  "visual-caption": { title: "Image captioning", summary: "Vision-language models that propose grounded captions from verified facts." },
  "visual-policy": { title: "Visual evidence decision", summary: "Text models that assign policy buckets without pixel authority." },
  "visual-final-review": { title: "Independent visual review", summary: "The model that inspects pixels and finalizes exact asset uses." },
  "visual-encoding": { title: "Learner visual receptor", summary: "The frozen encoder used to derive content-keyed visual features." },
};
const FALLBACK_CLASSES = {
  operational_transient: "Connection or machine temporarily unavailable",
  capability_transient: "Provider temporarily unavailable or rate-limited",
  repairable_output: "Model output can receive one bounded repair",
};
const REVIEW_ISSUE_NAMES = {
  job_handler_uncommissioned: "Executor not commissioned",
  route_disabled: "Execution path is off",
  route_has_no_model: "No model selected",
  model_disabled: "Model is unavailable",
  provider_disabled: "Model service is unavailable",
  live_execution_locked: "Live-execution lock is closed",
  machine_in_maintenance: "Trainingbox maintenance is on",
  route_token_cap_lower: "Execution token ceiling is lower",
  provider_enabled_unused: "Enabled model service is unused",
  visual_shadow_mode: "Visual asset admission is in shadow mode",
};

function helpTip(text) {
  return `<button type="button" class="help-tip" aria-label="More information" data-tooltip="${escapeHTML(text)}">?</button>`;
}

function friendlyIdentifier(value) {
  return String(value || "").split(/[._-]/).filter(Boolean).map((word) => word[0]?.toUpperCase() + word.slice(1)).join(" ");
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
    if (name === "observatory") await loadObservatory();
    if (name === "settings") await loadSettings();
  } catch (cause) { toast(cause.message, true); }
}

async function loadObservatory() {
  [state.observatory, state.retention] = await Promise.all([
    api("/lab/api/observatory"), api("/lab/api/retention"),
  ]);
  renderObservatory();
}

function scanButton(source, kind, label) {
  if (!source?.structured) return `<button class="quiet-button" type="button" disabled>${escapeHTML(label)}</button>`;
  const url = `/lab/observatory/view?artifact=${encodeURIComponent(source.id)}&view=${encodeURIComponent(kind)}`;
  return `<a class="quiet-button scan-link" href="${url}" target="_blank" rel="noopener">${escapeHTML(label)} ↗</a>`;
}

function renderObservatory() {
  const data = state.observatory;
  const stats = data.statistics;
  $("#observatoryTaught").textContent = String(stats.things_taught);
  $("#observatoryTaughtDetail").textContent = `${stats.lesson_records} append-only lesson records · ${stats.baseline_known} known at campaign start`;
  $("#observatoryBlocks").textContent = String(stats.training_blocks);
  $("#observatoryBlockDetail").textContent = `${stats.evaluations_completed} mandatory chat + MRI evaluations completed`;
  $("#observatoryAttempts").textContent = String(stats.attempts);
  $("#observatoryAttemptDetail").textContent = stats.retry_attempts ? `${stats.retry_attempts} retry attempts recorded` : "No retries recorded";
  $("#observatoryScans").textContent = `${data.campaign_scan.complete}/${data.campaign_scan.required}`;
  $("#observatoryScanDetail").textContent = data.campaign_scan.ready ? "Every declared branch has terminal scan evidence" : "Waiting for all declared branches";
  const scanStatus = $("#campaignScanStatus");
  scanStatus.textContent = data.campaign_scan.ready ? "Complete" : `${data.campaign_scan.complete}/${data.campaign_scan.required} ready`;
  scanStatus.className = `status-pill ${data.campaign_scan.ready ? "good" : "warn"}`;
  $("#campaignScanPolicy").textContent = data.campaign_scan.policy;
  $("#branchScanGrid").innerHTML = data.branches.map((branch, index) => {
    const source = branch.terminal_evaluation;
    const label = `Branch ${index + 1}`;
    const limitation = branch.scan_status === "historical_summary"
      ? "Historical chat/MRI evidence is preserved, but its full structured scan is unavailable; no details are invented."
      : branch.scan_status === "waiting" ? "Terminal chat and MRI evidence has not been recorded yet."
      : `Terminal evaluation ${shortHash(source.id)} · checkpoint ${shortHash(source.checkpoint_sha256)}`;
    return `<article class="panel branch-scan-card"><div class="branch-scan-head"><div><span>${escapeHTML(label)}</span><strong>${escapeHTML(branch.branch_id)}</strong></div><span class="status-pill ${statusClass(branch.status)}">${escapeHTML(branch.status)}</span></div><p>${escapeHTML(limitation)}</p><div class="scan-actions">${scanButton(source, "mri", "MRI")}${scanButton(source, "atlas", "Atlas")}${scanButton(source, "map", "3D map")}</div></article>`;
  }).join("") || '<div class="panel observatory-empty">No branches are declared in the active campaign contract.</div>';
  $("#observatoryTimeline").innerHTML = data.timeline.map((event) => `<article class="timeline-event"><i class="${statusClass(event.status)}"></i><div><span>${escapeHTML(when(event.at))} · ${escapeHTML(event.kind)}</span><strong>${escapeHTML(event.title)}</strong><p>${escapeHTML(event.detail)}</p></div><em class="status-pill ${statusClass(event.status)}">${escapeHTML(event.status)}</em></article>`).join("") || '<div class="observatory-empty">No campaign events recorded.</div>';
  $("#routeStatistics").innerHTML = data.route_statistics.map((route) => {
    const percent = Math.round(route.fallback_rate * 100);
    const attention = route.attention === "review_primary";
    return `<article class="panel route-card"><div><span>${escapeHTML(route.route_id)}</span><strong>${percent}% fallback use</strong></div><span class="status-pill ${attention ? "warn" : "good"}">${attention ? "Review primary" : "Normal"}</span><p>${route.jobs} routed jobs · ${route.attempts} model attempts · ${route.fallback_successes} fallback successes</p><div class="route-meter"><i style="width:${percent}%"></i></div><small>${route.models.map((model) => `${model.model_id}: ${model.attempts}`).join(" · ")}</small></article>`;
  }).join("") || '<div class="panel observatory-empty">No model-routed work has produced provider-attempt evidence yet. Deterministic training jobs are not misclassified as model-routing attempts.</div>';
  renderRetentionRegistry();
}

function byteSize(value) {
  const bytes = Number(value) || 0;
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KiB", "MiB", "GiB", "TiB"];
  let amount = bytes / 1024, unit = units[0];
  for (let index = 1; index < units.length && amount >= 1024; index += 1) { amount /= 1024; unit = units[index]; }
  return `${amount.toFixed(amount >= 10 ? 1 : 2)} ${unit}`;
}

function renderRetentionRegistry() {
  const retention = state.retention || { protected: [], eligible: [], artifact_protections: [] };
  const protections = new Map();
  retention.artifact_protections.forEach((pin) => {
    if (!protections.has(pin.artifact_id)) protections.set(pin.artifact_id, []);
    protections.get(pin.artifact_id).push(pin);
  });
  const entries = [
    ...retention.protected.map((item) => ({ ...item, protected: true })),
    ...retention.eligible.map((item) => ({ ...item, protected: false })),
  ];
  $("#retentionSummary").textContent = `${retention.protected.length} protected · ${byteSize(retention.eligible_bytes)} eligible`;
  $("#retentionSummary").className = `status-pill ${retention.eligible.length ? "warn" : "good"}`;
  $("#retentionRegistry").innerHTML = entries.map((item) => {
    const pins = protections.get(item.id) || [];
    const operatorPin = pins.find((pin) => pin.source === "operator");
    const reasons = pins.map((pin) => pin.reason).join(" · ") || "No protection reason is registered.";
    const action = operatorPin
      ? `<button class="quiet-button retention-release" data-protection-id="${escapeHTML(operatorPin.id)}">Release my pin</button>`
      : `<button class="quiet-button retention-protect" data-artifact-id="${escapeHTML(item.id)}">Protect</button>`;
    return `<article class="retention-row"><div><span>${escapeHTML(item.id)} · ${byteSize(item.byte_size)}</span><strong>${item.protected ? "Protected checkpoint" : "Eligible for cleanup"}</strong><p>${escapeHTML(reasons)}</p></div><span class="status-pill ${item.protected ? "good" : "warn"}">${item.protected ? "keep" : "unprotected"}</span>${action}</article>`;
  }).join("") || '<div class="observatory-empty">No checkpoint locations are registered on the training computer.</div>';
  $$(".retention-protect").forEach((button) => button.addEventListener("click", async () => {
    try {
      await api(`/lab/api/artifacts/${button.dataset.artifactId}/protect`, { method: "POST", body: JSON.stringify({ reason: "Operator marked this checkpoint as a keeper in The Lab." }) });
      await loadObservatory(); toast("Checkpoint protected.");
    } catch (cause) { toast(cause.message, true); }
  }));
  $$(".retention-release").forEach((button) => button.addEventListener("click", async () => {
    try {
      await api(`/lab/api/artifact-protections/${button.dataset.protectionId}/release`, { method: "POST", body: "{}" });
      await loadObservatory(); toast("Operator protection released.");
    } catch (cause) { toast(cause.message, true); }
  }));
}

async function loadDashboard() {
  state.dashboard = await api("/lab/api/dashboard");
  state.dashboardClockOffsetMs = (Number(state.dashboard.server_time) * 1000) - Date.now();
  renderDashboard();
}

function countdown(value) {
  const target = new Date(value).valueOf();
  if (!Number.isFinite(target)) return null;
  const remaining = Math.max(0, target - (Date.now() + state.dashboardClockOffsetMs));
  if (remaining <= 0) return { due: true, text: "due now" };
  const seconds = Math.ceil(remaining / 1000);
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;
  return { due: false, text: hours ? `${hours}h ${String(minutes).padStart(2, "0")}m ${String(rest).padStart(2, "0")}s` : `${minutes}m ${String(rest).padStart(2, "0")}s` };
}

function renderWorkflowProgress(progress) {
  const node = $("#workflowProgress");
  node.classList.toggle("hidden", !progress);
  if (!progress) return;
  const percent = Math.max(0, Math.min(100, Number(progress.percent) || 0));
  const unitLabel = progress.unit_label || "Block";
  const unitIndex = progress.unit_index ?? progress.block_index;
  const unitsTotal = progress.units_total ?? progress.blocks_total;
  $("#workflowProgressLabel").textContent = `${unitLabel} ${unitIndex}/${unitsTotal}`;
  $("#workflowProgressPercent").textContent = `${percent}%`;
  $("#workflowProgressBar").style.width = `${percent}%`;
  $("#workflowProgress .progress-track").setAttribute("aria-valuenow", String(percent));
  const visual = progress.workflow_kind === "visual";
  const campaign35 = progress.workflow_kind === "campaign35";
  const complete = ["succeeded", "shadow_complete"].includes(progress.workflow_status);
  const stageDescription = campaign35 ? "real campaign jobs" : visual ? "visual workflow stages" : "training and evaluation stages";
  const buildSummary = campaign35 && Array.isArray(progress.builds)
    ? ` · ${progress.builds.map((item) => `${friendlyIdentifier(item.id)}: ${friendlyIdentifier(item.status)}`).join(" · ")}`
    : "";
  const activity = progress.activity ? `${progress.activity} · ` : "";
  $("#workflowProgressDetail").textContent = complete
    ? `Complete · all ${progress.total_stages} required ${stageDescription} succeeded${buildSummary}`
    : `${friendlyIdentifier(progress.stage)} · ${activity}${progress.completed_stages}/${progress.total_stages} ${stageDescription} complete${buildSummary}`;
}

function branchLabel(progress) {
  if (progress?.workflow_kind === "campaign35") return "Campaign 35";
  const match = String(progress?.branch_id || "").match(/(?:^|[-_])0*(\d+)$/);
  return match ? `Branch ${Number(match[1])}` : "The authorized branch";
}

function nextTaskLabel(progress, job = null) {
  if (job?.job_type === "visual.generate") return "next image-generation task";
  if (job?.job_type === "visual.inspect") return "next image-review task";
  if (progress?.workflow_kind === "visual") return "next visual task";
  if (progress?.workflow_kind === "campaign35") return "next campaign task";
  if (progress?.workflow_kind === "cortex") return "next training task";
  return "next task";
}

function renderDashboardTiming() {
  const data = state.dashboard;
  if (!data || data.current_job || data.scheduler?.activity) return;
  const pipelinePaused = ["paused", "pausing"].includes(data.pipeline.effective_state);
  const trainbox = data.machines.find((item) => item.id === "trainbox");
  const stale = data.deployments.some((item) => item.status === "active" && item.config_snapshot_id !== data.config.active.id);
  if (pipelinePaused || trainbox?.maintenance_mode || stale || !data.next_job) return;
  const timing = countdown(data.next_job.available_at);
  const scheduled = timing && !timing.due;
  const pollSeconds = Number(data.scheduler?.poll_seconds) || 15;
  const lastFinished = new Date(data.last_job?.updated_at).valueOf();
  const ageSeconds = Math.max(0, Math.floor(((Date.now() + state.dashboardClockOffsetMs) - lastFinished) / 1000));
  const recentlyAdvanced = data.last_job?.status === "succeeded" && Number.isFinite(lastFinished) && ageSeconds <= Math.max(60, pollSeconds * 4);
  $("#systemKicker").textContent = scheduled ? "Mission Hub online · cooldown active" : recentlyAdvanced ? "Mission Hub online · queue advancing" : "Mission Hub online · queue ready";
  $("#systemTitle").textContent = scheduled ? `Next run in ${timing.text}.` : "Authorized work is queued.";
  $("#systemDetail").textContent = scheduled
    ? `The cooldown ends ${when(data.next_job.available_at)}. Work will resume at the first safe scheduler boundary afterward.`
    : recentlyAdvanced
      ? `A step completed ${ageSeconds < 2 ? "just now" : `${ageSeconds} seconds ago`}. The next authorized step is ready; no action is required.`
      : "The next authorized step is listed below and will start at a safe scheduler boundary; no action is required.";
  $("#activeJobLabel").textContent = "Next job";
  renderJobFeature(data.next_job, "active", scheduled ? `Cooling down · ${timing.text}` : recentlyAdvanced ? "Queued · scheduler active" : "Ready for safe dispatch");
  if (!scheduled && Date.now() >= state.nextDueRefreshAt) {
    state.nextDueRefreshAt = Date.now() + 5000;
    loadDashboard().catch(() => {});
  }
}

function renderDashboard() {
  const data = state.dashboard;
  const live = data.current_job;
  const next = data.next_job;
  const pipeline = data.pipeline;
  const trainbox = data.machines.find((item) => item.id === "trainbox");
  const maintenance = Boolean(trainbox?.maintenance_mode);
  const progress = data.workflow_progress;
  const schedulerActivity = !live && data.scheduler?.activity?.blocks_scheduling !== false ? data.scheduler.activity : null;
  const schedulerTask = nextTaskLabel(progress, next);
  const workflowComplete = ["succeeded", "shadow_complete"].includes(progress?.workflow_status);
  const workflowFailed = ["failed", "blocked", "cancelled"].includes(progress?.workflow_status);
  const staleDeployments = data.deployments.filter((item) => item.status === "active" && item.config_snapshot_id !== data.config.active.id);
  const hero = $("#statusHero");
  const pipelinePaused = pipeline.effective_state === "paused" || pipeline.effective_state === "pausing";
  hero.className = `status-hero ${live ? "state-live" : workflowFailed ? "state-error" : pipelinePaused || maintenance ? "state-paused" : "state-idle"}`;
  $("#systemKicker").textContent = live ? (pipeline.effective_state === "pausing" ? "Finishing active work · pause requested" : "Pipeline activity detected") : pipelinePaused ? "Mission Hub safe hold" : maintenance ? "Trainingbox maintenance · pipeline started" : schedulerActivity ? "Mission Hub online · preparing the next task" : next ? "Mission Hub online · scheduled work" : workflowComplete ? "Authorized workflow complete" : workflowFailed ? "Workflow requires attention" : "Mission Hub online · queue idle";
  $("#systemTitle").textContent = live ? `${live.job_type} is running.` : pipelinePaused ? "The pipeline is paused." : maintenance ? "The pipeline is started, with training held in maintenance." : schedulerActivity ? (next ? `The ${schedulerTask} is waiting.` : `Waiting to schedule the ${schedulerTask}.`) : workflowComplete ? `${branchLabel(progress)} is complete.` : workflowFailed ? `${branchLabel(progress)} ${progress.workflow_status}.` : "The pipeline is standing by.";
  $("#systemDetail").textContent = live ? `Mission Hub owns ${live.id}; pausing will not interrupt it, and its immutable evidence will remain here when the work closes.` : pipelinePaused ? "No new work will be scheduled or leased. Configuration, evidence, and messages remain available." : staleDeployments.length ? `${staleDeployments.map((item) => item.role).join(", ")} deployment configuration requires synchronization. The safety locks prevent it from accepting work meanwhile.` : schedulerActivity?.kind === "storage_inventory" ? `Blocked by a storage inventory scan that started ${when(schedulerActivity.started_at)}. ${next ? `The ${schedulerTask} will start` : `Mission Hub will create the ${schedulerTask}`} when the scan finishes.` : schedulerActivity ? `${schedulerActivity.summary}. ${next ? `The ${schedulerTask} will start` : `Mission Hub will create the ${schedulerTask}`} when this finishes.` : workflowComplete ? (progress.workflow_kind === "campaign35" ? "All five checkpoints and terminal scan bundles exist, and the authoritative post-campaign direction was recorded. Physical follow-up remains evidence-verified." : progress.workflow_kind === "visual" ? `All ${progress.total_stages} required visual workflow stages succeeded. No further work has been authorized, so Mission Hub has no work to lease.` : `All ${progress.blocks_total} blocks and their required evaluations succeeded. No further branch has been authorized, so Mission Hub has no work to lease.`) : workflowFailed ? `The latest authorized workflow ended ${progress.workflow_status}. Its preserved evidence must be reviewed before more work is authorized.` : "Mission Hub may take the next configured step. Training and external calls still require their independent authorization gates.";
  const pipelineButton = $("#pipelineControlButton");
  pipelineButton.textContent = pipeline.desired_state === "running" ? "Pause" : "Start";
  pipelineButton.dataset.nextState = pipeline.desired_state === "running" ? "paused" : "running";
  $("#pipelineControlLabel").textContent = pipeline.effective_state === "pausing" ? "Scheduler disarming" : pipeline.effective_state === "starting" ? "Scheduler arming" : pipeline.desired_state !== "running" ? "Scheduler paused" : live ? "Scheduler armed · active" : next ? "Scheduler armed · work queued" : schedulerActivity ? "Scheduler armed · preparing work" : "Scheduler armed · idle";
  $("#pipelineControlDetail").textContent = pipeline.effective_state === "pausing" ? "Pause requested. The active run will finish first." : pipeline.effective_state === "starting" ? "Start requested. Mission Hub will apply it at the next daemon boundary." : pipeline.desired_state === "running" && live ? "Pause prevents new work after this job finishes; it does not interrupt the active run." : pipeline.desired_state === "running" && schedulerActivity ? (next ? "The next job is queued behind the scheduler's current preparation work." : "The scheduler is working before it can create the next job.") : pipeline.desired_state === "running" && next ? "Pause prevents queued work from starting at its next safe boundary." : pipeline.desired_state === "running" ? "No job is active. Pause prevents future authorized work from starting." : "Paused safely; active runs are not interrupted.";
  $("#trainingGate").textContent = data.safety.live_execution ? "Authorized" : "Disabled";
  $("#configHash").textContent = `config ${shortHash(data.config.sha256)}`;
  $("#heroFacts").innerHTML = [`config ${shortHash(data.config.sha256)}`, `${data.jobs.length} recent jobs`, staleDeployments.length ? `${staleDeployments.length} deployment sync pending` : `${data.artifacts.length} recent artifacts`].map((item) => `<span>${escapeHTML(item)}</span>`).join("");
  updateUnread(data.unread_count);
  renderWorkflowProgress(data.workflow_progress);

  $("#activeJobLabel").textContent = "Active job";
  renderJobFeature(live, "active");
  if (schedulerActivity) {
    $("#activeJobLabel").textContent = "Next task";
    $("#activeJobTitle").textContent = next ? friendlyIdentifier(next.job_type) : friendlyIdentifier(schedulerTask);
    $("#activeJobMeta").textContent = schedulerActivity.kind === "storage_inventory" ? (next ? "Queued and waiting for the storage inventory scan to finish" : "Will be scheduled after the storage inventory scan") : schedulerActivity.summary;
    $("#activeJobStatus").textContent = "Waiting";
    $("#activeJobStatus").className = "status-pill warn";
  }
  renderJobFeature(data.last_job, "last");
  renderDashboardTiming();
  const campaign = data.active_campaign;
  $("#campaignName").textContent = campaign?.name || "No campaign";
  const trainingMode = campaign?.metadata?.campaign_contract?.mode;
  $("#campaignMode").textContent = trainingMode ? friendlyIdentifier(trainingMode) : (campaign ? "Preserved legacy campaign" : "No training mode");
  $("#campaignMode").title = trainingMode ? "The immutable purpose contract that controls how training and evaluation evidence are interpreted." : "Legacy evidence predates the training-purpose contract and cannot be resumed directly.";
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

function renderJobFeature(job, prefix, statusOverride = null) {
  const title = $(`#${prefix}JobTitle`), meta = $(`#${prefix}JobMeta`), status = $(`#${prefix}JobStatus`);
  if (!job) { title.textContent = prefix === "active" ? "No active job" : "No completed job"; meta.textContent = prefix === "active" ? "The queue is quiet." : "No terminal work is recorded."; status.textContent = prefix === "active" ? "Idle" : "None"; status.className = "status-pill neutral"; return; }
  title.textContent = job.job_type;
  const model = job.model_names?.[0] || "deterministic / no model";
  meta.textContent = `${model} · ${job.id} · ${when(job.updated_at)}`;
  status.textContent = statusOverride || job.status; status.className = `status-pill ${statusClass(job.status)}`;
}

function updateTabUnread(count) {
  document.title = count ? `(${count}) ${BASE_TAB_TITLE}` : BASE_TAB_TITLE;
  let icon = $("#tabIcon");
  if (!icon) {
    icon = document.createElement("link");
    icon.id = "tabIcon";
    icon.rel = "icon";
    document.head.appendChild(icon);
  }
  icon.href = count ? "/favicon-unread.svg" : "/favicon.svg";
}

function updateUnread(value) {
  const count = Math.max(0, Number(value) || 0);
  const badge = $("#unreadBadge"); badge.textContent = String(count); badge.classList.toggle("hidden", !count);
  $("#heroUnread").textContent = count ? `${count} unread` : "All read";
  $("#inboxTitle").textContent = count ? `${count} message${count === 1 ? "" : "s"} waiting` : "Nothing waiting";
  $("#inboxDetail").textContent = count ? "Open and mark them read" : "Open the shared message ledger";
  updateTabUnread(count);
}

async function loadThreads() {
  const data = await api("/lab/api/threads"); state.threads = data.items; updateUnread(data.unread_count); renderThreadList();
}

function renderThreadList() {
  $("#threadList").innerHTML = state.threads.map((thread) => {
    const waiting = Boolean(thread.on_call_next_check_at);
    const invoked = ["pending", "queued", "running"].includes(thread.on_call_status);
    const badge = waiting
      ? '<span class="status-pill warn">Sol waiting</span>'
      : invoked ? '<span class="status-pill good">Sol invoked</span>' : "";
    const waitDetail = waiting
      ? `<p>Next on-call check ${escapeHTML(when(thread.on_call_next_check_at))} · ${escapeHTML(thread.on_call_wait_reason || "waiting for a safe boundary")}</p>`
      : "";
    return `<button class="thread-item ${state.activeThread?.thread.id === thread.id ? "active" : ""}" data-thread-id="${escapeHTML(thread.id)}"><div class="thread-item-head"><strong>${escapeHTML(thread.subject)}</strong>${badge}${thread.unread_count ? '<span class="unread-dot"></span>' : ""}</div><p>${escapeHTML(when(thread.last_message_at || thread.created_at))} · ${thread.message_count} message${thread.message_count === 1 ? "" : "s"}</p>${waitDetail}</button>`;
  }).join("") || `<div class="empty-state"><h2>No threads yet</h2><p>Start the first operational conversation.</p></div>`;
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
  $("#chatList").innerHTML = state.chats.map((chat) => `<button class="thread-item ${state.activeChat?.thread.id === chat.id ? "active" : ""}" data-chat-id="${escapeHTML(chat.id)}"><div class="thread-item-head"><strong>${escapeHTML(chat.title)}</strong></div><p>${escapeHTML(shortHash(chat.checkpoint_sha256))} · ${chat.message_count || 0} turns</p></button>`).join("") || `<div class="empty-state"><h2>No chats yet</h2><p>Saved checkpoints will be listed here.</p></div>`;
  $$('[data-chat-id]').forEach((button) => button.addEventListener("click", () => openChat(button.dataset.chatId)));
}

function renderCheckpointOptions() {
  const eligible = state.checkpoints;
  $("#checkpointSelect").innerHTML = eligible.map((item) => `<option value="${escapeHTML(item.id)}">${escapeHTML(item.manifest.lineage_label || item.id)} · ${escapeHTML(shortHash(item.sha256))}</option>`).join("");
  $("#checkpointHelp").textContent = eligible.length ? `${eligible.length} exact checkpoint artifact${eligible.length === 1 ? "" : "s"}. Byte certification and compatibility status remain visible evidence, not a listing filter.` : "No checkpoint artifacts are registered yet.";
  $("#chatCreateForm button[type=submit]").disabled = !eligible.length;
}

async function openChat(id) { state.activeChat = await api(`/lab/api/chats/${id}`); renderChat(); renderChatList(); }
function renderChat() {
  const { thread, messages, invocations } = state.activeChat; $("#chatEmpty").classList.add("hidden"); $("#chatConversation").classList.remove("hidden");
  $("#chatTitle").textContent = thread.title; $("#chatCheckpoint").textContent = `${thread.checkpoint_artifact_id} · sha256 ${thread.checkpoint_sha256}`;
  $("#chatMessages").innerHTML = messages.map(messageHTML).join("") || `<div class="empty-state"><p>No turns recorded yet.</p></div>`;
  const pending = invocations.some((item) => ["queued", "running"].includes(item.status));
  $("#chatForm button[type=submit]").textContent = pending ? "Generating…" : "Send";
  $("#chatForm button[type=submit]").disabled = pending;
  if (pending) setTimeout(async () => {
    if (state.activeChat?.thread.id !== thread.id) return;
    await openChat(thread.id);
  }, 5000);
}

async function loadSettings() {
  if (!state.settings) { state.settings = await api("/lab/api/settings"); state.settingsWorking = structuredClone(state.settings.pending || state.settings.active); }
  try { const catalog = await api("/lab/api/providers/models"); state.catalogModels = catalog.items || []; state.providerCatalogs = catalog.providers || []; }
  catch (cause) { state.catalogModels = []; state.providerCatalogs = []; }
  renderSettings();
}

function ensureCatalogModel(modelId) {
  const existing = state.settingsWorking.models.find((item) => item.id === modelId);
  if (existing) { existing.enabled = true; return; }
  const catalog = state.catalogModels.find((item) => item.id === modelId);
  if (!catalog) return;
  const fields = ["id", "provider", "exact_name", "enabled", "local", "context_tokens", "output_tokens", "structured_output", "runtime", "weights", "device", "modality", "revision"];
  const model = Object.fromEntries(fields.map((field) => [field, structuredClone(catalog[field])]));
  const defaults = state.settingsWorking.model_defaults;
  model.context_tokens = catalog.provider_context_tokens || defaults.unlisted_context_tokens;
  model.output_tokens = catalog.provider_output_tokens || defaults.unlisted_output_tokens;
  model.enabled = true;
  state.settingsWorking.models.push(model);
}

function modelSupportsRoute(model, route) {
  if (!route?.model_modalities?.length) return true;
  const compatible = { text: ["text", "vision_language"], vision_language: ["text", "vision_language"], image_generation: ["image_generation"], vision_encoder: ["vision_encoder"] };
  return route.model_modalities.some((required) => (compatible[required] || [required]).includes(model.modality || "text"));
}

function modelSupportsJob(model, route, job) {
  if (!modelSupportsRoute(model, route)) return false;
  if (!String(job?.handler || "").startsWith("mission_hub.handlers.visual:")) return true;
  const provider = state.settingsWorking.providers.find((item) => item.id === model.provider);
  if (["visual.generate", "visual.encode"].includes(job.id)) return provider?.kind === "local_subprocess";
  if (["visual.inspect", "visual.caption", "visual.review"].includes(job.id)) {
    return job.executor_role === "mission_hub"
      ? ["codex_cli", "openai_compatible", "local_openai_compatible"].includes(provider?.kind)
      : ["local_subprocess", "codex_cli"].includes(provider?.kind);
  }
  return provider?.kind === "local_subprocess";
}

function allSelectableModels() {
  const result = [...state.settingsWorking.models];
  state.catalogModels.forEach((catalog) => { if (!result.some((model) => model.id === catalog.id || (model.provider === catalog.provider && model.exact_name === catalog.exact_name))) result.push(catalog); });
  return result;
}

function isCommissionedModelJob(job, routes = state.settingsWorking.routes) {
  if (!job) return false;
  const route = routes.find((item) => item.id === job.provider_route);
  return route?.id !== "deterministic" && job.handler !== "mission_hub.handlers.disabled:DisabledHandler";
}

function prepareModelRoutingForSave() {
  const routes = new Map(state.settingsWorking.routes.map((route) => [route.id, route]));
  const models = new Map(state.settingsWorking.models.map((model) => [model.id, model]));
  const providers = new Map(state.settingsWorking.providers.map((provider) => [provider.id, provider]));
  const prompts = new Map(state.settingsWorking.prompts.map((prompt) => [prompt.id, prompt]));
  state.settingsWorking.jobs.filter((job) => isCommissionedModelJob(job, state.settingsWorking.routes)).forEach((job) => {
    const route = routes.get(job.provider_route);
    const available = Boolean(route?.ordered_model_ids?.length);
    job.enabled = available;
    route.enabled = available;
    if (available && job.prompt_id) {
      const prompt = prompts.get(job.prompt_id);
      if (prompt) prompt.enabled = true;
    }
    route?.ordered_model_ids?.forEach((modelId) => {
      const model = models.get(modelId);
      if (!model) return;
      model.enabled = true;
      const provider = providers.get(model.provider);
      if (provider) provider.enabled = true;
    });
  });
}

function resolveMaximumModelLimits() {
  const defaultFields = {
    unlisted_context_tokens: "context_tokens",
    unlisted_output_tokens: "output_tokens",
  };
  Object.entries(defaultFields).forEach(([defaultField]) => {
    if (state.settingsWorking.model_defaults[defaultField] !== 0) return;
    const input = $(`[data-model-default-field="${defaultField}"]`);
    state.settingsWorking.model_defaults[defaultField] = Number(input?.dataset.maxValue) || 1;
  });
  state.settingsWorking.models.forEach((model) => {
    const card = $(`[data-model-card="${CSS.escape(model.id)}"]`);
    const catalog = state.catalogModels.find((item) => item.provider === model.provider && item.exact_name === model.exact_name);
    for (const field of ["context_tokens", "output_tokens"]) {
      if (model[field] !== 0) continue;
      const providerField = field === "context_tokens" ? "provider_context_tokens" : "provider_output_tokens";
      const input = card?.querySelector(`[data-model-field="${field}"]`);
      const defaultField = field === "context_tokens" ? "unlisted_context_tokens" : "unlisted_output_tokens";
      model[field] = Number(catalog?.[providerField]) || Number(input?.dataset.maxValue) || state.settingsWorking.model_defaults[defaultField];
    }
  });
}

function renderSettings() {
  const data = state.settingsWorking;
  const pending = Boolean(state.settings.activity?.pending_settings_id);
  $("#draftState").textContent = pending ? "Saved · applies after step" : "Saved · active";
  $("#draftState").className = `status-pill ${pending ? "warn" : "good"}`;
  const models = data.models;
  const selectableModels = allSelectableModels();
  const options = (selected, route, job) => `<option value="">No model</option>${selectableModels.filter((model) => modelSupportsJob(model, route, job)).map((model) => `<option value="${escapeHTML(model.id)}" ${model.id === selected ? "selected" : ""}>${escapeHTML(model.name || model.exact_name || friendlyIdentifier(model.id))} · ${escapeHTML(PROVIDER_NAMES[model.provider] || friendlyIdentifier(model.provider))}</option>`).join("")}`;
  const jobCards = data.jobs.filter((job) => isCommissionedModelJob(job, data.routes)).map((job) => {
    const route = data.routes.find((item) => item.id === job.provider_route);
    const primary = route?.ordered_model_ids?.[0] || "", fallback = route?.ordered_model_ids?.[1] || "";
    const presentation = JOB_PRESENTATION[job.id] || { category: "Other", title: friendlyIdentifier(job.id), summary: job.description, help: job.description };
    const modelControls = `<div class="setting-grid"><label>Try this model first ${helpTip("The first compatible model Mission Hub will ask for this job.")}<select data-field="primary_model">${options(primary, route, job)}</select></label><label>If that model fails ${helpTip("Mission Hub may try this second compatible model only for allowed failure types.")}<select data-field="fallback_model">${options(fallback, route, job)}</select></label><label>Execution path ${helpTip("The internal safety route that controls fallback and resource limits. It is shown for traceability and edited elsewhere.")}<input value="${escapeHTML(job.provider_route)}" disabled></label></div>`;
    return { category: presentation.category, html: `<article class="setting-card" data-job-card="${escapeHTML(job.id)}"><div class="setting-head"><div><p class="technical-id">${escapeHTML(job.id)} · runs on ${escapeHTML(job.executor_role === "trainbox" ? "trainingbox" : "this computer")}</p><h2>${escapeHTML(presentation.title)} ${helpTip(presentation.help)}</h2><p class="muted">${escapeHTML(presentation.summary)}</p></div><span class="status-pill good">Configured</span></div>${modelControls}</article>` };
  });
  $("#settingsJobs").innerHTML = `<div class="settings-notice"><strong>Built-in stages are automatic.</strong> Scripted pipeline steps, safety checks, and commissioning utilities are managed by Mission Hub and are not user settings. Choosing models here makes the corresponding commissioned capability available.</div>${[...JOB_CATEGORY_ORDER, "Other"].map((category) => {
    const cards = jobCards.filter((item) => item.category === category);
    return cards.length ? `<details class="settings-group" ${category === "Operations" ? "open" : ""}><summary><span>${escapeHTML(category)}</span><em>${cards.length} job${cards.length === 1 ? "" : "s"}</em></summary><div class="settings-group-body">${cards.map((item) => item.html).join("")}</div></details>` : "";
  }).join("")}`;
  const budgetCard = `<div class="settings-actionbar sub"><div><h2>External-model budget</h2><p>External calls remain locked until this switch is commissioned. A zero money value means no limit is set.</p></div></div><article class="setting-card" data-budget-card><div class="setting-grid"><label>Allow external calls<select data-budget-field="external_calls_enabled"><option value="false" ${!data.budget.external_calls_enabled ? "selected" : ""}>No</option><option value="true" ${data.budget.external_calls_enabled ? "selected" : ""}>Yes</option></select></label><label>Monthly ceiling (USD) ${helpTip("Zero means no monthly limit.")}<input type="number" min="0" step="0.01" data-budget-field="monthly_limit" value="${data.budget.monthly_limit}"></label><label>Weekly ceiling (USD) ${helpTip("Zero means no weekly limit.")}<input type="number" min="0" step="0.01" data-budget-field="weekly_limit" value="${data.budget.weekly_limit}"></label><label>Require per-run approval above (USD) ${helpTip("Zero means no automatic cost-threshold approval gate.")}<input type="number" min="0" step="0.01" data-budget-field="per_run_approval_above" value="${data.budget.per_run_approval_above}"></label><label>Emergency reserve (USD)<input type="number" min="0" step="0.01" data-budget-field="emergency_reserve" value="${data.budget.emergency_reserve}"></label><label>Warning fraction<input type="number" min="0" max="1" step="0.01" data-budget-field="warning_fraction" value="${data.budget.warning_fraction}"></label><label>Restriction fraction<input type="number" min="0" max="1" step="0.01" data-budget-field="restriction_fraction" value="${data.budget.restriction_fraction}"></label><label>Hard-stop fraction<input type="number" min="0" max="1" step="0.01" data-budget-field="hard_stop_fraction" value="${data.budget.hard_stop_fraction}"></label></div></article>`;
  $("#settingsRoutes").innerHTML = `<div class="settings-actionbar"><div><h2>Campaign pacing</h2><p>This quiet period applies once, before Mission Hub proposes the next campaign direction.</p></div></div><article class="setting-card" data-orchestration-card><div class="setting-grid two"><label>Wait before proposing the next campaign (minutes) ${helpTip("Budget pacing for the post-campaign strategic decision. Training, evaluation, deterministic handoffs, and retries do not wait.")}<input type="number" min="0" max="1440" step="1" data-orchestration-field="strategic_boundary_cooldown_seconds" value="${data.orchestration.strategic_boundary_cooldown_seconds / 60}"></label><div class="deterministic-note"><strong>Current contract</strong><span>Applied only to campaign.decide after terminal campaign evidence is ready.</span></div></div></article><div class="settings-actionbar sub"><div><h2>Visual pipeline limits</h2><p>Hard ceilings for one visual pack. Independent pixel review cannot be disabled here.</p></div></div><article class="setting-card" data-visual-card><div class="setting-grid"><label>Shadow mode ${helpTip("Runs may produce evidence but cannot admit assets for training while shadow mode is on.")}<select data-visual-field="shadow_mode"><option value="true" ${data.visual.shadow_mode ? "selected" : ""}>On</option><option value="false" ${!data.visual.shadow_mode ? "selected" : ""}>Off</option></select></label><label>Maximum pack items<input type="number" min="1" data-visual-field="max_pack_items" value="${data.visual.max_pack_items}"></label><label>Candidates per item<input type="number" min="1" data-visual-field="max_candidates_per_item" value="${data.visual.max_candidates_per_item}"></label><label>Maximum width<input type="number" min="1" data-visual-field="max_width" value="${data.visual.max_width}"></label><label>Maximum height<input type="number" min="1" data-visual-field="max_height" value="${data.visual.max_height}"></label><label>Generation steps<input type="number" min="1" data-visual-field="max_generation_steps" value="${data.visual.max_generation_steps}"></label><label>Stage timeout (seconds)<input type="number" min="1" data-visual-field="max_stage_seconds" value="${data.visual.max_stage_seconds}"></label><label>Pack byte ceiling<input type="number" min="1" data-visual-field="max_pack_bytes" value="${data.visual.max_pack_bytes}"></label><label>Required free disk bytes<input type="number" min="1" data-visual-field="minimum_free_bytes" value="${data.visual.minimum_free_bytes}"></label></div></article>${budgetCard}<div class="settings-actionbar sub"><div><h2>Execution paths</h2><p>These paths govern fallback, token ceilings, and spending. Their availability follows the model choices above.</p></div></div><div class="settings-card-stack">${data.routes.filter((route) => route.id !== "deterministic").map((route) => {
    const presentation = ROUTE_PRESENTATION[route.id] || { title: friendlyIdentifier(route.id), summary: "A bounded Mission Hub execution path." };
    const selected = route.ordered_model_ids.map((id) => models.find((model) => model.id === id)?.exact_name || id).join(" → ") || "No language model";
    const fallback = route.id === "deterministic" ? "" : `<div class="fallback-grid"><p>Try the fallback model only after:</p>${Object.entries(FALLBACK_CLASSES).map(([value, label]) => `<label class="toggle"><input type="checkbox" data-route-fallback="${escapeHTML(value)}" ${route.fallback_failure_classes.includes(value) ? "checked" : ""}> ${escapeHTML(label)}</label>`).join("")}</div>`;
    return `<article class="setting-card" data-route-card="${escapeHTML(route.id)}"><div class="setting-head"><div><p class="technical-id">${escapeHTML(route.id)}</p><h2>${escapeHTML(presentation.title)} ${helpTip(presentation.summary)}</h2><p class="muted">Current order: ${escapeHTML(selected)}. Choose primary and fallback models on the relevant model-routing card.</p></div></div><div class="setting-grid two"><label>Total token ceiling ${helpTip("The maximum combined token allowance for one routed request.")}<input type="number" min="1" data-route-field="max_total_tokens" value="${route.max_total_tokens}"></label><label>Maximum cost in USD ${helpTip("The spending reservation for one request. Zero means no per-request cost limit is set.")}<input type="number" min="0" step="0.01" data-route-field="max_cost_usd" value="${route.max_cost_usd}"></label></div>${fallback}</article>`;
  }).join("")}</div>`;
  const visualGrid = $("[data-visual-card] .setting-grid");
  visualGrid?.querySelector("label:nth-child(2)")?.insertAdjacentHTML("beforebegin", `<label>Wait between stages (minutes) ${helpTip("Starts when a visual stage finishes. This is the configurable budget and pacing buffer before the machinery may create the next stage.")}<input type="number" min="0" max="1440" step="1" data-visual-field="stage_cooldown_seconds" data-unit="minutes" value="${data.visual.stage_cooldown_seconds / 60}"></label>`);
  const providerCards = data.providers.map((provider) => {
    const local = ["local_openai_compatible", "local_subprocess"].includes(provider.kind);
    const codex = provider.kind === "codex_cli";
    const auth = codex ? "Existing ChatGPT login used by Codex CLI" : provider.credential_env ? `API key read from ${provider.credential_env}` : "No credential configured";
    const location = codex ? "A non-interactive Codex process on this computer." : local ? "A model server running inside the private machine boundary." : auth;
    const endpointLabel = codex ? "Codex program" : provider.kind === "local_subprocess" ? "Runtime program" : "API address";
    const endpointHelp = codex ? "The exact executable Mission Hub starts in non-interactive mode after settings are saved." : "The exact network endpoint Mission Hub contacts after settings are saved.";
    const providerCatalog = state.providerCatalogs.find((item) => item.provider_id === provider.id);
    const providerCatalogNote = providerCatalog ? `<p class="provider-note">Live catalog: ${escapeHTML(providerCatalog.message)}</p>` : '<p class="provider-note">Live catalog has not been loaded.</p>';
    const codexCatalog = codex ? `<div class="codex-catalog"><div class="catalog-heading"><strong>Models available to this Codex login</strong><span>${escapeHTML(providerCatalog?.message || "Catalog unavailable")} Discovered models are automatically available in Model routing.</span></div>${state.catalogModels.filter((model) => model.provider === provider.id).map((model) => `<div class="catalog-model"><div><strong>${escapeHTML(model.name)}</strong><span>${escapeHTML(model.description)}</span><em>${escapeHTML(model.reasoning_levels?.length ? `Reasoning: ${model.reasoning_levels.join(", ")}` : "Available in Model routing")}</em></div></div>`).join("") || '<p class="muted">No selectable models were returned.</p>'}</div>` : "";
    return `<article class="setting-card" data-provider-card="${escapeHTML(provider.id)}"><div class="setting-head"><div><p class="technical-id">${escapeHTML(provider.id)}</p><h2>${escapeHTML(PROVIDER_NAMES[provider.id] || friendlyIdentifier(provider.id))}</h2><p class="muted">${escapeHTML(location)}</p></div><label class="toggle"><input type="checkbox" data-provider-field="enabled" ${provider.enabled ? "checked" : ""}> Available for use</label></div><div class="setting-grid two"><label>${endpointLabel} ${helpTip(endpointHelp)}<input data-provider-field="endpoint" value="${escapeHTML(provider.endpoint)}"></label><label>Authentication ${helpTip(codex ? "Codex keeps and refreshes the ChatGPT account credential outside the Lab. The Lab never displays or copies it." : "Secrets are supplied to the service as environment variables and are never shown or saved in the Lab.")}<input value="${escapeHTML(auth)}" disabled></label></div>${codex ? '<p class="provider-note">Runs with <code>codex exec</code>, without an interactive terminal. Each job still supplies its own bounded prompt, output contract, timeout, sandbox, and model.</p>' : ""}${providerCatalogNote}${codexCatalog}</article>`;
  }).join("");
  const modelCards = data.models.map((model) => { const textModel = (model.modality || "text") === "text" || model.modality === "vision_language"; const catalog = state.catalogModels.find((item) => item.provider === model.provider && item.exact_name === model.exact_name); const contextMax = catalog?.provider_context_tokens || model.context_tokens; const outputMax = catalog?.provider_output_tokens || model.output_tokens; const limits = textModel ? `<label>Maximum context ${helpTip("The largest combined prompt and conversation the model can accept. Enter 0 to use the largest provider-reported or currently declared value.")}<input type="number" min="0" data-model-field="context_tokens" data-max-value="${contextMax}" value="${model.context_tokens}"></label><label>Maximum answer ${helpTip("The most tokens Mission Hub may allow in one response. Enter 0 to use the largest provider-reported or currently declared value.")}<input type="number" min="0" data-model-field="output_tokens" data-max-value="${outputMax}" value="${model.output_tokens}"></label>` : `<label>Immutable revision<input data-model-field="revision" value="${escapeHTML(model.revision)}"></label><label>Model role<input value="${escapeHTML(friendlyIdentifier(model.modality))}" disabled></label>`; return `<article class="setting-card" data-model-card="${escapeHTML(model.id)}"><div class="setting-head"><div><p class="technical-id">${escapeHTML(model.id)} · ${escapeHTML(PROVIDER_NAMES[model.provider] || friendlyIdentifier(model.provider))}</p><h2>${escapeHTML(friendlyIdentifier(model.id))}</h2><p class="muted">${escapeHTML(friendlyIdentifier(model.modality || "text"))} model${model.revision ? ` · pinned ${model.revision.slice(0, 12)}…` : ""}</p></div><label class="toggle"><input type="checkbox" data-model-field="enabled" ${model.enabled ? "checked" : ""}> Available for use</label></div><div class="setting-grid"><label>Provider's exact model name ${helpTip("Copy this identifier exactly from the provider. Similar-looking names may refer to different models.")}<input data-model-field="exact_name" value="${escapeHTML(model.exact_name)}"></label>${limits}</div></article>`; }).join("");
  $("#settingsProviders").innerHTML = `<div class="settings-actionbar"><div><h2>Model services</h2><p>Connections tell Mission Hub where models live. Secrets stay outside the Lab.</p></div><button id="addProviderButton" class="quiet-button">Add a service</button></div><div class="settings-card-stack">${providerCards}</div><div class="settings-actionbar sub"><div><h2>Models not listed</h2><p>These limits are used only when a service does not report its own maximum. Enter 0 to keep the current declared maximum.</p></div></div><article class="setting-card" data-model-defaults-card><div class="setting-grid two"><label>Context tokens ${helpTip("Used for manually named models when the provider reports no context maximum. Enter 0 to keep the current declared value.")}<input type="number" min="0" data-model-default-field="unlisted_context_tokens" data-max-value="${data.model_defaults.unlisted_context_tokens}" value="${data.model_defaults.unlisted_context_tokens}"></label><label>Output tokens ${helpTip("Used for manually named models when the provider reports no output maximum. Enter 0 to keep the current declared value.")}<input type="number" min="0" data-model-default-field="unlisted_output_tokens" data-max-value="${data.model_defaults.unlisted_output_tokens}" value="${data.model_defaults.unlisted_output_tokens}"></label></div></article><div class="settings-actionbar sub"><div><h2>Configured models</h2><p>Catalog models do not need to be added; choosing one in Model routing configures it automatically.</p></div><button id="addModelButton" class="quiet-button">Add a model not listed</button></div><div class="settings-card-stack">${modelCards || '<p class="muted">No models configured.</p>'}</div>`;
  $("#settingsPrompts").innerHTML = data.prompts.filter((prompt) => prompt.id !== "none" && isCommissionedModelJob(data.jobs.find((job) => job.id === prompt.job_type), data.routes)).map((prompt) => { const presentation = JOB_PRESENTATION[prompt.job_type]; return `<article class="setting-card" data-prompt-card="${escapeHTML(prompt.id)}"><div class="setting-head"><div><p class="technical-id">${escapeHTML(prompt.id)} · version ${prompt.version}</p><h2>${escapeHTML(presentation?.title || friendlyIdentifier(prompt.job_type))}</h2><p class="muted">These are the instructions sent when this job asks a language model for help.</p></div></div><div class="prompt-fields"><label>Role and rules ${helpTip("Stable instructions that define the task's role, boundaries, and required behavior.")}<textarea data-prompt-field="system">${escapeHTML(prompt.system)}</textarea></label><label>Task template ${helpTip("The job-specific request. Placeholders are filled from the approved job input when it runs.")}<textarea data-prompt-field="template">${escapeHTML(prompt.template)}</textarea></label></div></article>`; }).join("");
  bindSettingsInputs();
}

function reviewValue(value) {
  if (value === null || value === undefined || value === "") return "none";
  if (typeof value === "boolean") return value ? "on" : "off";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function reviewSettingRecord(pointer) {
  const section = state.settingsWorking?.[pointer.section];
  return Array.isArray(section) ? section.find((item) => item.id === pointer.id) : section;
}

function reviewModelOptions(selected, route) {
  return `<option value="">No model</option>${allSelectableModels().filter((model) => modelSupportsRoute(model, route)).map((model) => `<option value="${escapeHTML(model.id)}" ${model.id === selected ? "selected" : ""}>${escapeHTML(model.name || model.exact_name || friendlyIdentifier(model.id))} · ${escapeHTML(PROVIDER_NAMES[model.provider] || friendlyIdentifier(model.provider))}</option>`).join("")}`;
}

function reviewSettingHTML(item) {
  const pointer = item.setting;
  if (!pointer) return `<div class="review-managed-note">This is an operational safety state. It cannot be changed by a configuration draft.</div>`;
  const record = reviewSettingRecord(pointer);
  if (!record) return `<div class="review-managed-note">The referenced setting is no longer present in this draft.</div>`;
  const path = `${pointer.section}/${pointer.id}.${pointer.field}`;
  const common = `data-review-section="${escapeHTML(pointer.section)}" data-review-id="${escapeHTML(pointer.id)}" data-review-field="${escapeHTML(pointer.field)}"`;
  let control;
  if (pointer.field === "ordered_model_ids") {
    control = `<div class="review-model-pair"><label>Try first<select ${common} data-review-model-position="0">${reviewModelOptions(record.ordered_model_ids[0] || "", record)}</select></label><label>Fallback<select ${common} data-review-model-position="1">${reviewModelOptions(record.ordered_model_ids[1] || "", record)}</select></label></div>`;
  } else if (typeof record[pointer.field] === "boolean") {
    control = `<label class="toggle review-toggle"><input type="checkbox" ${common} ${record[pointer.field] ? "checked" : ""}> ${escapeHTML(pointer.label)}</label>`;
  } else if (typeof record[pointer.field] === "number") {
    control = `<label>${escapeHTML(pointer.label)}<input type="number" min="0" ${common} value="${record[pointer.field]}"></label>`;
  } else {
    control = `<label>${escapeHTML(pointer.label)}<input ${common} value="${escapeHTML(record[pointer.field])}"></label>`;
  }
  const explanation = item.code === "job_handler_uncommissioned"
    ? "Keep this on to preserve the job as commissioning work, or turn it off to remove it from this draft. A switch cannot create the missing executor."
    : "Changing this control saves the draft and recalculates the review immediately.";
  return `<div class="review-inline-setting"><div><code>${escapeHTML(path)}</code><span>${escapeHTML(explanation)}</span></div>${control}</div>`;
}

async function saveReviewSetting(input) {
  const pointer = { section: input.dataset.reviewSection, id: input.dataset.reviewId, field: input.dataset.reviewField };
  const record = reviewSettingRecord(pointer);
  if (!record) return;
  const previous = structuredClone(record[pointer.field]);
  if (pointer.field === "ordered_model_ids") {
    const controls = Array.from(document.querySelectorAll(`[data-review-section="${CSS.escape(pointer.section)}"][data-review-id="${CSS.escape(pointer.id)}"][data-review-field="ordered_model_ids"]`));
    record.ordered_model_ids = controls.sort((a, b) => Number(a.dataset.reviewModelPosition) - Number(b.dataset.reviewModelPosition)).map((control) => control.value).filter((value, index, values) => value && values.indexOf(value) === index);
    record.ordered_model_ids.forEach(ensureCatalogModel);
  } else if (input.type === "checkbox") record[pointer.field] = input.checked;
  else if (input.type === "number") record[pointer.field] = Number(input.value);
  else record[pointer.field] = input.value;
  $$('[data-review-field]').forEach((control) => { control.disabled = true; });
  try {
    const result = await api("/lab/api/settings/draft", { method: "POST", body: JSON.stringify(state.settingsWorking) });
    state.settings.draft = result.draft;
    state.settingsWorking = structuredClone(result.draft.payload);
    state.settingsReview = await api("/lab/api/settings/review");
    renderSettings();
    renderSettingsReview();
    toast(result.rebased ? "Draft updated to the current configuration and saved; your choices were preserved." : "Draft saved; commissioning review recalculated.");
  } catch (cause) {
    record[pointer.field] = previous;
    renderSettingsReview();
    toast(cause.message, true);
  }
}

function renderSettingsReview() {
  const review = state.settingsReview;
  $("#reviewSummary").innerHTML = `<div><span>Draft</span><strong>${escapeHTML(review.draft.id.replace("draft-", ""))}</strong></div><div><span>Changed values</span><strong>${review.change_count}</strong></div><div><span>Activation readiness</span><strong>${review.ready_for_activation ? "Ready for release work" : `${review.blockers.length} blocker${review.blockers.length === 1 ? "" : "s"}`}</strong></div>`;
  const issues = (items, empty) => items.map((item) => `<div class="review-item"><strong>${escapeHTML(REVIEW_ISSUE_NAMES[item.code] || friendlyIdentifier(item.code))}</strong><span>${escapeHTML(item.message)}</span>${reviewSettingHTML(item)}</div>`).join("") || `<div class="review-empty">${escapeHTML(empty)}</div>`;
  $("#reviewBlockers").innerHTML = issues(review.blockers, "No semantic blockers found.");
  $("#reviewWarnings").innerHTML = issues(review.warnings, "No warnings found.");
  $("#reviewBlockerCount").textContent = String(review.blockers.length);
  $("#reviewWarningCount").textContent = String(review.warnings.length);
  $("#reviewChanges").innerHTML = review.changes.map((change) => `<div class="review-change"><strong>${escapeHTML(`${change.section}/${change.id}.${change.field}`)}</strong><span>${escapeHTML(reviewValue(change.before))} → ${escapeHTML(reviewValue(change.after))}</span></div>`).join("");
  $("#reviewRequirements").innerHTML = review.requirements.map((item) => `<div class="review-requirement">${escapeHTML(item.label)}</div>`).join("");
  $("#reviewAcknowledgement").checked = false;
  $$('[data-review-field]').forEach((input) => input.addEventListener("change", () => saveReviewSetting(input)));
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
    if (field === "primary_model" || field === "fallback_model") { const route = state.settingsWorking.routes.find((item) => item.id === job.provider_route); if (!route) return; const primary = card.querySelector('[data-field="primary_model"]').value, fallback = card.querySelector('[data-field="fallback_model"]').value; ensureCatalogModel(primary); ensureCatalogModel(fallback); route.ordered_model_ids = [primary, fallback].filter((item, index, values) => item && values.indexOf(item) === index); }
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
  $$('[data-orchestration-field]').forEach((input) => input.addEventListener("change", () => { state.settingsWorking.orchestration[input.dataset.orchestrationField] = Math.round(Number(input.value) * 60); }));
  $$('[data-visual-field]').forEach((input) => input.addEventListener("change", () => { state.settingsWorking.visual[input.dataset.visualField] = input.dataset.visualField === "shadow_mode" ? input.value === "true" : input.dataset.unit === "minutes" ? Math.round(Number(input.value) * 60) : Number(input.value); }));
  $$('[data-budget-field]').forEach((input) => input.addEventListener("change", () => { state.settingsWorking.budget[input.dataset.budgetField] = input.dataset.budgetField === "external_calls_enabled" ? input.value === "true" : Number(input.value); }));
  $$('[data-model-default-field]').forEach((input) => input.addEventListener("change", () => { state.settingsWorking.model_defaults[input.dataset.modelDefaultField] = Number(input.value); }));
  $("#addProviderButton")?.addEventListener("click", () => $("#providerDialog").showModal());
  $("#addModelButton")?.addEventListener("click", () => { $("#modelProviderInput").innerHTML = state.settingsWorking.providers.map((provider) => `<option value="${escapeHTML(provider.id)}">${escapeHTML(PROVIDER_NAMES[provider.id] || friendlyIdentifier(provider.id))}</option>`).join(""); $("#modelContextInput").value = 0; $("#modelOutputInput").value = 0; $("#modelDialog").showModal(); });
}

async function initialize() {
  try {
    const data = await api("/lab/api/session"); state.session = data.session; $("#accountName").textContent = state.session.username;
    await loadDashboard();
    const requested = location.hash.slice(1); await navigate(["overview","threads","chat","observatory","settings"].includes(requested) ? requested : "overview");
    window.setInterval(() => loadDashboard().catch(() => {}), 15000);
    window.setInterval(renderDashboardTiming, 1000);
  } catch (cause) { toast(cause.message, true); }
}

$$('[data-nav]').forEach((node) => node.addEventListener("click", () => navigate(node.dataset.nav)));
$("#refreshButton").addEventListener("click", () => loadDashboard().then(() => toast("Mission Hub state refreshed.")).catch((cause) => toast(cause.message, true)));
$("#refreshObservatoryButton").addEventListener("click", () => loadObservatory().then(() => toast("Observatory evidence refreshed.")).catch((cause) => toast(cause.message, true)));
$("#pipelineControlButton").addEventListener("click", async (event) => { const button = event.currentTarget; const desiredState = button.dataset.nextState; button.disabled = true; try { await api("/lab/api/pipeline", { method: "POST", body: JSON.stringify({ desired_state: desiredState }) }); await loadDashboard(); toast(desiredState === "paused" ? "Pause requested. Active work will finish safely." : "Pipeline start requested."); } catch (cause) { toast(cause.message, true); } finally { button.disabled = false; } });
$("#logoutButton").addEventListener("click", async () => { await api("/lab/api/logout", { method: "POST", body: "{}" }); window.location.replace("/login"); });
$("#campaignForm").addEventListener("submit", async (event) => { event.preventDefault(); const id = event.currentTarget.dataset.campaignId; if (!id) return; try { await api(`/lab/api/campaigns/${id}/objective`, { method: "POST", body: JSON.stringify({ objective: $("#campaignObjective").value }) }); $("#campaignSaved").textContent = "Saved just now"; await loadDashboard(); } catch (cause) { toast(cause.message, true); } });
$("#newThreadButton").addEventListener("click", () => $("#threadDialog").showModal());
$("#threadForm").addEventListener("submit", async (event) => { event.preventDefault(); try { const created = await api("/lab/api/threads", { method: "POST", body: JSON.stringify({ subject: $("#threadSubjectInput").value, body: $("#threadBodyInput").value }) }); $("#threadDialog").close(); event.target.reset(); state.activeThread = created; renderThread(); await loadThreads(); toast("Message sent. Sol has been invoked."); } catch (cause) { toast(cause.message, true); } });
$("#replyForm").addEventListener("submit", async (event) => { event.preventDefault(); if (!state.activeThread) return; try { await api(`/lab/api/threads/${state.activeThread.thread.id}/messages`, { method: "POST", body: JSON.stringify({ body: $("#replyBody").value }) }); $("#replyBody").value = ""; await openThread(state.activeThread.thread.id); toast("Message sent. Sol has been invoked."); } catch (cause) { toast(cause.message, true); } });
$("#threadBack").addEventListener("click", () => $("#threads").classList.remove("thread-open"));
$("#newChatButton").addEventListener("click", async () => { if (!state.checkpoints.length) await loadChats(); $("#chatDialog").showModal(); });
$("#chatCreateForm").addEventListener("submit", async (event) => { event.preventDefault(); try { const created = await api("/lab/api/chats", { method: "POST", body: JSON.stringify({ title: $("#chatTitleInput").value, checkpoint_artifact_id: $("#checkpointSelect").value }) }); $("#chatDialog").close(); event.target.reset(); state.activeChat = created; renderChat(); await loadChats(); } catch (cause) { toast(cause.message, true); } });
$("#chatForm").addEventListener("submit", async (event) => { event.preventDefault(); if (!state.activeChat) return; try { state.activeChat = await api(`/lab/api/chats/${state.activeChat.thread.id}/messages`, { method: "POST", body: JSON.stringify({ body: $("#chatBody").value }) }); $("#chatBody").value = ""; renderChat(); toast("Turn preserved and generation queued."); } catch (cause) { toast(cause.message, true); } });
$("#reviewDraftButton")?.addEventListener("click", () => openSettingsReview().catch((cause) => toast(cause.message, true)));
$$('[data-close-dialog]').forEach((button) => button.addEventListener("click", () => $(`#${button.dataset.closeDialog}`).close()));
$("#providerForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const id = $("#providerIdInput").value.trim().toLowerCase();
  if (state.settingsWorking.providers.some((item) => item.id === id)) { toast("That service name is already in use.", true); return; }
  const local = $("#providerLocalInput").checked;
  state.settingsWorking.providers.push({ id, kind: local ? "local_openai_compatible" : "openai_compatible", enabled: false, endpoint: $("#providerEndpointInput").value.trim(), credential_env: $("#providerCredentialInput").value.trim(), timeout_seconds: 3600, max_attempts: 1, concurrency: 1 });
  $("#providerDialog").close(); event.target.reset(); renderSettings(); toast("Service added. Press Save settings to apply it.");
});
$("#modelForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const id = $("#modelIdInput").value.trim().toLowerCase();
  if (state.settingsWorking.models.some((item) => item.id === id)) { toast("That model name is already in use.", true); return; }
  const provider = $("#modelProviderInput").value;
  const local = state.settingsWorking.providers.find((item) => item.id === provider)?.kind === "local_openai_compatible";
  state.settingsWorking.models.push({ id, provider, exact_name: $("#modelExactNameInput").value.trim(), enabled: false, local, context_tokens: Number($("#modelContextInput").value), output_tokens: Number($("#modelOutputInput").value), structured_output: true, runtime: local ? "openai-compatible local service" : "api", weights: "", device: local ? "local-service" : "remote", modality: "text", revision: "" });
  $("#modelDialog").close(); event.target.reset(); renderSettings(); toast("Model added. Press Save settings to apply it.");
});
$$('[data-settings-tab]').forEach((button) => button.addEventListener("click", () => { $$('[data-settings-tab]').forEach((node) => node.classList.toggle("active", node === button)); $$(".settings-section").forEach((node) => node.classList.toggle("active", node.id === `settings${button.dataset.settingsTab[0].toUpperCase()}${button.dataset.settingsTab.slice(1)}`)); }));
function syncRenderedSettings() {
  const selectors = [
    "[data-field]", "[data-provider-field]", "[data-route-field]", "[data-route-fallback]",
    "[data-model-field]", "[data-prompt-field]", "[data-orchestration-field]", "[data-visual-field]",
    "[data-budget-field]", "[data-model-default-field]",
  ];
  $$(`#settings :is(${selectors.join(",")})`).forEach((control) => {
    control.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

async function saveSettings(action = null) {
  const button = $("#saveDraftButton");
  const choiceButtons = [$("#settingsRestartButton"), $("#settingsLaterButton")];
  const choosing = action !== null;
  syncRenderedSettings();
  resolveMaximumModelLimits();
  prepareModelRoutingForSave();
  button.disabled = true;
  if (choosing) {
    choiceButtons.forEach((node) => { node.disabled = true; });
    $("#settingsSaveError").classList.add("hidden");
  }
  try {
    const result = await api("/lab/api/settings/save", { method: "POST", body: JSON.stringify({ settings: state.settingsWorking, action }) });
    if (result.requires_choice) {
      const step = result.current_step;
      $("#settingsSaveDetail").textContent = `${friendlyIdentifier(step.job_type)} is running. Restarting stops this attempt and performs the step again from the beginning with the new settings.`;
      $("#settingsSaveError").classList.add("hidden");
      $("#settingsSaveDialog").showModal();
      return;
    }
    $("#settingsSaveDialog").close();
    state.settings.active = structuredClone(state.settingsWorking);
    state.settings.activity = {
      ...(state.settings.activity || {}),
      pending_settings_id: result.state === "waiting_for_step" ? result.settings_id : null,
      pending_after_run_id: result.state === "waiting_for_step" ? result.current_step?.run_id : null,
    };
    renderSettings();
    toast(result.state === "waiting_for_step" ? "Settings saved. They will apply as soon as this step finishes." : result.state === "restarting_step" ? "Settings saved. The current step is stopping and will restart from the beginning." : "Settings saved and active.");
  } catch (cause) {
    $("#draftState").textContent = "Save failed";
    $("#draftState").className = "status-pill bad";
    if (choosing && $("#settingsSaveDialog").open) {
      $("#settingsSaveError").textContent = `Settings were not saved: ${cause.message}`;
      $("#settingsSaveError").classList.remove("hidden");
    }
    toast(`Settings were not saved: ${cause.message}`, true);
  } finally {
    button.disabled = false;
    choiceButtons.forEach((node) => { node.disabled = false; });
  }
}

$("#saveDraftButton").addEventListener("click", () => saveSettings());
$("#settingsRestartButton").addEventListener("click", () => saveSettings("restart_step"));
$("#settingsLaterButton").addEventListener("click", () => saveSettings("apply_after_step"));
$("#settingsDiscardButton").addEventListener("click", () => {
  $("#settingsSaveDialog").close();
  state.settingsWorking = structuredClone(state.settings.active);
  renderSettings();
  toast("Changes discarded.");
});

initialize();
