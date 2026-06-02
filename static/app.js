const state = {
  market: "all",
  limit: 6,
  selectedSymbol: null,
  chart: null,
  latestResults: [],
  scanCache: new Map(),
  scanRequestId: 0,
  activeScanController: null,
  scanBusy: false,
};

const $ = (selector) => document.querySelector(selector);

function iconRefresh() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function formatPrice(value, currency = "USD") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
  const minimumFractionDigits = Math.abs(value) < 10 ? 3 : 2;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits,
    maximumFractionDigits: minimumFractionDigits,
  }).format(Number(value));
}

function formatPercent(value, plus = false) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
  const sign = plus && Number(value) > 0 ? "+" : "";
  return `${sign}${Number(value).toFixed(2)}%`;
}

function actionClass(action) {
  if (action.includes("BUY")) return "buy";
  if (action.includes("SELL") || action.includes("REDUCE")) return "sell";
  return "watch";
}

function directionClass(direction) {
  return direction === "UP" ? "up" : "down";
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Request failed");
  }
  return payload;
}

function setLoading(label = "Training market models") {
  $("#cardList").innerHTML = Array.from({ length: 6 })
    .map(
      () => `
        <article class="stock-card skeleton">
          <div></div><div></div><div></div>
        </article>
      `
    )
    .join("");
  $("#detailPanel").innerHTML = `
    <div class="detail-empty">
      <i data-lucide="loader-circle"></i>
      <span>${label}</span>
    </div>
  `;
  iconRefresh();
}

function marketLabel(market) {
  const labels = {
    all: "All markets",
    us: "US stocks",
    malaysia: "Malaysia stocks",
    etf: "ETFs",
    crypto: "Bitcoin",
  };
  return labels[market] || market;
}

function scanCacheKey() {
  return `${state.market}:${state.limit}`;
}

function setScanBusy(isBusy, label = "") {
  state.scanBusy = isBusy;
  document.body.classList.toggle("scan-busy", isBusy);
  document.querySelectorAll(".segment, #scanLimit, #refreshButton").forEach((control) => {
    control.disabled = isBusy;
  });
  const count = $("#resultCount");
  if (count && isBusy) count.textContent = label || "Updating";
}

function renderScanPayload(payload) {
  state.latestResults = payload.results || [];
  state.selectedSymbol = state.latestResults[0]?.symbol || null;
  renderStats(payload);
  renderCards(state.latestResults);
  if (state.selectedSymbol) {
    renderQuickDetail(state.latestResults[0]);
  }
}

function renderStats(payload) {
  const results = payload.results || [];
  const best = results[0];
  const averageConfidence =
    results.length === 0
      ? 0
      : results.reduce((total, item) => total + Number(item.confidence_pct || 0), 0) / results.length;

  $("#topSignal").textContent = best ? `${best.symbol} ${best.action}` : "No signal";
  $("#bestForecast").textContent = best
    ? `${best.direction} ${formatPercent(best.predicted_change_from_current_pct, true)}`
    : "...";
  $("#avgConfidence").textContent = results.length ? `${averageConfidence.toFixed(1)}%` : "...";
  $("#generatedAt").textContent = payload.generated_at
    ? new Date(payload.generated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "...";
  $("#resultCount").textContent = `${results.length} assets`;
}

function renderCards(results) {
  $("#cardList").innerHTML = results
    .map(
      (item) => `
        <article class="stock-card ${state.selectedSymbol === item.symbol ? "selected" : ""}" data-symbol="${item.symbol}">
          <div class="card-head">
            <div>
              <h3>${item.symbol}</h3>
              <p>${item.name}</p>
            </div>
            <span class="market-tag">${item.market}</span>
          </div>
          <div class="price-row">
            <span>${formatPrice(item.current_price, item.currency)}</span>
            <b class="${directionClass(item.direction)}">${item.direction} ${formatPercent(item.predicted_change_from_current_pct, true)}</b>
          </div>
          <div class="signal-row">
            <span class="pill ${actionClass(item.action)}">${item.action}</span>
            <span>${Number(item.confidence_pct || 0).toFixed(1)}% confidence</span>
          </div>
          <div class="mini-grid">
            <span>Pred close <b>${formatPrice(item.predicted_close, item.currency)}</b></span>
            <span>Backtest <b>${Number(item.validation.direction_accuracy_pct || 0).toFixed(1)}%</b></span>
          </div>
        </article>
      `
    )
    .join("");

  document.querySelectorAll(".stock-card").forEach((card) => {
    card.addEventListener("click", () => {
      state.selectedSymbol = card.dataset.symbol;
      renderCards(state.latestResults);
      loadDetail(card.dataset.symbol);
    });
  });
}

function metric(label, value) {
  return `
    <div class="metric">
      <span>${label}</span>
      <b>${value}</b>
    </div>
  `;
}

function renderDetail(data) {
  const cls = actionClass(data.action);
  $("#detailPanel").innerHTML = `
    <div class="detail-head">
      <div>
        <span class="eyebrow">${data.market} &bull; ${data.target_horizon}</span>
        <h2>${data.name} <span>${data.symbol}</span></h2>
      </div>
      <span class="signal-badge ${cls}">${data.action}</span>
    </div>

    ${window.SignalAlerts ? window.SignalAlerts.renderBanner(data) : ""}
    ${window.MarketStatus ? window.MarketStatus.renderClock(data.market_status) : ""}
    ${window.MarketStatus ? window.MarketStatus.render(data.market_status) : ""}

    <div class="headline-metrics">
      ${metric("Current price", formatPrice(data.current_price, data.currency))}
      ${metric("Predicted close", formatPrice(data.predicted_close, data.currency))}
      ${metric("Forecast move", formatPercent(data.predicted_change_from_current_pct, true))}
      ${metric("Confidence", `${Number(data.confidence_pct || 0).toFixed(1)}%`)}
    </div>

    <div class="chart-wrap">
      <canvas id="priceChart" height="280"></canvas>
    </div>

    <div class="trade-plan">
      <div>
        <span><i data-lucide="shopping-bag"></i> When to buy</span>
        <p>${window.SignalAlerts ? window.SignalAlerts.highlightRiskText(data.trade_plan.buy_text) : data.trade_plan.buy_text}</p>
      </div>
      <div>
        <span><i data-lucide="target"></i> When to sell</span>
        <p>${window.SignalAlerts ? window.SignalAlerts.highlightRiskText(data.trade_plan.sell_text) : data.trade_plan.sell_text}</p>
      </div>
    </div>

    <div class="model-strip">
      ${metric("Model", data.model_name)}
      ${metric("Validation MAE", formatPercent(data.validation.mae_pct))}
      ${metric("Direction backtest", formatPercent(data.validation.direction_accuracy_pct))}
      ${metric("Risk/reward", data.risk_reward ? `${data.risk_reward}:1` : "N/A")}
      ${metric("RSI 14", Number(data.risk.rsi_14 || 0).toFixed(1))}
      ${metric("ATR", `${formatPrice(data.risk.atr, data.currency)} / ${formatPercent(data.risk.atr_pct)}`)}
    </div>

    <div class="signals">
      <h3>Signal Notes</h3>
      <ul>
        ${data.signals
          .map((signal) => `<li>${window.SignalAlerts ? window.SignalAlerts.highlightRiskText(signal) : signal}</li>`)
          .join("")}
      </ul>
    </div>

    ${window.MarketNews ? window.MarketNews.renderSymbolNews(data.news) : ""}
  `;
  iconRefresh();
  renderChart(data);
  if (window.LiveQuotes) {
    window.LiveQuotes.start(data.symbol);
  }
  if (window.MarketStatus) {
    window.MarketStatus.startClock(data.market_status);
  }
  if (window.SignalAlerts) {
    window.SignalAlerts.notify(data);
  }
}

function renderQuickDetail(data) {
  if (!data) return;
  if (state.chart) {
    state.chart.destroy();
    state.chart = null;
  }

  const cls = actionClass(data.action);
  $("#detailPanel").innerHTML = `
    <div class="detail-head">
      <div>
        <span class="eyebrow">${data.market} • ${data.target_horizon}</span>
        <h2>${data.name} <span>${data.symbol}</span></h2>
      </div>
      <span class="signal-badge ${cls}">${data.action}</span>
    </div>

    ${window.SignalAlerts ? window.SignalAlerts.renderBanner(data) : ""}
    ${window.MarketStatus ? window.MarketStatus.renderClock(data.market_status) : ""}
    ${window.MarketStatus ? window.MarketStatus.render(data.market_status) : ""}

    <div class="headline-metrics">
      ${metric("Current price", formatPrice(data.current_price, data.currency))}
      ${metric("Predicted close", formatPrice(data.predicted_close, data.currency))}
      ${metric("Forecast move", formatPercent(data.predicted_change_from_current_pct, true))}
      ${metric("Confidence", `${Number(data.confidence_pct || 0).toFixed(1)}%`)}
    </div>

    <div class="detail-action-row">
      <button class="refresh-button" id="loadFullDetailButton">
        <i data-lucide="line-chart"></i>
        <span>Full Analysis</span>
      </button>
    </div>

    <div class="trade-plan">
      <div>
        <span><i data-lucide="shopping-bag"></i> When to buy</span>
        <p>${window.SignalAlerts ? window.SignalAlerts.highlightRiskText(data.trade_plan.buy_text) : data.trade_plan.buy_text}</p>
      </div>
      <div>
        <span><i data-lucide="target"></i> When to sell</span>
        <p>${window.SignalAlerts ? window.SignalAlerts.highlightRiskText(data.trade_plan.sell_text) : data.trade_plan.sell_text}</p>
      </div>
    </div>

    <div class="model-strip compact-model-strip">
      ${metric("Model", data.model_name || "Fast scan model")}
      ${metric("Direction backtest", formatPercent(data.validation.direction_accuracy_pct))}
      ${metric("Risk/reward", data.risk_reward ? `${data.risk_reward}:1` : "N/A")}
      ${metric("RSI 14", Number(data.risk.rsi_14 || 0).toFixed(1))}
      ${metric("ATR", `${formatPrice(data.risk.atr, data.currency)} / ${formatPercent(data.risk.atr_pct)}`)}
      ${metric("News", `${data.news?.count || 0} linked`)}
    </div>
  `;
  iconRefresh();
  $("#loadFullDetailButton").addEventListener("click", () => loadDetail(data.symbol));
  if (window.LiveQuotes) {
    window.LiveQuotes.start(data.symbol);
  }
  if (window.MarketStatus) {
    window.MarketStatus.startClock(data.market_status);
  }
  if (window.SignalAlerts) {
    window.SignalAlerts.notify(data);
  }
}

function renderChart(data) {
  if (!window.Chart) return;
  const ctx = $("#priceChart");
  const labels = [...data.chart.dates, data.chart.prediction.label];
  const closeValues = [...data.chart.close, null];
  const predictionValues = [...Array(data.chart.close.length).fill(null), data.chart.prediction.price];

  if (state.chart) {
    state.chart.destroy();
  }

  state.chart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Close",
          data: closeValues,
          borderColor: "#4fd1a5",
          backgroundColor: "rgba(79, 209, 165, 0.12)",
          fill: true,
          tension: 0.28,
          pointRadius: 0,
          borderWidth: 2,
        },
        {
          label: "AI predicted close",
          data: predictionValues,
          borderColor: "#ffb84d",
          backgroundColor: "#ffb84d",
          pointRadius: 6,
          pointHoverRadius: 8,
          showLine: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: { color: "#e9ebdf", boxWidth: 10, usePointStyle: true },
        },
        tooltip: {
          mode: "index",
          intersect: false,
          backgroundColor: "#151713",
          titleColor: "#ffffff",
          bodyColor: "#d9ddcf",
          borderColor: "rgba(255, 255, 255, 0.16)",
          borderWidth: 1,
        },
      },
      scales: {
        x: { ticks: { color: "#8f9789", maxTicksLimit: 7 }, grid: { display: false } },
        y: { ticks: { color: "#8f9789" }, grid: { color: "rgba(255,255,255,0.08)" } },
      },
    },
  });
}

async function loadDetail(symbol, refresh = false) {
  $("#detailPanel").innerHTML = `
    <div class="detail-empty">
      <i data-lucide="loader-circle"></i>
      <span>Training ${symbol}</span>
    </div>
  `;
  iconRefresh();
  try {
    const data = await fetchJson(`/api/analyze/${encodeURIComponent(symbol)}${refresh ? "?refresh=1" : ""}`);
    renderDetail(data);
  } catch (error) {
    $("#detailPanel").innerHTML = `
      <div class="detail-empty error">
        <i data-lucide="circle-alert"></i>
        <span>${error.message}</span>
      </div>
    `;
    iconRefresh();
  }
}

async function loadScan(refresh = false) {
  const requestId = ++state.scanRequestId;
  const cacheKey = scanCacheKey();
  const cachedPayload = state.scanCache.get(cacheKey);

  if (!refresh && cachedPayload) {
    renderScanPayload(cachedPayload);
    return;
  }

  if (state.activeScanController) {
    state.activeScanController.abort();
  }
  state.activeScanController = new AbortController();

  if (state.latestResults.length) {
    setScanBusy(true, `Updating ${marketLabel(state.market)}`);
  } else {
    setLoading(`Loading ${marketLabel(state.market)}`);
    setScanBusy(true, `Loading ${marketLabel(state.market)}`);
  }

  if (window.MarketNews) {
    window.MarketNews.loadMarketNews(state.market);
  }
  const url = `/api/scan?market=${encodeURIComponent(state.market)}&limit=${state.limit}${refresh ? "&refresh=1" : ""}`;
  try {
    const payload = await fetchJson(url, { signal: state.activeScanController.signal });
    if (requestId !== state.scanRequestId) return;
    state.scanCache.set(cacheKey, payload);
    renderScanPayload(payload);
  } catch (error) {
    if (error.name === "AbortError") return;
    $("#cardList").innerHTML = `<div class="empty-error">${error.message}</div>`;
    $("#detailPanel").innerHTML = `
      <div class="detail-empty error">
        <i data-lucide="circle-alert"></i>
        <span>${error.message}</span>
      </div>
    `;
    iconRefresh();
  } finally {
    if (requestId === state.scanRequestId) {
      setScanBusy(false);
    }
  }
}

function bindEvents() {
  document.querySelectorAll(".segment").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".segment").forEach((segment) => segment.classList.remove("active"));
      button.classList.add("active");
      state.market = button.dataset.market;
      loadScan();
    });
  });

  $("#scanLimit").addEventListener("input", (event) => {
    state.limit = Number(event.target.value);
    $("#scanLimitText").textContent = state.limit;
  });

  $("#scanLimit").addEventListener("change", () => loadScan());
  $("#refreshButton").addEventListener("click", () => loadScan(true));

  $("#symbolForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const rawInput = $("#symbolInput").value.trim();
    const symbol = window.StockSearch ? await window.StockSearch.resolveSymbol(rawInput) : rawInput.toUpperCase();
    if (!symbol) return;
    $("#symbolInput").value = symbol;
    state.selectedSymbol = symbol;
    loadDetail(symbol, true);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  iconRefresh();
  loadScan();
});
