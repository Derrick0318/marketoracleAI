let previousRunId = null;

function adminIconRefresh() {
  if (window.lucide) window.lucide.createIcons();
}

async function adminFetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (response.status === 401) {
    window.location.href = `/admin/login?next=${encodeURIComponent(window.location.pathname)}`;
    throw new Error("Admin login required");
  }
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

function formatAdminPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
  return `${Number(value).toFixed(1)}%`;
}

function formatAdminPrice(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
  return Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 });
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
  const [status, alertsPayload, databaseStatus, predictionAudit] = await Promise.all([
    adminFetchJson("/api/admin/status"),
    adminFetchJson("/api/alerts?limit=80"),
    adminFetchJson("/api/admin/database-status"),
    adminFetchJson("/api/admin/prediction-accuracy?days=10"),
  ]);
  renderStatus(status);
  renderAlerts(alertsPayload.alerts || []);
  renderDatabaseStatus(databaseStatus);
  renderPredictionAudit(predictionAudit);
  adminIconRefresh();
}

function renderDatabaseStatus(status) {
  const title = document.querySelector("#databaseTitle");
  const copy = document.querySelector("#databaseCopy");
  const pills = document.querySelector("#databasePills");
  title.textContent = status.ok ? "Supabase connected" : status.storage_mode === "supabase" ? "Supabase needs attention" : "Local JSON fallback";
  copy.textContent = status.message;

  const tablePills = Object.entries(status.tables || {})
    .map(([name, result]) => `<span class="database-pill ${result.ok ? "ok" : "bad"}">${escapeAdmin(name)} ${result.ok ? "OK" : "ERROR"}</span>`)
    .join("");
  pills.innerHTML = `
    <span class="database-pill ${status.supabase_url_present ? "ok" : "bad"}">URL ${status.supabase_url_present ? "set" : "missing"}</span>
    <span class="database-pill ${status.supabase_key_present ? "ok" : "bad"}">Key ${status.supabase_key_present ? "set" : "missing"}</span>
    <span class="database-pill ${status.ok ? "ok" : "bad"}">${escapeAdmin(status.storage_mode)}</span>
    ${tablePills}
  `;
}

function renderPredictionAudit(report) {
  document.querySelector("#auditTitle").textContent =
    report.evaluated_count > 0 ? "Prediction accuracy is ready" : "Waiting for actual closes";
  document.querySelector("#auditCopy").textContent = report.error
    ? report.error
    : `Stored ${report.record_count || 0} predictions from the last ${report.days || 10} days.`;
  document.querySelector("#auditAccuracy").textContent = formatAdminPercent(report.accuracy_pct);
  document.querySelector("#auditCorrect").textContent = `${report.correct_count || 0}/${report.evaluated_count || 0}`;
  document.querySelector("#auditError").textContent = formatAdminPercent(report.avg_price_error_pct);
  document.querySelector("#auditPending").textContent = report.pending_count || 0;

  renderAuditDays(report.daily || []);
  renderAuditRecords(report.records || []);
}

function renderAuditDays(days) {
  document.querySelector("#auditDayCount").textContent = `${days.length} days`;
  document.querySelector("#auditDailyList").innerHTML =
    days.length === 0
      ? `<div class="admin-item"><p>No prediction history yet. Run the daily update once to start collecting records.</p></div>`
      : days
          .map(
            (day) => `
              <article class="admin-item">
                <div class="admin-item-head">
                  <h3>${escapeAdmin(day.date)}</h3>
                  <span>${formatAdminPercent(day.accuracy_pct)}</span>
                </div>
                <p>${day.correct_count || 0}/${day.evaluated_count || 0} correct, ${day.pending_count || 0} pending, ${day.record_count || 0} stored.</p>
              </article>
            `
          )
          .join("");
}

function renderAuditRecords(records) {
  document.querySelector("#auditRecordCount").textContent = `${records.length} records`;
  document.querySelector("#auditRecordsList").innerHTML =
    records.length === 0
      ? `<div class="admin-item"><p>No prediction comparison records yet.</p></div>`
      : records
          .map((record) => {
            const statusClass =
              record.evaluation_status === "correct" ? "success" : record.evaluation_status === "wrong" ? "danger" : "pending";
            const verdict =
              record.evaluation_status === "pending"
                ? "Pending actual close"
                : record.direction_correct
                  ? "Correct"
                  : "Wrong";
            return `
              <article class="admin-item ${statusClass}">
                <div class="admin-item-head">
                  <h3>${escapeAdmin(record.symbol)} ${escapeAdmin(verdict)}</h3>
                  <span>${escapeAdmin(record.prediction_date || "")}</span>
                </div>
                <p>
                  Predicted ${escapeAdmin(record.direction || "N/A")} to ${formatAdminPrice(record.predicted_close)}
                  ${record.actual_close ? `&bull; actual ${escapeAdmin(record.actual_direction || "")} to ${formatAdminPrice(record.actual_close)}` : ""}
                </p>
                <span>
                  ${escapeAdmin(record.name || record.market || "")}
                  ${record.confidence_pct ? `&bull; confidence ${formatAdminPercent(record.confidence_pct)}` : ""}
                  ${record.price_error_pct !== null && record.price_error_pct !== undefined ? `&bull; price error ${formatAdminPercent(record.price_error_pct)}` : ""}
                </span>
              </article>
            `;
          })
          .join("");
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

async function recheckPredictionAccuracy() {
  const button = document.querySelector("#recheckPredictionsButton");
  button.disabled = true;
  button.querySelector("span").textContent = "Checking";
  try {
    const report = await adminFetchJson("/api/admin/evaluate-predictions?days=10", { method: "POST" });
    renderPredictionAudit(report);
    showAdminToast(
      "Prediction audit updated",
      `${report.evaluation?.evaluated_count || 0} predictions checked, ${report.evaluation?.correct_count || 0} correct.`
    );
    adminIconRefresh();
  } catch (error) {
    showAdminToast("Prediction audit failed", error.message);
  } finally {
    button.querySelector("span").textContent = "Recheck Accuracy";
    button.disabled = false;
  }
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
  document.querySelector("#recheckPredictionsButton").addEventListener("click", recheckPredictionAccuracy);
  adminIconRefresh();
  loadAdmin();
  window.setInterval(loadAdmin, 15000);
});
