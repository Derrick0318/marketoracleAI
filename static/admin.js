let previousRunId = null;

function adminIconRefresh() {
  if (window.lucide) window.lucide.createIcons();
}

async function adminFetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Request failed");
  return payload;
}

function formatDateTime(value) {
  if (!value) return "Not yet";
  return new Date(value).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function escapeAdmin(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function renderStatus(status) {
  document.querySelector("#updateStatus").textContent = status.running ? "Running" : "Idle";
  document.querySelector("#nextRun").textContent = formatDateTime(status.next_run_at);
  document.querySelector("#latestRun").textContent = status.latest_run ? status.latest_run.status : "No runs";
  document.querySelector("#assetCount").textContent = status.universe_size;
  document.querySelector("#scheduleTitle").textContent = status.running ? "Updating market data now" : "Midnight collector ready";
  document.querySelector("#scheduleCopy").textContent = status.schedule;
  document.querySelector("#runUpdateButton").disabled = status.running;

  if (status.latest_run && previousRunId && previousRunId !== status.latest_run.id) {
    showAdminToast(`Update ${status.latest_run.status}`, `${status.latest_run.asset_count || 0} assets updated.`);
  }
  if (status.latest_run) previousRunId = status.latest_run.id;
  renderRuns(status.runs || []);
}

function renderRuns(runs) {
  document.querySelector("#runCount").textContent = `${runs.length} runs`;
  document.querySelector("#runsList").innerHTML =
    runs.length === 0
      ? `<div class="admin-item"><p>No update runs yet.</p></div>`
      : runs
          .map(
            (run) => `
              <article class="admin-item ${escapeAdmin(run.status)}">
                <div class="admin-item-head">
                  <h3>${escapeAdmin(run.status)} • ${escapeAdmin(run.reason)}</h3>
                  <span>${formatDateTime(run.finished_at || run.started_at)}</span>
                </div>
                <p>${run.asset_count || 0} assets updated, ${run.actionable_count || 0} actionable alerts, ${run.error_count || 0} errors.</p>
                ${run.snapshot_path ? `<span>Snapshot: ${escapeAdmin(run.snapshot_path)}</span>` : ""}
                ${run.error ? `<p><span class="risk-word">${escapeAdmin(run.error)}</span></p>` : ""}
              </article>
            `
          )
          .join("");
}

function renderAlerts(alerts) {
  document.querySelector("#alertCount").textContent = `${alerts.length} alerts`;
  document.querySelector("#alertsList").innerHTML =
    alerts.length === 0
      ? `<div class="admin-item"><p>No alerts yet.</p></div>`
      : alerts
          .map(
            (alert) => `
              <article class="admin-item ${escapeAdmin(alert.level)} ${alert.read ? "" : "unread"}">
                <div class="admin-item-head">
                  <h3>${escapeAdmin(alert.title)}</h3>
                  <span>${formatDateTime(alert.created_at)}</span>
                </div>
                <p>${escapeAdmin(alert.body)}</p>
                <span>${escapeAdmin(alert.source)}${alert.symbol ? ` • ${escapeAdmin(alert.symbol)}` : ""}</span>
                ${alert.read ? "" : `<button data-alert-id="${escapeAdmin(alert.id)}">Mark read</button>`}
              </article>
            `
          )
          .join("");

  document.querySelectorAll("[data-alert-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      await adminFetchJson(`/api/alerts/${button.dataset.alertId}/read`, { method: "POST" });
      await loadAdmin();
    });
  });
}

async function loadAdmin() {
  const [status, alertsPayload] = await Promise.all([
    adminFetchJson("/api/admin/status"),
    adminFetchJson("/api/alerts?limit=80"),
  ]);
  renderStatus(status);
  renderAlerts(alertsPayload.alerts || []);
  adminIconRefresh();
}

async function runUpdateNow() {
  const button = document.querySelector("#runUpdateButton");
  button.disabled = true;
  button.querySelector("span").textContent = "Starting";
  await adminFetchJson("/api/admin/run-update", { method: "POST" });
  showAdminToast("Update started", "The admin panel will notify you when it completes.");
  button.querySelector("span").textContent = "Run Update Now";
  await loadAdmin();
}

function showAdminToast(title, body) {
  let toast = document.querySelector("#adminToast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "adminToast";
    document.body.appendChild(toast);
  }
  toast.className = "admin-toast";
  toast.innerHTML = `<b>${escapeAdmin(title)}</b><p>${escapeAdmin(body)}</p>`;
  window.setTimeout(() => toast.classList.add("show"), 20);
  window.setTimeout(() => toast.classList.remove("show"), 6500);
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelector("#runUpdateButton").addEventListener("click", runUpdateNow);
  adminIconRefresh();
  loadAdmin();
  window.setInterval(loadAdmin, 15000);
});
