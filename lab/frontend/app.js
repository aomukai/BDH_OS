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
  lastKnownSchedule: null,
  timing: [],
  viewMode: "desktop",
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));
let statusLoad = null;

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
  const [data, timingData] = await Promise.all([
    api(`/api/control/status${suffix}`),
    api("/api/control/timing?limit=300"),
  ]);
  const incomingControl = data.control || {};
  const incomingSchedule = incomingControl.schedule || {};
  if (
    incomingSchedule.available
    && incomingSchedule.next_run_at != null
    && Number.isFinite(Number(incomingSchedule.next_run_at))
  ) {
    state.lastKnownSchedule = { ...incomingSchedule };
    try {
      sessionStorage.setItem(
        "ninereeds-last-known-schedule",
        JSON.stringify(state.lastKnownSchedule)
      );
    } catch (_error) {
      // The clock still works when browser storage is unavailable.
    }
  } else {
    if (!state.lastKnownSchedule) {
      try {
        state.lastKnownSchedule = JSON.parse(
          sessionStorage.getItem("ninereeds-last-known-schedule") || "null"
        );
      } catch (_error) {
        state.lastKnownSchedule = null;
      }
    }
    const mayRetainDeadline = ![
      "waiting_for_trainbox",
      "idle",
    ].includes(incomingSchedule.status);
    if (!mayRetainDeadline) {
      state.lastKnownSchedule = null;
      try {
        sessionStorage.removeItem("ninereeds-last-known-schedule");
      } catch (_error) {
        // The live schedule remains authoritative without browser storage.
      }
    }
    if (
      mayRetainDeadline
      &&
      state.lastKnownSchedule
      && state.lastKnownSchedule.next_run_at != null
      && Number.isFinite(Number(state.lastKnownSchedule.next_run_at))
    ) {
      incomingControl.schedule = {
        ...state.lastKnownSchedule,
        status: (
          incomingSchedule.status && incomingSchedule.status !== "unavailable"
            ? incomingSchedule.status
            : state.lastKnownSchedule.status
        ),
        plan_id: incomingSchedule.plan_id || state.lastKnownSchedule.plan_id,
        stale: true,
      };
    }
  }
  state.control = incomingControl;
  state.timing = timingData.timing?.events || [];
  renderControl();
  renderOrchestratorClock();
}

function fmtTime(value) {
  if (!value) return "Unknown";
  return new Date(value * 1000).toLocaleString("ja-JP", {
    hourCycle: "h23",
  });
}

function fmtClockTime(value, { seconds = false } = {}) {
  const date = value instanceof Date ? value : new Date(value);
  return date.toLocaleTimeString("ja-JP", {
    hour: "2-digit",
    minute: "2-digit",
    ...(seconds ? { second: "2-digit" } : {}),
    hourCycle: "h23",
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function artifactContentUrl(artifact) {
  return `/api/artifacts/${encodeURIComponent(artifact.id)}/content`;
}

function isHtmlArtifact(artifact) {
  return artifact.path.toLowerCase().endsWith(".html") || artifact.media_type.includes("html");
}

function opensInNewTab(artifact) {
  return ["mri", "graph", "atlas"].includes(artifact.type);
}

function artifactAction(artifact, label = "Open", extraClass = "") {
  const classes = `ghost ${extraClass}`.trim();
  if (opensInNewTab(artifact)) {
    return `<a class="${classes}" href="${artifactContentUrl(artifact)}" target="_blank" rel="noopener">${escapeHtml(label)}</a>`;
  }
  return `<button class="${classes}" data-artifact="${artifact.id}">${escapeHtml(label)}</button>`;
}

function card(title, value, meta, artifact) {
  const action = artifact ? artifactAction(artifact) : "";
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

function loadStatus() {
  if (statusLoad) return statusLoad;
  statusLoad = api("/api/status")
    .then((data) => {
      state.dashboard = data.dashboard;
      state.git = data.git;
      renderDashboard();
      renderSettings(data.git);
    })
    .finally(() => {
      statusLoad = null;
    });
  return statusLoad;
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
  const [data, timingData] = await Promise.all([
    api(`/api/timeline?limit=${encodeURIComponent(limit)}`),
    api(`/api/control/timing?limit=${encodeURIComponent(limit)}`),
  ]);
  const operational = (timingData.timing?.events || []).map((event) => ({
    title: timingEventTitle(event),
    kind: ["pipeline", event.role, event.provider, event.model]
      .filter(Boolean)
      .join(" · "),
    timestamp: event.epoch_seconds,
    details: event,
  }));
  const combined = [...data.events, ...operational]
    .sort((a, b) => Number(b.timestamp || 0) - Number(a.timestamp || 0))
    .slice(0, Number(limit));
  renderTimeline(combined);
}

function timingEventTitle(event) {
  const names = {
    "orchestrator.wake_requested": "Orchestrator wake requested",
    "orchestrator.wake_failed": "Orchestrator wake failed",
    "orchestrator.started": "Orchestrator started",
    "orchestrator.finished": "Orchestrator finished",
    "campaign.identity_repaired": "Campaign identity repaired",
    "plan.queued": "Plan queued",
    "plan.status": `Plan ${String(event.status || "changed").replaceAll("_", " ")}`,
    "plan.attempt_failed": "Model attempt failed",
    "plan.report": "Plan finished",
  };
  const base = names[event.event]
    || String(event.event || "Pipeline event").replaceAll(".", " ");
  return event.plan_kind ? `${base} · ${event.plan_kind}` : base;
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
  const development = d.development_state;
  const evolution = d.evolution_state;
  const play = state.control?.campaign?.play || null;
  const latestRecommendation =
    development?.recommended_next_action || d.latest_recommendations;
  const fullCore = Number(development?.evidence?.full_core_optimizer_steps || 0);
  const requiredSteps = Number(
    development?.readiness_gates?.full_core_optimizer_steps?.required || 0
  );
  const foundationProgress = requiredSteps
    ? Math.min(100, Math.round((fullCore / requiredSteps) * 100))
    : 0;
  const playSteps = Number(play?.optimizer_steps || 0);
  const playTargetSteps = Number(play?.target_steps || 0);
  const progress = play && playTargetSteps
    ? Math.min(100, Math.round((playSteps / playTargetSteps) * 100))
    : foundationProgress;

  $("#missionGrid").innerHTML = [
    missionCard(
      "Current campaign",
      d.current_campaign?.title || "No campaign indexed",
      d.current_campaign
        ? `Generation ${evolution?.generation ?? "—"} · ${
            development?.stage?.replaceAll("_", " ") || "unknown stage"
          } · ${d.current_campaign.artifacts?.length || 0} campaign artifacts`
        : "Waiting for a campaign manifest.",
      "campaign"
    ),
    missionCard(
      "North star",
      evolution?.autonomy === "active" ? "Autonomous evolution" : "Controller inactive",
      evolution?.north_star || "Waiting for the durable evolution controller.",
      "north-star"
    ),
    missionCard(
      "Current bottleneck",
      d.current_bottleneck || "No bottleneck detected",
      d.current_bottleneck
        ? "Derived from the latest deterministic evaluation."
        : "The current evaluation has not identified a dominant constraint.",
      "bottleneck"
    ),
  ].join("");

  $("#recommendationKind").textContent = development?.recommended_next_action
    ? "Active developmental policy"
    : (d.latest_recommendations ? "Evaluator advisory" : "None yet");
  $("#recommendationText").textContent =
    latestRecommendation || "No recommendation has been published yet.";
  const missionStatus = $("#missionStatus");
  missionStatus.textContent = evolution?.autonomy === "active" ? "Autonomous" : "Inactive";
  missionStatus.className = `badge ${
    evolution?.autonomy === "active" ? "status-good" : "status-warn"
  }`;

  const stage = play
    ? `Play · branch ${play.branch_index ?? "—"}/${play.max_branches ?? "—"}`
    : (development?.stage?.replaceAll("_", " ") || "Unknown stage");
  $("#developmentStage").textContent = stage;
  $("#developmentPercent").textContent = (play ? playTargetSteps : requiredSteps)
    ? `${progress}%`
    : "—";
  $("#developmentBar").style.width = `${progress}%`;
  $("#developmentDetail").textContent = play
    ? `${playSteps.toLocaleString()} / ${playTargetSteps.toLocaleString()} branch steps · ${
        Number(play.completed_branches || 0).toLocaleString()
      } branches documented · best observed score ${Math.round(Number(play.best_score || 0) * 100)}% · insight-first research`
    : development
      ? `${fullCore.toLocaleString()} / ${requiredSteps ? requiredSteps.toLocaleString() : "?"} full-core steps · ${
        development.behavioral_admission_eligible
          ? "behavioral admission enabled"
          : "bootstrap continuation only"
      }`
      : "Waiting for the durable Cortex ledger.";

  $("#dashboardBrief").innerHTML = `
    <dt>Generation</dt><dd>${escapeHtml(evolution?.generation ?? "—")}</dd>
    <dt>Campaigns</dt><dd>${escapeHtml(d.campaign_count || 0)} indexed</dd>
    <dt>Epoch</dt><dd>${escapeHtml(d.current_epoch ? `E${d.current_epoch}` : "—")}</dd>
    <dt>Chat build</dt><dd>${escapeHtml(d.current_published_chat_build?.label || "Not published")}</dd>
  `;

  $("#artifactCount").textContent = `${Number(d.artifact_count || 0).toLocaleString()} indexed artifacts`;
  $("#dashboardGrid").innerHTML = [
    artifactCard("Report", d.latest_report, "Campaign synthesis"),
    artifactCard("MRI", d.latest_mri, "Activation health"),
    artifactCard("3D map", d.latest_graph, "Structural view"),
    artifactCard("Atlas", d.latest_atlas, "Grounding traces"),
  ].join("");
  renderPipelineActivity();
}

function missionCard(label, value, detail, tone) {
  return `
    <article class="mission-card mission-${escapeHtml(tone)}">
      <p class="card-label">${escapeHtml(label)}</p>
      <h3>${escapeHtml(value)}</h3>
      <p>${escapeHtml(detail)}</p>
    </article>
  `;
}

function artifactCard(label, artifact, detail) {
  return `
    <article class="artifact-card ${artifact ? "" : "is-empty"}">
      <div>
        <p class="card-label">${escapeHtml(label)}</p>
        <h3>${escapeHtml(artifact?.title || "Not available")}</h3>
        <p>${escapeHtml(artifact ? detail : "No artifact published for this campaign.")}</p>
      </div>
      ${
        artifact
          ? artifactAction(artifact, "Open", "artifact-open")
          : ""
      }
    </article>
  `;
}

function renderTrainbox() {
  const snapshot = state.trainbox || {};
  const status = snapshot.status;
  const freshness = $("#trainboxFreshness");
  if (!snapshot.reachable || !status) {
    freshness.textContent = "Offline";
    freshness.className = "badge status-bad";
    $("#trainboxGrid").innerHTML = `
      ${telemetryCard(
        "Trainbox",
        "Offline",
        snapshot.error?.message || "Restricted telemetry did not respond.",
        "bad"
      )}
    `;
    renderPipelineActivity();
    return;
  }

  const healthy = snapshot.ok && !snapshot.stale;
  freshness.textContent = snapshot.stale ? "Stale" : "Live";
  freshness.className = `badge ${healthy ? "status-good" : "status-warn"}`;
  const gpus = status.gpu?.gpus || [];
  const gpuSummary = gpus.length
    ? gpus.map((gpu) => `GPU ${gpu.index}: ${gpu["utilization.gpu"]}% · ${gpu["temperature.gpu"]}°C · ${gpu["memory.free"]} MiB free`).join(" | ")
    : "No GPU telemetry";
  const pipeline = status.pipeline || {};
  const cortex = pipeline.cortex || null;
  const system = status.system || {};
  const busyGpus = gpus.filter((gpu) => Number(gpu["utilization.gpu"]) > 5).length;

  $("#trainboxGrid").innerHTML = [
    telemetryCard(
      "Trainbox",
      healthy ? "Online" : "Attention",
      `${status.hostname || "trainbox"} · ${fmtDuration(system.uptime_seconds)} uptime · ${Math.round(snapshot.latency_ms || 0)} ms`,
      healthy ? "good" : "warn"
    ),
    telemetryCard(
      "Compute",
      `${busyGpus}/${gpus.length || 2} GPUs active`,
      gpuSummary,
      busyGpus ? "active" : "quiet"
    ),
    telemetryCard(
      "Capacity",
      `${fmtBytes(system.disk?.free_bytes)} free`,
      `${fmtBytes(system.memory?.available_bytes)} RAM · ${cortex ? `Cortex ${cortex.status || "present"}` : "pipeline ready"}`,
      "quiet"
    ),
  ].join("");
  renderPipelineActivity();
}

function renderControl() {
  const control = state.control || {};
  const local = control.local || {};
  const remote = control.trainbox || {};
  const services = control.services || {};
  const providers = control.providers || {};
  const campaign = control.campaign || {};
  const campaignBoundary = campaign.wave
    ? `${campaign.boundary_index ?? "—"}/${campaign.wave.blocks_total || "—"}`
    : (campaign.boundary_index ?? "—");
  const badge = $("#controlFreshness");
  badge.textContent = control.ok ? "Healthy" : "Attention";
  badge.className = `badge ${control.ok ? "status-good" : "status-warn"}`;

  const count = (snapshot, status) => Number(snapshot.counts?.[status] || 0);
  const active = (snapshot) =>
    count(snapshot, "queued") + count(snapshot, "claimed") + count(snapshot, "running");
  const recent = [...(local.latest_receipts || []), ...(remote.latest_receipts || [])]
    .sort((a, b) => String(b.updated_at || "").localeCompare(String(a.updated_at || "")))[0];
  const supervisorServices = ["supervisor", "supervisor_path", "supervisor_timer"];
  const healthyServices = supervisorServices.filter((name) => services[name]).length;

  $("#controlGrid").innerHTML = [
    telemetryCard(
      "Control plane",
      control.ok ? "Healthy" : "Attention",
      `${healthyServices}/${supervisorServices.length} supervisors · ${active(local) + active(remote)} active receipts`,
      control.ok ? "good" : "warn"
    ),
    telemetryCard(
      "Strategic provider",
      providers.selected_provider
        ? String(providers.selected_provider).toUpperCase()
        : "Waiting",
      `Codex ${providers.codex?.state || "unknown"} · Fugu ${providers.fugu?.state || "unknown"}`,
      providers.selected_provider ? "active" : "quiet"
    ),
    telemetryCard(
      "Current work",
      recent
        ? (
            recent.status === "dead_letter"
              ? "Boundary failed"
              : (
                  recent.status === "blocked"
                    ? "Boundary blocked"
                    : pipelineActivity(recent.plan_id).label
                )
          )
        : "No receipt",
      recent
        ? `${String(recent.status || "unknown").replaceAll("_", " ")} · boundary ${campaignBoundary}`
        : "No plans recorded.",
      receiptTone(recent?.status)
    ),
  ].join("");
  renderPipelineTiming();
  renderPipelineActivity();
}

function renderPipelineTiming() {
  const grid = $("#pipelineTimingGrid");
  const badge = $("#timingActivityStatus");
  if (!grid || !badge) return;
  const control = state.control || {};
  const receipts = [
    ...(control.local?.latest_receipts || []),
    ...(control.trainbox?.latest_receipts || []),
  ];
  const activeStatuses = new Set(["queued", "claimed", "running", "retry_wait"]);
  const statusRank = { running: 4, claimed: 3, queued: 2, retry_wait: 1 };
  const active = receipts
    .filter((receipt) => activeStatuses.has(receipt.status))
    .sort((a, b) => (
      (statusRank[b.status] || 0) - (statusRank[a.status] || 0)
      || String(b.updated_at || "").localeCompare(String(a.updated_at || ""))
    ))[0];
  const events = state.timing || [];
  const latestReport = [...events].reverse().find((event) => (
    ["plan.report", "plan.attempt_failed"].includes(event.event)
    && (event.model || event.requested_model || event.role)
  ));
  const latestSupervisor = [...events].reverse().find((event) => (
    event.event === "orchestrator.finished"
  ));
  const pipelineFault = (
    latestSupervisor?.status === "failed"
    && Number(latestSupervisor.epoch_seconds || 0)
      > Number(latestReport?.epoch_seconds || 0)
  );
  const focus = active || (
    latestReport
      ? { plan_id: latestReport.plan_id, status: latestReport.status }
      : null
  );
  const attribution = focus ? timingAttribution(focus.plan_id) : null;
  const event = active ? attribution : latestReport;
  const isActive = Boolean(active);
  const isRetry = active?.status === "retry_wait";
  const leaseDeadline = Date.parse(active?.lease_expires_at || "");
  const leaseOverdue = (
    ["claimed", "running"].includes(active?.status)
    && Number.isFinite(leaseDeadline)
    && leaseDeadline < Date.now()
  );
  badge.textContent = isActive
    ? (leaseOverdue ? "Lease overdue" : (isRetry ? "Retry scheduled" : "Active"))
    : (pipelineFault ? "Pipeline fault" : (latestReport ? "Latest completed" : "Waiting"));
  badge.className = `pipeline-timing-status ${
    isActive && !isRetry && !leaseOverdue
      ? "is-active"
      : (isRetry || leaseOverdue || pipelineFault ? "is-warn" : "")
  }`;

  if (!focus) {
    grid.innerHTML = timingMetric(
      "Pipeline timing",
      "No events yet",
      "The rolling operational log is ready.",
      "quiet"
    );
    return;
  }

  const provider = event?.provider
    || (
      event?.role === "orchestrator"
        ? control.providers?.selected_provider
        : null
    );
  const model = event?.model
    || event?.requested_model
    || (event?.role === "trainer" ? "Ninereeds trainer" : "Not reported yet");
  const startedAt = active?.started_at || active?.created_at;
  const elapsedSeconds = startedAt
    ? Math.max(0, Date.now() / 1000 - Date.parse(startedAt) / 1000)
    : null;
  const duration = isActive
    ? fmtOperationalDuration(elapsedSeconds)
    : fmtOperationalDuration(
        Number(latestReport?.runtime_ms ?? latestReport?.model_attempt_ms) / 1000
      );
  const attempts = Number(
    isActive
      ? active?.attempt_count
      : (latestReport?.script_attempt_count ?? latestReport?.attempt_count)
  );
  const attemptMeta = isActive
    ? (
        active?.last_error
        || `${String(active.status || "unknown").replaceAll("_", " ")} · ${event?.workflow || event?.role || "control"}`
      )
    : [
        latestReport?.script_attempt_count ? "script generation" : "control execution",
        latestReport?.semantic_attempt_count
          ? `${latestReport.semantic_attempt_count} semantic`
          : null,
      ].filter(Boolean).join(" · ");
  const tokenMeta = latestReport?.total_tokens
    ? `${Number(latestReport.total_tokens).toLocaleString()} tokens`
    : "No token usage reported";
  const activity = pipelineActivity(focus.plan_id);
  const task = event?.task;
  const jobMeta = pipelineFault
    ? [
        latestSupervisor?.first_error_type || "Supervisor error",
        latestSupervisor?.first_error_plan,
      ].filter(Boolean).join(" · ")
    : (
        leaseOverdue
          ? `Worker lease expired ${fmtClockTime(leaseDeadline, { seconds: true })}`
          : `${event?.plan_kind || event?.role || "control"} · ${String(
              focus.status || "unknown"
            ).replaceAll("_", " ")}`
      );

  grid.innerHTML = [
    timingMetric(
      isActive ? "Active job" : "Last model job",
      activity.label,
      [task, jobMeta].filter(Boolean).join(" · "),
      isActive && !leaseOverdue
        ? "active"
        : (pipelineFault || leaseOverdue ? "warn" : receiptTone(focus.status))
    ),
    timingMetric(
      isActive ? "Model" : "Last model",
      model,
      provider ? `Provider: ${String(provider).toUpperCase()}` : "Provider not reported",
      provider || event?.model ? "active" : "quiet"
    ),
    timingMetric(
      isActive ? "Elapsed" : "Duration",
      duration,
      isActive && startedAt
        ? `Started ${fmtClockTime(startedAt, { seconds: true })}`
        : tokenMeta,
      isActive ? "active" : "quiet"
    ),
    timingMetric(
      "Attempts",
      Number.isFinite(attempts) && attempts > 0 ? String(attempts) : "—",
      attemptMeta || "No attempt metadata",
      attempts > 1 ? "warn" : "quiet"
    ),
  ].join("");
}

function timingMetric(label, value, meta, tone = "quiet") {
  return `
    <div class="pipeline-timing-metric tone-${escapeHtml(tone)}">
      <p class="card-label">${escapeHtml(label)}</p>
      <strong title="${escapeHtml(value)}">${escapeHtml(value)}</strong>
      <span title="${escapeHtml(meta)}">${escapeHtml(meta)}</span>
    </div>
  `;
}

function fmtOperationalDuration(seconds) {
  if (!Number.isFinite(Number(seconds))) return "Not reported";
  const total = Math.max(0, Math.round(Number(seconds)));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const remainder = total % 60;
  if (hours) return `${hours}h ${String(minutes).padStart(2, "0")}m`;
  if (minutes) return `${minutes}m ${String(remainder).padStart(2, "0")}s`;
  return `${remainder}s`;
}

function renderOrchestratorClock() {
  const clock = $("#orchestratorClock");
  if (!clock) return;
  const schedule = state.control?.schedule || {};
  const hasNextRun = schedule.next_run_at != null
    && Number.isFinite(Number(schedule.next_run_at));
  const nextRunAt = hasNextRun ? Number(schedule.next_run_at) : null;
  const timerActive = state.control?.services?.supervisor_timer === true;
  const statusLabels = {
    waiting_for_training_cooldown: "15-minute training cooldown",
    waiting_for_trainbox: "training box still running",
    retry_throttled: "recovery retry scheduled",
    supervisor_triggered: "orchestrator wake sent",
    strategic_plan_ready: "strategic work ready",
    idle: "no orchestration work due",
  };
  const statusLabel = statusLabels[schedule.status] || "waiting for due work";
  const displayStatus = schedule.stale ? `${statusLabel} · refreshing` : statusLabel;

  if (!schedule.available || !hasNextRun) {
    clock.dataset.state = timerActive ? "waiting" : "unavailable";
    $("#orchestratorNextRun").textContent = schedule.status === "waiting_for_trainbox"
      ? "After this job"
      : (schedule.status === "idle" ? "Not scheduled" : "Schedule unavailable");
    $("#orchestratorCountdown").textContent = schedule.status === "waiting_for_trainbox"
      ? "waiting"
      : "—";
    $("#orchestratorScheduleStatus").textContent = timerActive
      ? displayStatus
      : "due-work timer inactive";
    return;
  }

  const remainingSeconds = Math.max(0, Math.ceil(nextRunAt - Date.now() / 1000));
  const nextRun = new Date(nextRunAt * 1000);
  $("#orchestratorNextRun").textContent = fmtClockTime(nextRun);

  if (remainingSeconds === 0) {
    clock.dataset.state = "checking";
    $("#orchestratorCountdown").textContent = "now";
    $("#orchestratorScheduleStatus").textContent = displayStatus;
    return;
  }

  clock.dataset.state = "waiting";
  $("#orchestratorCountdown").textContent = fmtCountdown(remainingSeconds);
  $("#orchestratorScheduleStatus").textContent = displayStatus;
}

function fmtCountdown(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const remainder = total % 60;
  if (hours) return `${hours}h ${String(minutes).padStart(2, "0")}m ${String(remainder).padStart(2, "0")}s`;
  return `${minutes}m ${String(remainder).padStart(2, "0")}s`;
}

function telemetryCard(title, value, meta, tone = "quiet") {
  return `
    <article class="telemetry-card tone-${escapeHtml(tone)}">
      <div class="telemetry-title">
        <span class="telemetry-dot" aria-hidden="true"></span>
        <p class="card-label">${escapeHtml(title)}</p>
      </div>
      <h3>${escapeHtml(value || "Unknown")}</h3>
      <p>${escapeHtml(meta || "")}</p>
    </article>
  `;
}

function receiptTone(status) {
  if (["queued", "claimed", "running"].includes(status)) return "active";
  if (status === "retry_wait") return "warn";
  if (["blocked", "dead_letter"].includes(status)) return "bad";
  if (status === "completed") return "good";
  return "quiet";
}

function humanizePlan(planId) {
  const value = String(planId || "");
  if (!value) return "No current plan";
  if (value.includes("strategy") || value.includes("campaign-")) return "Orchestrating";
  if (value.includes("cortex")) return "Training Cortex";
  if (value.includes("eval")) return "Evaluating";
  if (value.includes("executor")) return "Preparing experiment";
  return value.replace(/^plan-/, "").replaceAll("-", " ");
}

function humanizeExecutor(executorId) {
  const value = String(executorId || "");
  const names = {
    "deepseek:deepseek-v4-flash": "DeepSeek V4 Flash",
    "openrouter:deepseek-v4-flash": "DeepSeek V4 Flash via OpenRouter",
    "deepseek:deepseek-v4-pro": "DeepSeek V4 Pro",
    "qwen3.6-35b-a3b-q4-k-m-turboquant": "Qwen 3.6 35B TurboQuant",
    "ternary-bonsai-27b": "Ternary Bonsai 27B",
    "gemma-4-26b-a4b": "Gemma 4 26B",
  };
  return names[value] || value;
}

function timingAttribution(planId) {
  const fields = [
    "model",
    "requested_model",
    "provider",
    "plan_kind",
    "role",
    "workflow",
    "task",
    "task_id",
  ];
  const result = {};
  for (const event of [...(state.timing || [])].reverse()) {
    if (event.plan_id !== planId) continue;
    for (const field of fields) {
      if (result[field] == null && event[field] != null) {
        result[field] = event[field];
      }
    }
  }
  return result;
}

function pipelineActivity(planId) {
  const receipts = [
    ...(state.control?.local?.latest_receipts || []),
    ...(state.control?.trainbox?.latest_receipts || []),
  ];
  const receipt = receipts
    .filter((value) => value.plan_id === planId)
    .sort((a, b) => String(b.updated_at || "").localeCompare(String(a.updated_at || "")))[0];
  const progress = receipt?.progress;
  const metadata = {
    ...timingAttribution(planId),
    progress,
    worker_updated_at: receipt?.updated_at || null,
  };
  if (
    progress?.kind === "cortex_curriculum"
    && (
      Number(progress.active_chunk) > 0
      || Number(progress.completed_chunks) > 0
    )
  ) {
    const activeChunk = Number(progress.active_chunk)
      || Number(progress.completed_chunks || 0) + 1;
    return {
      label: `Curriculum authoring · chunk ${activeChunk}`,
      phase: "prepare",
      metadata,
    };
  }
  if (metadata.workflow === "cortex_curriculum") {
    return { label: "Curriculum authoring", phase: "prepare", metadata };
  }
  if (metadata.role === "orchestrator" || metadata.plan_kind === "strategic_decision") {
    return { label: "Orchestrating", phase: "orchestrate", metadata };
  }
  if (metadata.role === "executor" || metadata.plan_kind === "executor_job") {
    return { label: "Scripting", phase: "prepare", metadata };
  }
  if (
    metadata.role === "trainer"
    || [
      "cortex_block",
      "phase_block",
      "trainer_session",
      "micro_update",
    ].includes(metadata.plan_kind)
  ) {
    return { label: "Training", phase: "train", metadata };
  }
  if (metadata.role === "evaluator" || metadata.plan_kind === "cortex_evaluation") {
    return { label: "Evaluating", phase: "evaluate", metadata };
  }
  const fallback = humanizePlan(planId);
  if (fallback === "Preparing experiment") {
    return { label: "Scripting", phase: "prepare", metadata };
  }
  if (fallback === "Training Cortex") {
    return { label: "Training", phase: "train", metadata };
  }
  if (fallback === "Evaluating") {
    return { label: "Evaluating", phase: "evaluate", metadata };
  }
  return { label: fallback, phase: "orchestrate", metadata };
}

function renderPipelineActivity() {
  const stage = $("#pipelineStage");
  if (!stage) return;

  const control = state.control || {};
  const campaign = control.campaign || {};
  const wave = campaign.wave || null;
  const receipts = [
    ...(control.local?.latest_receipts || []),
    ...(control.trainbox?.latest_receipts || []),
  ];
  const currentReceipts = receipts.filter(
    (receipt) => receipt.plan_id === campaign.current_plan_id
  );
  const priority = {
    running: 6,
    claimed: 5,
    queued: 4,
    retry_wait: 3,
    blocked: 2,
    dead_letter: 2,
    completed: 1,
  };
  const current = currentReceipts.sort(
    (a, b) => (priority[b.status] || 0) - (priority[a.status] || 0)
  )[0] || receipts[0];
  const receiptStatus = current?.status || null;
  const campaignStatus = campaign.status || "unknown";
  const active = ["queued", "claimed", "running"].includes(receiptStatus);
  const blocked = ["blocked", "dead_letter"].includes(receiptStatus)
    || ["blocked", "paused"].includes(campaignStatus);
  const retrying = receiptStatus === "retry_wait";
  const activity = pipelineActivity(current?.plan_id);
  const leaseDeadline = Date.parse(current?.lease_expires_at || "");
  const leaseOverdue = (
    ["claimed", "running"].includes(receiptStatus)
    && Number.isFinite(leaseDeadline)
    && leaseDeadline < Date.now()
  );
  const latestReport = [...(state.timing || [])].reverse().find(
    (event) => event.event === "plan.report"
  );
  const latestSupervisor = [...(state.timing || [])].reverse().find(
    (event) => event.event === "orchestrator.finished"
  );
  const pipelineFault = (
    latestSupervisor?.status === "failed"
    && Number(latestSupervisor.epoch_seconds || 0)
      > Number(latestReport?.epoch_seconds || 0)
  );

  let stateName = "idle";
  let motion = "paused";
  let label = "Pipeline at rest";
  let title = "Waiting for the next bounded action";
  let detail = campaign.stop_reason || "No active receipt is moving through the research loop.";

  if (!control.campaign) {
    stateName = "checking";
    label = "Reading the control ledger";
    title = "Pipeline state is loading";
    detail = "Connecting live telemetry to the durable orchestration ledger.";
  } else if (leaseOverdue) {
    stateName = "attention";
    label = "Pipeline appears stalled";
    title = "Worker lease is overdue";
    detail = `${activity.label} stopped renewing its lease at ${
      fmtClockTime(leaseDeadline, { seconds: true })
    }. Automatic reconciliation remains enabled.`;
  } else if (active) {
    stateName = "active";
    motion = "active";
    label = receiptStatus === "queued" ? "Work commissioned" : "Research loop active";
    title = activity.label;
    const progress = activity.metadata.progress;
    const observedExecutor = progress?.active_executor || activity.metadata.model;
    const actor = observedExecutor
      ? humanizeExecutor(observedExecutor)
      : (
          activity.metadata.workflow === "cortex_curriculum"
            ? "The executor ladder (DeepSeek V4 Flash primary)"
            : humanizeExecutor(
                activity.metadata.requested_model
                || activity.metadata.role
                || "The assigned worker"
              )
        );
    const progressDetail = progress?.kind === "cortex_curriculum"
      ? `${Number(progress.completed_examples || 0)}/${Number(progress.target_examples || 0)} examples accepted`
      : (
          activity.metadata.workflow === "cortex_curriculum"
          && activity.metadata.worker_updated_at
            ? `Chunk telemetry starts with the next worker job; latest heartbeat ${
                fmtClockTime(activity.metadata.worker_updated_at, { seconds: true })
              }.`
            : null
        );
    detail = receiptStatus === "queued"
      ? `${actor} is waiting to begin ${activity.metadata.task || "the bounded job"}.`
      : [
          `${actor} is working on ${activity.metadata.task || "the bounded job"}.`,
          wave
            ? `${Number(wave.concepts_admitted || 0)}/${Number(wave.concepts_total || 0)} concepts admitted across ${Number(wave.blocks_admitted || 0)}/${Number(wave.blocks_total || 0)} blocks.`
            : null,
          progressDetail,
        ].filter(Boolean).join(" ");
  } else if (retrying) {
    stateName = "waiting";
    label = "Automatic recovery";
    title = "Waiting before retry";
    detail = current?.last_error
      || "The current receipt is in deterministic retry backoff. No operator action is required.";
  } else if (blocked) {
    stateName = "attention";
    label = "Pipeline paused";
    title = campaign.stop_reason || "The current boundary needs attention";
    detail = "Motion is stopped until the blocker is resolved or the controller resumes.";
  } else if (pipelineFault) {
    stateName = "attention";
    label = "Automatic recovery";
    title = "The supervisor hit a pipeline fault";
    detail = [
      latestSupervisor?.first_error_type || "Supervisor error",
      latestSupervisor?.first_error_plan,
      "A deterministic retry is scheduled.",
    ].filter(Boolean).join(" · ");
  } else if (campaignStatus === "waiting") {
    stateName = "waiting";
    label = "Pipeline waiting";
    title = campaign.stop_reason || "Waiting for an external condition";
    detail = "The research loop is intentionally paused.";
  } else if (campaignStatus === "running") {
    stateName = "transition";
    label = "Between bounded steps";
    title = "Reconciling the latest result";
    detail = "The previous receipt is terminal; the supervisor is deciding or dispatching what follows.";
  } else if (campaignStatus === "completed") {
    stateName = "idle";
    label = "Campaign complete";
    title = "Research loop at rest";
    detail = campaign.stop_reason || "The objective gate was met.";
  }

  const provider = control.providers?.selected_provider;
  const gpus = state.trainbox?.status?.gpu?.gpus || [];
  const averageGpu = gpus.length
    ? Math.round(
        gpus.reduce(
          (sum, gpu) => sum + Number(gpu["utilization.gpu"] || 0),
          0
        ) / gpus.length
      )
    : null;
  const activePhase = activity.phase;
  const steps = [
    ["orchestrate", "Orchestrate"],
    ["prepare", "Prepare"],
    ["train", "Train"],
    ["evaluate", "Evaluate"],
  ];

  stage.dataset.state = stateName;
  stage.dataset.motion = motion;
  $("#pipelineStateLabel").textContent = label;
  $("#pipelineStateTitle").textContent = title;
  $("#pipelineStateDetail").textContent = detail;
  $("#pipelineFacts").innerHTML = [
    ["Campaign", campaign.display_name || campaign.campaign_id || "Not started"],
    [
      "Boundary",
      wave
        ? `${campaign.boundary_index ?? "—"}/${wave.blocks_total || "—"}`
        : (campaign.boundary_index ?? "—"),
    ],
    ["Provider", provider ? String(provider).toUpperCase() : "—"],
    ["GPU load", averageGpu === null ? "—" : `${averageGpu}% avg`],
  ].map(([fact, value]) => `
    <div><span>${escapeHtml(fact)}</span><strong>${escapeHtml(value)}</strong></div>
  `).join("");
  $("#pipelineSteps").innerHTML = steps.map(([key, value]) => `
    <div class="pipeline-step ${key === activePhase && active ? "is-active" : ""}">
      <span></span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `).join("");
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
      ${event.artifact_id ? eventArtifactAction(event.artifact_id, "Open artifact") : ""}
      <pre>${escapeHtml(JSON.stringify(event.details, null, 2))}</pre>
    </details>
  `).join("");
}

function eventArtifactAction(artifactId, label) {
  const artifact = state.artifacts.find((item) => item.id === artifactId);
  return artifact ? artifactAction(artifact, label) : `<button class="ghost" data-artifact="${artifactId}">${escapeHtml(label)}</button>`;
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
      ${artifactAction(artifact)}
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
  state.viewMode = "desktop";
  localStorage.setItem("lab:viewMode", state.viewMode);
  document.body.classList.remove("lab-view-phone");
  document.body.classList.add("lab-view-desktop");
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
  const url = artifactContentUrl(artifact);
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
      const action = result.kind === "artifact" ? artifactAction(item) : "";
      return `
        <article class="item">
          <div class="item-head">
            <div>
              <h3>${escapeHtml(item.title)}</h3>
              <p class="meta">${escapeHtml(result.kind)} · ${escapeHtml(item.path || item.id)}</p>
            </div>
            ${action}
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
  const refreshEvents = [
    "artifacts_indexed",
    "message_outbox",
    "git_pull",
    "build_published",
    "human_message",
    "recommendation_published",
  ];
  for (const name of refreshEvents) {
    events.addEventListener(name, async (event) => {
      const payload = JSON.parse(event.data);
      if (
        "Notification" in window
        && Notification.permission === "granted"
        && name === "human_message"
      ) {
        new Notification(payload.title || "Message from The Lab", {
          body: payload.body || "A new message is waiting.",
        });
      } else if (
        "Notification" in window
        && Notification.permission === "granted"
        && name === "recommendation_published"
      ) {
        new Notification(payload.title || "New research recommendation", {
          body: payload.body,
        });
      }
      await refreshAll();
      console.debug("Lab event", payload);
    });
  }
}

async function boot() {
  bindEvents();
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (sessionStorage.getItem("lab:workerReloaded") === "1") return;
      sessionStorage.setItem("lab:workerReloaded", "1");
      window.location.reload();
    });
    navigator.serviceWorker.register("/service-worker.js")
      .then((registration) => registration.update())
      .catch(() => {});
  }
  await refreshAll();
  connectEvents();
  window.setInterval(() => loadStatus().catch(() => {}), 15000);
  window.setInterval(() => loadTrainboxStatus(true).catch(() => {}), 15000);
  window.setInterval(() => loadControlStatus(true).catch(() => {}), 15000);
  window.setInterval(() => loadMessages().catch(() => {}), 10000);
  window.setInterval(() => {
    renderOrchestratorClock();
    renderPipelineTiming();
  }, 1000);
}

await boot().catch((error) => {
  document.body.insertAdjacentHTML("afterbegin", `<p class="panel">${escapeHtml(error.message)}</p>`);
});
