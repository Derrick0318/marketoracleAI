let previousRunId = null;
let resetInProgress = false;
let catchUpInProgress = false;

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
  document.querySelector("#nextRun").textContent = status.next_run_label
    ? `${status.next_run_label}: ${formatDateTime(status.next_run_at)}`
    : formatDateTime(status.next_run_at);
  document.querySelector("#latestRun").textContent = status.latest_run ? status.latest_run.status : "No runs";
  document.querySelector("#assetCount").textContent = status.universe_size;
  document.querySelector("#scheduleTitle").textContent = status.running ? "Updating market data now" : "Market-session collector ready";
  document.querySelector("#scheduleCopy").textContent = status.schedule;
  document.querySelector("#runUpdateButton").disabled = status.running;
  document.querySelector("#resetCollectionButton").disabled = status.running || resetInProgress;
  document.querySelector("#catchUpPricesButton").disabled = catchUpInProgress;

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
                  <h3>${escapeAdmin(run.status)} &bull; ${escapeAdmin(run.reason)}</h3>
                  <span>${formatDateTime(run.finished_at || run.started_at)}</span>
                </div>
                <p>${run.asset_count || 0} assets updated, ${run.actionable_count || 0} actionable alerts, ${run.error_count || 0} errors.</p>
                ${renderRunSuggestionSummary(run.metadata)}
                ${run.snapshot_path ? `<span>Snapshot: ${escapeAdmin(run.snapshot_path)}</span>` : ""}
                ${run.error ? `<p><span class="risk-word">${escapeAdmin(run.error)}</span></p>` : ""}
              </article>
            `
          )
          .join("");
}

function renderRunSuggestionSummary(metadata = {}) {
  if (
    !metadata ||
    (metadata.buy_count === undefined && metadata.watch_count === undefined && metadata.not_buy_count === undefined)
  ) {
    return "";
  }
  const markets = Array.isArray(metadata.markets) ? metadata.markets.join(", ") : "";
  return `
    <span>
      ${markets ? `${escapeAdmin(markets)} &bull; ` : ""}
      Buy ${Number(metadata.buy_count || 0)},
      wait ${Number(metadata.watch_count || 0)},
      do not buy ${Number(metadata.not_buy_count || 0)}
      ${metadata.price_events_stored !== undefined ? `, price events ${Number(metadata.price_events_stored || 0)}` : ""}
    </span>
  `;
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
                <span>${escapeAdmin(alert.source)}${alert.symbol ? ` &bull; ${escapeAdmin(alert.symbol)}` : ""}</span>
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
  const [status, alertsPayload, databaseStatus, priceEvents, predictionAudit, modelHealth] = await Promise.all([
    adminFetchJson("/api/admin/status"),
    adminFetchJson("/api/alerts?limit=80"),
    adminFetchJson("/api/admin/database-status"),
    adminFetchJson("/api/admin/price-events?days=2"),
    adminFetchJson("/api/admin/prediction-accuracy?days=10"),
    adminFetchJson("/api/admin/model-health"),
  ]);
  renderStatus(status);
  renderAlerts(alertsPayload.alerts || []);
  renderDatabaseStatus(databaseStatus);
  renderPriceEvents(priceEvents);
  renderPredictionAudit(predictionAudit);
  renderModelHealth(modelHealth);
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

function renderPriceEvents(report) {
  const title = document.querySelector("#priceEventsTitle");
  const copy = document.querySelector("#priceEventsCopy");
  const pills = document.querySelector("#priceEventPills");
  const latest = report.latest_event;
  const latestText = latest
    ? `${escapeAdmin(latest.symbol)} ${escapeAdmin(latest.event_type)} ${formatAdminPrice(latest.price)} on ${escapeAdmin(latest.trading_date)}`
    : "No price event rows yet.";

  title.textContent = report.error
    ? "Price event table needs attention"
    : report.event_count > 0
      ? "Open/close price storage working"
      : "Waiting for first price event";
  copy.textContent = report.error || latestText;
  pills.innerHTML = `
    <span class="database-pill ${report.today_count ? "ok" : "warn"}">Today ${report.today_count || 0}</span>
    <span class="database-pill ${report.open_count ? "ok" : "warn"}">Open ${report.open_count || 0}</span>
    <span class="database-pill ${report.close_count ? "ok" : "warn"}">Close ${report.close_count || 0}</span>
    <span class="database-pill ${report.crypto_count ? "ok" : "warn"}">Bitcoin ${report.crypto_count || 0}</span>
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

function renderModelHealth(health) {
  const status = health.status || {};
  const retrain = health.retrain || {};
  const level = status.level || "warn";
  document.querySelector("#modelHealth").className = `admin-actions model-health ${level}`;
  document.querySelector("#modelHealthTitle").textContent = status.title || "Model status unavailable";
  document.querySelector("#modelHealthCopy").textContent = status.copy || health.error || "No model status returned.";
  document.querySelector("#retrainStatusCard").className = `stat retrain-status-card ${retrain.level || "warn"}`;
  document.querySelector("#retrainStatus").textContent = retrain.title || "Unknown";
  document.querySelector("#retrainStatusCopy").textContent = retrain.copy || "No retrain recommendation returned.";
  document.querySelector("#modelHealthFreshness").textContent =
    health.latest_prediction_age_hours === null || health.latest_prediction_age_hours === undefined
      ? "No data"
      : `${Number(health.latest_prediction_age_hours).toFixed(1)}h old`;
  document.querySelector("#modelHealth10Day").textContent = `${health.evaluated_count_10d || 0}/${health.record_count_10d || 0}`;
  document.querySelector("#modelHealth30Day").textContent = `${health.evaluated_count_30d || 0}/${health.record_count_30d || 0}`;
  document.querySelector("#modelHealthLatestCheck").textContent = formatDateTime(health.latest_evaluated_at);

  document.querySelector("#modelHealthPills").innerHTML = `
    <span class="database-pill ${level === "ok" ? "ok" : level === "bad" ? "bad" : "warn"}">${escapeAdmin(status.title || "Unknown")}</span>
    <span class="database-pill ${retrain.level === "ok" ? "ok" : retrain.level === "bad" ? "bad" : "warn"}">${escapeAdmin(retrain.title || "Retrain unknown")}</span>
    <span class="database-pill ${health.record_count_10d ? "ok" : "bad"}">10D stored ${health.record_count_10d || 0}</span>
    <span class="database-pill ${health.evaluated_count_10d >= 10 ? "ok" : "warn"}">10D accuracy ${formatAdminPercent(health.accuracy_10d_pct)}</span>
    <span class="database-pill ${health.evaluated_count_30d >= 10 ? "ok" : "warn"}">30D accuracy ${formatAdminPercent(health.accuracy_30d_pct)}</span>
    <span class="database-pill ${health.pending_count_10d ? "warn" : "ok"}">Pending ${health.pending_count_10d || 0}</span>
  `;
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
            const metadata = parseRecordMetadata(record.metadata);
            const forecast = metadata.forecast_window || {};
            const probabilityUp = metadata.direction_probability_up_pct;
            const probabilityDown = metadata.direction_probability_down_pct;
            const statusClass =
              record.evaluation_status === "correct" ? "success" : record.evaluation_status === "wrong" ? "danger" : "pending";
            const verdict =
              record.evaluation_status === "pending"
                ? "Pending actual close"
                : record.direction_correct
                  ? "Correct"
                  : "Wrong";
            const actualReady = record.actual_close !== null && record.actual_close !== undefined;
            return `
              <article class="comparison-row ${statusClass}">
                <div class="comparison-asset">
                  <b>${escapeAdmin(record.symbol)}</b>
                  <span>${escapeAdmin(record.name || record.market || "")}</span>
                  <small>${escapeAdmin(record.prediction_date || "")}</small>
                </div>
                <div class="comparison-cell predicted">
                  <span class="comparison-label">Predicted</span>
                  <b class="${record.direction === "UP" ? "comparison-up" : "comparison-down"}">${escapeAdmin(record.direction || "N/A")} to ${formatAdminPrice(record.predicted_close)}</b>
                  <small>Move ${formatAdminPercent(record.predicted_change_pct)} &bull; confidence ${formatAdminPercent(record.confidence_pct)}</small>
                  <small>${record.action ? escapeAdmin(suggestionText(record.action)) : "No action"}${probabilityUp !== undefined ? ` &bull; UP ${formatAdminPercent(probabilityUp)} / DOWN ${formatAdminPercent(probabilityDown)}` : ""}</small>
                  ${forecast.horizon_text ? `<em>${escapeAdmin(forecast.horizon_text)}</em>` : ""}
                </div>
                <div class="comparison-cell actual">
                  <span class="comparison-label">Actual</span>
                  ${
                    actualReady
                      ? `
                        <b class="${record.actual_direction === "UP" ? "comparison-up" : "comparison-down"}">${escapeAdmin(record.actual_direction || "N/A")} to ${formatAdminPrice(record.actual_close)}</b>
                        <small>Move ${formatAdminPercent(record.actual_change_pct)} &bull; next close ${escapeAdmin(record.target_date || "N/A")}</small>
                        <small>Price error ${formatAdminPercent(record.price_error_pct)}</small>
                      `
                      : `
                        <b>Waiting for close</b>
                        <small>Target after ${escapeAdmin(record.target_after_date || "N/A")}</small>
                        <small>Actual result will appear after market data updates.</small>
                      `
                  }
                </div>
                <div class="comparison-result">
                  <span class="${statusClass}">${escapeAdmin(verdict)}</span>
                  <small>${escapeAdmin(record.model_profile || "model")} &bull; ${escapeAdmin(record.market || "")}</small>
                </div>
              </article>
            `;
          })
          .join("");
}

function parseRecordMetadata(metadata) {
  if (!metadata) return {};
  if (typeof metadata === "object") return metadata;
  try {
    return JSON.parse(metadata);
  } catch {
    return {};
  }
}

function suggestionText(action) {
  const upper = String(action || "").toUpperCase();
  if (upper.includes("BUY")) return "Can buy";
  if (upper.includes("SELL") || upper.includes("REDUCE") || upper.includes("AVOID")) return "Do not buy";
  return "Wait / watch";
}

async function runUpdateNow() {
  const button = document.querySelector("#runUpdateButton");
  button.disabled = true;
  button.querySelector("span").textContent = "Running... (up to 60s)";
  showAdminToast("Update started", "Running full market scan. This may take up to 60 seconds on Vercel.");
  try {
    const payload = await adminFetchJson("/api/admin/run-update", { method: "POST" });
    if (payload.completed) {
      const result = payload.result || {};
      showAdminToast(
        `Update ${result.status || "complete"}`,
        `${result.asset_count || 0} assets updated, ${result.actionable_count || 0} actionable, ${result.error_count || 0} errors.`
      );
    } else {
      showAdminToast("Update started", "The admin panel will notify you when it completes.");
    }
  } catch (error) {
    showAdminToast("Update failed", error.message);
  } finally {
    button.querySelector("span").textContent = "Run Update Now";
    button.disabled = false;
    await loadAdmin();
  }
}

async function resetCollectionNow() {
  const confirmation = window.prompt(
    "This clears stored predictions, snapshots, update history, and alerts. Type RESET to clear data and start a fresh all-market collection from today."
  );
  if (confirmation !== "RESET") {
    showAdminToast("Reset cancelled", "No market data was changed.");
    return;
  }

  const button = document.querySelector("#resetCollectionButton");
  resetInProgress = true;
  button.disabled = true;
  button.querySelector("span").textContent = "Clearing";
  try {
    const payload = await adminFetchJson("/api/admin/reset-collection", { method: "POST" });
    const tables = Object.entries(payload.clear?.cleared || {})
      .map(([name, count]) => `${name} ${count}`)
      .join(", ");
    showAdminToast(
      payload.started ? "Fresh collection started" : "Data cleared",
      `${tables || "Collection data cleared"}. The new run will collect all configured assets from today's market data.`
    );
  } catch (error) {
    showAdminToast("Reset failed", error.message);
  } finally {
    resetInProgress = false;
    button.querySelector("span").textContent = "Clear Data + Start Today";
    await loadAdmin();
  }
}

async function catchUpTodayPrices() {
  const button = document.querySelector("#catchUpPricesButton");
  catchUpInProgress = true;
  button.disabled = true;
  button.querySelector("span").textContent = "Collecting";
  try {
    const payload = await adminFetchJson("/api/admin/catch-up-price-events", { method: "POST" });
    renderPriceEvents(payload.report);
    const stored = payload.result?.stored_count || 0;
    const errors = payload.result?.errors?.length || 0;
    showAdminToast(
      "Today prices checked",
      `${stored} open/close price rows stored or refreshed. ${errors} quote errors. Learning data updates from Run Update Now or the scheduled collector.`
    );
    adminIconRefresh();
  } catch (error) {
    showAdminToast("Price catch-up failed", error.message);
  } finally {
    catchUpInProgress = false;
    button.querySelector("span").textContent = "Catch Up Today Prices";
    await loadAdmin();
  }
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
  document.querySelector("#resetCollectionButton").addEventListener("click", resetCollectionNow);
  document.querySelector("#catchUpPricesButton").addEventListener("click", catchUpTodayPrices);
  document.querySelector("#recheckPredictionsButton").addEventListener("click", recheckPredictionAccuracy);
  adminIconRefresh();
  loadAdmin();
  window.setInterval(loadAdmin, 15000);
});
