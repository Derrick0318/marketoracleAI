function renderMarketStatus(status) {
  if (!status) return "";
  const cls = status.is_open ? "open" : "closed";
  const eventText =
    status.next_event_my_time && status.next_event_exchange_time
      ? `${status.next_event_label}: ${status.next_event_my_time} / ${status.next_event_exchange_time}`
      : status.next_event_label;

  return `
    <div class="market-status-note ${cls}">
      <div class="market-status-head">
        <b><span class="market-status-dot"></span>${status.exchange} is ${status.status_label}</b>
        <span>${status.session}</span>
      </div>
      <div class="market-status-grid">
        <span>Malaysia time <b>${status.my_time}</b></span>
        <span>Exchange time <b>${status.exchange_time}</b></span>
        <span>Next event <b>${eventText}</b></span>
      </div>
      <p>Regular hours: ${status.regular_hours}. ${status.note}</p>
    </div>
  `;
}

function renderSessionClock(status) {
  if (!status) return "";
  return `
    <div class="session-clock" data-session-clock>
      <div class="session-clock-head">
        <b>Live market clock</b>
        <span>${status.exchange}</span>
      </div>
      <div class="session-clock-time">
        <div>
          <span>Malaysia time</span>
          <b data-clock-my>--:--:--</b>
        </div>
        <div>
          <span>Exchange time</span>
          <b data-clock-exchange>--:--:--</b>
        </div>
      </div>
      <div class="session-countdown">
        <span class="session-countdown-label" data-countdown-label>${status.next_event_label}</span>
        <strong data-countdown-value>--</strong>
      </div>
    </div>
  `;
}

function startSessionClock(status) {
  if (window.sessionClockTimer) window.clearInterval(window.sessionClockTimer);
  const mount = document.querySelector("[data-session-clock]");
  if (!mount || !status) return;

  const myClock = mount.querySelector("[data-clock-my]");
  const exchangeClock = mount.querySelector("[data-clock-exchange]");
  const countdownLabel = mount.querySelector("[data-countdown-label]");
  const countdownValue = mount.querySelector("[data-countdown-value]");
  const eventTime = status.next_event_my_iso ? new Date(status.next_event_my_iso) : null;
  const exchangeTimeZone = status.exchange_timezone || "Asia/Kuala_Lumpur";

  function tick() {
    const now = new Date();
    myClock.textContent = formatClock(now, "Asia/Kuala_Lumpur");
    exchangeClock.textContent = formatClock(now, exchangeTimeZone);

    if (!eventTime) {
      countdownLabel.textContent = status.next_event_label || "Session";
      countdownValue.textContent = status.market === "Crypto" ? "24/7 open" : "--";
      return;
    }

    const diffMs = eventTime.getTime() - now.getTime();
    if (diffMs <= 0) {
      countdownLabel.textContent = "Refresh status";
      countdownValue.textContent = "Now";
      return;
    }
    countdownLabel.textContent = status.next_event_label;
    countdownValue.textContent = formatCountdown(diffMs);
  }

  tick();
  window.sessionClockTimer = window.setInterval(tick, 1000);
}

function formatClock(date, timeZone) {
  return new Intl.DateTimeFormat("en-MY", {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  }).format(date);
}

function formatCountdown(ms) {
  const totalSeconds = Math.floor(ms / 1000);
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (days > 0) return `${days}d ${hours}h ${minutes}m ${seconds}s`;
  return `${hours}h ${minutes}m ${seconds}s`;
}

window.MarketStatus = {
  render: renderMarketStatus,
  renderClock: renderSessionClock,
  startClock: startSessionClock,
};
