const state = {
  market: "all",
  limit: 6,
  selectedSymbol: null,
  chart: null,
  chartMode: "line",
  language: localStorage.getItem("marketOracleLanguage") || "en",
  universe: [],
  universeFilter: "",
  lastScanPayload: null,
  latestResults: [],
  scanCache: new Map(),
  scanRequestId: 0,
  activeScanController: null,
  scanBusy: false,
};

const $ = (selector) => document.querySelector(selector);

const i18n = {
  en: {
    brandTitle: "Market Oracle AI",
    brandCopy: "US stocks, Malaysia stocks, ETFs, and Bitcoin forecasts",
    searchPlaceholder: "Search Apple, Maybank, Press Metal...",
    analyzeSymbol: "Analyze symbol",
    marketAll: "All",
    marketUs: "US",
    marketMalaysia: "Malaysia",
    marketEtf: "ETF",
    marketBitcoin: "Bitcoin",
    scanLabel: "Scan",
    refresh: "Refresh",
    refreshTitle: "Refresh live data",
    alerts: "Alerts",
    alertsTitle: "Enable browser alerts",
    admin: "Admin",
    adminTitle: "Open admin panel",
    topSignal: "Top signal",
    bestForecast: "Best forecast",
    avgConfidence: "Avg confidence",
    generated: "Generated",
    dailyMarketNews: "Daily Market News",
    loadingHeadlines: "Loading latest headlines",
    aiRanking: "AI Ranking",
    universeTitle: "Market Universe",
    universeSearch: "Filter symbols or names",
    riskNote:
      "Educational research system only. It is not personalized financial advice. Always confirm liquidity, news, earnings, Bursa/SEC filings, fees, and your risk limit before trading.",
    loading: "Loading",
    trainingMarketModels: "Training market models",
    assets: "assets",
    cachedAssets: "cached assets",
    stocks: "stocks",
    noSignal: "No signal",
    currentPrice: "Current price",
    predictedClose: "Predicted close",
    forecastMove: "Forecast move",
    confidence: "Confidence",
    predCloseShort: "Pred close",
    backtest: "Backtest",
    whenToBuy: "When to buy",
    whenToSell: "When to sell",
    model: "Model",
    validationMae: "Validation MAE",
    directionBacktest: "Direction backtest",
    riskReward: "Risk/reward",
    rsi14: "RSI 14",
    atr: "ATR",
    news: "News",
    linked: "linked",
    fullAnalysis: "Full Analysis",
    signalNotes: "Signal Notes",
    line: "Line",
    candle: "Candle",
    askAiTitle: "Ask AI",
    askAiCopy: "Ask about buy timing, sell timing, or risk for the selected symbol.",
    assistantPlaceholder: "Example: Is it good to buy now? When should I buy?",
    askButton: "Ask AI",
    quickBuy: "Can buy now?",
    quickWhenBuy: "When to buy?",
    quickRisk: "What is the risk?",
    assistantSelect: "Select a stock first, then ask the AI.",
    assistantThinking: "Checking the model, trade plan, and latest data...",
    assistantError: "AI answer failed",
    filterEmpty: "No symbols match this filter.",
  },
  zh: {
    brandTitle: "Market Oracle AI",
    brandCopy: "美国股票、马来西亚股票、ETF 和比特币预测",
    searchPlaceholder: "搜索 Apple、Maybank、Press Metal...",
    analyzeSymbol: "分析股票",
    marketAll: "全部",
    marketUs: "美国",
    marketMalaysia: "马来西亚",
    marketEtf: "ETF",
    marketBitcoin: "比特币",
    scanLabel: "扫描",
    refresh: "刷新",
    refreshTitle: "刷新实时数据",
    alerts: "提醒",
    alertsTitle: "开启浏览器提醒",
    admin: "管理员",
    adminTitle: "打开管理员面板",
    topSignal: "最强信号",
    bestForecast: "最佳预测",
    avgConfidence: "平均信心",
    generated: "生成时间",
    dailyMarketNews: "每日市场新闻",
    loadingHeadlines: "正在加载最新新闻",
    aiRanking: "AI 排名",
    universeTitle: "股票清单",
    universeSearch: "筛选代码或名称",
    riskNote: "本系统只用于研究，不是个人投资建议。交易前请确认流动性、新闻、财报、Bursa/SEC 文件、费用和自己的风险限制。",
    loading: "正在加载",
    trainingMarketModels: "正在训练市场模型",
    assets: "资产",
    cachedAssets: "缓存资产",
    stocks: "股票",
    noSignal: "没有信号",
    currentPrice: "当前价格",
    predictedClose: "预测收盘价",
    forecastMove: "预测涨跌",
    confidence: "信心",
    predCloseShort: "预测收盘",
    backtest: "回测",
    whenToBuy: "何时买入",
    whenToSell: "何时卖出",
    model: "模型",
    validationMae: "验证 MAE",
    directionBacktest: "方向回测",
    riskReward: "风险回报",
    rsi14: "RSI 14",
    atr: "ATR",
    news: "新闻",
    linked: "条",
    fullAnalysis: "完整分析",
    signalNotes: "信号说明",
    line: "线图",
    candle: "K线",
    askAiTitle: "问 AI",
    askAiCopy: "询问所选股票的买入时机、卖出时机或风险。",
    assistantPlaceholder: "例如：现在可以买入吗？什么时候买？",
    askButton: "问 AI",
    quickBuy: "现在能买吗？",
    quickWhenBuy: "什么时候买？",
    quickRisk: "风险是什么？",
    assistantSelect: "请先选择一只股票，然后再问 AI。",
    assistantThinking: "正在检查模型、交易计划和最新数据...",
    assistantError: "AI 回答失败",
    filterEmpty: "没有符合筛选的股票。",
  },
};

function t(key) {
  return i18n[state.language]?.[key] || i18n.en[key] || key;
}

window.AppI18n = { t: (key) => t(key), language: () => state.language };

function iconRefresh() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function formatPrice(value, currency = "USD") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
  const minimumFractionDigits = Math.abs(value) < 10 ? 3 : 2;
  return new Intl.NumberFormat(state.language === "zh" ? "zh-CN" : "en-US", {
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

function setLoading(label = t("trainingMarketModels")) {
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
    all: state.language === "zh" ? "全部市场" : "All markets",
    us: state.language === "zh" ? "美国股票" : "US stocks",
    malaysia: state.language === "zh" ? "马来西亚股票" : "Malaysia stocks",
    etf: state.language === "zh" ? "ETF" : "ETFs",
    crypto: state.language === "zh" ? "比特币" : "Bitcoin",
  };
  return labels[market] || market;
}

function scanCacheKey() {
  return `${state.market}:${state.limit}`;
}

function setScanBusy(isBusy, label = "") {
  state.scanBusy = isBusy;
  document.body.classList.toggle("scan-busy", isBusy);
  document.querySelectorAll("#scanLimit, #refreshButton").forEach((control) => {
    control.disabled = isBusy;
  });
  const count = $("#resultCount");
  if (count && isBusy) count.textContent = label || "Updating";
}

function renderScanPayload(payload) {
  state.lastScanPayload = payload;
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

  $("#topSignal").textContent = best ? `${best.symbol} ${best.action}` : t("noSignal");
  $("#bestForecast").textContent = best
    ? `${best.direction} ${formatPercent(best.predicted_change_from_current_pct, true)}`
    : "...";
  $("#avgConfidence").textContent = results.length ? `${averageConfidence.toFixed(1)}%` : "...";
  $("#generatedAt").textContent = payload.generated_at
    ? new Date(payload.generated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "...";
  $("#resultCount").textContent = payload.snapshot ? `${results.length} ${t("cachedAssets")}` : `${results.length} ${t("assets")}`;
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
            <span>${Number(item.confidence_pct || 0).toFixed(1)}% ${t("confidence").toLowerCase()}</span>
          </div>
          <div class="mini-grid">
            <span>${t("predCloseShort")} <b>${formatPrice(item.predicted_close, item.currency)}</b></span>
            <span>${t("backtest")} <b>${Number(item.validation.direction_accuracy_pct || 0).toFixed(1)}%</b></span>
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

async function loadUniverse() {
  try {
    const payload = await fetchJson("/api/universe");
    state.universe = payload.symbols || [];
    renderUniverse();
  } catch {
    state.universe = [];
    renderUniverse();
  }
}

function renderUniverse() {
  const list = $("#universeList");
  const count = $("#universeCount");
  if (!list || !count) return;
  const items = filteredUniverse();
  count.textContent = `${items.length} ${t("stocks")}`;
  if (!items.length) {
    list.innerHTML = `<div class="empty-error">${t("filterEmpty")}</div>`;
    return;
  }

  list.innerHTML = items
    .map(
      (item) => `
        <button class="universe-item" type="button" data-universe-symbol="${item.symbol}">
          <span>
            <b>${item.symbol}</b>
            <small>${item.name}</small>
          </span>
          <em>${item.market}</em>
        </button>
      `
    )
    .join("");

  document.querySelectorAll("[data-universe-symbol]").forEach((button) => {
    button.addEventListener("click", () => {
      const symbol = button.dataset.universeSymbol;
      state.selectedSymbol = symbol;
      $("#symbolInput").value = symbol;
      loadDetail(symbol);
    });
  });
}

function filteredUniverse() {
  const query = state.universeFilter.trim().toLowerCase();
  return state.universe.filter((item) => {
    const market = String(item.market || "").toLowerCase();
    const symbol = String(item.symbol || "");
    const matchesMarket =
      state.market === "all" ||
      (state.market === "us" && market === "us") ||
      (state.market === "malaysia" && market === "malaysia") ||
      (state.market === "etf" && market.includes("etf")) ||
      (state.market === "crypto" && market === "crypto");
    if (!matchesMarket) return false;
    if (!query) return true;
    return symbol.toLowerCase().includes(query) || String(item.name || "").toLowerCase().includes(query);
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

function applyLanguage() {
  document.documentElement.lang = state.language === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    node.placeholder = t(node.dataset.i18nPlaceholder);
  });
  document.querySelectorAll("[data-i18n-title]").forEach((node) => {
    node.title = t(node.dataset.i18nTitle);
  });
  document.querySelectorAll("[data-language]").forEach((button) => {
    button.classList.toggle("active", button.dataset.language === state.language);
  });
  localStorage.setItem("marketOracleLanguage", state.language);
  window.AppI18n = { t: (key) => t(key), language: () => state.language };
  renderUniverse();
  if (state.latestResults.length) {
    renderStats(state.lastScanPayload || { results: state.latestResults });
    renderCards(state.latestResults);
    const selected = state.latestResults.find((item) => item.symbol === state.selectedSymbol) || state.latestResults[0];
    if (selected) renderQuickDetail(selected);
  }
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
      ${metric(t("currentPrice"), formatPrice(data.current_price, data.currency))}
      ${metric(t("predictedClose"), formatPrice(data.predicted_close, data.currency))}
      ${metric(t("forecastMove"), formatPercent(data.predicted_change_from_current_pct, true))}
      ${metric(t("confidence"), `${Number(data.confidence_pct || 0).toFixed(1)}%`)}
    </div>

    ${renderChartControls()}
    <div class="chart-wrap">
      <canvas id="priceChart" height="280"></canvas>
    </div>

    <div class="trade-plan">
      <div>
        <span><i data-lucide="shopping-bag"></i> ${t("whenToBuy")}</span>
        <p>${window.SignalAlerts ? window.SignalAlerts.highlightRiskText(data.trade_plan.buy_text) : data.trade_plan.buy_text}</p>
      </div>
      <div>
        <span><i data-lucide="target"></i> ${t("whenToSell")}</span>
        <p>${window.SignalAlerts ? window.SignalAlerts.highlightRiskText(data.trade_plan.sell_text) : data.trade_plan.sell_text}</p>
      </div>
    </div>

    <div class="model-strip">
      ${metric(t("model"), data.model_name)}
      ${metric(t("validationMae"), formatPercent(data.validation.mae_pct))}
      ${metric(t("directionBacktest"), formatPercent(data.validation.direction_accuracy_pct))}
      ${metric(t("riskReward"), data.risk_reward ? `${data.risk_reward}:1` : "N/A")}
      ${metric(t("rsi14"), Number(data.risk.rsi_14 || 0).toFixed(1))}
      ${metric(t("atr"), `${formatPrice(data.risk.atr, data.currency)} / ${formatPercent(data.risk.atr_pct)}`)}
    </div>

    <div class="signals">
      <h3>${t("signalNotes")}</h3>
      <ul>
        ${data.signals
          .map((signal) => `<li>${window.SignalAlerts ? window.SignalAlerts.highlightRiskText(signal) : signal}</li>`)
          .join("")}
      </ul>
    </div>

    ${window.MarketNews ? window.MarketNews.renderSymbolNews(data.news) : ""}
    ${renderAssistantPanel(data.symbol)}
  `;
  iconRefresh();
  bindChartModeControls(data);
  bindAssistantPanel();
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
        <span class="eyebrow">${data.market} &bull; ${data.target_horizon}</span>
        <h2>${data.name} <span>${data.symbol}</span></h2>
      </div>
      <span class="signal-badge ${cls}">${data.action}</span>
    </div>

    ${window.SignalAlerts ? window.SignalAlerts.renderBanner(data) : ""}
    ${window.MarketStatus ? window.MarketStatus.renderClock(data.market_status) : ""}
    ${window.MarketStatus ? window.MarketStatus.render(data.market_status) : ""}

    <div class="headline-metrics">
      ${metric(t("currentPrice"), formatPrice(data.current_price, data.currency))}
      ${metric(t("predictedClose"), formatPrice(data.predicted_close, data.currency))}
      ${metric(t("forecastMove"), formatPercent(data.predicted_change_from_current_pct, true))}
      ${metric(t("confidence"), `${Number(data.confidence_pct || 0).toFixed(1)}%`)}
    </div>

    <div class="detail-action-row">
      <button class="refresh-button" id="loadFullDetailButton">
        <i data-lucide="line-chart"></i>
        <span>${t("fullAnalysis")}</span>
      </button>
    </div>

    <div class="trade-plan">
      <div>
        <span><i data-lucide="shopping-bag"></i> ${t("whenToBuy")}</span>
        <p>${window.SignalAlerts ? window.SignalAlerts.highlightRiskText(data.trade_plan.buy_text) : data.trade_plan.buy_text}</p>
      </div>
      <div>
        <span><i data-lucide="target"></i> ${t("whenToSell")}</span>
        <p>${window.SignalAlerts ? window.SignalAlerts.highlightRiskText(data.trade_plan.sell_text) : data.trade_plan.sell_text}</p>
      </div>
    </div>

    <div class="model-strip compact-model-strip">
      ${metric(t("model"), data.model_name || "Fast scan model")}
      ${metric(t("directionBacktest"), formatPercent(data.validation.direction_accuracy_pct))}
      ${metric(t("riskReward"), data.risk_reward ? `${data.risk_reward}:1` : "N/A")}
      ${metric(t("rsi14"), Number(data.risk.rsi_14 || 0).toFixed(1))}
      ${metric(t("atr"), `${formatPrice(data.risk.atr, data.currency)} / ${formatPercent(data.risk.atr_pct)}`)}
      ${metric(t("news"), `${data.news?.count || 0} ${t("linked")}`)}
    </div>
    ${renderAssistantPanel(data.symbol)}
  `;
  iconRefresh();
  $("#loadFullDetailButton").addEventListener("click", () => loadDetail(data.symbol));
  bindAssistantPanel();
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

function renderChartControls() {
  return `
    <div class="chart-toolbar">
      <button class="chart-mode ${state.chartMode === "line" ? "active" : ""}" data-chart-mode="line">
        <i data-lucide="line-chart"></i>
        <span>${t("line")}</span>
      </button>
      <button class="chart-mode ${state.chartMode === "candle" ? "active" : ""}" data-chart-mode="candle">
        <i data-lucide="chart-candlestick"></i>
        <span>${t("candle")}</span>
      </button>
    </div>
  `;
}

function bindChartModeControls(data) {
  document.querySelectorAll("[data-chart-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      state.chartMode = button.dataset.chartMode;
      document.querySelectorAll("[data-chart-mode]").forEach((item) => item.classList.toggle("active", item === button));
      renderChart(data);
    });
  });
}

function renderAssistantPanel(symbol) {
  return `
    <section class="assistant-panel" id="assistantPanel" data-assistant-symbol="${symbol || ""}">
      <div class="section-title">
        <div>
          <h3>${t("askAiTitle")}</h3>
          <span>${t("askAiCopy")}</span>
        </div>
      </div>
      <form class="assistant-form" id="assistantForm">
        <textarea id="assistantQuestion" rows="3" placeholder="${t("assistantPlaceholder")}"></textarea>
        <div class="assistant-actions">
          <button type="button" class="assistant-chip" data-question="${t("quickBuy")}">${t("quickBuy")}</button>
          <button type="button" class="assistant-chip" data-question="${t("quickWhenBuy")}">${t("quickWhenBuy")}</button>
          <button type="button" class="assistant-chip" data-question="${t("quickRisk")}">${t("quickRisk")}</button>
          <button class="refresh-button assistant-submit" type="submit">
            <i data-lucide="sparkles"></i>
            <span>${t("askButton")}</span>
          </button>
        </div>
      </form>
      <div class="assistant-answer" id="assistantAnswer">${t("assistantSelect")}</div>
    </section>
  `;
}

function bindAssistantPanel() {
  const form = $("#assistantForm");
  if (!form) return;
  const questionInput = $("#assistantQuestion");
  document.querySelectorAll("[data-question]").forEach((button) => {
    button.addEventListener("click", () => {
      questionInput.value = button.dataset.question;
      form.requestSubmit();
    });
  });
  form.addEventListener("submit", askAssistant);
}

async function askAssistant(event) {
  event.preventDefault();
  const symbol = state.selectedSymbol || $("#assistantPanel")?.dataset.assistantSymbol;
  const question = $("#assistantQuestion")?.value.trim() || t("quickBuy");
  const answerBox = $("#assistantAnswer");
  if (!symbol) {
    answerBox.textContent = t("assistantSelect");
    return;
  }
  answerBox.textContent = t("assistantThinking");
  try {
    const payload = await fetchJson("/api/assistant", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, question, language: state.language }),
    });
    answerBox.textContent = payload.answer;
  } catch (error) {
    answerBox.textContent = `${t("assistantError")}: ${error.message}`;
  }
}

function renderChart(data) {
  if (!window.Chart) return;
  const ctx = $("#priceChart");
  if (state.chartMode === "candle" && data.chart?.open?.length) {
    renderCandleChart(ctx, data);
    return;
  }
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

function renderCandleChart(canvas, data) {
  if (state.chart) {
    state.chart.destroy();
    state.chart = null;
  }
  const context = canvas.getContext("2d");
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(320, rect.width) * dpr;
  canvas.height = Math.max(260, rect.height || 330) * dpr;
  context.setTransform(dpr, 0, 0, dpr, 0, 0);

  const width = canvas.width / dpr;
  const height = canvas.height / dpr;
  const padding = { top: 22, right: 54, bottom: 34, left: 14 };
  const open = data.chart.open || [];
  const high = data.chart.high || [];
  const low = data.chart.low || [];
  const close = data.chart.close || [];
  const dates = data.chart.dates || [];
  const values = [...high, ...low, data.chart.prediction?.price].filter((value) => Number.isFinite(Number(value)));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const step = plotWidth / Math.max(1, close.length);
  const candleWidth = Math.max(3, Math.min(12, step * 0.58));
  const y = (value) => padding.top + ((max - value) / range) * plotHeight;

  context.clearRect(0, 0, width, height);
  context.fillStyle = "rgba(8, 9, 7, 0.28)";
  context.fillRect(0, 0, width, height);
  context.strokeStyle = "rgba(255,255,255,0.08)";
  context.lineWidth = 1;
  context.font = "12px Inter, sans-serif";
  context.fillStyle = "#8f9789";

  for (let grid = 0; grid <= 4; grid += 1) {
    const gy = padding.top + (plotHeight / 4) * grid;
    context.beginPath();
    context.moveTo(padding.left, gy);
    context.lineTo(width - padding.right, gy);
    context.stroke();
    const label = max - (range / 4) * grid;
    context.fillText(label.toFixed(label < 10 ? 3 : 2), width - padding.right + 8, gy + 4);
  }

  close.forEach((closeValue, index) => {
    const o = Number(open[index]);
    const h = Number(high[index]);
    const l = Number(low[index]);
    const c = Number(closeValue);
    if (![o, h, l, c].every(Number.isFinite)) return;

    const x = padding.left + step * index + step / 2;
    const up = c >= o;
    const color = up ? "#4fd1a5" : "#ff5c7a";
    context.strokeStyle = color;
    context.fillStyle = color;
    context.beginPath();
    context.moveTo(x, y(h));
    context.lineTo(x, y(l));
    context.stroke();

    const bodyTop = Math.min(y(o), y(c));
    const bodyHeight = Math.max(2, Math.abs(y(o) - y(c)));
    context.globalAlpha = up ? 0.78 : 0.86;
    context.fillRect(x - candleWidth / 2, bodyTop, candleWidth, bodyHeight);
    context.globalAlpha = 1;
  });

  const prediction = Number(data.chart.prediction?.price);
  if (Number.isFinite(prediction)) {
    const py = y(prediction);
    context.setLineDash([5, 5]);
    context.strokeStyle = "#ffb84d";
    context.beginPath();
    context.moveTo(padding.left, py);
    context.lineTo(width - padding.right, py);
    context.stroke();
    context.setLineDash([]);
    context.fillStyle = "#ffb84d";
    context.fillText(`${t("predictedClose")} ${formatPrice(prediction, data.currency)}`, padding.left + 8, py - 8);
  }

  context.fillStyle = "#8f9789";
  context.fillText(dates[0] || "", padding.left, height - 12);
  context.fillText(dates[dates.length - 1] || "", Math.max(padding.left, width - padding.right - 98), height - 12);
}

async function loadDetail(symbol, refresh = false) {
  $("#detailPanel").innerHTML = `
    <div class="detail-empty">
      <i data-lucide="loader-circle"></i>
      <span>${t("loading")} ${symbol}</span>
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
    setScanBusy(true, `${t("loading")} ${marketLabel(state.market)}`);
  } else {
    setLoading(`${t("loading")} ${marketLabel(state.market)}`);
    setScanBusy(true, `${t("loading")} ${marketLabel(state.market)}`);
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
      renderUniverse();
      loadScan();
    });
  });

  $("#scanLimit").addEventListener("input", (event) => {
    state.limit = Number(event.target.value);
    $("#scanLimitText").textContent = state.limit;
  });

  $("#scanLimit").addEventListener("change", () => loadScan());
  $("#refreshButton").addEventListener("click", () => loadScan(true));
  $("#universeSearch").addEventListener("input", (event) => {
    state.universeFilter = event.target.value;
    renderUniverse();
  });
  document.querySelectorAll("[data-language]").forEach((button) => {
    button.addEventListener("click", () => {
      state.language = button.dataset.language;
      applyLanguage();
    });
  });

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
  applyLanguage();
  bindEvents();
  iconRefresh();
  loadUniverse();
  loadScan();
});
