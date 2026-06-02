const ACTION_ALERTS = new Set(["STRONG BUY", "BUY", "SELL / AVOID", "REDUCE"]);
const DANGER_WORDS = [
  "sell",
  "avoid",
  "reduce",
  "risk",
  "risks",
  "cut",
  "stop",
  "loss",
  "weak",
  "negative",
  "down",
  "failed",
  "error",
  "errors",
  "bearish",
  "hot",
];
const seenSignalAlerts = new Set();

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function highlightRiskText(value) {
  const escaped = escapeHtml(value);
  const pattern = new RegExp(`\\b(${DANGER_WORDS.join("|")})\\b`, "gi");
  return escaped.replace(pattern, '<span class="risk-word">$1</span>');
}

function signalType(action) {
  return action && action.includes("BUY") ? "buy" : "sell";
}

function renderSignalBanner(data) {
  if (!ACTION_ALERTS.has(data.action)) return "";
  const cls = signalType(data.action);
  return `
    <div class="signal-alert ${cls}">
      <b>${escapeHtml(data.symbol)} ${escapeHtml(data.action)} alert</b>
      <p>${highlightRiskText(data.alert?.body || `${data.name} triggered ${data.action}.`)}</p>
    </div>
  `;
}

function showSignalToast(data) {
  if (!ACTION_ALERTS.has(data.action)) return;
  const key = `${data.symbol}:${data.action}:${data.predicted_close}:${data.confidence_pct}`;
  if (seenSignalAlerts.has(key)) return;
  seenSignalAlerts.add(key);

  const cls = signalType(data.action);
  let toast = document.querySelector("#signalToast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "signalToast";
    document.body.appendChild(toast);
  }

  toast.className = `signal-toast ${cls}`;
  toast.innerHTML = `
    <b>${escapeHtml(data.symbol)} ${escapeHtml(data.action)}</b>
    <span>${escapeHtml(data.name)} • confidence ${Number(data.confidence_pct || 0).toFixed(1)}%</span>
    <p>${highlightRiskText(data.trade_plan?.sell_text || data.alert?.body || "")}</p>
  `;
  window.setTimeout(() => toast.classList.add("show"), 20);
  window.setTimeout(() => toast.classList.remove("show"), 8500);

  if ("Notification" in window && Notification.permission === "granted") {
    new Notification(`${data.symbol} ${data.action}`, {
      body: data.alert?.body || `${data.name} triggered ${data.action}`,
    });
  }
}

function bindAlertPermissionButton() {
  const button = document.querySelector("#enableAlertsButton");
  if (!button) return;
  button.addEventListener("click", async () => {
    if (!("Notification" in window)) {
      showPermissionToast("Browser notifications are not available here.");
      return;
    }
    const permission = await Notification.requestPermission();
    showPermissionToast(permission === "granted" ? "Browser alerts enabled." : "Browser alerts not enabled.");
  });
}

function showPermissionToast(message) {
  let toast = document.querySelector("#signalToast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "signalToast";
    document.body.appendChild(toast);
  }
  toast.className = "signal-toast buy";
  toast.innerHTML = `<b>${escapeHtml(message)}</b><span>In-app alerts still show automatically.</span>`;
  window.setTimeout(() => toast.classList.add("show"), 20);
  window.setTimeout(() => toast.classList.remove("show"), 4200);
}

document.addEventListener("DOMContentLoaded", bindAlertPermissionButton);

window.SignalAlerts = {
  renderBanner: renderSignalBanner,
  notify: showSignalToast,
  highlightRiskText,
  escapeHtml,
};
