const LIVE_QUOTE_INTERVAL_MS = 30000;
let liveQuoteTimer = null;
let activeLiveSymbol = null;

function liveFormatPrice(value, currency = "USD") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
  const digits = Math.abs(Number(value)) < 10 ? 3 : 2;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(Number(value));
}

function liveFormatMove(value, percent) {
  if (value === null || value === undefined || percent === null || percent === undefined) return "N/A";
  const sign = Number(value) >= 0 ? "+" : "";
  return `${sign}${Number(value).toFixed(2)} / ${sign}${Number(percent).toFixed(2)}%`;
}

function ensureLiveQuoteMount() {
  const detail = document.querySelector("#detailPanel");
  if (!detail) return null;

  let mount = detail.querySelector("#liveQuotePanel");
  if (!mount) {
    mount = document.createElement("div");
    mount.id = "liveQuotePanel";
    detail.insertBefore(mount, detail.querySelector(".headline-metrics"));
  }
  return mount;
}

function renderLiveQuoteLoading(symbol) {
  const mount = ensureLiveQuoteMount();
  if (!mount) return;
  mount.innerHTML = `
    <div class="live-quote">
      <div class="live-quote-head">
        <b><span class="live-dot"></span> Live quote</b>
        <span>${symbol} • polling every 30 seconds</span>
      </div>
      <div class="live-quote-price">
        <strong>Loading</strong>
        <span class="live-move up">...</span>
      </div>
    </div>
  `;
}

function renderLiveQuote(quote) {
  const mount = ensureLiveQuoteMount();
  if (!mount) return;

  const moveClass = Number(quote.change || 0) >= 0 ? "up" : "down";
  mount.innerHTML = `
    <div class="live-quote">
      <div class="live-quote-head">
        <b><span class="live-dot"></span> Live quote</b>
        <span>${quote.symbol} • updated ${new Date(quote.generated_at).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        })}</span>
      </div>
      <div class="live-quote-price">
        <strong>${liveFormatPrice(quote.price, quote.currency)}</strong>
        <span class="live-move ${moveClass}">${liveFormatMove(quote.change, quote.change_pct)}</span>
      </div>
      <div class="live-quote-meta">
        <span>Open <b>${liveFormatPrice(quote.open, quote.currency)}</b></span>
        <span>Day high <b>${liveFormatPrice(quote.day_high, quote.currency)}</b></span>
        <span>Day low <b>${liveFormatPrice(quote.day_low, quote.currency)}</b></span>
      </div>
      ${window.MarketStatus ? window.MarketStatus.render(quote.market_status) : ""}
      <p class="live-quote-note">Live quote polls every 30 seconds. AI forecast retrains every 10 minutes, or immediately when you press Refresh.</p>
      <p class="live-quote-note">${quote.freshness_note}</p>
    </div>
  `;
}

async function updateLiveQuote(symbol) {
  try {
    const response = await fetch(`/api/quote/${encodeURIComponent(symbol)}`);
    const quote = await response.json();
    if (!response.ok) throw new Error(quote.error || "Live quote failed");
    if (activeLiveSymbol === symbol) renderLiveQuote(quote);
  } catch (error) {
    const mount = ensureLiveQuoteMount();
    if (mount) {
      mount.innerHTML = `<div class="live-quote"><p class="live-quote-note">${error.message}</p></div>`;
    }
  }
}

function startLiveQuote(symbol) {
  activeLiveSymbol = symbol;
  if (liveQuoteTimer) window.clearInterval(liveQuoteTimer);
  renderLiveQuoteLoading(symbol);
  updateLiveQuote(symbol);
  liveQuoteTimer = window.setInterval(() => updateLiveQuote(symbol), LIVE_QUOTE_INTERVAL_MS);
}

window.LiveQuotes = {
  start: startLiveQuote,
  intervalMs: LIVE_QUOTE_INTERVAL_MS,
};
